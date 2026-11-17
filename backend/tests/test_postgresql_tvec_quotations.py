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
