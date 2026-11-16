"""Private DEV campaigns. No public ranking writes, no self labels, no score disclosure."""
from collections import defaultdict
from copy import deepcopy
from datetime import date,datetime,timedelta,timezone
from uuid import uuid4
from pathlib import Path
from functools import lru_cache
from sqlalchemy import or_,update
from app.core.config import get_settings
from app.db.models import (User,Opportunity,CompanyProfile,AuditLog,CompatibilityShadowRun,CompatibilityShadowResult,UserOpportunity,EvaluationCampaign as Campaign,EvaluationSample as Sample,EvaluationAssignment as Assignment,EvaluationJudgment as Judgment,EvaluationAdjudication as Adjudication,EvaluationReport as Report,EvaluationExposure as Exposure,EvaluationDataGrant as DataGrant,Document)
from app.services.evaluation_guard import require_environment
from app.services.evaluation_sampling import select
from app.services.compatibility_shadow import config as v2_config
from app.services.compatibility_v2 import evaluate as score_v2,feature_snapshot,PROFILE_FIELDS,OPPORTUNITY_FIELDS,model_version
from app.services.match_versions import digest,algorithm_version,embedding_version,profile_version
from app.services.opportunity_status import classify_opportunity
from app.services.matcher import score_opportunity,_profile_text
from app.services.embeddings import _fake_embed

RUBRIC={'version':'relevance-dev-2.1-1','positive_labels':[2,3],'positive_score_threshold':70,'sampling_retrieval_k':20,'scale':{'0':'Irrelevante','1':'Relación débil','2':'Compatible con reservas','3':'Altamente relevante'},'legal_warning':'Opinión independiente, no certificación jurídica','material_p10_margin':.02,'bootstrap_min_pairs':100,'bootstrap_min_companies':20}
CRITERIA_VERSION=digest(RUBRIC)


def now():return datetime.now(timezone.utc).replace(tzinfo=None)

def audit(db,actor,action,identifier,**detail):
    db.add(AuditLog(user_id=actor,action='evaluation_'+action,entity='evaluation',detail={'id':identifier,**detail}))

def live(c):
    if c.expires_at<=now():raise ValueError('Campaign retention expired; access revoked, no automatic historical deletion')

def owned(db,identifier,actor,lock=False):
    require_environment(db)
    q=db.query(Campaign).filter_by(id=identifier,owner_user_id=actor)
    c=(q.with_for_update() if lock else q).one_or_none()
    if not c:raise LookupError('Campaign not found')
    live(c);validate_consents(db,c);return c


def clean_input(data,fields):
    if set(data)-set(fields):raise ValueError('Unexpected snapshot field')
    if len(str(data))>30000:raise ValueError('Snapshot exceeds bounded text limit')
    for key,value in data.items():
        arrays={'keywords','departamentos','municipios','modalidades','unspsc_codes','certificaciones'}
        if key in arrays and value is not None and not isinstance(value,list):raise ValueError('String array required')
        if key not in arrays|{'valor','presupuesto_min','presupuesto_max','cancelled'} and value is not None and not isinstance(value,str):raise ValueError('Text field required')
        if key in {'valor','presupuesto_min','presupuesto_max'} and value is not None and type(value) not in (int,float):raise ValueError('Numeric field required')
        if key=='cancelled' and value is not None and type(value) is not bool:raise ValueError('Boolean cancellation required')
        if isinstance(value,(dict,list)):
            if not isinstance(value,list) or len(value)>100 or any(not isinstance(x,str) or len(x)>500 for x in value):raise ValueError('Only bounded string arrays allowed')
        elif value is not None and type(value) not in (str,int,float,bool):raise ValueError('Invalid snapshot value')
        elif isinstance(value,str) and len(value)>6000:raise ValueError('Text too large')
        elif isinstance(value,float):
            import math
            if not math.isfinite(value):raise ValueError('Nonfinite input')
    return feature_snapshot(data,fields)


