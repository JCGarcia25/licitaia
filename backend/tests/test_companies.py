"""Fase 6 — Aislamiento por empresa, roles, permisos y auditoría."""


def test_crear_empresa_miembros_y_auditoria(client, auth_headers):
    r = client.post("/api/companies", json={"nombre": "Acme SAS", "nit": "900123", "sector": "TI"}, headers=auth_headers)
    assert r.status_code == 201 and r.json()["rol"] == "owner"
    cid = r.json()["id"]

    me = client.get("/api/auth/me", headers=auth_headers).json()
    assert me["company_id"] == cid and me["role"] == "owner"

    # empresa duplicada
    r = client.post("/api/companies", json={"nombre": "Otra"}, headers=auth_headers)
    assert r.status_code == 409

    # agregar miembro (debe registrarse primero)
    client.post("/api/auth/register", json={"email": "miembro@licitaia.co", "password": "ClaveSegura123", "full_name": "M"})
    r = client.post("/api/companies/members", json={"email": "miembro@licitaia.co", "role": "analista"}, headers=auth_headers)
    assert r.status_code == 201, r.text

    members = client.get("/api/companies/members", headers=auth_headers).json()
    assert any(m["email"] == "miembro@licitaia.co" and m["role"] == "analista" for m in members)

    # auditoría visible para owner con la acción registrada
    audit = client.get("/api/audit", headers=auth_headers)
    assert audit.status_code == 200
    assert any(a["action"] == "crear_empresa" for a in audit.json())
    assert any(a["action"] == "agregar_miembro" for a in audit.json())

    # dashboard administrativo
    metrics = client.get("/api/admin/metrics", headers=auth_headers)
    assert metrics.status_code == 200
    assert metrics.json()["miembros"] == 2


def test_permisos_por_rol(client, auth_headers):
    client.post("/api/companies", json={"nombre": "Beta SAS"}, headers=auth_headers)
    client.post("/api/auth/register", json={"email": "analista1@licitaia.co", "password": "ClaveSegura123"})
    r = client.post("/api/companies/members", json={"email": "analista1@licitaia.co", "role": "analista"}, headers=auth_headers)
    assert r.status_code == 201

    login = client.post("/api/auth/login", data={"username": "analista1@licitaia.co", "password": "ClaveSegura123"})
    h2 = {"Authorization": f"Bearer {login.json()['access_token']}"}

    # analista lista miembros pero no agrega
    assert client.get("/api/companies/members", headers=h2).status_code == 200
    assert client.post("/api/companies/members", json={"email": "x@licitaia.co", "role": "lector"}, headers=h2).status_code == 403

    # analista no accede a auditoría ni métricas administrativas
    assert client.get("/api/audit", headers=h2).status_code == 403
    assert client.get("/api/admin/metrics", headers=h2).status_code == 403

    # cambiar rol requiere owner
    assert client.patch("/api/companies/members/999", json={"role": "admin"}, headers=h2).status_code in (403, 404)


def test_usuario_sin_empresa_rechazado(client):
    client.post("/api/auth/register", json={"email": "solo@licitaia.co", "password": "ClaveSegura123"})
    login = client.post("/api/auth/login", data={"username": "solo@licitaia.co", "password": "ClaveSegura123"})
    h = {"Authorization": f"Bearer {login.json()['access_token']}"}
    assert client.get("/api/companies/members", headers=h).status_code == 400
    assert client.get("/api/audit", headers=h).status_code == 400


def test_aislamiento_entre_empresas(client, db):
    # empresa A con owner A
    r = client.post("/api/auth/register", json={"email": "ownerA@licitaia.co", "password": "ClaveSegura123"})
    hA = {"Authorization": f"Bearer {r.json()['access_token']}"}
    client.post("/api/companies", json={"nombre": "Empresa A"}, headers=hA)
    # empresa B con owner B
    r = client.post("/api/auth/register", json={"email": "ownerB@licitaia.co", "password": "ClaveSegura123"})
    hB = {"Authorization": f"Bearer {r.json()['access_token']}"}
    client.post("/api/companies", json={"nombre": "Empresa B"}, headers=hB)

    # A no puede agregar como miembro a un usuario de B... pero sí ver solo sus miembros
    membersA = client.get("/api/companies/members", headers=hA).json()
    assert all(m["email"] != "ownerB@licitaia.co" for m in membersA)
    membersB = client.get("/api/companies/members", headers=hB).json()
    assert all(m["email"] != "ownerA@licitaia.co" for m in membersB)

    # auditoría de A no contiene acciones de B
    auditA = client.get("/api/audit", headers=hA).json()
    auditB = client.get("/api/audit", headers=hB).json()
    assert all(a["detail"].get("nombre") != "Empresa B" for a in auditA)
    assert all(a["detail"].get("nombre") != "Empresa A" for a in auditB)
