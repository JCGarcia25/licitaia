"""Real-schema synthetic samples only; no request to the official dataset."""
from copy import deepcopy
from datetime import timedelta
from decimal import Decimal
import json
from pathlib import Path
from threading import Event
from concurrent.futures import ThreadPoolExecutor

import httpx
import pytest
from sqlalchemy import inspect

from app.core.config import get_settings
from app.db.models import Base, Opportunity, UserOpportunity, TvecPurchaseOrder as Order
from app.db.models import TvecSyncState as State,TvecSyncRun as Run,TvecOrderRevision as Revision
from app.services import tvec_ingest as ingest
from app.services.tvec_client import DATASET,EXPECTED,TvecClient,normalize,now,validate_metadata
from app.services.tvec_guard import configuration

SAMPLES=json.loads((Path(__file__).parent/'fixtures/tvec_orders_synthetic.json').read_text())
META={'id':DATASET,'rowsUpdatedAt':1793177887,'columns':[{'fieldName':k,'dataTypeName':v} for k,v in EXPECTED.items()]}


class FakeClient:
    page_size=2
    def __init__(self,rows=None):self.rows=deepcopy(SAMPLES if rows is None else rows);self.calls=[]
    def metadata(self):return deepcopy(META)
    def count(self):return len(self.rows)
    def page(self,after=None):
        self.calls.append(after)
        return [r for r in self.rows if after is None or r['identificador_de_la_orden']>after][:self.page_size]


@pytest.fixture
def tvec(db,client,monkeypatch):
    from evaluation_test_support import authorize
    Base.metadata.create_all(db.bind,tables=[t for t in Base.metadata.tables.values() if t.name.startswith('tvec_')])
    for table in reversed([Base.metadata.tables[n] for n in ['tvec_purchase_orders','tvec_order_revisions','tvec_source_metadata','tvec_sync_states','tvec_sync_runs']]):db.execute(table.delete())
    db.commit()
    authorize(db,monkeypatch,origin='http://testserver')
    s=get_settings();monkeypatch.setattr(s,'tvec_enabled',True);monkeypatch.setattr(s,'tvec_ingest_enabled',True)
    monkeypatch.setattr(s,'tvec_dev_targets',s.evaluation_dev_targets);monkeypatch.setattr(s,'tvec_api_origin','http://testserver')
    return db


def run(db,rows=None,pages=2):
    row=ingest.create_run(db,pages);identifier=row.id;db.commit()
    return identifier,ingest.process_run(db,identifier,FakeClient(rows))


def test_verified_schema_mapping_money_dates_and_minimisation():
    assert validate_metadata(META)==EXPECTED
    changed=deepcopy(META);changed['columns'][0]['dataTypeName']='unknown'
    with pytest.raises(ValueError):validate_metadata(changed)
    added=deepcopy(META);added['columns'].append({'fieldName':'currency','dataTypeName':'text'})
    with pytest.raises(ValueError):validate_metadata(added)
    data=normalize(SAMPLES[0]);assert data['amount']==Decimal('100');assert data['currency'] is None
    assert data['official_url'] is None and data['description']==SAMPLES[0]['items']
    assert 'solicitante' not in data['raw_json'] and 'source_row_id' not in data['raw_json']
    assert data['expires_at'].year==2027 # order expiry, never an offer deadline
    nulls=normalize(SAMPLES[2]);assert nulls['amount'] is None
    for value in ['nan','Infinity','1e30','1.0000001','not money']:
        with pytest.raises(ValueError):normalize({**SAMPLES[0],'total':value})
    with pytest.raises(ValueError):normalize({**SAMPLES[0],'fecha':'not a date'})
    with pytest.raises(ValueError):normalize({**SAMPLES[0],'identificador_de_la_orden':None})


def test_socrata_ordered_page_escaping_retry_and_429(monkeypatch):
    calls=[]
    def get(url,**kwargs):
        calls.append((url,kwargs))
        response=httpx.Response(429 if len(calls)==1 else 200,json=SAMPLES[:1],request=httpx.Request('GET',url));return response
    monkeypatch.setattr(httpx,'get',get);monkeypatch.setattr('app.services.tvec_client.time.sleep',lambda _:None)
    c=TvecClient();rows=c.page("X' OR 1=1")
    assert rows and len(calls)==2
    assert calls[-1][1]['params']['$where']=="identificador_de_la_orden > 'X'' OR 1=1'"
    assert calls[-1][1]['params']['$order']=='identificador_de_la_orden ASC'
    assert 'solicitante' not in calls[-1][1]['params']['$select']
    assert 'datos.gov.co' in calls[-1][0] and calls[-1][1]['timeout']==10
    monkeypatch.setattr(c,'request',lambda *a:[{'total':'3','orders':'2'}])
    with pytest.raises(ValueError):c.count() # don't double count future item rows
    def fail(*a,**k):raise httpx.ConnectError('synthetic')
    monkeypatch.setattr(httpx,'get',fail)
    with pytest.raises(httpx.ConnectError):TvecClient().page()


