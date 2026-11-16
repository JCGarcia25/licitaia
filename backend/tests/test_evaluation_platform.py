"""All labels/companies in this module are explicitly synthetic test fixtures."""
from datetime import timedelta
from uuid import uuid4
import json
import pytest
from app.core.config import get_settings
from app.db.models import (User,EvaluationEnvironmentIdentity as Identity,EvaluationCampaign as Campaign,EvaluationSample as Sample,EvaluationAssignment as Assignment,EvaluationJudgment as Judgment,EvaluationReport as Report)
from app.evaluation_schemas import CampaignIn,AssignIn
from app.services import evaluation_platform as p
from app.services.evaluation_guard import destination,require_environment,EnvironmentDenied
from app.services.match_versions import digest
from app.services.evaluation_sampling import select
from app.services.evaluation_reporting import agreement,close
from test_match_api import account

@pytest.fixture
def gate(client,db,monkeypatch):
    s=get_settings()
    monkeypatch.setattr(s,'evaluation_enabled',True);monkeypatch.setattr(s,'evaluation_api_origin','http://testserver')
    fp=digest(destination(s));marker=db.query(Identity).filter_by(fingerprint=fp).one_or_none()
    if not marker:marker=Identity(id=str(uuid4()),fingerprint=fp,purpose='isolated-development');db.add(marker);db.commit()
    monkeypatch.setattr(s,'evaluation_dev_targets',[{'database':s.database_url,'broker':s.redis_url,'api_origin':s.evaluation_api_origin,'identity':marker.id}])
    return s


def body(count=12,**kwargs):
    rows=[{'company_key':f'fixture-company-{i%4}','process_key':f'fixture-process-{i}','profile':{'sector':'software','actividades':'software contable','departamentos':['Meta'],'presupuesto_min':1,'presupuesto_max':2000000},'opportunity':{'objeto':'software contable' if i%2 else 'maquinaria agrícola','departamento':'Meta','valor':1000000,'estado':'En proceso','modalidad':'Licitación'},'retrieval_origin':['legacy_only','v2_only','independent_search','random_frame'][i%4]} for i in range(count)]
    return CampaignIn(name='SYNTHETIC TEST ONLY',synthetic_pairs=rows,authorization_reference='synthetic controlled fixture',blinded_sharing_authorized=True,sample_size=min(count,100),**kwargs)


def ready(db,actor,count=12,**kw):
    c=p.create(db,actor,body(count,**kw));db.commit()
    for _ in range(110):
        state=p.process_batch(db,c.id)
        if state not in {'PREPARING','SEMANTICS'}:break
    assert state=='READY';db.expire_all();return db.get(Campaign,c.id)


def users(client,db):
    result=[]
    for role in ('admin','evaluation_reviewer','evaluation_reviewer','evaluation_reviewer','owner'):
        email,h=account(client);u=db.query(User).filter_by(email=email).one();u.role=role;db.commit();result.append((u.id,h))
    return result


def payload(relevance):return {'relevance':relevance,'eligibility':'NOT_EVALUABLE','evidence_quality':'INSUFFICIENT','reason':'Synthetic fixture independent judgment','pending_requirements':[],'supporting_reference':None}


def test_guard_exact_tuple_identity_and_environment(client,db,gate,monkeypatch):
    assert require_environment(db)
    for field,value in [('redis_url','redis://production.invalid:6379/0'),('database_url','postgresql://fake@production.invalid/customer'),('environment','production')]:
        with monkeypatch.context() as m:
            m.setattr(gate,field,value)
            with pytest.raises(EnvironmentDenied):require_environment(db)
    with monkeypatch.context() as m:
        m.setattr(gate,'evaluation_dev_targets',[])
        with pytest.raises(EnvironmentDenied):p.create(db,1,body())


