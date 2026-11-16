import os
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Event
from uuid import uuid4
import pytest
from app.db.models import User,EvaluationCampaign as Campaign,EvaluationEnvironmentIdentity as Identity,EvaluationSample as Sample
from app.core.config import get_settings
from app.services import evaluation_platform as p
from app.services.evaluation_guard import destination
from app.services.match_versions import digest
from test_postgresql_matches import pg_factory
from test_evaluation_platform import body

pytestmark=pytest.mark.skipif(not os.environ.get('MYSECOP_TEST_POSTGRES_URL'),reason='Disposable PostgreSQL required')

@pytest.fixture
def configured(pg_factory,monkeypatch):
    factory,migrate=pg_factory;s=get_settings();url=os.environ['MYSECOP_TEST_POSTGRES_URL']
    monkeypatch.setattr(s,'database_url',url);monkeypatch.setattr(s,'evaluation_enabled',True);monkeypatch.setattr(s,'evaluation_api_origin','http://isolated.local')
    with factory() as db:
        marker=db.query(Identity).first()
        if not marker:marker=Identity(id=str(uuid4()),fingerprint=digest(destination(s)),purpose='isolated-development');db.add(marker);db.commit()
        identifier=marker.id
    monkeypatch.setattr(s,'evaluation_dev_targets',[{'database':url,'broker':s.redis_url,'api_origin':s.evaluation_api_origin,'identity':identifier}])
    return factory,migrate


def seed(factory):
    with factory() as db:
        u=User(email=f'{uuid4().hex}@example.invalid',hashed_password='synthetic',role='admin');db.add(u);db.flush()
        c=p.create(db,u.id,body(12));db.commit();return c.id


def test_pg_campaign_fencing_and_recovery_without_locks(configured,monkeypatch):
    factory,migrate=configured;identifier=seed(factory);entered,release=Event(),Event();original=p.calculate_base
    def hold(*a,**kw):entered.set();assert release.wait(10);return original(*a,**kw)
    monkeypatch.setattr(p,'calculate_base',hold)
    def worker():
        with factory() as db:return p.process_batch(db,identifier)
    with ThreadPoolExecutor(2) as pool:
        first=pool.submit(worker);assert entered.wait(10)
        assert worker()=='BUSY_OR_FINISHED'
        with factory() as db:
            c=db.query(Campaign).filter_by(id=identifier).with_for_update().one();c.lease_until=p.now()-timedelta(seconds=1);db.commit()
        release.set();assert first.result(10)=='LEASE_LOST'
    with factory() as db:
        assert db.get(Campaign,identifier).cursor==0
        while p.process_batch(db,identifier)=='PREPARING':pass
        assert db.query(Sample).filter_by(campaign_id=identifier).count()==12
        assert p.process_batch(db,identifier)=='BUSY_OR_FINISHED'
    result=migrate('downgrade','0013_compatibility_shadow')
    assert result.returncode!=0 and 'historial de evaluación' in result.stderr


def test_pg_campaign_commit_rollback_retry(configured,monkeypatch):
    factory,_=configured;identifier=seed(factory)
    with factory() as db:
        original=db.commit;count=0
        def failure():
            nonlocal count
            count+=1
            if count==2:raise RuntimeError('controlled before confirmation commit')
            return original()
        monkeypatch.setattr(db,'commit',failure)
        with pytest.raises(RuntimeError):p.process_batch(db,identifier)
        db.rollback()
    with factory() as db:
        c=db.get(Campaign,identifier);assert c.cursor==0;c.lease_until=p.now()-timedelta(seconds=1);db.commit()
        while p.process_batch(db,identifier)=='PREPARING':pass
        assert db.query(Sample).filter_by(campaign_id=identifier).count()==12