def create(db,actor,body):
    require_environment(db);s=get_settings()
    if body.scope=='authorized_real' and len(s.secret_key)<32:raise ValueError('Real-data pseudonyms require a reviewed installation secret of at least 32 characters')
    if body.sample_size>s.evaluation_max_sample or body.max_external_calls>s.evaluation_external_max_calls or body.max_cost_usd>s.evaluation_max_cost_usd:raise ValueError('Campaign exceeds configured limits')
    universe=[];snapshot_at=now().isoformat()+'+00:00'
    for item in body.synthetic_pairs:
        p=clean_input(item.profile,PROFILE_FIELDS);o=clean_input(item.opportunity,(*OPPORTUNITY_FIELDS,'tipo_contrato'))
        cluster=digest([s.secret_key,'synthetic',actor,item.company_key])
        universe.append({'profile':p,'opportunity':o,'company_cluster_id':cluster,'process_key':'synthetic:'+item.process_key,'requirements':[],'evidence':{},'retrieval_origin':item.retrieval_origin,'official_url':None,'predictions':{},'baseline':'controlled-fake-64','validity':snapshot_validity(o),'document_available':False,'source_owner_id':actor})
    grants=db.query(DataGrant).filter(DataGrant.id.in_(body.grant_ids),DataGrant.administrator_user_id==actor,DataGrant.state=='ACTIVE',DataGrant.expires_at>now()).all()
    if len(grants)!=len(set(body.grant_ids)):raise ValueError('Missing authorized data grant')
    if body.run_ids or grants:
        runs=db.query(CompatibilityShadowRun).filter(CompatibilityShadowRun.id.in_(body.run_ids),CompatibilityShadowRun.user_id==actor).all()
        if len(runs)!=len(set(body.run_ids)) or any(r.state!='COMPLETED' for r in runs):raise ValueError('Only owned completed snapshots may be imported')
        for grant in grants:
            run=db.get(CompatibilityShadowRun,grant.run_id)
            if not run or run.state!='COMPLETED' or run.user_id!=grant.owner_user_id or digest(run.snapshot)!=grant.payload['snapshot_hash']:raise ValueError('Granted snapshot changed')
            if run.id not in {r.id for r in runs}:runs.append(run)
        account_organizations={identifier:organization for identifier,organization in db.query(User.id,User.company_id).filter(User.id.in_([r.user_id for r in runs]))}
        for run in runs:
            grant=next((g for g in grants if g.run_id==run.id),None)
            current_profile=db.query(CompanyProfile).filter_by(user_id=run.user_id).one_or_none()
            if not current_profile:raise ValueError('Current authorized profile required to verify legacy provenance')
            organization_identity=statistical_organization(current_profile.company_id,account_organizations.get(run.user_id))
            results={r.opportunity_id:r for r in db.query(CompatibilityShadowResult).filter_by(run_id=run.id)}
            ids=list({r['id'] for r in run.snapshot['candidates']}|set(body.additional_opportunity_ids))
            opps={o.id:o for o in db.query(Opportunity).filter(Opportunity.id.in_(ids))}
            private_scores={r.opportunity_id:r for r in db.query(UserOpportunity).filter(UserOpportunity.user_id==run.user_id,UserOpportunity.opportunity_id.in_(ids))}
            documents={r[0] for r in db.query(Document.opportunity_id).filter(Document.user_id==run.user_id,Document.opportunity_id.in_(ids)).distinct()}
            current_ids={r['id'] for r in run.snapshot['candidates']}
            candidates=[*run.snapshot['candidates'],*[{'id':i,'opportunity':feature_snapshot(opps[i],OPPORTUNITY_FIELDS),'requirements':[],'independent':True} for i in body.additional_opportunity_ids if i not in current_ids and i in opps]]
            if any(i not in opps for i in body.additional_opportunity_ids):raise ValueError('Independent opportunity missing')
            for item in candidates:
                o=opps.get(item['id']);score=results.get(item['id'])
                if not o or o.source!='secop2_procesos' or not o.source_id:raise ValueError('Verified process-level SECOP II identifier required; uid/contract IDs not accepted')
                if not item.get('independent') and (not score or score.legacy_versions.get('status')!='CURRENT' or o.match_version!=score.legacy_versions['opportunity']):raise ValueError('Legacy comparison requires a matching frozen current source')
                if item.get('independent'):
                    old=private_scores.get(o.id);profile_fingerprint=run.snapshot['candidates'][0]['legacy_versions']['profile'] if run.snapshot['candidates'] else None
                    valid=bool(old and old.match_state=='CURRENT' and old.profile_version==profile_fingerprint and old.opportunity_version==o.match_version and old.algorithm_version==algorithm_version() and old.embedding_version==embedding_version())
                    legacy_prediction={'score':old.score if valid else None,'algorithm_version':algorithm_version(),'source_status':'CURRENT' if valid else 'UNAVAILABLE'}
                else:legacy_prediction={'score':score.legacy_score,'algorithm_version':score.legacy_versions['algorithm'],'source_versions':score.legacy_versions}
                source_profile=item.get('legacy_versions',{}).get('profile') if item.get('independent') else (score.legacy_versions.get('profile') if score else None)
                if item.get('independent'):source_profile=profile_fingerprint
                if profile_version(current_profile)!=source_profile:raise ValueError('Legacy profile inputs changed; prepare a new authorized snapshot')
                p=deepcopy(run.snapshot['profile']);p['learning_weights']=deepcopy(current_profile.learning_weights or {});snapshot=deepcopy(item['opportunity']);snapshot['tipo_contrato']=o.tipo_contrato
                universe.append({'profile':p,'opportunity':snapshot,'company_cluster_id':digest([s.secret_key,*organization_identity]),'company_cluster_basis':organization_identity[0],'process_key':'secop2_procesos:'+o.source_id,'requirements':deepcopy(item.get('requirements',[])),'evidence':deepcopy(run.snapshot.get('evidence',{})),'retrieval_origin':'independent_search' if item.get('independent') else 'owned_shadow_frame','validity':classify_opportunity(o)['status'],'document_available':o.id in documents,'official_url':o.url_oficial,'predictions':{'A':legacy_prediction},'baseline':'frozen-current-legacy','source_owner_id':run.user_id,'external_text_authorized':grant.payload['external_text_authorized'] if grant else body.external_text_authorized,'documentary_excerpts_authorized':grant.payload.get('documentary_excerpts_authorized',False) if grant else body.documentary_excerpts_authorized})
    if not universe or len(universe)>s.evaluation_max_universe:raise ValueError('Empty or oversized universe')
    for row in universe:
        row['profile_version']=digest([row['profile'],row.get('evidence',{})]);row['opportunity_version']=digest(row['opportunity'])
        row['query_id']=digest([s.secret_key,'evaluation-query',row['source_owner_id'],row['company_cluster_id'],row['profile_version'],snapshot_at])
        row['pair_key']=digest([row['profile_version'],row['opportunity_version'],row['process_key']])
    if len({r['pair_key'] for r in universe})!=len(universe):raise ValueError('Duplicate pairs; import a single frozen window')
    c=Campaign(id=str(uuid4()),owner_user_id=actor,name=body.name,state='PREPARING',data_scope=body.scope,universe=universe,config={'seed':body.seed,'sample_size':body.sample_size,'holdout_fraction':body.holdout_fraction,'snapshot_at':snapshot_at,'as_of':date.today().isoformat(),'rubric':RUBRIC,'criteria_version':CRITERIA_VERSION,'model_version':model_version(v2_config()),'pipeline_version':pipeline_version(),'authorization_reference':body.authorization_reference,'blinded_sharing_authorized':True,'external_text_authorized':body.external_text_authorized,'provider_terms_reference':body.provider_terms_reference,'semantic_embedding_version':embedding_version(),'tariff_usd_per_million_tokens':s.evaluation_embedding_usd_per_million_tokens,'max_external_calls':body.max_external_calls,'max_cost_usd':body.max_cost_usd,'universe_hash':digest(universe),'grant_ids':[g.id for g in grants],'independent_search_reference':body.independent_search_reference},expires_at=now()+timedelta(days=s.evaluation_retention_days))
    db.add(c);audit(db,actor,'create',c.id,scope=body.scope,count=len(universe));db.flush();return c