def test_stratified_reproducibility_dedup_and_company_holdout(client,db,gate):
    actor=users(client,db)[0][0];c=ready(db,actor,100)
    a=select(c.universe,100,123,.2);b=select(list(reversed(c.universe)),100,123,.2)
    assert a==b and len(a['selected'])==100
    assert all(0<r['inclusion_probability']<=1 for r in a['selected'])
    duplicated=[*c.universe,{**c.universe[0],'pair_key':'another-pair'}]
    d=select(duplicated,100,123,.2)
    assert d['frame_pairs']==100 and len(d['duplicate_process_pairs_excluded'])==1
    index={r['pair_key']:r for r in c.universe};part={}
    for row in a['selected']:part.setdefault(index[row['pair_key']]['company_cluster_id'],set()).add(row['split'])
    assert all(len(s)==1 for s in part.values())


def test_double_blind_disagreement_adjudication_and_sealed_report(client,db,gate):
    people=users(client,db);actor,admin_headers=people[0];c=ready(db,actor,2);samples=db.query(Sample).filter_by(campaign_id=c.id).all()
    p.assign(db,c,actor,AssignIn(sample_ids=[s.id for s in samples],evaluator_user_ids=[people[1][0],people[2][0]]));db.commit()
    primary=db.query(Assignment).filter(Assignment.sample_id.in_([s.id for s in samples])).all()
    for a in primary:
        view=client.get(f'/api/internal/evaluation/assignments/{a.id}',headers=dict(people[1:3])[a.evaluator_user_id])
        assert view.status_code==200,view.text
        assert not any(word in view.text for word in ('predictions','compatibility_score','evidence_coverage','legacy_score','inclusion_probability'))
        relevance=0 if a.evaluator_user_id==people[1][0] else 3
        assert client.post(f'/api/internal/evaluation/assignments/{a.id}/judgments',headers=dict(people[1:3])[a.evaluator_user_id],json=payload(relevance)).status_code==201
        assert client.post(f'/api/internal/evaluation/assignments/{a.id}/judgments',headers=dict(people[1:3])[a.evaluator_user_id],json=payload(1)).status_code==409
    db.expire_all();c=db.get(Campaign,c.id)
    p.assign(db,c,actor,AssignIn(sample_ids=[s.id for s in samples],evaluator_user_ids=[people[3][0]],kind='ADJUDICATION'));db.commit()
    for a in db.query(Assignment).filter(Assignment.sample_id.in_([s.id for s in samples]),Assignment.kind=='ADJUDICATION'):
        p.submit(db,a.id,a.evaluator_user_id,payload(2))
    db.commit();r=close(db,c,actor);db.commit()
    assert r.payload['resolved_pairs']==2 and r.payload['human_label_count']==0 and r.payload['synthetic_test_labels']==2
    assert r.payload['activation_authorized'] is False
    assert client.get(f'/api/internal/evaluation/campaigns/{c.id}/report',headers=people[1][1]).status_code==403
    assert client.get(f'/api/internal/evaluation/campaigns/{c.id}/report',headers=admin_headers).status_code==200
    assert client.get(f'/api/internal/evaluation/assignments/{primary[0].id}',headers=dict(people[1:3])[primary[0].evaluator_user_id]).status_code==409
    row=db.query(Judgment).filter_by(assignment_id=primary[0].id).one();row.payload={**row.payload,'relevance':1}
    with pytest.raises(ValueError):db.flush()
    db.rollback()


def test_permissions_unknown_labels_and_missing_consent(client,db,gate):
    people=users(client,db);actor,h=people[0];c=ready(db,actor,1);sample=db.query(Sample).filter_by(campaign_id=c.id).one()
    assert client.get('/api/internal/evaluation/campaigns',headers=people[4][1]).status_code==403
    assert client.get(f'/api/internal/evaluation/campaigns/{c.id}',headers=people[1][1]).status_code==403
    assert client.get('/api/internal/evaluation/assignments/missing',headers=people[1][1]).status_code==404
    with pytest.raises(ValueError):p.assign(db,c,actor,AssignIn(sample_ids=[sample.id],evaluator_user_ids=[actor]))
    r=close(db,c,actor);db.commit()
    assert r.payload['resolved_pairs']==0 and r.payload['statistical_conclusion']=='INCONCLUSIVE'
    with pytest.raises(ValueError):body(1,max_external_calls=1)
    gate.evaluation_dev_targets=[]
    assert client.get('/api/internal/evaluation/campaigns',headers=h).status_code==404


