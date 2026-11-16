"""Servicios reales aislados: Redis por socket, worker Celery prefork y PG."""
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
import importlib.util
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
from uuid import uuid4

import pytest
from celery import Celery
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker
from app.db.models import CompanyProfile, MatchJob, MatchSlot, MatchScoreHistory, Opportunity, User, UserOpportunity
from app.services.match_jobs import request_job, coverage, cancel_job, resume_job, utc_now

URL = os.environ.get('MYSECOP_TEST_POSTGRES_URL','')
pytestmark = pytest.mark.skipif(not URL or not os.environ.get('MYSECOP_RUN_REDIS_TESTS'),reason='Requiere runner PG/Redis aislado')

class Services:
    def __init__(self, directory, binary, factory):
        self.directory, self.binary, self.factory = directory,binary,factory
        self.control = directory/'control.json'
        self.control.write_text('{}')
        self.broker = f'redis+socket://{directory}/redis.sock?virtual_host=0'
        self.application = Celery('isolated-client',broker=self.broker,backend=self.broker)
        self.application.conf.update(task_publish_retry=False,broker_connection_timeout=.5,
            broker_transport_options={'socket_connect_timeout':.5,'socket_timeout':.5})
        self.redis = self.worker = None
    def redis_start(self):
        self.redis = subprocess.Popen([self.binary,'--port','0','--unixsocket',str(self.directory/'redis.sock'),
            '--unixsocketperm','700','--dir',str(self.directory),'--appendonly','yes','--appendfsync','always','--save',''],
            stdout=open(self.directory/'redis.log','a'),stderr=subprocess.STDOUT)
        import redis
        self.client = redis.Redis(unix_socket_path=str(self.directory/'redis.sock'),socket_timeout=.5)
        wait(lambda:self.client.ping(),10)
    def redis_stop(self):
        if self.redis and self.redis.poll() is None:
            self.redis.terminate(); self.redis.wait(timeout=10)
    def worker_start(self, queues="matches", extra_env=None):
        env={**os.environ,'DATABASE_URL':URL,'REDIS_URL':self.broker,'ENVIRONMENT':'isolated-integration',
            'SECRET_KEY':'isolated-test-key-with-32-characters','EMBEDDING_PROVIDER':'fake','EMBEDDING_DIM':'64',
            'MATCH_BATCH_SIZE':'20','MATCH_GLOBAL_CONCURRENCY':'2','MATCH_LEASE_SECONDS':'10',
            'MYSECOP_TEST_CONTROL':str(self.control),'OBJC_DISABLE_INITIALIZE_FORK_SAFETY':'YES',
            'PYTHONPATH':str(Path.cwd()/'tests')+os.pathsep+str(Path.cwd()), **(extra_env or {})}
        self.worker=subprocess.Popen([sys.executable,'-m','celery','-A','isolated_match_worker:app','worker',
            '--pool=prefork','--concurrency=2','--prefetch-multiplier=1',f'--queues={queues}','--loglevel=INFO',
            '--without-gossip','--without-mingle','--without-heartbeat'],env=env,start_new_session=True,
            stdout=open(self.directory/'worker.log','a'),stderr=subprocess.STDOUT)
        wait(lambda:bool(self.application.control.ping(timeout=.5)),20)
    def worker_stop(self, hard=False):
        if self.worker and self.worker.poll() is None:
            os.killpg(self.worker.pid,signal.SIGKILL if hard else signal.SIGTERM)
            self.worker.wait(timeout=15)
    def publish(self,jid):
        return self.application.send_task('app.workers.tasks.process_match_batch',args=[jid],queue='matches',retry=False)
    def flags(self, **values):
        staging=self.control.with_suffix('.new')
        staging.write_text(json.dumps(values));staging.replace(self.control)
        self.control.with_suffix('.entered').write_text('')
    def entered(self):
        return self.control.with_suffix('.entered').read_text() == 'entered'
    def state(self,jid):
        with self.factory() as db: return db.get(MatchJob,jid).state
    def completed(self,jid):
        wait(lambda:self.state(jid)=='COMPLETED',40)
    def seed(self,count=3):
        with self.factory() as db:
            user=User(email=f'{uuid4().hex}@example.invalid',hashed_password='fixture')
            db.add(user);db.flush()
            db.add(CompanyProfile(user_id=user.id,sector='software',keywords=['software']))
            db.add_all([Opportunity(source='qa',source_id=uuid4().hex,objeto='software',estado='En proceso') for _ in range(count)])
            db.commit();job=request_job(db,user.id);db.commit()
            return job.id,user.id


def wait(predicate, timeout):
    end=time.monotonic()+timeout
    while time.monotonic()<end:
        try:
            if predicate(): return
        except Exception: pass
        time.sleep(.1)
    raise AssertionError(f'Condición no cumplida en {timeout}s')

