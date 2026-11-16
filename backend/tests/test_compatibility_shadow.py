from datetime import datetime,timedelta
from uuid import uuid4
import pytest
from app.core.config import get_settings
from app.db.models import User, CompanyProfile, Opportunity, UserOpportunity, CompatibilityShadowRun as Run, CompatibilityShadowResult as Result
from app.services import compatibility_shadow as shadow
from test_match_api import account

@pytest.fixture(autouse=True)
def clean_only_new_test_candidates(client,db):
    # Session-scoped SQLite fixtures are shared with legacy E2E tests. Remove
    # only this module's disposable rows after each test, never application data.
    previous={r.id for r in db.query(Run)}
    yield
    db.rollback()
    new=[r.id for r in db.query(Run) if r.id not in previous]
    if new:
        db.query(Result).filter(Result.run_id.in_(new)).delete(synchronize_session=False)
        db.query(Run).filter(Run.id.in_(new)).delete(synchronize_session=False)
    db.query(Opportunity).filter_by(source='qa-phase2-unit').delete(synchronize_session=False)
    db.commit()


@pytest.fixture
def enabled(client,db,monkeypatch):
    from evaluation_test_support import authorize
    authorize(db,monkeypatch)
    monkeypatch.setattr(get_settings(),'compatibility_v2_shadow_enabled',True)
    monkeypatch.setattr(get_settings(),'compatibility_v2_batch_size',2)


def seed(db):
    user=User(email=f'{uuid4().hex}@example.invalid',hashed_password='fixture',role='admin')
    db.add(user);db.flush();db.add(CompanyProfile(user_id=user.id,sector='software',departamentos=['Meta']))
    db.add_all([Opportunity(source='qa-phase2-unit',source_id=uuid4().hex,objeto='diagnóstico aislado',estado='En proceso') for _ in range(3)])
    db.commit();return user.id


def test_flag_default_and_production_guard(client,auth_headers,monkeypatch):
    assert not get_settings().compatibility_v2_shadow_enabled
    assert client.get('/api/internal/compatibility-v2/runs',headers=auth_headers).status_code==404
    monkeypatch.setattr(get_settings(),'compatibility_v2_shadow_enabled',True)
    monkeypatch.setattr(get_settings(),'environment','production')
    assert not shadow.enabled()


def test_bounded_idempotent_shadow_preserves_legacy(client,db,enabled):
    uid=seed(db);before=[(r.id,r.score,r.triage) for r in db.query(UserOpportunity)]
    run=shadow.create_run(db,uid,3);db.commit();rid=run.id
    with pytest.raises(ValueError):shadow.create_run(db,uid,3)
    db.rollback()
    assert shadow.process_batch(db,rid)=='RUNNING'
    assert shadow.process_batch(db,rid)=='COMPLETED'
    assert shadow.process_batch(db,rid)=='BUSY_OR_FINISHED'
    assert db.query(Result).filter_by(run_id=rid).count()==3
    assert [(r.id,r.score,r.triage) for r in db.query(UserOpportunity)]==before
    output=shadow.diagnostic(db,db.get(Run,rid))
    assert all(r['legacy_score'] is None for r in output['results'])
    with pytest.raises(ValueError):shadow.create_run(db,uid,101)


def test_lease_takeover_and_disable(client,db,enabled):
    uid=seed(db);r=shadow.create_run(db,uid,3);db.commit();rid=r.id
    r.lease_token='other';r.lease_until=datetime.utcnow()+timedelta(minutes=1);db.commit()
    assert shadow.process_batch(db,rid)=='BUSY_OR_FINISHED'
    r.lease_until=datetime.utcnow()-timedelta(seconds=1);db.commit()
    assert shadow.process_batch(db,rid)=='RUNNING'
    get_settings().compatibility_v2_shadow_enabled=False
    assert shadow.process_batch(db,rid)=='DISABLED'