def test_agreement_known_cases():
    assert agreement([])['quadratic_weighted_kappa'] is None
    assert agreement([(0,0),(3,3)])['quadratic_weighted_kappa']==1
    assert agreement([(0,3),(3,0)])['quadratic_weighted_kappa']==-1
    assert agreement([(1,1),(1,1)])['quadratic_weighted_kappa'] is None


def test_expiration_revokes_access_without_deleting_history(client,db,gate):
    actor=users(client,db)[0][0];c=ready(db,actor,1);c.expires_at=p.now()-timedelta(seconds=1);db.commit()
    with pytest.raises(ValueError):p.owned(db,c.id,actor)
    assert db.get(Campaign,c.id) is not None


def test_semantic_cache_budget_kill_switch_and_no_documents(client,db,gate,monkeypatch):
    from app.services import evaluation_semantic as semantic
    from app.db.models import EvaluationEmbedding as Cache
    actor=users(client,db)[0][0]
    for name,value in [('evaluation_external_max_calls',3),('evaluation_semantic_enabled',True),('embedding_provider','openai'),('openai_api_key','synthetic-test-key-never-sent'),('evaluation_embedding_usd_per_million_tokens',.02)]:monkeypatch.setattr(gate,name,value)
    calls=[]
    def fake_api(text):calls.append(text);return [1.]+[0.]*1535,10
    monkeypatch.setattr(semantic,'request_embedding',fake_api)
    c=ready(db,actor,4,max_external_calls=3,external_text_authorized=True,provider_terms_reference='test fixture terms reviewed')
    assert len(calls)==3 and c.external_calls==3
    assert not any('source_ref' in t or 'document' in t for t in calls)
    assert db.query(Cache).filter_by(campaign_id=c.id,state='READY').count()==3
    assert any(r['predictions']['C']['status']=='REAL_PROVIDER' for r in c.universe)
    # New campaign reuses only same owner's provenance-compatible cache.
    c2=ready(db,actor,4,max_external_calls=3,external_text_authorized=True,provider_terms_reference='test fixture terms reviewed')
    assert len(calls)==3 and c2.external_calls==0
    monkeypatch.setattr(gate,'evaluation_semantic_enabled',False)
    c3=ready(db,actor,2,max_external_calls=3,external_text_authorized=True,provider_terms_reference='test fixture terms reviewed')
    assert len(calls)==3 and all(r['predictions']['C']['score'] is None for r in c3.universe)


def test_failed_external_reservation_never_retries_silently(client,db,gate,monkeypatch):
    from app.services import evaluation_semantic as semantic
    actor=users(client,db)[0][0]
    for name,value in [('evaluation_external_max_calls',2),('evaluation_semantic_enabled',True),('embedding_provider','openai'),('openai_api_key','synthetic-key'),('evaluation_embedding_usd_per_million_tokens',.02)]:monkeypatch.setattr(gate,name,value)
    calls=[]
    def fail(text):calls.append(text);raise TimeoutError('controlled API fixture failure')
    monkeypatch.setattr(semantic,'request_embedding',fail)
    c=ready(db,actor,2,max_external_calls=2,external_text_authorized=True,provider_terms_reference='fixture terms review')
    assert len(calls)==1 and c.external_calls==1
    assert all(r['predictions']['C']['score'] is None for r in c.universe)


