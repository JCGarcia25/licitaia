from datetime import datetime, timedelta

from match_test_support import stamp_fixture_scores

from app.db.models import CompanyProfile, Opportunity, User, UserOpportunity


def test_ranking_usa_perfil_puntaje_y_filtra_antes_de_paginar(client, db, auth_headers):
    email = client.get('/api/auth/me', headers=auth_headers).json()['email']
    user = db.query(User).filter_by(email=email).one()
    db.add(CompanyProfile(user_id=user.id, sector='software', actividades='desarrollo de software', productos_servicios='aplicaciones', keywords=['software']))
    data = [('Desarrollo de software A', 62, 'Publicado'), ('Desarrollo de software B', 85, 'Publicado'), ('Servicios de fisioterapia', 95, 'Publicado'), ('Software vencido', 99, 'En ejecución')]
    for i, (title, score, status) in enumerate(data):
        opp = Opportunity(source='qa', source_id=f'ranking-{user.id}-{i}', objeto=title, descripcion='', estado=status, fecha_publicacion=datetime.utcnow() - timedelta(days=1), cancelled=False)
        db.add(opp)
        db.flush()
        db.add(UserOpportunity(user_id=user.id, opportunity_id=opp.id, score=score, triage='detectada'))
    db.commit()
    stamp_fixture_scores(db, user.id)
    response = client.get('/api/opportunities?profile_match=true&score_min=50&limit=1', headers=auth_headers)
    assert response.status_code == 200
    assert response.json()['total'] == 2
    assert response.json()['items'][0]['objeto'] == 'Desarrollo de software B'
    second = client.get('/api/opportunities?profile_match=true&score_min=50&limit=1&offset=1', headers=auth_headers).json()
    assert second['items'][0]['objeto'] == 'Desarrollo de software A'
    assert client.get('/api/opportunities?profile_match=true&score_min=90', headers=auth_headers).json()['total'] == 0
    db.query(UserOpportunity).filter_by(user_id=user.id).delete()
    db.query(Opportunity).filter(Opportunity.source == 'qa', Opportunity.source_id.like(f'ranking-{user.id}-%')).delete(synchronize_session=False)
    db.commit()


def test_ranking_desempata_puntuaciones_y_conserva_total(client, db, auth_headers):
    from uuid import uuid4
    email = client.get('/api/auth/me', headers=auth_headers).json()['email']
    user = db.query(User).filter_by(email=email).one()
    db.add(CompanyProfile(user_id=user.id, sector='software', actividades='desarrollo de software', keywords=['software']))
    ids = []
    for _ in range(3):
        opp = Opportunity(source='qa', source_id=uuid4().hex, objeto='Desarrollo de software', estado='Publicado', cancelled=False)
        db.add(opp)
        db.flush()
        ids.append(opp.id)
        db.add(UserOpportunity(user_id=user.id, opportunity_id=opp.id, score=60))
    db.commit()
    stamp_fixture_scores(db, user.id)
    pages = [client.get(f'/api/opportunities?profile_match=true&score_min=50&limit=1&offset={i}', headers=auth_headers).json() for i in range(3)]
    assert all(page['total'] == 3 for page in pages)
    assert [page['items'][0]['id'] for page in pages] == sorted(ids, reverse=True)
    db.query(UserOpportunity).filter(UserOpportunity.opportunity_id.in_(ids)).delete(synchronize_session=False)
    db.query(Opportunity).filter(Opportunity.id.in_(ids)).delete(synchronize_session=False)
    db.commit()
