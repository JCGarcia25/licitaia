"""Casos funcionales del envío opcional de resúmenes por correo."""


def _create_pro_user(client, db, email):
    from app.db.models import Subscription, User

    response = client.post("/api/auth/register", json={
        "email": email, "password": "ClaveSegura123", "full_name": "Alertas QA",
    })
    assert response.status_code == 201, response.text
    user = db.query(User).filter(User.email == email).one()
    user.email_verified = True
    db.add(Subscription(user_id=user.id, plan="profesional", status="activa", provider="test"))
    db.commit()
    return {"Authorization": f"Bearer {response.json()['access_token']}"}, user


def test_preferencias_por_defecto_y_actualizacion(client, db):
    headers, _ = _create_pro_user(client, db, "alerts-prefs@licitaia.co")

    response = client.get("/api/alerts/prefs", headers=headers)
    assert response.status_code == 200
    assert response.json()["email_enabled"] is False

    response = client.put("/api/alerts/prefs", json={
        "email_enabled": True,
        "high_score_threshold": 80,
        "close_days": [10, 3, 1],
        "digest_hour": 8,
    }, headers=headers)
    assert response.status_code == 200
    assert response.json()["ok"] is True
    assert response.json()["email_enabled"] is True
    assert response.json()["high_score_threshold"] == 80
    assert response.json()["close_days"] == [10, 3, 1]
    assert response.json()["digest_hour"] == 8

    response = client.delete("/api/alerts/prefs", headers=headers)
    assert response.status_code == 200
    response = client.get("/api/alerts/prefs", headers=headers)
    assert response.json()["email_enabled"] is False


def test_casilla_controla_destinatario_y_envio(client, db, monkeypatch):
    headers, user = _create_pro_user(client, db, "alerts-recipient@licitaia.co")
    enviados = []

    def fake_send_email(to, subject, body):
        enviados.append((to, subject, body))
        return True

    monkeypatch.setattr("app.routers.alerts.send_email", fake_send_email)

    # Desactivada: no se intenta enviar correo.
    response = client.post("/api/alerts/digest", headers=headers)
    assert response.status_code == 200
    assert response.json()["correo_enviado"] is False
    assert enviados == []

    client.put("/api/alerts/prefs", json={
        "email_enabled": True, "high_score_threshold": 70,
        "close_days": [10, 5, 1], "digest_hour": 7,
    }, headers=headers)
    response = client.post("/api/alerts/digest", headers=headers)
    assert response.status_code == 200
    assert response.json()["correo_enviado"] is True
    assert len(enviados) == 1
    assert enviados[0][0] == user.email
    assert "Resumen" in enviados[0][1]


def test_usuario_no_verificado_no_recibe_resumen(client, db, monkeypatch):
    headers, user = _create_pro_user(client, db, "alerts-unverified@licitaia.co")
    user.email_verified = False
    db.commit()
    client.put("/api/alerts/prefs", json={
        "email_enabled": True, "high_score_threshold": 70,
        "close_days": [10, 5, 1], "digest_hour": 7,
    }, headers=headers)
    monkeypatch.setattr("app.routers.alerts.send_email", lambda *args: (_ for _ in ()).throw(AssertionError("no debe enviar")))

    response = client.post("/api/alerts/digest", headers=headers)
    assert response.status_code == 200
    assert response.json()["correo_enviado"] is False
def test_alertas_exigen_actividad_relacionada_y_proceso_vigente():
    from datetime import datetime, timedelta
    from types import SimpleNamespace
    from app.services.alerts import has_profile_match, opportunity_is_current

    perfil = SimpleNamespace(sector='software', actividades='desarrollo de software', productos_servicios='aplicaciones web', keywords=['software'], unspsc_codes=[])
    proceso = SimpleNamespace(objeto='Servicios de fisioterapia', descripcion='Atención en salud', unspsc_code=None, cancelled=False, fecha_publicacion=datetime.utcnow() - timedelta(days=1), fecha_cierre=datetime.utcnow() + timedelta(days=1), estado='Publicado')
    assert not has_profile_match(None, perfil, proceso)
    proceso.objeto = 'Desarrollo de software'
    assert has_profile_match(None, perfil, proceso)
    assert opportunity_is_current(proceso)
    proceso.fecha_cierre = datetime.utcnow() - timedelta(days=1)
    assert not opportunity_is_current(proceso)
    proceso.fecha_cierre = None
    proceso.estado = 'En ejecución'
    assert not opportunity_is_current(proceso)