def test_reconciliation_resume_duplicate_delivery_and_historical_updates(tvec):
    db=tvec;before=(db.query(Opportunity).count(),db.query(UserOpportunity.id,UserOpportunity.score,UserOpportunity.triage).all())
    first=ingest.create_run(db,1);db.commit();assert ingest.process_run(db,first.id,FakeClient())=='DONE'
    assert db.get(State,DATASET).cursor_id=='SYN-101' and db.query(Order).count()==2
    assert ingest.process_run(db,first.id,FakeClient())=='DONE' and db.query(Order).count()==2
    _,state=run(db,pages=1);assert state=='DONE' and db.query(Order).count()==3
    assert db.get(State,DATASET).last_complete_at is not None
    assert run(db)[1]=='DONE' and db.query(Revision).count()==0
    changed=deepcopy(SAMPLES);changed[0]['total']='123.123456'
    assert run(db,changed)[1]=='DONE';assert db.query(Order).filter_by(official_id='SYN-100').one().amount==Decimal('123.123456')
    assert db.query(Revision).count()==1
    assert db.query(Revision).one().payload['total']=='100'
    assert (db.query(Opportunity).count(),db.query(UserOpportunity.id,UserOpportunity.score,UserOpportunity.triage).all())==before
    from app.services.secop_client import DATASETS
    assert 'tvec' not in DATASETS


def test_bad_page_network_failure_and_expired_lease_rollback(tvec,monkeypatch):
    db=tvec
    class Bad(FakeClient):
        def page(self,after=None):return [SAMPLES[0],SAMPLES[0]]
    job=ingest.create_run(db,1);db.commit();assert ingest.process_run(db,job.id,Bad())=='FAILED'
    assert db.query(Order).count()==0 and db.get(State,DATASET).cursor_id is None
    class Offline(FakeClient):
        def page(self,after=None):raise httpx.ConnectError('synthetic')
    assert ingest.process_run(db,job.id,Offline())=='FAILED' and db.query(Order).count()==0
    original=ingest.save_order
    def expires(*args):
        value=original(*args);db.get(State,DATASET).lease_until=now()-timedelta(seconds=1);return value
    monkeypatch.setattr(ingest,'save_order',expires)
    assert ingest.process_run(db,job.id,FakeClient())=='FAILED'
    assert db.query(Order).count()==0 and db.get(State,DATASET).cursor_id is None


def test_dev_only_guard_and_no_automatic_schedules(tvec,monkeypatch):
    settings=get_settings()
    for env in ['production','staging']:
        monkeypatch.setattr(settings,'environment',env)
        with pytest.raises(ValueError):configuration()
    monkeypatch.setattr(settings,'environment','testing');monkeypatch.setattr(settings,'tvec_dev_targets',[])
    with pytest.raises(ValueError):configuration()
    from app.workers.celery_app import celery_app
    assert not any('tvec' in v['task'] for v in celery_app.conf.beat_schedule.values())


def test_api_combined_filters_exact_values_paging_and_private_boundary(tvec,client,auth_headers):
    db=tvec;assert run(db)[1]=='DONE'
    assert client.get('/api/tvec/orders').status_code==401
    response=client.get('/api/tvec/orders',headers=auth_headers,params={'department':'Meta','q':'sintético','amount_min':'150','date_to':'2025-02-28','limit':1})
    assert response.status_code==200,response.text
    payload=response.json();assert payload['total']==1 and payload['items'][0]['official_id']=='SYN-101'
    assert payload['items'][0]['amount']=='200.000000' and 'raw_json' not in payload['items'][0]
    assert 'compatibility' not in response.text.lower() and 'solicitante' not in response.text.lower()
    assert client.get('/api/tvec/orders?q=%25',headers=auth_headers).json()['total']==0
    assert client.get('/api/tvec/orders?department=NO_MATCH',headers=auth_headers).json()['items']==[]
    assert client.get('/api/tvec/orders?amount_min=500&amount_max=1',headers=auth_headers).status_code==422
    assert client.get('/api/tvec/orders?limit=10000',headers=auth_headers).status_code==422
    assert client.get('/api/tvec/orders?date_from=2026-01-01&date_to=2025-01-01',headers=auth_headers).status_code==422
    assert client.get('/api/tvec/orders/999999',headers=auth_headers).status_code==404
    for route in ['summary','buyers','suppliers','instruments','sync-status']:
        r=client.get('/api/tvec/'+route,headers=auth_headers);assert r.status_code==200,(route,r.text)
    summary=client.get('/api/tvec/summary',headers=auth_headers).json()
    assert summary['orders']==3 and summary['monetary_total'] is None and summary['orders_with_value']==2
    assert len(summary['periods'])==3
