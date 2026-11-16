"""Bounded private snapshots and independent leased batches; never modifies legacy rows."""
from datetime import datetime, timedelta, date, timezone
from time import perf_counter
import uuid
from sqlalchemy import or_, update, func
from app.core.config import get_settings
from app.db.models import CompanyProfile, Opportunity, UserOpportunity, Analysis, CompatibilityEvidenceProfile as Evidence, CompatibilityShadowRun as Run, CompatibilityShadowResult as Result
from app.services import compatibility_v2 as v2
from app.services.evaluation_guard import require_environment,configured_target,broker_identity,EnvironmentDenied
from app.services.match_versions import algorithm_version, embedding_version, digest
from app.services.opportunity_status import potentially_current_condition


def enabled():
    s = get_settings()
    return s.compatibility_v2_shadow_enabled and s.environment in {'development','testing','isolated-integration'}


def config():
    s=get_settings()
    return v2.ModelConfig(weights=dict(s.compatibility_v2_weights),affinity_weights=s.compatibility_v2_affinity_weights,hierarchy=s.compatibility_v2_hierarchy_weights,min_coverage=s.compatibility_v2_min_coverage,lexical_gate=s.compatibility_v2_lexical_gate,semantic_gate=s.compatibility_v2_semantic_gate)


def create_run(db, user_id, limit):
    if not enabled():
        raise ValueError('Shadow disabled')
    require_environment(db,allow_shadow=True)
    s = get_settings()
    if not 1 <= limit <= s.compatibility_v2_sample_limit:
        raise ValueError('Sample limit exceeded')
    profile = db.query(CompanyProfile).filter_by(user_id=user_id).with_for_update().one_or_none()
    if not profile:
        raise ValueError('Company profile required')
    if db.query(Run.id).filter(Run.user_id==user_id,Run.state.in_(['PENDING','RUNNING'])).first():
        raise ValueError('Active private run already exists; resume it')
    p = v2.feature_snapshot(profile,v2.PROFILE_FIELDS)
    evidence = db.query(Evidence).filter_by(user_id=user_id).order_by(Evidence.id.desc()).first()
    # One bounded candidate query, one private-score query, one private-analysis query.
    opportunities = db.query(Opportunity).filter(potentially_current_condition()).order_by(Opportunity.id).limit(limit).all()
    ids = [o.id for o in opportunities]
    old = {r.opportunity_id:r for r in db.query(UserOpportunity).filter(UserOpportunity.user_id==user_id,UserOpportunity.opportunity_id.in_(ids)).all()}
    latest = db.query(func.max(Analysis.id)).filter(Analysis.user_id==user_id,Analysis.opportunity_id.in_(ids)).group_by(Analysis.opportunity_id)
    analyses = db.query(Analysis).filter(Analysis.id.in_(latest)).all()
    requirements = {}
    for a in analyses:
        if a.opportunity_id in requirements:
            continue
        # Extractor output is merely identified, never trusted reviewed evidence.
        requirements[a.opportunity_id] = [{'id':f'analysis:{a.id}:{i}','criterion':{'experiencia':'experience','financiero':'financial','tecnico':'technical','técnico':'technical'}.get(str(r.get('tipo','')).lower(),'eligibility'),'key':r.get('descripcion'), 'source_ref':{'analysis_id':a.id,'document':r.get('documento'),'reference':r.get('referencia'),'quote':r.get('evidencia')},'excluding':bool(r.get('es_excluyente')),'level':'DOCUMENTED'} for i,r in enumerate(a.requisitos or []) if isinstance(r,dict)]
    candidates=[]
    for o in opportunities:
        previous = old.get(o.id)
        compatible = bool(previous and previous.match_state=='CURRENT' and previous.profile_version==profile.match_version and previous.opportunity_version==o.match_version and previous.algorithm_version==algorithm_version() and previous.embedding_version==embedding_version())
        candidates.append({'id':o.id,'opportunity':v2.feature_snapshot(o,v2.OPPORTUNITY_FIELDS),'requirements':requirements.get(o.id,[]),'legacy_score':previous.score if compatible else None,'legacy_versions':{'status':'CURRENT' if compatible else 'UNAVAILABLE_OR_STALE','profile':profile.match_version,'opportunity':o.match_version,'algorithm':algorithm_version(),'embedding':embedding_version()}})
    run=Run(id=str(uuid.uuid4()),user_id=user_id,state='PENDING',model_version=v2.model_version(config()),snapshot={'profile':p,'evidence':evidence.payload if evidence else {},'candidates':candidates,'as_of':date.today().isoformat(),'sample_strategy':'first-current-ID deterministic bounded diagnostic, not representative evaluation'})
    db.add(run)
    db.flush()
    return run


