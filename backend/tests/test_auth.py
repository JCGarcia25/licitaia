"""Pruebas de autenticación: registro, login JWT, perfil actual, errores."""


def test_register_login_me(client):
    r = client.post("/api/auth/register", json={"email": "auth1@licitaia.co", "password": "ClaveSegura123", "full_name": "Auth Uno"})
    assert r.status_code == 201
    token = r.json()["access_token"]

    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["email"] == "auth1@licitaia.co"
    assert me.json()["full_name"] == "Auth Uno"


def test_register_duplicado(client):
    client.post("/api/auth/register", json={"email": "dup@licitaia.co", "password": "ClaveSegura123"})
    r = client.post("/api/auth/register", json={"email": "dup@licitaia.co", "password": "ClaveSegura123"})
    assert r.status_code == 409


def test_login_credenciales(client):
    client.post("/api/auth/register", json={"email": "login@licitaia.co", "password": "ClaveSegura123"})
    ok = client.post("/api/auth/login", data={"username": "login@licitaia.co", "password": "ClaveSegura123"})
    assert ok.status_code == 200
    assert ok.json()["token_type"] == "bearer"
    bad = client.post("/api/auth/login", data={"username": "login@licitaia.co", "password": "incorrecta"})
    assert bad.status_code == 401


def test_sin_token_rechaza(client):
    assert client.get("/api/auth/me").status_code == 401
    assert client.get("/api/opportunities").status_code == 401