def calculate_base(row,as_of):
    row=deepcopy(row);p,o=row['profile'],row['opportunity']
    if 'A' not in row['predictions']:
        vector=_fake_embed(_profile_text(p),64)
        legacy=score_opportunity(p,{**o,'_vector':_fake_embed(f"{o.get('objeto') or ''} {o.get('descripcion') or ''}",64)},profile_vector=vector)
        row['predictions']['A']={'score':legacy.score,'algorithm_version':algorithm_version(),'embedding':'controlled-fake-64; not real semantic evidence'}
    b=score_v2(p,o,evidence=row.get('evidence'),requirements=row.get('requirements'),as_of=as_of,config=v2_config())
    row['predictions']['B']={'score':b['compatibility_score'],'algorithm_version':b['model_version'],'evidence_coverage':b['evidence_coverage'],'eligibility_status':b['eligibility_status'],'result':b}
    row['predictions']['C']={'score':None,'algorithm_version':b['model_version']+':semantic-ablation','status':'NOT_REQUESTED'}
    return row


def process_batch(db,identifier):
    require_environment(db);token=str(uuid4());time=now()
    q=db.execute(update(Campaign).where(Campaign.id==identifier,Campaign.state.in_(['PREPARING','SEMANTICS']),Campaign.expires_at>time,or_(Campaign.lease_until.is_(None),Campaign.lease_until<time)).values(lease_token=token,lease_until=time+timedelta(seconds=120)))
    if not q.rowcount:db.rollback();return 'BUSY_OR_FINISHED'
    db.commit();c=db.get(Campaign,identifier);validate_consents(db,c);phase=c.state;cursor=c.cursor;rows=deepcopy(c.universe);cfg=deepcopy(c.config);db.rollback()
    if cfg['model_version']!=model_version(v2_config()) or cfg['pipeline_version']!=pipeline_version():
        updated=[];next_state='SUPERSEDED'
    else:
        batch=rows[cursor:cursor+(1 if phase=='SEMANTICS' else 5)];updated=[]
        for row in batch:
            if phase=='PREPARING':updated.append(calculate_base(row,date.fromisoformat(cfg['as_of'])))
            else:
                from app.services.evaluation_semantic import calculate_semantic
                updated.append(calculate_semantic(db,identifier,token,row,cfg))
        next_state=phase
    require_environment(db)
    c=db.query(Campaign).filter(Campaign.id==identifier,Campaign.lease_token==token,Campaign.cursor==cursor,Campaign.lease_until>now()).with_for_update().one_or_none()
    if not c:db.rollback();return 'LEASE_LOST'
    validate_consents(db,c)  # Recheck revocation after computation, before persisting results.
    if next_state!='SUPERSEDED':
        rows[cursor:cursor+len(updated)]=updated;c.universe=rows;c.cursor=cursor+len(updated)
        if c.cursor>=len(rows):
            if phase=='PREPARING' and cfg['max_external_calls']:
                next_state='SEMANTICS';c.cursor=0
            else:
                selection=select(rows,cfg['sample_size'],cfg['seed'],cfg['holdout_fraction']);c.selection=selection
                bykey={r['pair_key']:r for r in rows}
                for item in selection['selected']:
                    row=bykey[item['pair_key']]
                    db.add(Sample(id=str(uuid4()),campaign_id=identifier,pair_key=item['pair_key'],process_key=row['process_key'],snapshot=row,stratum=item['stratum'],inclusion_probability=item['inclusion_probability'],split=item['split']))
                next_state='READY';audit(db,c.owner_user_id,'freeze',c.id,frame_hash=digest(selection),model_version=cfg['model_version'])
    c.state=next_state;c.lease_token=None;c.lease_until=None;db.commit();return next_state


