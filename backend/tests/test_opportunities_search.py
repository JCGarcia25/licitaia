"""Regresiones del buscador y la paginación de Oportunidades."""


def test_score_filter_is_applied_before_pagination(client, db):
    from app.db.models import User
    from app.services.demo import seed_demo_if_empty

    seed_demo_if_empty(db)
    email = "search-pagination@licitaia.co"
    response = client.post("/api/auth/register", json={
        "email": email, "password": "ClaveSegura123", "full_name": "Search QA",
    })
    assert response.status_code == 201
    headers = {"Authorization": f"Bearer {response.json()['access_token']}"}
    user = db.query(User).filter(User.email == email).one()
    profile_response = client.put("/api/profile", json={
        "sector": "Tecnologías de la información",
        "actividades": "Desarrollo de software",
        "productos_servicios": "Sistemas de información",
        "keywords": ["software"],
        "departamentos": ["Bogotá D.C."],
        "presupuesto_min": 0,
        "presupuesto_max": 999999999999,
    }, headers=headers)
    assert profile_response.status_code == 200, profile_response.text

    # A user can have scored records mixed with unscored records. The API must
    # count and paginate the filtered set, not paginate the unfiltered set.
    from app.services.alerts import rescore_user
    rescore_user(db, user.id)
    response = client.get(
        "/api/opportunities?solo_con_score=true&limit=1&offset=0",
        headers=headers,
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["total"] >= len(payload["items"])
    assert all(item["score"] is not None and item["score"] > 0 for item in payload["items"])


def test_manual_search_honours_score_and_triage_filters(client, db):
    from app.db.models import User
    from app.services.demo import seed_demo_if_empty

    seed_demo_if_empty(db)
    email = "search-filters@licitaia.co"
    response = client.post("/api/auth/register", json={
        "email": email, "password": "ClaveSegura123", "full_name": "Search Filters QA",
    })
    assert response.status_code == 201
    headers = {"Authorization": f"Bearer {response.json()['access_token']}"}
    user = db.query(User).filter(User.email == email).one()
    profile_response = client.put("/api/profile", json={
        "sector": "Tecnologías de la información",
        "actividades": "Desarrollo de software",
        "productos_servicios": "Sistemas de información",
        "keywords": ["software"],
    }, headers=headers)
    assert profile_response.status_code == 200, profile_response.text
    from app.services.alerts import rescore_user
    rescore_user(db, user.id)

    response = client.post("/api/search", json={
        "q": "software",
        "solo_con_score": True,
        "score_min": 70,
        "triage": "guardada",
        "limit": 25,
        "offset": 0,
    }, headers=headers)
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["total"] == len(payload["items"])
    assert all((item["score"] or 0) >= 70 and item["triage"] == "guardada" for item in payload["items"])
