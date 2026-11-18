"""Real PG/Redis/Celery; source HTTP is always replaced by synthetic fixtures."""
import json
import os
from datetime import timedelta

import pytest
from app.core.config import get_settings
from app.db.models import TvecPurchaseOrder as Order,TvecSyncRun as Run,TvecSyncState as State,Opportunity,UserOpportunity
from app.services import tvec_ingest as ingest
from app.services.tvec_client import DATASET,now
from test_redis_operations import services,wait

pytestmark=pytest.mark.skipif(not os.environ.get('MYSECOP_TEST_POSTGRES_URL') or not os.environ.get('MYSECOP_RUN_REDIS_TESTS'),reason='Requires isolated PostgreSQL/Redis runner')


def test_real_tvec_queue_duplicate_broker_restart_and_worker_kill(services,monkeypatch):
    from evaluation_test_support import authorize
    s=services;settings=get_settings();url=os.environ['MYSECOP_TEST_POSTGRES_URL']
    with s.factory() as db:
        authorize(db,monkeypatch,database=url,broker=s.broker,origin='http://isolated.local')
    for k,v in dict(tvec_enabled=True,tvec_ingest_enabled=True,tvec_dev_targets=settings.evaluation_dev_targets,tvec_api_origin='http://isolated.local').items():monkeypatch.setattr(settings,k,v)
    env={'TVEC_ENABLED':'true','TVEC_INGEST_ENABLED':'true','TVEC_DEV_TARGETS':json.dumps(settings.tvec_dev_targets),
         'TVEC_API_ORIGIN':settings.tvec_api_origin,'MYSECOP_TVEC_FAKE_SOURCE':'1'}
    s.worker_stop();s.worker_start(queues='tvec',extra_env=env)
    with s.factory() as db:run=ingest.create_run(db,2);identifier=run.id;db.commit()
    for _ in range(3):s.application.send_task('app.workers.tasks.sync_tvec_orders',args=[identifier],queue='tvec')
    def completed(ident):
        with s.factory() as db:return db.get(Run,ident).state=='DONE'
    wait(lambda:completed(identifier),30)
    with s.factory() as db:assert db.query(Order).count()==3
    # Persist a queued run across real AOF-backed broker restart.
    s.worker_stop()
    with s.factory() as db:run=ingest.create_run(db,2);replay=run.id;db.commit()
    s.application.send_task('app.workers.tasks.sync_tvec_orders',args=[replay],queue='tvec')
    s.redis_stop();s.redis_start();s.worker_start(queues='tvec',extra_env=env)
    wait(lambda:completed(replay),30)
    # Hard stop our process group during source acquisition; resume the DB run.
    s.flags(tvec_hold=True)
    with s.factory() as db:run=ingest.create_run(db,2);interrupted=run.id;db.commit()
    s.application.send_task('app.workers.tasks.sync_tvec_orders',args=[interrupted],queue='tvec')
    wait(s.entered,15);s.worker_stop(hard=True);s.flags()
    with s.factory() as db:
        assert db.get(Run,interrupted).pages==0
        state=db.get(State,DATASET);state.lease_until=now()-timedelta(seconds=1);db.commit()
    s.worker_start(queues='tvec',extra_env=env)
    s.application.send_task('app.workers.tasks.sync_tvec_orders',args=[interrupted],queue='tvec')
    wait(lambda:completed(interrupted),30)
    with s.factory() as db:
        assert db.query(Order).count()==3
        assert db.query(Opportunity).count()==0 and db.query(UserOpportunity).count()==0


def test_quotation_network_failure_recovers_automatically_on_same_cursor(services,monkeypatch):
    from evaluation_test_support import authorize
    from app.db.models import TvecQuotationSnapshot as Snapshot,TvecQuotationEvent as Event
    from app.services.tvec_quotations import SOURCE
    settings=get_settings();s=services;url=os.environ['MYSECOP_TEST_POSTGRES_URL']
    with s.factory() as db:
        authorize(db,monkeypatch,database=url,broker=s.broker,origin='http://isolated.local')
        previous_opportunities=db.query(Opportunity).count()
    env={'TVEC_ENABLED':'true','TVEC_EVENTS_ENABLED':'true','TVEC_EVENTS_REFRESH_ENABLED':'true',
         'TVEC_DEV_TARGETS':json.dumps(settings.evaluation_dev_targets),
         'TVEC_API_ORIGIN':'http://isolated.local','MYSECOP_TVEC_QUOTATIONS_FAKE_SOURCE':'1'}
    from datetime import datetime,timezone
    s.control.with_suffix('.quotation-clock').write_text(datetime.now(timezone.utc).replace(tzinfo=None).isoformat())
    s.worker_stop();s.worker_start(queues='tvec',extra_env=env)
    # Exactly one initial task; the task must arrange its own retry/continuation.
    s.application.send_task('app.workers.tasks.refresh_tvec_quotations',queue='tvec')
    wait(lambda:s.control.with_suffix('.quotation-failed').exists(),20)
    with s.factory() as db:
        state=db.get(Snapshot,SOURCE)
        assert state.scan_progress['next_page']==2 and state.published_snapshot is None
        generation=state.scan_progress['id']
    def completed():
        with s.factory() as db:
            state=db.get(Snapshot,SOURCE)
            return state and state.status=='IDLE' and state.scan_progress.get('complete')
    wait(completed,40)
    with s.factory() as db:
        state=db.get(Snapshot,SOURCE)
        assert state.scan_progress['id']==generation
        assert state.scanned_pages==3 and state.scanned_rows==33
        assert db.query(Event).filter_by(snapshot_id=generation).count()==2
        assert db.query(Opportunity).count()==previous_opportunities