def test_private_api_no_self_verification(client,db,enabled):
    email,h=account(client);email2,h2=account(client)
    users=[db.query(User).filter_by(email=e).one() for e in (email,email2)]
    assert client.get('/api/internal/compatibility-v2/runs',headers=h).status_code==403
    for u in users:u.role='admin'
    db.add(CompanyProfile(user_id=users[0].id,sector='software'));db.commit()
    response=client.post('/api/internal/compatibility-v2/evidence',headers=h,json={'facts':[{'key':'liquidity','value':3,'level':'VERIFIED'}]})
    assert response.status_code==422
    assert client.post('/api/internal/compatibility-v2/evidence',headers=h,json={'facts':[],'not_applicable':{'financial':True}}).status_code==422
    assert client.post('/api/internal/compatibility-v2/evidence',headers=h,json={'facts':[{'key':'executed_contract','value':'declared contract','category':'experience'}]}).status_code==201
    run=client.post('/api/internal/compatibility-v2/runs',headers=h,json={'limit':3})
    assert run.status_code==202,run.text
    rid=run.json()['id']
    assert client.get(f'/api/internal/compatibility-v2/runs/{rid}',headers=h2).status_code==404
    assert client.post(f'/api/internal/compatibility-v2/runs/{rid}/resume',headers=h2).status_code==404
    assert client.post('/api/internal/compatibility-v2/documents/999999/extract',headers=h2).status_code==404


def test_snapshot_historic_profile_changes_do_not_mix(client,db,enabled):
    uid=seed(db);run=shadow.create_run(db,uid,1);db.commit()
    profile=db.query(CompanyProfile).filter_by(user_id=uid).one();profile.sector='agriculture';db.commit()
    assert shadow.process_batch(db,run.id)=='COMPLETED'
    row=db.query(Result).filter_by(run_id=run.id).one()
    assert row.result['criteria'][0]['company_value']['text'].startswith('software')


def test_document_extraction_provenance_and_foreign_document(client,db,enabled,tmp_path,monkeypatch):
    from io import BytesIO
    from docx import Document as Word
    from app.db.models import Document,CompatibilityEvidenceProfile as Evidence
    from app.services.compatibility_documents import extract
    uid=seed(db);doc=Word();doc.add_paragraph('Objeto: Desarrollo de aplicaciones contables')
    doc.add_paragraph('Contratante: Empresa sintética de prueba');doc.add_paragraph('Valor: COP 1000000')
    doc.add_paragraph('Tipo de contrato: Servicios');doc.add_paragraph('Fecha: 2025-01-01')
    doc.add_paragraph('Actividades: Implementación de aplicaciones');doc.add_paragraph('Certificación: ISO 9001')
    data=BytesIO();doc.save(data);path=tmp_path/'contract.docx';path.write_bytes(data.getvalue())
    row=Document(user_id=uid,filename='contract.docx',storage_path=str(path));db.add(row);db.commit()
    extracted=extract(row,str(tmp_path))
    assert {r['key'] for r in extracted['observations']}=={'object','contracting_entity','amount_literal','contract_type','dates_literal','activities','certifications'}
    assert all(r['level']=='DOCUMENTED' and r['source_ref']['quote'] and r['source_ref']['file_hash'] for r in extracted['observations'])
    with pytest.raises(ValueError):extract(row,str(tmp_path/'unrelated'))
    email,headers=account(client);user=db.query(User).filter_by(email=email).one();user.role='admin';db.commit()
    assert client.post(f'/api/internal/compatibility-v2/documents/{row.id}/extract',headers=headers).status_code==404


def test_private_paired_export_is_unlabeled_and_input_frozen(client,db,enabled):
    from app.services.compatibility_evaluation import compare
    uid=seed(db);run=shadow.create_run(db,uid,2);db.commit()
    with pytest.raises(ValueError):shadow.evaluation_export(db,run)
    assert shadow.process_batch(db,run.id)=='COMPLETED'
    payload=shadow.evaluation_export(db,db.get(Run,run.id))
    assert payload['judgments']==[] and payload['queries'][0]['universe_complete'] is False
    assert payload['queries'][0]['company_cluster_id']!=str(uid)
    report=compare(payload['legacy'],payload['v2'],[],payload['queries'])
    assert report['status']=='PENDING_SUFFICIENT_HUMAN_LABELS'
    assert not report['promotion_authorized']
    assert client.get(f'/api/internal/compatibility-v2/runs/{run.id}/evaluation').status_code==401
