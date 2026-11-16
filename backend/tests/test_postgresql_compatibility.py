"""Real PG transactions/leases; synthetic company/opportunity fixtures, no external LLM."""
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timedelta
from threading import Event
from uuid import uuid4
import pytest
from sqlalchemy import inspect,text
from app.core.config import get_settings
from app.db.models import User,CompanyProfile,Opportunity,UserOpportunity,CompatibilityShadowRun as Run,CompatibilityShadowResult as Result
from app.services import compatibility_shadow as shadow
from test_postgresql_matches import pg_factory

pytestmark=pytest.mark.skipif(not os.environ.get('MYSECOP_TEST_POSTGRES_URL'),reason='Requires disposable real PostgreSQL')

@pytest.fixture
def configured(pg_factory,monkeypatch):
    monkeypatch.setattr(get_settings(),'compatibility_v2_shadow_enabled',True)
    monkeypatch.setattr(get_settings(),'compatibility_v2_batch_size',2)
    from evaluation_test_support import authorize
    with pg_factory[0]() as db:authorize(db,monkeypatch,database=os.environ['MYSECOP_TEST_POSTGRES_URL'],origin='http://isolated.local')
    return pg_factory


def new_run(factory):
    with factory() as db:
        u=User(email=f'{uuid4().hex}@example.invalid',hashed_password='test',role='admin');db.add(u);db.flush()
        db.add(CompanyProfile(user_id=u.id,sector='software',departamentos=['Meta']))
        db.add_all([Opportunity(source='qa',source_id=uuid4().hex,objeto='software',estado='En proceso') for _ in range(4)])
        db.commit();run=shadow.create_run(db,u.id,4);db.commit();return run.id,u.id


def test_pg_shadow_concurrent_fencing_no_lock_during_compute(configured,monkeypatch):
    factory,_=configured;rid,uid=new_run(factory)
    entered,release=Event(),Event();original=shadow.v2.evaluate
    def hold(*a,**k):
        entered.set();assert release.wait(10);return original(*a,**k)
    monkeypatch.setattr(shadow.v2,'evaluate',hold)
    def worker():
        with factory() as db:return shadow.process_batch(db,rid)
    with ThreadPoolExecutor(2) as pool:
        first=pool.submit(worker);assert entered.wait(10)
        assert worker()=='BUSY_OR_FINISHED'
        # Another connection can lock/update the row while first worker calculates.
        with factory() as db:
            db.execute(text("SET LOCAL lock_timeout='1s'"))
            r=db.query(Run).filter_by(id=rid).with_for_update().one()
            r.lease_until=datetime.utcnow()-timedelta(seconds=1);db.commit()
        release.set();assert first.result(10)=='LEASE_LOST'
    with factory() as db:
        assert db.query(Result).filter_by(run_id=rid).count()==0
        assert shadow.process_batch(db,rid)=='RUNNING'
        assert shadow.process_batch(db,rid)=='COMPLETED'
        assert shadow.process_batch(db,rid)=='BUSY_OR_FINISHED'
        assert db.query(Result).filter_by(run_id=rid).count()==4
        assert db.query(UserOpportunity).filter_by(user_id=uid).count()==0


def test_pg_shadow_rollback_connection_loss_and_migration_guard(configured,monkeypatch):
    factory,migrate=configured;rid,uid=new_run(factory)
    with factory() as db:
        original=db.commit;calls=0
        def lost_commit():
            nonlocal calls
            calls+=1
            if calls==2:raise RuntimeError('controlled pre-commit interruption')
            return original()
        monkeypatch.setattr(db,'commit',lost_commit)
        with pytest.raises(RuntimeError):shadow.process_batch(db,rid)
        db.rollback()
    with factory() as db:
        assert db.get(Run,rid).cursor==0 and db.query(Result).filter_by(run_id=rid).count()==0
        db.get(Run,rid).lease_until=datetime.utcnow()-timedelta(seconds=1);db.commit()
        assert shadow.process_batch(db,rid)=='RUNNING'
        # Kill the client connection and prove a clean connection resumes durable cursor.
        pid=db.execute(text('select pg_backend_pid()')).scalar_one()
        with factory() as other:other.execute(text('select pg_terminate_backend(:pid)'),{'pid':pid});other.commit()
        with pytest.raises(Exception):db.execute(text('select 1'))
        db.rollback()
    with factory() as db:
        assert shadow.process_batch(db,rid)=='COMPLETED'
        assert db.query(Result).filter_by(run_id=rid).count()==4
    outcome=migrate('downgrade','0012_failed_match_inputs')
    assert outcome.returncode!=0 and ('historial V2' in outcome.stderr or 'historial de evaluación' in outcome.stderr)
