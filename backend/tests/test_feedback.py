"""Fase 6 — Retroalimentación del usuario mejora el scoring."""
from app.services.demo import seed_demo_if_empty

PERFIL = {
    "nombre_comercial": "TechSoft", "sector": "Tecnologías de la información",
    "actividades": "Desarrollo de software",
    "keywords": ["desarrollo de software", "sistemas de información", "interoperabilidad"],
    "unspsc_codes": ["81101500"], "departamentos": ["Bogotá D.C.", "Valle del Cauca"],
    "presupuesto_min": 100000000, "presupuesto_max": 50000000000,
    "modalidades": ["Licitación Pública", "Contratación Directa"],
}


def test_feedback_ajusta_pesos(client, db, auth_headers):
    seed_demo_if_empty(db)
    r = client.put("/api/profile", json=PERFIL, headers=auth_headers)
    assert r.status_code == 200
    r = client.post("/api/rescore", headers=auth_headers)
    assert r.status_code == 200 and r.json()["puntuadas"] >= 4

    items = client.get("/api/opportunities?limit=5", headers=auth_headers).json()["items"]
    con_score = [o for o in items if o["score"] is not None]
    assert con_score
    oid = con_score[0]["id"]

    r = client.post(f"/api/opportunities/{oid}/feedback", json={"util": True, "nota": "relevante"}, headers=auth_headers)
    assert r.status_code == 200 and r.json()["feedback"] is True
    assert r.json()["learning_weights"]  # pesos ajustados por la retroalimentación
    pesos_utiles = r.json()["learning_weights"]

    r = client.post(f"/api/opportunities/{oid}/feedback", json={"util": False}, headers=auth_headers)
    assert r.status_code == 200

    # re-scoring aplica los pesos (endpoint responde sin error)
    r = client.post("/api/rescore", headers=auth_headers)
    assert r.status_code == 200

    # feedback sobre oportunidad sin score
    r = client.post("/api/opportunities/999999/feedback", json={"util": True}, headers=auth_headers)
    assert r.status_code == 404
    assert pesos_utiles