def test_false_dev_label_does_not_override_unapproved_destination(client,db,gate,monkeypatch):
    actor,h=users(client,db)[0]
    monkeypatch.setattr(gate,'database_url','postgresql://dummy@prod.example.invalid/live')
    assert client.post('/api/internal/evaluation/campaigns',headers=h,json=body(1).model_dump()).status_code==404


def test_cross_owner_snapshot_requires_explicit_revocable_grant(client,db,gate,monkeypatch):
    monkeypatch.setattr(gate,"secret_key","synthetic-test-installation-key-over-32-characters")
    from app.db.models import CompanyProfile,Opportunity,CompatibilityShadowRun as Run,CompatibilityShadowResult as Result,EvaluationDataGrant as Grant
    from app.services.compatibility_v2 import feature_snapshot,OPPORTUNITY_FIELDS,model_version
    from app.services.compatibility_shadow import config
    from app.evaluation_schemas import GrantIn
    people=users(client,db);data_owner=people[1][0];administrator=people[0][0]
    o=Opportunity(source='secop2_procesos',source_id=uuid4().hex,objeto='Herramientas de demostración privada',estado='En proceso');db.add(o);db.commit()
    from app.services.match_versions import profile_version
    from app.services.compatibility_v2 import PROFILE_FIELDS
    company_profile=CompanyProfile(user_id=data_owner,**body(1).synthetic_pairs[0].profile);db.add(company_profile);db.commit()
    profile=feature_snapshot(company_profile,PROFILE_FIELDS)
    run=Run(id=str(uuid4()),user_id=data_owner,state='COMPLETED',model_version=model_version(config()),snapshot={'profile':profile,'evidence':{},'as_of':'2026-11-15','candidates':[{'id':o.id,'opportunity':feature_snapshot(o,OPPORTUNITY_FIELDS),'requirements':[],'legacy_versions':{'profile':profile_version(company_profile)}}]});db.add(run);db.commit()
    db.add(Result(run_id=run.id,opportunity_id=o.id,legacy_score=75,legacy_versions={'status':'CURRENT','profile':profile_version(company_profile),'opportunity':o.match_version,'algorithm':'fixture-legacy'},result={},duration_ms=0));db.commit()
    foreign=CampaignIn(name='TEST AUTHORIZATION',scope='authorized_real',run_ids=[run.id],authorization_reference='test fixture explicit authorization',blinded_sharing_authorized=True,sample_size=1)
    with pytest.raises(ValueError):p.create(db,administrator,foreign)
    g=p.create_grant(db,data_owner,GrantIn(run_id=run.id,administrator_user_id=administrator,authorization_reference='synthetic owner consent fixture',blinded_sharing_authorized=True));db.commit()
    request=CampaignIn(name='TEST GRANTED SNAPSHOT',scope='authorized_real',grant_ids=[g.id],authorization_reference='test fixture explicit campaign authorization',blinded_sharing_authorized=True,sample_size=1)
    c=p.create(db,administrator,request);db.commit()
    assert p.process_batch(db,c.id)=='READY'
    s=db.query(Sample).filter_by(campaign_id=c.id).one()
    with pytest.raises(ValueError):p.assign(db,c,administrator,AssignIn(sample_ids=[s.id],evaluator_user_ids=[data_owner]))
    g.state='REVOKED';db.commit()
    with pytest.raises(ValueError):p.owned(db,c.id,administrator)
    # Clean only this test's disposable source row so legacy shared fixtures stay isolated.
    db.query(Grant).filter_by(id=g.id).delete(synchronize_session=False)
    db.query(Result).filter_by(run_id=run.id).delete(synchronize_session=False)
    db.query(Run).filter_by(id=run.id).delete(synchronize_session=False)
    db.query(Opportunity).filter_by(id=o.id).delete(synchronize_session=False);db.commit()