def enqueue(identifier):
    from app.services.evaluation_guard import configured_target
    configured_target()
    if get_settings().environment=='testing':return None
    from app.workers.celery_app import celery_app
    if celery_app is None:raise ValueError('Explicit evaluation worker required')
    from app.services.evaluation_guard import broker_identity,EnvironmentDenied
    if broker_identity(celery_app.conf.broker_url)!=broker_identity(get_settings().redis_url):raise EnvironmentDenied('Actual publisher broker differs')
    return celery_app.send_task('app.workers.tasks.process_evaluation_campaign',args=[identifier],queue='evaluation').id


def judgments(db,sample):
    ids=[a.id for a in db.query(Assignment).filter_by(sample_id=sample.id,kind='REVIEW')]
    return db.query(Judgment).filter(Judgment.assignment_id.in_(ids)).order_by(Judgment.id).all()


def signature(payload):return digest([payload['relevance'],payload['eligibility'],payload['evidence_quality'],sorted(payload['pending_requirements'])])


def assign(db,c,actor,body):
    require_environment(db);live(c)
    if c.state!='READY':raise ValueError('Frozen ready campaign required')
    if len(set(body.evaluator_user_ids))!=len(body.evaluator_user_ids):raise ValueError('Duplicate reviewer')
    people=db.query(User).filter(User.id.in_(body.evaluator_user_ids),User.is_active.is_(True),User.role=='evaluation_reviewer').all()
    if len(people)!=len(body.evaluator_user_ids) or actor in body.evaluator_user_ids:raise ValueError('Only explicitly authorized independent reviewers')
    samples=db.query(Sample).filter(Sample.id.in_(body.sample_ids),Sample.campaign_id==c.id).all()
    if len(samples)!=len(set(body.sample_ids)):raise LookupError('Sample not found')
    for sample in samples:
        if sample.snapshot.get('source_owner_id') in body.evaluator_user_ids:raise ValueError('Data owner cannot review own results')
        existing=db.query(Assignment).filter_by(sample_id=sample.id).all()
        if any(e.evaluator_user_id in body.evaluator_user_ids for e in existing):raise ValueError('Already assigned; no reassessment after exposure')
        if db.query(Exposure.id).filter(Exposure.user_id.in_(body.evaluator_user_ids),Exposure.pair_key==sample.pair_key).first():raise ValueError('Reviewer previously exposed to scores')
        if body.kind=='REVIEW' and sum(e.kind=='REVIEW' for e in existing)+len(people)>2:raise ValueError('Exactly two primary independent slots')
        if body.kind=='ADJUDICATION':
            js=judgments(db,sample)
            if len(people)!=1 or len(js)!=2 or signature(js[0].payload)==signature(js[1].payload) or any(e.kind=='ADJUDICATION' for e in existing):raise ValueError('Disagreement and independent third reviewer required')
        for person in people:db.add(Assignment(id=str(uuid4()),sample_id=sample.id,evaluator_user_id=person.id,kind=body.kind))
    audit(db,actor,'assign',c.id,samples=len(samples),reviewers=body.evaluator_user_ids,kind=body.kind);db.flush()


