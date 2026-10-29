"""Perfil empresarial: todos los campos del Agente 1 (sección 6 del enunciado)."""

PROFILE = {
    "nombre_comercial": "TechSoft Andina",
    "razon_social": "TechSoft Andina S.A.S.",
    "nit": "901.234.567-8",
    "sector": "Tecnologías de la información",
    "actividades": "Desarrollo de software y soporte de aplicaciones",
    "productos_servicios": "Sistemas de información, interoperabilidad, transformación digital",
    "keywords": ["desarrollo de software", "interoperabilidad"],
    "unspsc_codes": ["81101500"],
    "departamentos": ["Bogotá D.C.", "Cundinamarca"],
    "municipios": ["Bogotá D.C."],
    "presupuesto_min": 100000000,
    "presupuesto_max": 5000000000,
    "modalidades": ["Licitación Pública", "Contratación Directa"],
    "experiencia": "10 años en modernización tecnológica",
    "capacidades": "30 ingenieros",
    "certificaciones": ["ISO 9001"],
    "acepta_consorcios": True,
}


def test_crear_y_leer_perfil(client, auth_headers):
    r = client.put("/api/profile", json=PROFILE, headers=auth_headers)
    assert r.status_code == 200
    data = r.json()
    assert data["nit"] == "901.234.567-8"
    assert data["unspsc_codes"] == ["81101500"]
    assert data["acepta_consorcios"] is True

    g = client.get("/api/profile", headers=auth_headers)
    assert g.status_code == 200
    assert g.json()["nombre_comercial"] == "TechSoft Andina"


def test_actualizar_perfil(client, auth_headers):
    client.put("/api/profile", json=PROFILE, headers=auth_headers)
    r = client.put("/api/profile", json={**PROFILE, "presupuesto_max": 8000000000}, headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["presupuesto_max"] == 8000000000
