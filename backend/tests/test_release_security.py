"""Cross-tenant regressions found during release audit; only fictional data."""
from datetime import datetime, timedelta
from uuid import uuid4

import pytest

from app.core.security import decode_token
from app.db.models import Analysis, Company, Opportunity, Subscription, User


def test_release_preflight_is_offline_and_rejects_unsafe_defaults():
    from scripts.release_preflight import check
    from app.core.config import Settings
    base = Settings(_env_file=None, environment='development', secret_key='x'*40,
                    database_url='postgresql+psycopg2://qa@127.0.0.1/mysecop_test_rc',
                    redis_url='redis://127.0.0.1:6379/13', frontend_url='http://127.0.0.1:3000',
                    cors_origins='http://127.0.0.1:3000', allow_demo_seed=False,
                    evaluation_enabled=False, compatibility_v2_shadow_enabled=False,
                    evaluation_semantic_enabled=False, evaluation_external_max_calls=0)
    assert check(base)['status'] == 'PASS_OFFLINE'
    assert check(base)['connections_opened'] == 0
    for change in [dict(environment='production'), dict(secret_key='short'),
                   dict(database_url='postgresql:///ambient'), dict(allow_demo_seed=True),
                   dict(evaluation_enabled=True, evaluation_dev_targets=[]),
                   dict(evaluation_semantic_enabled=True), dict(evaluation_external_max_calls=1),
                   dict(cors_origins='*'), dict(embedding_provider='openai')]:
        assert check(base.model_copy(update=change))['status'] == 'BLOCKED'


@pytest.mark.parametrize('has_owned_analysis', [False, True])
def test_private_analysis_never_flows_from_other_company(
    client, db, auth_headers, monkeypatch, has_owned_analysis,
):
    from app.routers import agents

    actor = db.query(User).filter_by(email=decode_token(auth_headers['Authorization'][7:])).one()
    companies = [Company(nombre='Release fictional company '+uuid4().hex) for _ in range(2)]
    db.add_all(companies); db.flush()
    actor.company_id = companies[0].id
    other = User(email=uuid4().hex+'@example.com', hashed_password='unused-fixture', company_id=companies[1].id)
    db.add(other); db.flush()
    db.add(Subscription(user_id=actor.id, plan='profesional', status='activa', provider='test'))
    opportunity = Opportunity(source='release-test', source_id=uuid4().hex, objeto='Synthetic release process')
    db.add(opportunity); db.flush()
    own_requirements = [{'tipo':'documental', 'descripcion':'OWN_REQUIREMENT'}] if has_owned_analysis else []
    if has_owned_analysis:
        db.add(Analysis(opportunity_id=opportunity.id, user_id=actor.id, company_id=actor.company_id,
                        resumen_ejecutivo={'marker':'OWN'}, requisitos=own_requirements,
                        created_at=datetime.utcnow()-timedelta(days=1)))
    db.add(Analysis(opportunity_id=opportunity.id, user_id=other.id, company_id=other.company_id,
                    resumen_ejecutivo={'marker':'FOREIGN_PRIVATE', 'fecha_hora_cierre':{
                        'valor':(datetime.utcnow()+timedelta(days=2)).strftime('%Y-%m-%d')}},
                    requisitos=[{'tipo':'documental','descripcion':'FOREIGN_PRIVATE'}]))
    db.commit()
    detail = client.get(f'/api/opportunities/{opportunity.id}', headers=auth_headers)
    assert detail.status_code == 200
    assert 'FOREIGN_PRIVATE' not in detail.text
    assert bool(detail.json()['analysis']) == has_owned_analysis

    seen = []
    eligibility = agents.evaluar_elegibilidad
    viability = agents.evaluar_viabilidad
    def capture_eligibility(profile, requirements):
        seen.append(requirements)
        return eligibility(profile, requirements)
    def capture_viability(profile, summary, requirements, **kwargs):
        assert summary == ({'marker':'OWN'} if has_owned_analysis else {})
        seen.append(requirements)
        return viability(profile, summary, requirements, **kwargs)
    monkeypatch.setattr(agents, 'evaluar_elegibilidad', capture_eligibility)
    monkeypatch.setattr(agents, 'evaluar_viabilidad', capture_viability)
    assert client.get(f'/api/opportunities/{opportunity.id}/eligibility', headers=auth_headers).status_code == 200
    assert client.post(f'/api/opportunities/{opportunity.id}/viability', headers=auth_headers).status_code == 200
    assert seen == [own_requirements, own_requirements]
    project = client.post('/api/offer-projects', json={'opportunity_id':opportunity.id}, headers=auth_headers)
    assert project.status_code == 201, project.text
    assert 'FOREIGN_PRIVATE' not in project.text
    draft = client.post(f"/api/offer-projects/{project.json()['id']}/borradores",
                        json={'tipo':'matriz_cumplimiento'}, headers=auth_headers)
    assert draft.status_code == 200, draft.text
    assert 'FOREIGN_PRIVATE' not in draft.text
    from app.services.alerts import close_reminders
    assert close_reminders(db, actor.id, days=[1]) == 0