def assignment_context(db,identifier,actor):
    require_environment(db)
    a=db.query(Assignment).filter_by(id=identifier,evaluator_user_id=actor).one_or_none()
    if not a:raise LookupError('Assignment not found')
    s=db.get(Sample,a.sample_id);c=db.get(Campaign,s.campaign_id);live(c)
    validate_consents(db,c)
    if c.state!='READY':raise ValueError('Campaign unavailable or closed')
    return a,s,c


def blind_view(db,identifier,actor):
    a,s,c=assignment_context(db,identifier,actor);r=s.snapshot;p=r['profile'];o=r['opportunity']
    # Explicit allowlist, no generic serializer of snapshot, criteria or predictions.
    return {'assignment_id':a.id,'kind':a.kind,'campaign_alias':digest(c.id)[:12],'profile_alias':digest(['blind-profile',r['query_id']])[:12],'profile':{k:blind_redact(p.get(k)) for k in PROFILE_FIELDS},'opportunity':{k:o.get(k) for k in ('objeto','descripcion','modalidad','tipo_contrato','unspsc_code','valor','departamento','estado','fecha_cierre')},'documentary_evidence':[{'quote':blind_redact(str(q.get('source_ref',{}).get('quote') or '')[:1000]),'reference':q.get('source_ref',{}).get('reference'),'verification':'EXTRACTED_NOT_VERIFIED'} for q in r.get('requirements',[])[:10] if q.get('source_ref',{}).get('quote')] if r.get('documentary_excerpts_authorized') else [],'requirements':[{'description':q.get('key'),'excluding':bool(q.get('excluding')),'verification':'PENDING'} for q in r.get('requirements',[])],'official_url':official_reference(r.get('official_url')),'rubric':RUBRIC,'submitted':bool(db.query(Judgment.id).filter_by(assignment_id=a.id).first()),'warning':'Sólo contexto autorizado. Declaraciones y requisitos pendientes no certifican cumplimiento.'}


def submit(db,identifier,actor,payload):
    a,s,c=assignment_context(db,identifier,actor)
    # Serialize closure with submission, while unique keys serialize duplicates.
    c=db.query(Campaign).filter_by(id=c.id,state='READY').with_for_update().one_or_none()
    if not c:raise ValueError('Campaign closed')
    if db.query(Judgment.id).filter_by(assignment_id=a.id).first():raise ValueError('Judgment sealed; corrections require a new audited campaign')
    row=Judgment(id=str(uuid4()),assignment_id=a.id,payload=payload,criteria_version=c.config['criteria_version']);db.add(row)
    if a.kind=='ADJUDICATION':db.add(Adjudication(id=str(uuid4()),sample_id=s.id,assignment_id=a.id,payload=payload))
    audit(db,actor,'judge',c.id,assignment=a.id,kind=a.kind);db.flush();return row


