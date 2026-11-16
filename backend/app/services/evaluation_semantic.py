"""Opt-in external adapter; only consented profile text + public object, never documents."""
from copy import deepcopy
from datetime import date,timedelta
from uuid import uuid4
from sqlalchemy.exc import IntegrityError
from app.core.config import get_settings
from app.db.models import EvaluationEmbedding as Cache,EvaluationCampaign as Campaign
from app.services.evaluation_guard import require_environment
from app.services.match_versions import embedding_spec,embedding_version,digest
from app.services.compatibility_v2 import profile_text,contract_text,evaluate
from app.services.compatibility_shadow import config
from app.services.evaluation_platform import now,audit

MODEL='text-embedding-3-small'


def provider_available():
    s=get_settings()
    return s.evaluation_semantic_enabled and embedding_spec()==('openai-text-embedding-3-small',1536) and s.evaluation_embedding_usd_per_million_tokens is not None


def request_embedding(text):
    from openai import OpenAI
    # Pin official endpoint. No implicit OPENAI_BASE_URL or hidden SDK retries.
    client=OpenAI(api_key=get_settings().openai_api_key,base_url='https://api.openai.com/v1',timeout=10.,max_retries=0)
    response=client.embeddings.create(input=[text],model=MODEL,dimensions=1536,encoding_format='float')
    if response.model!=MODEL:raise ValueError('Provider returned different model')
    return response.data[0].embedding,response.usage.prompt_tokens


def vector(db,identifier,token,text,source_owner_id):
    require_environment(db)
    if not provider_available():db.rollback();return None,'PROVIDER_DISABLED_OR_UNCONFIGURED'
    if not text.strip() or len(text.encode())>6000:db.rollback();return None,'TEXT_LIMIT'
    version=digest(['evaluation-semantic-adapter-1',embedding_version(),MODEL,1536]);text_hash=digest(text);key=digest([version,text_hash,source_owner_id])
    campaign=db.query(Campaign).filter(Campaign.id==identifier,Campaign.lease_token==token,Campaign.lease_until>now(),Campaign.expires_at>now()).with_for_update().one_or_none()
    if not campaign:db.rollback();return None,'LEASE_LOST'
    from app.services.evaluation_platform import validate_consents
    validate_consents(db,campaign)
    if campaign.semantic_disabled_at is not None:db.rollback();return None,'CAMPAIGN_PROVIDER_STOPPED'
    cfg=campaign.config
    if cfg.get('semantic_embedding_version')!=embedding_version() or cfg.get('tariff_usd_per_million_tokens')!=get_settings().evaluation_embedding_usd_per_million_tokens:
        db.rollback();return None,'PROVIDER_VERSION_OR_TARIFF_CHANGED'
    if not cfg.get('external_text_authorized') or not cfg.get('provider_terms_reference'):db.rollback();return None,'CONSENT_MISSING'
    cache=db.query(Cache).filter_by(owner_user_id=campaign.owner_user_id,cache_key=key).one_or_none()
    if cache:
        if cache.state=='READY' and cache.expires_at>now():
            payload={'provider':'openai','model':cache.model,'dimensions':cache.dimensions,'version':cache.version,'text_hash':cache.text_hash,'vector':cache.vector}
            db.rollback();return payload,'CACHE_HIT'
        # Ambiguous/crashed reservations are never automatically charged twice.
        db.rollback();return None,'CACHE_RESERVED_FAILED_OR_EXPIRED'
    s=get_settings();rate=s.evaluation_embedding_usd_per_million_tokens
    maximum_cost=len(text.encode())*rate/1_000_000
    if campaign.external_calls>=min(cfg['max_external_calls'],s.evaluation_external_max_calls) or campaign.reserved_cost+maximum_cost>min(cfg['max_cost_usd'],s.evaluation_max_cost_usd):db.rollback();return None,'BUDGET_LIMIT'
    row=Cache(id=str(uuid4()),owner_user_id=campaign.owner_user_id,campaign_id=identifier,cache_key=key,text_hash=text_hash,model=MODEL,dimensions=1536,version=version,state='RESERVED',expires_at=campaign.expires_at)
    campaign.external_calls+=1;campaign.reserved_cost+=maximum_cost
    audit(db,campaign.owner_user_id,'external_reserve',identifier,text_hash=text_hash,maximum_cost_usd=maximum_cost,model=MODEL,rate_usd_per_million_tokens=rate)
    db.add(row);rid=row.id
    try:db.commit()
    except IntegrityError:db.rollback();return None,'CACHE_CONCURRENT_RESERVATION'
    # Transaction fully released during external request. No document/quote included.
    if not provider_available():return None,'PROVIDER_DISABLED_AFTER_RESERVATION'
    try:
        values,usage=request_embedding(text)
        import math
        if type(usage) is not int or usage<0 or not isinstance(values,list) or len(values)!=1536 or not all(type(v) in (int,float) and math.isfinite(v) for v in values) or not 0<math.hypot(*values)<float('inf'):raise ValueError('Invalid embedding response')
        state='READY';cost=usage*rate/1_000_000
    except Exception:
        state='FAILED';values=None;usage=None;cost=None
    require_environment(db)
    stored=db.query(Cache).filter_by(id=rid,state='RESERVED').with_for_update().one()
    stored.state=state;stored.vector=values;stored.usage_tokens=usage;stored.estimated_cost=cost;db.commit()
    stopped=db.query(Campaign.semantic_disabled_at).filter_by(id=identifier).scalar() is not None
    db.rollback()
    if state!='READY' or not provider_available() or stopped:return None,'PROVIDER_FAILED_OR_DISABLED'
    return {'provider':'openai','model':MODEL,'dimensions':1536,'version':version,'text_hash':text_hash,'vector':values},'GENERATED_REAL'


def calculate_semantic(db,identifier,token,row,cfg):
    result=deepcopy(row)
    if row.get('external_text_authorized') is False:
        result['predictions']['C']['status']='SOURCE_CONSENT_DENIES_EXTERNAL';return result
    a,sa=vector(db,identifier,token,profile_text(row['profile']),row['source_owner_id'])
    b,sb=vector(db,identifier,token,contract_text(row['opportunity']),row['source_owner_id']) if a else (None,'NOT_CALLED')
    if a and b:
        output=evaluate(row['profile'],row['opportunity'],evidence=row.get('evidence'),requirements=row.get('requirements'),semantic_pair=[a,b],as_of=date.fromisoformat(cfg['as_of']),config=config())
        result['predictions']['C']={'score':output['compatibility_score'],'algorithm_version':output['model_version']+':real-semantic-ablation','evidence_coverage':output['evidence_coverage'],'eligibility_status':output['eligibility_status'],'result':output,'status':'REAL_PROVIDER','vector_versions':[a['version'],b['version']]}
    else:result['predictions']['C']['status']=';'.join([sa,sb])
    return result
