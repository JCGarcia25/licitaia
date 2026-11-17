"""Opt-in real isolated PostgreSQL: migration parity and quotation fencing."""
import os
from threading import Event as Signal
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
import pytest
from sqlalchemy import inspect,text
from test_postgresql_tvec import pg,configured
from test_tvec_quotations import Fake,prepared
from app.core.config import get_settings
from app.db.models import TvecQuotationEvent as Event,TvecQuotationSnapshot as Snapshot,TvecPurchaseOrder as Order
from app.services import tvec_quotations as quotations
from app.services.tvec_client import now

pytestmark=pytest.mark.skipif(not os.environ.get('MYSECOP_TEST_POSTGRES_URL'),reason='Requires disposable PostgreSQL')


def test_pg_quotation_workers_atomic_fencing_and_populated_downgrade(configured,monkeypatch):
    factory,migrate=configured;s=get_settings()
    monkeypatch.setattr(s,'tvec_events_enabled',True);monkeypatch.setattr(s,'tvec_events_refresh_enabled',True)
    entered=Signal();release=Signal()
    with factory() as db:
        order_count=db.query(Order).count()
        assert 'tvec_quotation_events' in inspect(db.bind).get_table_names()
    class Held(Fake):
        def collect(self):
            assert not session.in_transaction();entered.set();assert release.wait(15);return super().collect()
    with ThreadPoolExecutor(max_workers=2) as pool:
        session=factory();future=pool.submit(quotations.refresh,session,Held());assert entered.wait(10)
        with factory() as db:
            assert quotations.refresh(db,Fake())=='BUSY'
            db.query(Snapshot).update({'lease_until':now()-timedelta(seconds=1)});db.commit()
        with factory() as db:assert quotations.refresh(db,Fake())=='DONE'
        release.set()
        with pytest.raises(RuntimeError):future.result(timeout=15)
        session.close()
    with factory() as db:
        assert db.query(Event).count()==1
        snapshot=db.get(Snapshot,quotations.SOURCE);published=snapshot.published_snapshot
        assert snapshot.status=='IDLE' and snapshot.lease_token is None
        assert quotations.refresh(db,Fake())=='DONE' and db.query(Event).count()==1
        assert db.query(Order).count()==order_count
        # An actual constraint failure cannot publish a half-written snapshot.
        bad=prepared();bad['title']=None
        with pytest.raises(Exception):quotations.refresh(db,Fake([bad]))
        assert db.get(Snapshot,quotations.SOURCE).published_snapshot!=None
        assert db.query(Event).one().title is not None
        assert db.get(Snapshot,quotations.SOURCE).status=='ERROR'
        assert db.execute(text('select score from user_opportunities')).scalar_one()==81
    result=migrate('downgrade','0015_tvec_orders')
    assert result.returncode!=0 and 'populated downgrade forbidden' in result.stderr
    with factory() as db:assert db.query(Event).count()==1


def test_pg_full_scan_resume_json_fencing_and_migration_preserves_data(configured,monkeypatch):
    from app.services import tvec_full_scan as full
    from test_tvec_full_scan import Pages
    from test_tvec_quotations import INSTANT
    from app.services.tvec_ingest import save_order
    from test_tvec import SAMPLES
    factory,migrate=configured;s=get_settings()
    monkeypatch.setattr(s,'tvec_events_enabled',True);monkeypatch.setattr(s,'tvec_events_refresh_enabled',True)
    monkeypatch.setattr(full,'now',lambda:INSTANT)
    with factory() as db:previous=db.query(Event).count()
    assert migrate('downgrade','0016_tvec_quotations').returncode==0
    assert migrate('upgrade','head').returncode==0
    with factory() as db:
        assert db.query(Event).count()==previous
        db.query(Event).delete();db.query(Snapshot).delete();save_order(db,SAMPLES[0],'pg-preserved');db.commit()
        original=db.query(Order).one().version
    entered=Signal();release=Signal()
    class Held(Pages):
        def batch(self,progress):
            assert not session.in_transaction();entered.set();assert release.wait(15)
            return super().batch(progress)
    with ThreadPoolExecutor(max_workers=2) as pool:
        session=factory();future=pool.submit(full.refresh_batch,session,None,Held());assert entered.wait(10)
        with factory() as db:
            assert full.refresh_batch(db,client=Pages())['status']=='BUSY'
            db.query(Snapshot).update({'lease_until':INSTANT-timedelta(seconds=1)});db.commit()
        with factory() as db:first=full.refresh_batch(db,client=Pages())
        assert first['status']=='MORE' and first['pages']==2
        release.set()
        with pytest.raises(RuntimeError):future.result(timeout=15)
        session.close()
    with factory() as db:
        assert db.query(Event).count()==0
        assert db.get(Snapshot,quotations.SOURCE).scan_progress['next_page']==2
        assert full.refresh_batch(db,first['scan_id'],Pages())['status']=='DONE'
        assert db.query(Event).count()==2 and db.query(Order).one().version==original
        assert db.execute(text('select score from user_opportunities')).scalar_one()==81
    refused=migrate('downgrade','0016_tvec_quotations')
    assert refused.returncode!=0 and 'Preserve TVEC scan progress' in refused.stderr
