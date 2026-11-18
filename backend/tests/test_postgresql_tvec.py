"""Opt-in real PostgreSQL, exclusively a database created by isolated runner."""
import os
import subprocess
import sys
import json
from datetime import timedelta
from threading import Event
from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy import create_engine, inspect, text, Column, UniqueConstraint
from sqlalchemy.orm import sessionmaker
from sqlalchemy.engine import make_url
from alembic.migration import MigrationContext

from app.db.models import Base,TvecPurchaseOrder as Order,TvecOrderRevision as Revision,TvecSyncState as State,User,Opportunity,UserOpportunity
from app.services import tvec_ingest as ingest
from app.services.tvec_client import DATASET,now
from test_tvec import FakeClient,SAMPLES

URL=os.environ.get('MYSECOP_TEST_POSTGRES_URL','')
pytestmark=pytest.mark.skipif(not URL,reason='Requires isolated PostgreSQL runner')


@pytest.fixture(scope='module')
def pg():
    assert make_url(URL).get_backend_name()=='postgresql' and make_url(URL).database.startswith('mysecop_test_')
    engine=create_engine(URL,pool_pre_ping=True);assert not inspect(engine).get_table_names()
    def migrate(action,target):
        return subprocess.run([sys.executable,'-m','alembic',action,target],env={**os.environ,'DATABASE_URL':URL,'ENVIRONMENT':'testing'},capture_output=True,text=True)
    assert migrate('upgrade','head').returncode==0
    assert migrate('downgrade','0014_evaluation_platform').returncode==0
    assert not inspect(engine).has_table('tvec_purchase_orders')
    with engine.begin() as c:
        uid=c.execute(text("INSERT INTO users(email,hashed_password) VALUES('tvec-legacy@example.com','fixture-only') RETURNING id")).scalar_one()
        oid=c.execute(text("INSERT INTO opportunities(source,source_id,objeto) VALUES('qa','tvec-preserved','Synthetic software') RETURNING id")).scalar_one()
        c.execute(text("INSERT INTO user_opportunities(user_id,opportunity_id,score,triage) VALUES(:u,:o,81,'guardada')"),{'u':uid,'o':oid})
    result=migrate('upgrade','head');assert result.returncode==0,result.stderr
    ins=inspect(engine)
    with engine.connect() as c:
        comparator=MigrationContext.configure(c).impl.compare_type
        for table in [t for t in Base.metadata.tables.values() if t.name.startswith('tvec_')]:
            actual={col['name']:col for col in ins.get_columns(table.name)}
            assert set(actual)==set(table.columns.keys())
            for col in table.columns:
                assert actual[col.name]['nullable']==col.nullable
                assert not comparator(Column(col.name,actual[col.name]['type']),col)
            assert {tuple(c.name for c in u.columns) for u in table.constraints if isinstance(u,UniqueConstraint)}<={tuple(u['column_names']) for u in ins.get_unique_constraints(table.name)}
            assert {tuple(c.name for c in index.columns) for index in table.indexes}<={tuple(index['column_names']) for index in ins.get_indexes(table.name)}
        assert c.execute(text('SELECT score FROM user_opportunities WHERE user_id=:u'),{'u':uid}).scalar_one()==81
    yield sessionmaker(bind=engine,expire_on_commit=False),migrate
    engine.dispose()


@pytest.fixture
def configured(pg,monkeypatch):
    from evaluation_test_support import authorize
    from app.core.config import get_settings
    factory,migrate=pg
    with factory() as db:
        authorize(db,monkeypatch,database=URL,origin='http://isolated.local')
        for name in ['tvec_order_revisions','tvec_purchase_orders','tvec_sync_runs','tvec_sync_states','tvec_source_metadata']:db.execute(Base.metadata.tables[name].delete())
        db.commit()
    s=get_settings()
    for k,v in dict(tvec_enabled=True,tvec_ingest_enabled=True,tvec_dev_targets=s.evaluation_dev_targets,tvec_api_origin='http://isolated.local').items():monkeypatch.setattr(s,k,v)
    return pg


def test_pg_tvec_concurrent_workers_no_transaction_during_io_and_expired_fencing(configured):
    factory,_=configured;entered=Event();release=Event()
    with factory() as db:run=ingest.create_run(db,2);identifier=run.id;db.commit()
    class Held(FakeClient):
        def page(self,after=None):
            assert not session.in_transaction()
            entered.set();assert release.wait(15);return super().page(after)
    with ThreadPoolExecutor(max_workers=2) as pool:
        session=factory();future=pool.submit(ingest.process_run,session,identifier,Held());assert entered.wait(10)
        with factory() as db:
            assert ingest.process_run(db,identifier,FakeClient())=='BUSY'
            db.query(State).filter_by(dataset_id=DATASET).update({'lease_until':now()-timedelta(seconds=1)});db.commit()
        with factory() as db:assert ingest.process_run(db,identifier,FakeClient())=='DONE'
        release.set();assert future.result(timeout=15)=='FAILED';session.close()
    with factory() as db:
        assert db.query(Order).count()==3
        assert db.get(ingest.Run,identifier).state=='DONE'
        assert db.query(UserOpportunity).one().score==81 and db.query(UserOpportunity).one().triage=='guardada'


def test_pg_tvec_connection_loss_rollback_cursor_history_and_guard(configured,monkeypatch):
    factory,migrate=configured
    with factory() as db:
        run=ingest.create_run(db,2);identifier=run.id;db.commit()
        class Lost(FakeClient):
            def page(self,after=None):
                if after:
                    # Kill this test's own connection only, never a shared process.
                    db.execute(text('SELECT pg_terminate_backend(pg_backend_pid())'))
                return super().page(after)
        assert ingest.process_run(db,identifier,Lost())=='FAILED'
        assert db.query(Order).count()==2 and db.get(State,DATASET).cursor_id=='SYN-101'
        assert ingest.process_run(db,identifier,FakeClient())=='DONE'
        assert db.query(Order).count()==3
        order=db.query(Order).first();db.add(Revision(order_id=order.id,version=order.version,payload=order.raw_json,recorded_at=now()));db.commit()
    result=migrate('downgrade','0014_evaluation_platform')
    assert result.returncode!=0 and 'Preserve TVEC history' in result.stderr
    with factory() as db:assert db.query(Order).count()==3 and db.query(Revision).count()==1
    # Existing evaluation tooling must still verify the reviewed additive head;
    # no V2 computation/provider or marker write is triggered here.
    from app.core.config import get_settings
    settings=get_settings()
    result=subprocess.run([sys.executable,'scripts/evaluation_target.py','--verify-database'],capture_output=True,text=True,
        env={**os.environ,'DATABASE_URL':URL,'REDIS_URL':settings.redis_url,'SECRET_KEY':settings.secret_key,
             'ENVIRONMENT':'testing','EVALUATION_ENABLED':'true','EVALUATION_API_ORIGIN':'http://isolated.local',
             'EVALUATION_DEV_TARGETS':json.dumps(settings.evaluation_dev_targets)})
    assert result.returncode==0,result.stdout