def test_persisted_semantic_stop_and_zero_budget_prevent_network(client,db,gate,monkeypatch):
    from app.services import evaluation_semantic as semantic
    actor,h=users(client,db)[0]
    for name,value in [('evaluation_external_max_calls',3),('evaluation_semantic_enabled',True),('embedding_provider','openai'),('openai_api_key','fixture-key'),('evaluation_embedding_usd_per_million_tokens',.02)]:monkeypatch.setattr(gate,name,value)
    calls=[]
    monkeypatch.setattr(semantic,'request_embedding',lambda text:(calls.append(text) or [1.]+[0.]*1535,10))
    c=p.create(db,actor,body(2,max_external_calls=3,external_text_authorized=True,provider_terms_reference='fixture terms reviewed'));db.commit()
    assert p.process_batch(db,c.id)=='SEMANTICS'
    r=client.post(f'/api/internal/evaluation/campaigns/{c.id}/stop-semantics',headers=h)
    assert r.status_code==200,r.text
    while p.process_batch(db,c.id)=='SEMANTICS':pass
    assert not calls
    limited=ready(db,actor,1,max_external_calls=1,max_cost_usd=.00000000001,external_text_authorized=True,provider_terms_reference='fixture tariff reviewed')
    assert limited.external_calls==0 and not calls


def test_blind_redaction_and_conditional_rank_directions():
    from app.services.evaluation_reporting import rank_change
    text=p.blind_redact('Contacto caso@example.com teléfono: 3001234567 https://example.com NIT: 900123456-7')
    assert 'caso@example.com' not in text and '3001234567' not in text and '900123456' not in text
    assert rank_change(5,2,3,10)=='IMPROVES'
    assert rank_change(5,2,0,10)=='WORSENS'
    assert rank_change(1,None,3,10)=='WORSENS'
    assert rank_change(1,None,0,10)=='IMPROVES'


def test_completed_abstention_penalized_unexecuted_arm_not_imputed():
    from app.services.ranking_evaluation import evaluate
    rows=[{'query_id':'q','opportunity_id':i,'score':None,'computed':True,'algorithm_version':'fixture','profile_version':'p','opportunity_version':str(i)} for i in range(3)]
    labels=[{'query_id':'q','opportunity_id':i,'relevance':2,'label_source':'synthetic_test','blinded':True,'reason':'Synthetic statistical unit fixture','evaluator_id':'fixture','evaluated_at':'2026-11-15T00:00:00Z'} for i in range(3)]
    queries=[{'query_id':'q','universe_ids':[0,1,2],'universe_complete':True,'ranking_complete':True,'require_complete_execution':True}]
    r=evaluate(rows,labels,queries,allow_synthetic=True)
    assert r['macro']['precision_at_10']==0 and r['macro']['recall_at_20']==0 and r['macro']['ndcg_at_10']==0
    rows[0]['computed']=False
    assert evaluate(rows,labels,queries,allow_synthetic=True)['macro']['precision_at_10'] is None
    rows[0]['computed']=True
    assert evaluate(rows,[],queries,allow_synthetic=True)['macro']['precision_at_10'] is None


def test_ambient_database_and_broker_destinations_rejected():
    from app.services.evaluation_guard import database_identity,broker_identity
    for uri in ('postgresql:///dev','postgresql://user@/dev','postgresql://user@localhost','postgresql://localhost/dev'):
        with pytest.raises(EnvironmentDenied):database_identity(uri)
    for uri in ('redis:///0','redis://localhost','redis+socket://'):
        with pytest.raises(EnvironmentDenied):broker_identity(uri)


def test_redis_unix_socket_uses_url_path_not_sql_database(tmp_path):
    from app.services.evaluation_guard import broker_identity
    uri=f'redis+socket://{tmp_path}/redis.sock?virtual_host=0'
    identity=broker_identity(uri)
    assert identity[0]=='redis+socket' and identity[1]==str((tmp_path/'redis.sock').resolve())