def summary(db,c):
    samples=db.query(Sample).filter_by(campaign_id=c.id).all();ids=[s.id for s in samples]
    assignments=db.query(Assignment).filter(Assignment.sample_id.in_(ids)).all();byid={a.id:a for a in assignments}
    all_judgments=db.query(Judgment).filter(Judgment.assignment_id.in_(list(byid))).all()
    primary=defaultdict(list)
    for j in all_judgments:
        if byid[j.assignment_id].kind=='REVIEW':primary[byid[j.assignment_id].sample_id].append(j)
    resolved={a.sample_id for a in db.query(Adjudication).filter(Adjudication.sample_id.in_(ids))}
    from app.db.models import EvaluationEmbedding
    usage=db.query(EvaluationEmbedding).filter_by(campaign_id=c.id).all()
    consumption={'known_tokens':sum(r.usage_tokens or 0 for r in usage),'known_estimated_cost_usd':sum(r.estimated_cost or 0 for r in usage),'unknown_usage_reservations':sum(r.usage_tokens is None for r in usage)}
    return {'semantic_consumption':consumption,'id':c.id,'name':c.name,'state':c.state,'data_scope':c.data_scope,'cursor':c.cursor,'universe_total':len(c.universe),'sample_total':len(samples),'judgments':len(all_judgments),'external_calls':c.external_calls,'reserved_cost_usd':c.reserved_cost,'expires_at':c.expires_at.isoformat(),'samples':[{'id':s.id,'split':s.split,'inclusion_probability':s.inclusion_probability,'disagreement':len(js:=primary[s.id])==2 and signature(js[0].payload)!=signature(js[1].payload),'adjudicated':s.id in resolved} for s in samples]}


def validate_consents(db,c):
    ids=c.config.get('grant_ids',[])
    if ids and db.query(DataGrant).filter(DataGrant.id.in_(ids),DataGrant.state=='ACTIVE',DataGrant.expires_at>now()).count()!=len(ids):raise ValueError('Data authorization expired or revoked')


def create_grant(db,actor,body):
    require_environment(db)
    run=db.query(CompatibilityShadowRun).filter_by(id=body.run_id,user_id=actor,state='COMPLETED').one_or_none()
    administrator=db.query(User).filter_by(id=body.administrator_user_id,role='admin',is_active=True).one_or_none()
    if not run or not administrator:raise ValueError('Owned snapshot and authorized administrator required')
    payload=body.model_dump();payload['snapshot_hash']=digest(run.snapshot)
    row=DataGrant(id=str(uuid4()),owner_user_id=actor,administrator_user_id=administrator.id,run_id=run.id,state='ACTIVE',payload=payload,expires_at=now()+timedelta(days=body.expires_days))
    db.add(row);audit(db,actor,'grant',row.id,administrator=administrator.id);db.flush();return row


def official_reference(value):
    from urllib.parse import urlsplit
    if not value:return None
    u=urlsplit(value)
    return value if u.scheme=='https' and u.hostname in {'community.secop.gov.co','www.contratos.gov.co','www.datos.gov.co','datos.gov.co'} and not u.username and not u.password else None


def snapshot_validity(opportunity):
    from types import SimpleNamespace
    values={**opportunity}
    for key in ('fecha_publicacion','fecha_cierre'):
        raw=values.get(key)
        values[key]=datetime.fromisoformat(raw.replace('Z','+00:00')) if raw else None
    values['estado']=values.get('estado') or '';values['cancelled']=bool(values.get('cancelled'));values['source']=values.get('source') or 'synthetic'
    return classify_opportunity(SimpleNamespace(**values))['status']


@lru_cache(maxsize=1)
def pipeline_version():
    files=('evaluation_platform.py','evaluation_sampling.py','evaluation_semantic.py','evaluation_reporting.py','compatibility_evaluation.py','ranking_evaluation.py')
    return digest([Path(__file__).with_name(name).read_text() for name in files])


def blind_redact(value):
    """Common direct identifiers only; real text still needs owner review/consent."""
    import re
    if isinstance(value,list):return [blind_redact(v) for v in value]
    if not isinstance(value,str):return value
    value=re.sub(r'[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}','[CORREO OMITIDO]',value)
    value=re.sub(r'https?://[^\s]+','[URL OMITIDA]',value)
    value=re.sub(r'(?i)\b(?:nit|cédula|cedula|teléfono|telefono|celular)\s*[:#]?\s*[+\d][\d .()-]{5,}','[IDENTIFICADOR OMITIDO]',value)
    return value


def statistical_organization(profile_organization,account_organization):
    """Never equate accounts with independent companies; collapse unknown identities."""
    identities={v for v in (profile_organization,account_organization) if v is not None}
    if len(identities)==1:return ('existing-organization',next(iter(identities)))
    return ('unverified-organization-collapsed',)
