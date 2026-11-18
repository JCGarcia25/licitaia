"""Task recovery policy: no actual broker or official HTTP calls."""
from contextlib import nullcontext
from types import SimpleNamespace
import httpx
import pytest
from celery.exceptions import Retry
from kombu.exceptions import OperationalError as BrokerUnavailable
from app.workers.tasks import refresh_tvec_quotations as task
from app.services import tvec_full_scan,tvec_quotations
from app.workers.celery_app import celery_app

@pytest.fixture
def worker(monkeypatch):
    monkeypatch.setattr(tvec_quotations,'configured',lambda **kw:SimpleNamespace(redis_url=celery_app.conf.broker_url))
    monkeypatch.setattr('app.db.session.SessionLocal',lambda:nullcontext(object()))
    sent=[]
    monkeypatch.setattr(celery_app,'send_task',lambda *a,**kw:sent.append((a,kw)))
    task.push_request(retries=0,called_directly=False,is_eager=True,args=['same-scan'],kwargs={})
    yield sent
    task.pop_request()

@pytest.mark.parametrize('error',[httpx.ConnectError('synthetic'),httpx.ReadTimeout('synthetic'),TimeoutError('budget'),httpx.HTTPStatusError('synthetic',request=httpx.Request('GET','https://example.invalid'),response=httpx.Response(503))])
def test_transient_failure_retries_same_scan(worker,monkeypatch,error):
    seen=[]
    def failed(db,expected_scan):seen.append(expected_scan);raise error
    monkeypatch.setattr(tvec_full_scan,'refresh_batch',failed)
    with pytest.raises(Retry) as retry:task.run('same-scan')
    assert seen==['same-scan'] and retry.value.when==10
    assert list(retry.value.sig.args)==['same-scan'] and worker==[]

@pytest.mark.parametrize('error',[ValueError('schema changed'),RuntimeError('lease lost'),httpx.HTTPStatusError('unauthorized',request=httpx.Request('GET','https://example.invalid'),response=httpx.Response(403))])
def test_permanent_and_fencing_errors_not_retried(worker,monkeypatch,error):
    monkeypatch.setattr(tvec_full_scan,'refresh_batch',lambda *a,**kw:(_ for _ in ()).throw(error))
    with pytest.raises(type(error)):task.run('same-scan')
    assert worker==[]

def test_retry_budget_exhausted(worker,monkeypatch):
    error=httpx.ConnectError('synthetic')
    monkeypatch.setattr(tvec_full_scan,'refresh_batch',lambda *a,**kw:(_ for _ in ()).throw(error))
    task.request.retries=3
    with pytest.raises(httpx.ConnectError):task.run('same-scan')
    assert worker==[]

def test_busy_retries_same_generation(worker,monkeypatch):
    monkeypatch.setattr(tvec_full_scan,'refresh_batch',lambda *a,**kw:{'status':'BUSY'})
    with pytest.raises(Retry) as retry:task.run('same-scan')
    assert retry.value.when==15 and worker==[]

def test_publish_failure_uses_committed_generation(worker,monkeypatch):
    monkeypatch.setattr(tvec_full_scan,'refresh_batch',lambda *a,**kw:{'status':'MORE','scan_id':'committed-generation'})
    monkeypatch.setattr(celery_app,'send_task',lambda *a,**kw:(_ for _ in ()).throw(BrokerUnavailable('synthetic')))
    with pytest.raises(Retry) as retry:task.run(None)
    assert list(retry.value.sig.args)==['committed-generation']

def test_completed_delivery_does_not_reschedule(worker,monkeypatch):
    monkeypatch.setattr(tvec_full_scan,'refresh_batch',lambda *a,**kw:{'status':'DONE'})
    assert task.run('same-scan')=={'status':'DONE'} and worker==[]
