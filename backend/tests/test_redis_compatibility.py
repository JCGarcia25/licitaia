"""Production V2 task in a real isolated Celery process, Redis and PostgreSQL."""
import os
import pytest
from app.core.config import get_settings
from app.db.models import CompatibilityShadowRun as Run,CompatibilityShadowResult as Result,UserOpportunity
from app.services import compatibility_shadow as shadow
from test_redis_operations import services, wait

pytestmark=pytest.mark.skipif(not os.environ.get('MYSECOP_TEST_POSTGRES_URL') or not os.environ.get('MYSECOP_RUN_REDIS_TESTS'),reason='Requires isolated PG/Redis runner')


def test_real_shadow_queue_duplicate_resume_and_legacy_isolation(services,monkeypatch):
    s=services
    monkeypatch.setattr(get_settings(),'compatibility_v2_shadow_enabled',True)
    from evaluation_test_support import authorize
    import json
    with s.factory() as db:target=authorize(db,monkeypatch,database=os.environ['MYSECOP_TEST_POSTGRES_URL'],broker=s.broker,origin='http://isolated.local')
    environment={'EVALUATION_DEV_TARGETS':json.dumps([target]),'EVALUATION_API_ORIGIN':target['api_origin']}
    jid,uid=s.seed(6)
    s.worker_stop();s.worker_start(queues='compatibility-shadow',extra_env={**environment,'COMPATIBILITY_V2_SHADOW_ENABLED':'true','COMPATIBILITY_V2_BATCH_SIZE':'2'})
    with s.factory() as db:
        run=shadow.create_run(db,uid,6);db.commit();rid=run.id
    for _ in range(3):s.application.send_task('app.workers.tasks.process_compatibility_shadow',args=[rid],queue='compatibility-shadow')
    def done():
        with s.factory() as db:return db.get(Run,rid).state=='COMPLETED'
    wait(done,30)
    with s.factory() as db:
        assert db.get(Run,rid).cursor==6
        assert db.query(Result).filter_by(run_id=rid).count()==6
        assert db.query(UserOpportunity).filter_by(user_id=uid).count()==0
    s.worker_stop();s.redis_stop();s.redis_start()
    s.worker_start(queues='compatibility-shadow',extra_env={**environment,'COMPATIBILITY_V2_SHADOW_ENABLED':'true'})
    result=s.application.send_task('app.workers.tasks.process_compatibility_shadow',args=[rid],queue='compatibility-shadow')
    wait(lambda:result.ready(),15)
    assert result.get(timeout=2)=='BUSY_OR_FINISHED'
    # Flag off in a new worker: existing calculation state and legacy queue remain untouched.
    s.worker_stop();s.worker_start(queues='compatibility-shadow',extra_env={**environment,'COMPATIBILITY_V2_SHADOW_ENABLED':'false'})
    result=s.application.send_task('app.workers.tasks.process_compatibility_shadow',args=[rid],queue='compatibility-shadow')
    wait(lambda:result.ready(),15);assert result.get(timeout=2)=='DISABLED'