@pytest.fixture(scope='module')
def services():
    assert (make_url(URL).database or '').startswith('mysecop_test_')
    spec=importlib.util.find_spec('redislite')
    assert spec, 'Instalar redislite únicamente en venv de prueba'
    binary=str(Path(spec.origin).parent/'bin/redis-server')
    directory=Path(tempfile.mkdtemp(prefix='mysecop-test-redis-'))
    engine=create_engine(URL,pool_size=4,max_overflow=0,pool_pre_ping=True)
    from sqlalchemy import inspect
    assert not inspect(engine).get_table_names(),'Base debe estar vacía'
    subprocess.run([sys.executable,'-m','alembic','upgrade','head'],check=True,
        env={**os.environ,'DATABASE_URL':URL,'ENVIRONMENT':'testing'})
    from app.core.config import get_settings
    settings=get_settings()
    previous=(settings.embedding_dim,settings.match_batch_size,settings.match_lease_seconds)
    settings.embedding_dim,settings.match_batch_size,settings.match_lease_seconds=64,20,10
    s=Services(directory,binary,sessionmaker(bind=engine,expire_on_commit=False))
    print('REDIS_EVIDENCE',directory)
    try:
        s.redis_start();s.worker_start()
        yield s
    finally:
        s.flags()
        s.worker_stop();s.redis_stop();engine.dispose();s.application.close()
        settings.embedding_dim,settings.match_batch_size,settings.match_lease_seconds=previous


def test_redis_complete_simultaneous_and_same_user(services):
    s=services
    first,u1=s.seed(25); second,u2=s.seed(0)
    def start():
        with s.factory() as db:
            job=request_job(db,u1);db.commit();return job.id
    with ThreadPoolExecutor(max_workers=2) as pool: assert list(pool.map(lambda _:start(),range(2)))==[first,first]
    s.publish(first);s.publish(second);s.completed(first);s.completed(second)
    with s.factory() as db:
        assert coverage(db,u1)['coverage_percent']==100
        assert coverage(db,u2)['coverage_percent']==100
        assert db.query(MatchJob).filter_by(active_key=u1).count()==0


def test_redis_duplicate_messages_no_duplicate_history(services):
    s=services;jid,uid=s.seed();s.publish(jid);s.completed(jid)
    with s.factory() as db:
        profile=db.query(CompanyProfile).filter_by(user_id=uid).one();profile.actividades='actividad modificada';db.commit()
        job=request_job(db,uid);db.commit();jid=job.id
        expected=db.query(UserOpportunity).filter_by(user_id=uid).count()
    for _ in range(6):s.publish(jid)
    s.completed(jid)
    with s.factory() as db:
        assert db.query(MatchScoreHistory).filter_by(user_id=uid).count()==expected
        assert db.query(UserOpportunity).filter_by(user_id=uid).count()==expected


def test_redis_cancel_and_warm_restart(services):
    s=services;s.flags(hold=True);jid,uid=s.seed();s.publish(jid);wait(s.entered,15)
    with s.factory() as db:
        started=time.monotonic();cancel_job(db,db.get(MatchJob,jid));db.commit()
        assert time.monotonic()-started<2
    s.flags();s.worker_stop();s.worker_start()
    assert s.state(jid)=='CANCELLED'
    with s.factory() as db:assert db.query(UserOpportunity).filter_by(user_id=uid).count()==0


def test_redis_worker_killed_recovers_expired_slots(services):
    s=services;s.flags(hold=True);jid,uid=s.seed();s.publish(jid);wait(s.entered,15)
    s.worker_stop(hard=True);s.flags();s.worker_start()
    # Expiración real del lease de diez segundos, no cambio manual de reloj/DB.
    with s.factory() as db:until=db.get(MatchJob,jid).lease_until
    wait(lambda:utc_now()>until,15)
    s.application.send_task('app.workers.tasks.rescore_all_task',queue='matches',retry=False)
    s.completed(jid)
    # The coordinator also recovers other users from this module's shared fixture.
    # Their legitimate batches must finish before asserting global slot idleness.
    def globally_idle():
        with s.factory() as db:
            return db.query(MatchJob).filter(MatchJob.state.in_(['PENDING','RUNNING','RETRY'])).count()==0 and db.query(MatchSlot).filter(MatchSlot.token.isnot(None)).count()==0
    wait(globally_idle,20)
    with s.factory() as db:
        assert coverage(db,uid)['coverage_percent']==100
        assert db.query(MatchSlot).filter(MatchSlot.token.isnot(None)).count()==0


def test_redis_loss_broker_restart_and_pending_recovery(services):
    s=services;jid,uid=s.seed();s.redis_stop()
    with pytest.raises(Exception):s.publish(jid)
    assert s.state(jid)=='PENDING'
    s.redis_start()
    wait(lambda:bool(s.application.control.ping(timeout=.5)),25)
    s.application.send_task('app.workers.tasks.rescore_all_task',queue='matches',retry=False)
    s.completed(jid)
    with s.factory() as db:assert coverage(db,uid)['coverage_percent']==100


def test_redis_exhaustion_resume_and_provider_failure(services):
    s=services;s.flags(fail_commit=True);jid,uid=s.seed();s.publish(jid)
    wait(lambda:s.state(jid)=='FAILED',30)
    with s.factory() as db:
        assert db.get(MatchJob,jid).retries==3
        assert db.query(UserOpportunity).filter_by(user_id=uid).count()==0
        resume_job(db,db.get(MatchJob,jid));db.commit()
    s.flags();s.publish(jid);s.completed(jid)
    s.flags(provider_failure=True);jid,uid=s.seed();s.publish(jid);s.completed(jid)
    with s.factory() as db:assert coverage(db,uid)['failed_scores']>0
    s.flags()
