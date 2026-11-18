"""Authenticated shared refresh requests. Redis and task publication mocked here."""
import json
from types import SimpleNamespace
import pytest
from test_tvec import tvec
from test_tvec_quotations import quotations
from app.services import tvec_refresh_requests as requests
from app.db.models import TvecQuotationSnapshot as Snapshot
from app.services.tvec_quotations import SOURCE
from app.services.tvec_client import now
from app.core.config import get_settings

class MemoryRedis:
    def __init__(self):self.value=None
    def set(self,key,value,**options):
        if self.value is not None:return False
        self.value=value;return True
    def get(self,key):return self.value
    def ttl(self,key):return 300 if self.value else -2
    def eval(self,script,count,key,before,after):
        if self.value==before:self.value=after;return 1
        return 0
    def close(self):pass

@pytest.fixture
def manual(quotations,monkeypatch):
    redis=MemoryRedis();sent=[]
    queue=SimpleNamespace(conf=SimpleNamespace(broker_url=get_settings().redis_url,result_backend=get_settings().redis_url),send_task=lambda *a,**k:sent.append((a,k)))
    monkeypatch.setattr(requests,'connection',lambda s:redis)
    monkeypatch.setattr('app.workers.celery_app.celery_app',queue)
    return quotations,redis,sent,queue


def test_two_users_share_one_pending_request_and_unauthenticated_denied(manual,client,auth_headers):
    db,redis,sent,queue=manual
    assert client.post('/api/tvec/quotations/refresh').status_code==401
    first=client.post('/api/tvec/quotations/refresh',headers=auth_headers)
    assert first.status_code==202 and first.json()['accepted'] and first.json()['state']=='PENDING'
    user=client.post('/api/auth/register',json={'email':'manual-second@example.com','password':'SafePassword123','full_name':'Synthetic second user'})
    assert user.status_code==201
    headers={'Authorization':'Bearer '+user.json()['access_token']}
    second=client.post('/api/tvec/quotations/refresh',headers=headers)
    assert second.status_code==202 and second.json()['accepted'] is False
    assert len(sent)==1 and sent[0][1]['args']==[None] and sent[0][1]['queue']=='tvec'
    assert client.get('/api/tvec/quotations/refresh-status',headers=headers).json()['state']=='PENDING'
    assert 'scan_id' not in first.json()


def test_active_scan_is_reused_without_enqueue_and_recent_result_cools_down(manual,client,auth_headers):
    db,redis,sent,queue=manual
    db.add(Snapshot(source=SOURCE,status='SCANNING',scan_progress={'id':'existing-generation','next_page':14,'total_pages':47,'complete':False}));db.commit()
    response=client.post('/api/tvec/quotations/refresh',headers=auth_headers).json()
    assert response['state']=='RUNNING' and response['accepted'] is False and response['pages']==14
    assert not sent and redis.value is None
    row=db.get(Snapshot,SOURCE);row.status='IDLE';row.scan_progress={'id':'existing-generation','complete':True};row.checked_at=now();db.commit()
    cooled=client.post('/api/tvec/quotations/refresh',headers=auth_headers).json()
    assert cooled['state']=='COOLDOWN' and 0<cooled['retry_after']<=300 and not cooled['accepted']
    assert not sent


def test_error_retry_resumes_same_generation_and_unconfirmed_send_is_not_repeated(manual,client,auth_headers):
    db,redis,sent,queue=manual
    db.add(Snapshot(source=SOURCE,status='ERROR',scan_progress={'id':'resume-generation','next_page':4,'complete':False}));db.commit()
    def fail(*a,**k):sent.append((a,k));raise ConnectionError('synthetic broker failure')
    queue.send_task=fail
    assert client.post('/api/tvec/quotations/refresh',headers=auth_headers).status_code==503
    assert sent[0][1]['args']==['resume-generation']
    assert json.loads(redis.value)['state']=='RESERVED'
    assert client.post('/api/tvec/quotations/refresh',headers=auth_headers).json()['accepted'] is False
    assert len(sent)==1
    # Without a failed DB generation, the uncertain queue reservation is explicit.
    row=db.get(Snapshot,SOURCE);row.status='IDLE';row.scan_progress=None;db.commit()
    assert client.get('/api/tvec/quotations/refresh-status',headers=auth_headers).json()['state']=='UNCONFIRMED'


def test_disabled_and_redis_failure_fail_closed_without_affecting_reads(manual,client,auth_headers,monkeypatch):
    db,redis,sent,queue=manual
    def unavailable(s):raise ConnectionError('synthetic Redis failure')
    monkeypatch.setattr(requests,'connection',unavailable)
    assert client.post('/api/tvec/quotations/refresh',headers=auth_headers).status_code==503
    assert client.get('/api/tvec/quotations/refresh-status',headers=auth_headers).status_code==503
    assert client.get('/api/tvec/quotations',headers=auth_headers).status_code==200
    monkeypatch.setattr(get_settings(),'tvec_events_refresh_enabled',False)
    assert client.post('/api/tvec/quotations/refresh',headers=auth_headers).status_code==404
    assert not sent


def test_retry_after_old_failure_reports_pending_until_new_task_result(manual,client,auth_headers):
    db,redis,sent,queue=manual
    db.add(Snapshot(source=SOURCE,status='ERROR',scan_progress={'id':'retry-generation','next_page':2,'complete':False}));db.commit()
    queue.AsyncResult=lambda identifier:SimpleNamespace(state='PENDING')
    response=client.post('/api/tvec/quotations/refresh',headers=auth_headers).json()
    assert response['accepted'] and response['state']=='PENDING'
    assert client.get('/api/tvec/quotations/refresh-status',headers=auth_headers).json()['state']=='PENDING'
    queue.AsyncResult=lambda identifier:SimpleNamespace(state='FAILURE')
    assert client.get('/api/tvec/quotations/refresh-status',headers=auth_headers).json()['state']=='ERROR'
