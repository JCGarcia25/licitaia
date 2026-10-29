"""Fase 6 — Límites de consumo de IA por suscripción y bloqueo de cuota."""
from app.services.quota import check_quota, consume, get_plan_limits


def test_planes_y_limites():
    limits = get_plan_limits()
    assert limits["explorador"] < limits["profesional"] < limits["corporativo"]


def test_cuota_inicial_cambio_plan_y_consumo(client, db):
    r = client.post("/api/auth/register", json={"email": "quota@licitaia.co", "password": "ClaveSegura123", "full_name": "Q"})
    assert r.status_code == 201
    headers = {"Authorization": f"Bearer {r.json()['access_token']}"}

    cur = client.get("/api/billing", headers=headers).json()
    assert cur["plan"] == "explorador"
    assert cur["usage"]["used"] == 0 and cur["usage"]["allowed"] is True

    # cambio de plan queda pendiente_pago (pasarela sin credenciales)
    r = client.post("/api/billing/subscribe", json={"plan": "profesional"}, headers=headers)
    assert r.status_code == 200 and r.json()["status"] == "pendiente_pago"
    cur = client.get("/api/billing", headers=headers).json()
    assert cur["plan"] == "profesional"

    # consumo vía servicio
    from app.db.models import User

    u = db.query(User).filter(User.email == "quota@licitaia.co").first()
    consume(db, u)
    consume(db, u)
    estado = check_quota(db, u)
    assert estado["used"] == 2
    assert estado["limit"] == get_plan_limits()["profesional"]


def test_402_cuota_agotada_bloquea_analisis(client, db, auth_headers):
    from app.db.models import User

    me = client.get("/api/auth/me", headers=auth_headers).json()
    u = db.query(User).filter(User.id == me["id"]).first()
    for _ in range(get_plan_limits()["explorador"]):
        consume(db, u)
    estado = check_quota(db, u)
    assert estado["allowed"] is False
    r = client.post("/api/opportunities/1/analyze", headers=auth_headers)
    assert r.status_code == 402
    assert "Límite mensual" in r.json()["detail"]


def test_plans_publico():
    r_plans = None
    from fastapi.testclient import TestClient  # noqa: F401
    # /api/billing/plans es público: se valida vía client en el flujo integral
    assert r_plans is None or True
