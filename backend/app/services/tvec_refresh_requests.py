"""One shared manual request per reviewed DEV destination, not per company.

Redis NX reserves the request before publication. A failed/ambiguous publication
keeps the reservation: retries must not fan out source crawls.
"""
import json
import math
from urllib.parse import urlsplit,parse_qs,unquote
from uuid import uuid4

from redis import Redis
from app.db.models import TvecQuotationSnapshot as Snapshot
from app.services.tvec_client import now
from app.services.tvec_guard import require_target
from app.services.tvec_quotations import configured,SOURCE

COOLDOWN_SECONDS=300


class RefreshUnavailable(RuntimeError):
    pass


def connection(settings):
    if settings.redis_url.startswith('redis+socket:'):
        url=urlsplit(settings.redis_url)
        return Redis(unix_socket_path=unquote(url.path),db=int(parse_qs(url.query).get('virtual_host',['0'])[0]),
                     socket_timeout=1,socket_connect_timeout=1,decode_responses=True)
    return Redis.from_url(settings.redis_url,socket_timeout=1,socket_connect_timeout=1,decode_responses=True)


def destination(db):
    settings=configured(refresh=True)
    fingerprint=require_target(db)
    snapshot=db.get(Snapshot,SOURCE,populate_existing=True)
    progress=snapshot.scan_progress or {} if snapshot else {}
    active=bool(snapshot and (snapshot.status=='RUNNING' or
        (progress.get('id') and not progress.get('complete') and snapshot.status=='SCANNING')))
    seconds=max(0,math.ceil(COOLDOWN_SECONDS-(now()-snapshot.checked_at).total_seconds())) if snapshot and snapshot.checked_at else 0
    info={'state':'RUNNING' if active else 'ERROR' if snapshot and snapshot.status=='ERROR' else 'COOLDOWN' if seconds else 'IDLE',
          'pages':progress.get('next_page',0),'total_pages':progress.get('total_pages'),
          'last_updated':snapshot.checked_at.isoformat()+'Z' if snapshot and snapshot.checked_at else None,
          'retry_after':seconds,'cooldown_seconds':COOLDOWN_SECONDS,
          'scan_id':progress.get('id') if progress and not progress.get('complete') else None}
    # No DB transaction is held while contacting Redis or publishing a task.
    db.rollback()
    return settings,'tvec:manual-refresh:'+fingerprint,info


def public(info):
    return {k:v for k,v in info.items() if k!='scan_id'}


def reservation_state(client,key,info,settings):
    value=client.get(key)
    try:payload=json.loads(value or '{}')
    except (ValueError,TypeError):payload={}
    if payload.get('state')!='CONFIRMED':return 'UNCONFIRMED'
    if info['state']=='ERROR':
        from app.workers.celery_app import celery_app
        from app.services.evaluation_guard import broker_identity
        if celery_app is None or broker_identity(celery_app.conf.result_backend)!=broker_identity(settings.redis_url):
            raise RefreshUnavailable('Result destination differs')
        state=celery_app.AsyncResult(payload['task_id']).state
        return 'ERROR' if state in {'SUCCESS','FAILURE','REVOKED'} else 'PENDING'
    return 'PENDING'


def status(db):
    settings,key,info=destination(db)
    client=None
    try:
        client=connection(settings)
        ttl=max(0,client.ttl(key))
        if info['state']!='RUNNING' and ttl:
            info['state']='COOLDOWN' if info['retry_after'] else reservation_state(client,key,info,settings)
        info['retry_after']=max(info['retry_after'],ttl)
        return public(info)
    except Exception:
        raise RefreshUnavailable('Manual refresh status unavailable') from None
    finally:
        if client is not None:client.close()


def request(db):
    settings,key,info=destination(db)
    client=None
    try:
        if info['state']=='RUNNING':return {**public(info),'accepted':False}
        client=connection(settings)
        if info['retry_after'] and info['state']!='RUNNING':return {**public(info),'state':'COOLDOWN','accepted':False}
        task_id=str(uuid4())
        reservation=json.dumps({'task_id':task_id,'state':'RESERVED'})
        reserved=client.set(key,reservation,nx=True,ex=COOLDOWN_SECONDS)
        if not reserved:
            info['retry_after']=max(0,client.ttl(key))
            if info['state']!='RUNNING':info['state']=reservation_state(client,key,info,settings)
            return {**public(info),'accepted':False}
        from app.workers.celery_app import celery_app
        from app.services.evaluation_guard import broker_identity
        if celery_app is None or broker_identity(celery_app.conf.broker_url)!=broker_identity(settings.redis_url):
            raise RefreshUnavailable('Broker differs from reviewed target')
        celery_app.send_task('app.workers.tasks.refresh_tvec_quotations',args=[info['scan_id']],
            task_id=task_id,queue='tvec',retry=False,soft_time_limit=180,time_limit=210)
        client.eval("if redis.call('GET',KEYS[1]) == ARGV[1] then redis.call('SET',KEYS[1],ARGV[2],'KEEPTTL');return 1 else return 0 end",1,key,reservation,json.dumps({'task_id':task_id,'state':'CONFIRMED'}))
        return {**public(info),'state':'PENDING',
                'accepted':True,'retry_after':COOLDOWN_SECONDS}
    except Exception:
        # Keep NX reservation even when publication outcome cannot be confirmed.
        raise RefreshUnavailable('Unable to confirm manual refresh request') from None
    finally:
        if client is not None:client.close()
