"""Fase 6 — Contacto funcional y verificación de correo."""


def test_contacto_funcional(client):
    r = client.post("/api/contact", json={
        "nombre": "Ana Rojas", "email": "ana@empresa.co",
        "mensaje": "Quiero una demostración de LicitaIA para mi equipo comercial.",
    })
    assert r.status_code == 201, r.text
    assert r.json()["recibido"] is True
    assert r.json()["correo_entregado"] is False  # SMTP sin configurar en pruebas: queda registrado


def test_contacto_validacion(client):
    r = client.post("/api/contact", json={"nombre": "A", "email": "no-es-correo", "mensaje": "corto"})
    assert r.status_code == 422


def test_verificacion_de_correo(client):
    r = client.post("/api/auth/register", json={"email": "verify@licitaia.co", "password": "ClaveSegura123"})
    token = r.json().get("verification_token")
    assert token  # sin SMTP configurado el token se devuelve (dev/pruebas); con SMTP se envía por correo
    r = client.post("/api/auth/verify-email", json={"token": token})
    assert r.status_code == 200 and r.json()["verificado"] is True
    # token de un solo uso
    r = client.post("/api/auth/verify-email", json={"token": token})
    assert r.status_code == 400