def test_semantic_cache_separates_source_owners_under_same_admin(client,db,gate,monkeypatch):
    from app.services import evaluation_semantic as semantic
    people=users(client,db);actor=people[0][0]
    for name,value in [('evaluation_external_max_calls',3),('evaluation_semantic_enabled',True),('embedding_provider','openai'),('openai_api_key','fixture-key'),('evaluation_embedding_usd_per_million_tokens',.02)]:monkeypatch.setattr(gate,name,value)
    calls=[]
    monkeypatch.setattr(semantic,'request_embedding',lambda text:(calls.append(text) or [1.]+[0.]*1535,10))
    c=p.create(db,actor,body(1,max_external_calls=3,external_text_authorized=True,provider_terms_reference='fixture source scope consent'));db.commit()
    assert p.process_batch(db,c.id)=='SEMANTICS'
    c=db.get(Campaign,c.id);c.lease_token='scope-test';c.lease_until=p.now()+timedelta(seconds=120);db.commit()
    # Trusted adapter fixture with identical fictitious text, distinct data owners.
    first,_=semantic.vector(db,c.id,'scope-test','identical fictitious text',actor)
    cached,_=semantic.vector(db,c.id,'scope-test','identical fictitious text',actor)
    separate,_=semantic.vector(db,c.id,'scope-test','identical fictitious text',people[1][0])
    assert first and cached and separate and len(calls)==2


def test_api_startup_does_not_apply_evaluation_schema(tmp_path,monkeypatch):
    from sqlalchemy import create_engine,inspect
    from app.db import session as storage
    engine=create_engine(f'sqlite:///{tmp_path}/startup-only.db')
    monkeypatch.setattr(storage,'engine',engine)
    storage.init_db()
    names=inspect(engine).get_table_names()
    assert 'users' in names and 'opportunities' in names
    assert not any(name.startswith('evaluation_') for name in names)
    engine.dispose()


def test_multiple_accounts_are_not_independent_companies():
    assert p.statistical_organization(42,None)==p.statistical_organization(None,42)==p.statistical_organization(42,42)
    assert p.statistical_organization(42,42)!=p.statistical_organization(43,43)
    assert p.statistical_organization(None,None)==p.statistical_organization(42,43)==p.statistical_organization(12,13)


def test_bootstrap_requires_verified_company_identities_even_with_many_accounts():
    # Statistical fixtures only: these are not collected human judgments.
    from test_compatibility_evaluation import sample
    from app.services.compatibility_evaluation import compare
    a,b,labels,queries=sample(20,True)
    queries[0]['cluster_identity_verified']=False
    result=compare(a,b,labels,queries)
    assert result['paired_deltas']['precision_at_10']['ci95'] is None
    assert result['status']=='PENDING_VERIFIED_COMPANY_IDENTITIES'


def test_sampling_includes_actual_exclusive_retrieval_groups_when_available(client,db,gate):
    actor=users(client,db)[0][0];c=ready(db,actor,60)
    rows=[{**r,'query_id':'controlled-single-query','predictions':{**r['predictions'],'A':{**r['predictions']['A'],'score':float(i)},'B':{**r['predictions']['B'],'score':float(60-i)}}} for i,r in enumerate(c.universe)]
    sampled=select(rows,12,7)
    available=sampled['retrieval_groups_available'];chosen=sampled['retrieval_groups_selected']
    assert any(k.endswith('A_ONLY') for k in available) and any(k.endswith('B_ONLY') for k in available)
    assert set(chosen)==set(available) and all(n>=1 for n in chosen.values())
    assert len(sampled['selected'])==12 and all(0<r['inclusion_probability']<=1 for r in sampled['selected'])


def test_weak_installation_secret_denies_evaluation_before_write(client,db,gate,monkeypatch):
    monkeypatch.setattr(gate,'secret_key','weak-test-key')
    with pytest.raises(EnvironmentDenied):require_environment(db)