def process_batch(db, run_id):
    if not enabled():
        return 'DISABLED'
    require_environment(db,allow_shadow=True)
    now=datetime.now(timezone.utc).replace(tzinfo=None); token=str(uuid.uuid4()); settings=get_settings()
    acquired=db.execute(update(Run).where(Run.id==run_id,Run.state.in_(['PENDING','RUNNING']),or_(Run.lease_until.is_(None),Run.lease_until<now)).values(state='RUNNING',lease_token=token,lease_until=now+timedelta(seconds=settings.compatibility_v2_lease_seconds)))
    if not acquired.rowcount:
        db.rollback()
        return 'BUSY_OR_FINISHED'
    db.commit()
    run=db.get(Run,run_id)
    cursor=run.cursor; snapshot=run.snapshot; owner=run.user_id; version=run.model_version
    batch=snapshot['candidates'][cursor:cursor+settings.compatibility_v2_batch_size]
    db.rollback()  # No database locks while deterministic calculations run.
    calculated=[]
    cfg=config()
    if version!=v2.model_version(cfg):
        state='SUPERSEDED'
    else:
        state='RUNNING'
        for item in batch:
            start=perf_counter();timings={}
            result=v2.evaluate(snapshot['profile'],item['opportunity'],evidence=snapshot['evidence'],requirements=item['requirements'],config=cfg,as_of=date.fromisoformat(snapshot['as_of']),timings=timings)
            result['timings_ms']=timings
            calculated.append((item,result,(perf_counter()-start)*1000))
    # Fencing prevents a late worker from committing after lease expiration/takeover.
    require_environment(db,allow_shadow=True)
    locked=db.query(Run).filter(Run.id==run_id,Run.user_id==owner,Run.lease_token==token,Run.cursor==cursor,Run.lease_until>datetime.now(timezone.utc).replace(tzinfo=None)).with_for_update().one_or_none()
    if locked is None:
        db.rollback(); return 'LEASE_LOST'
    if not enabled():
        state='DISABLED'
    if state=='RUNNING':
        for item,result,duration in calculated:
            db.add(Result(run_id=run_id,opportunity_id=item['id'],legacy_score=item['legacy_score'],legacy_versions=item['legacy_versions'],result=result,duration_ms=duration))
        locked.cursor=cursor+len(batch)
        if locked.cursor>=len(snapshot['candidates']):state='COMPLETED'
    locked.state=state; locked.lease_token=None; locked.lease_until=None
    if state!='RUNNING':locked.finished_at=datetime.now(timezone.utc).replace(tzinfo=None)
    db.commit()
    return state


def enqueue(run_id):
    if enabled():configured_target(require_evaluation_enabled=False)
    if enabled() and get_settings().environment!='testing':
        from app.workers.celery_app import celery_app
        if celery_app is None:raise RuntimeError('Shadow requires an isolated asynchronous worker')
        if broker_identity(celery_app.conf.broker_url)!=broker_identity(get_settings().redis_url):raise EnvironmentDenied('Shadow publisher broker differs')
        return celery_app.send_task('app.workers.tasks.process_compatibility_shadow',args=[run_id],queue='compatibility-shadow').id
    return None


def diagnostic(db,run):
    rows=db.query(Result).filter_by(run_id=run.id).order_by(Result.opportunity_id).all()
    return {'id':run.id,'state':run.state,'processed':run.cursor,'total':len(run.snapshot['candidates']),'model_version':run.model_version,'snapshot_as_of':run.snapshot['as_of'],'results':[{'opportunity_id':r.opportunity_id,'legacy_score':r.legacy_score,'legacy_versions':r.legacy_versions,'v2':r.result,'difference':r.result['compatibility_score']-r.legacy_score if r.result['compatibility_score'] is not None and r.legacy_score is not None else None,'duration_ms':r.duration_ms} for r in rows]}


def evaluation_export(db, run):
    """Private frozen paired inputs; no labels, no representative-sample claims."""
    if run.state!='COMPLETED':raise ValueError('Complete the bounded snapshot before exporting')
    rows={r.opportunity_id:r for r in db.query(Result).filter_by(run_id=run.id)}
    snapshot_at=run.created_at.replace(tzinfo=timezone.utc).isoformat()
    profile_hash=digest(run.snapshot['profile'])
    query={'query_id':run.id,'company_cluster_id':digest(['private-evaluation',get_settings().secret_key,run.user_id]),'sector':run.snapshot['profile'].get('sector') or 'unspecified','snapshot_at':snapshot_at,'universe_ids':[c['id'] for c in run.snapshot['candidates']],'universe_complete':False,'ranking_complete':False,'positive_score_threshold':70,'sampling_warning':run.snapshot['sample_strategy']}
    legacy=[];v2_rows=[]
    for candidate in run.snapshot['candidates']:
        row=rows[candidate['id']]
        common={'query_id':run.id,'opportunity_id':candidate['id'],'profile_version':profile_hash,'opportunity_version':digest(candidate['opportunity']),'snapshot_at':snapshot_at}
        legacy.append({**common,'score':row.legacy_score,'algorithm_version':row.legacy_versions['algorithm']})
        v2_rows.append({**common,'score':row.result['compatibility_score'],'algorithm_version':row.result['model_version'],'evidence_coverage':row.result['evidence_coverage'],'eligibility_status':row.result['eligibility_status']})
    return {'queries':[query],'legacy':legacy,'v2':v2_rows,'judgments':[],'status':'PENDING_HUMAN_LABELS','warning':'Exportación privada sin etiquetas; no enviar documentos ni identificadores a evaluadores sin autorización. La muestra diagnóstica no es representativa.'}
