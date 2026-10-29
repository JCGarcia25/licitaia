"""Flujo integral: registro → perfil → Agente 1 → NLQ → triage → Agente 2 → 3 → 4 → export → alertas → métricas."""
import io


def _docx_en_memoria(parrafos: list[str]) -> bytes:
    import docx

    doc = docx.Document()
    for p in parrafos:
        doc.add_paragraph(p)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def test_flujo_integral(client, db):
    # --- Datos de ejemplo (el seed automático se desactiva en testing) ---
    from app.services.demo import seed_demo_if_empty

    seed_demo_if_empty(db)

    # --- Registro y perfil ---
    r = client.post("/api/auth/register", json={
        "email": "flow@licitaia.co", "password": "ClaveSegura123", "full_name": "Equipo Flow",
    })
    assert r.status_code == 201, r.text
    headers = {"Authorization": f"Bearer {r.json()['access_token']}"}

    r = client.put("/api/profile", json={
        "nombre_comercial": "TechSoft Andina", "razon_social": "TechSoft Andina S.A.S.",
        "nit": "901.234.567-8", "sector": "Tecnologías de la información",
        "actividades": "Desarrollo de software y soporte de aplicaciones",
        "productos_servicios": "Sistemas de información, interoperabilidad, transformación digital",
        "keywords": ["desarrollo de software", "sistemas de información", "interoperabilidad", "modernización tecnológica"],
        "unspsc_codes": ["81101500"], "departamentos": ["Bogotá D.C.", "Cundinamarca", "Valle del Cauca"],
        "municipios": ["Bogotá D.C."], "presupuesto_min": 100000000, "presupuesto_max": 5000000000,
        "modalidades": ["Licitación Pública", "Contratación Directa", "Selección Abreviada"],
        "experiencia": "10 años en modernización tecnológica",
        "capacidades": "30 ingenieros, capacidad financiera",
        "certificaciones": ["ISO 9001"], "acepta_consorcios": True,
    }, headers=headers)
    assert r.status_code == 200, r.text

    # --- AGENTE 1: rescore con razones verificables ---
    r = client.post("/api/rescore", headers=headers)
    assert r.status_code == 200, r.text
    assert r.json()["puntuadas"] >= 4

    r = client.get("/api/opportunities?limit=20", headers=headers)
    assert r.status_code == 200
    items = r.json()["items"]
    assert len(items) >= 4
    tech = next(o for o in items if "software" in (o["objeto"] or "").lower())
    assert tech["score"] is not None and tech["score"] >= 50
    assert tech["reasons"]
    cancelada = None
    r = client.get("/api/opportunities?limit=20&include_cancelled=true", headers=headers)
    for o in r.json()["items"]:
        if o["estado"] == "Cancelado":
            cancelada = o
            break
    assert cancelada is not None and cancelada["score"] < 30

    # --- Búsqueda en lenguaje natural (ejemplo de la sección 10) ---
    r = client.post("/api/search", json={
        "q": "Busca procesos abiertos de desarrollo de software en Bogotá superiores a 200 millones de pesos que cierren dentro de los próximos 20 días.",
    }, headers=headers)
    assert r.status_code == 200, r.text
    assert r.json()["filtros_interpretados"]["departamento"] == "Bogotá D.C."
    assert r.json()["filtros_interpretados"]["valor_min"] == 200000000
    assert r.json()["total"] >= 1

    # --- Triage ---
    r = client.post(f"/api/opportunities/{tech['id']}/triaje", json={"triage": "guardada"}, headers=headers)
    assert r.status_code == 200 and r.json()["triage"] == "guardada"

    # --- AGENTE 2: carga de documento y análisis con citas ---
    pliego = _docx_en_memoria([
        "PLEGOS DE CONDICIONES",
        "Objeto del proceso: Adquisición e implementación de una plataforma de desarrollo de software para la entidad.",
        "Presupuesto oficial: $ 1.500.000.000",
        "Fecha de cierre: 15/12/2026 17:00",
        "Entidad contratante: Unidad Administrativa Especial de Servicios Públicos",
        "Modalidad de selección: Licitación Pública",
        "El proponente deberá acreditar experiencia en contratos similares de desarrollo de software.",
        "Se exige póliza de cumplimiento del 10% del valor de la propuesta, requisito habilitante.",
        "Capacidad financiera acreditada mediante estados financieros certificados.",
    ])
    r = client.post("/api/documents", files={
        "file": ("pliegos.docx", pliego, "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
    }, data={"opportunity_id": str(tech["id"])}, headers=headers)
    assert r.status_code == 200, r.text
    doc_id = r.json()["id"]

    r = client.get("/api/documents", headers=headers)
    assert any(d["id"] == doc_id for d in r.json())

    r = client.post(f"/api/opportunities/{tech['id']}/analyze", headers=headers)
    assert r.status_code == 200, r.text
    assert r.json()["total_requisitos"] >= 2
    analisis = r.json()
    assert "validación humana" in analisis["resumen"]["descargo"]
    r = client.get(f"/api/opportunities/{tech['id']}", headers=headers)
    detalle = r.json()
    assert detalle["analysis"] is not None
    req0 = detalle["analysis"]["requisitos"][0]
    assert req0["evidencia"] and req0["referencia"].startswith("sección ")
    assert req0["estado"] in ("Cumple", "No cumple", "Por verificar", "Información insuficiente")

    # --- AGENTE 3: viabilidad con pesos configurables ---
    r = client.post(f"/api/opportunities/{tech['id']}/viability", json={
        "pesos": {"compatibilidad_tecnica": 40, "experiencia_acreditable": 25,
                  "capacidad_financiera": 15, "viabilidad_operativa": 12, "riesgos": 8},
    }, headers=headers)
    assert r.status_code == 200, r.text
    viab = r.json()
    assert 0 <= viab["global_score"] <= 100
    assert viab["recommendation"] in ("participar", "revisar", "descartar")
    assert "adjudicación" in viab["disclaimer"].lower()

    # --- AGENTE 4: proyecto de oferta ---
    r = client.post("/api/offer-projects", json={"opportunity_id": tech["id"]}, headers=headers)
    assert r.status_code == 201, r.text
    pid = r.json()["id"]
    assert len(r.json()["checklist"]) >= 7

    r = client.get("/api/offer-projects", headers=headers)
    assert any(p["id"] == pid for p in r.json())

    r = client.get(f"/api/offer-projects/{pid}", headers=headers)
    assert r.status_code == 200
    assert r.json()["opportunity"]["id"] == tech["id"]

    # borradores: carta generada, respuestas técnicas NO inventadas
    r = client.post(f"/api/offer-projects/{pid}/borradores", json={"tipo": "carta_presentacion"}, headers=headers)
    assert r.status_code == 200 and len(r.json()["borradores"]) == 1
    r = client.post(f"/api/offer-projects/{pid}/borradores", json={"tipo": "respuestas_tecnicas"}, headers=headers)
    assert r.status_code == 400  # exige contenido del cliente

    r = client.patch(f"/api/offer-projects/{pid}/checklist", json={"index": 0, "estado": "listo"}, headers=headers)
    assert r.json()["checklist"][0]["estado"] == "listo"

    r = client.post(f"/api/offer-projects/{pid}/comentarios", json={"texto": "Revisar pólizas"}, headers=headers)
    assert r.status_code == 200

    r = client.post(f"/api/offer-projects/{pid}/status", json={"status": "aprobado", "approved_by": "Gerente Comercial"}, headers=headers)
    assert r.json()["status"] == "aprobado" and r.json()["approved_by"] == "Gerente Comercial"

    # exportación DOCX / XLSX / PDF
    for formato in ("docx", "xlsx", "pdf"):
        r = client.get(f"/api/offer-projects/{pid}/export?formato={formato}", headers=headers)
        assert r.status_code == 200, f"{formato}: {r.text}"
        assert len(r.content) > 500

    # --- Alertas ---
    r = client.post("/api/alerts/digest", headers=headers)
    assert r.status_code == 200, r.text
    r = client.put("/api/alerts/prefs", json={
        "email_enabled": False, "high_score_threshold": 60, "close_days": [5, 1], "digest_hour": 7,
    }, headers=headers)
    assert r.json()["high_score_threshold"] == 60
    r = client.get("/api/alerts", headers=headers)
    assert r.status_code == 200
    r = client.post("/api/alerts/read-all", headers=headers)
    assert r.json()["ok"] is True

    # guarda otra oportunidad (distinta de la convertida en proyecto)
    otro = next(o for o in items if "software" not in (o["objeto"] or "").lower() and o["estado"] == "En proceso")
    r = client.post(f"/api/opportunities/{otro['id']}/triaje", json={"triage": "guardada"}, headers=headers)
    assert r.status_code == 200

    # --- Métricas del dashboard ---
    r = client.get("/api/dashboard/metrics", headers=headers)
    assert r.status_code == 200, r.text
    m = r.json()
    assert m["oportunidades_detectadas"] >= 4
    assert m["guardadas"] >= 1
    assert m["proyectos_propuesta"] >= 1
    assert m["valor_agregado_cop"] > 0
    assert len(m["tendencia_mensual"]) == 6

    # --- Auditoría de sincronización ---
    r = client.get("/api/sync/runs", headers=headers)
    assert r.status_code == 200
