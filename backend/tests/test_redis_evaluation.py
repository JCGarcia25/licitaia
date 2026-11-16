import os
from uuid import uuid4
import pytest
from app.core.config import get_settings
from app.db.models import EvaluationEnvironmentIdentity as Identity,EvaluationCampaign as Campaign,EvaluationSample as Sample,UserOpportunity
from app.services.evaluation_guard import destination
from app.services.match_versions import digest
from app.services import evaluation_platform as p
from test_redis_operations import services,wait
from test_evaluation_platform import body

pytestmark=pytest.mark.skipif(not os.environ.get('MYSECOP_TEST_POSTGRES_URL') or not os.environ.get('MYSECOP_RUN_REDIS_TESTS'),reason='Disposable PG/Redis runner required')


def test_real_evaluation_queue_replay_and_broker_isolation(services,monkeypatch):
    import json
    s=services;settings=get_settings();url=os.environ['MYSECOP_TEST_POSTGRES_URL']
    monkeypatch.setattr(settings,'database_url',url);monkeypatch.setattr(settings,'redis_url',s.broker);monkeypatch.setattr(settings,'evaluation_enabled',True);monkeypatch.setattr(settings,'evaluation_api_origin','http://isolated.local')
    identity=str(uuid4());targets=[{'database':url,'broker':s.broker,'api_origin':settings.evaluation_api_origin,'identity':identity}]
    monkeypatch.setattr(settings,'evaluation_dev_targets',targets)
    jid,uid=s.seed(1)
    with s.factory() as db:
        db.add(Identity(id=identity,fingerprint=digest(destination(settings)),purpose='isolated-development'));db.commit()
        c=p.create(db,uid,body(12));db.commit();cid=c.id
    s.worker_stop();s.worker_start(queues='evaluation',extra_env={'EVALUATION_ENABLED':'true','EVALUATION_API_ORIGIN':settings.evaluation_api_origin,'EVALUATION_DEV_TARGETS':json.dumps(targets)})
    for _ in range(3):s.application.send_task('app.workers.tasks.process_evaluation_campaign',args=[cid],queue='evaluation')
    def ready():
        with s.factory() as db:return db.get(Campaign,cid).state=='READY'
    wait(ready,30)
    with s.factory() as db:
        assert db.query(Sample).filter_by(campaign_id=cid).count()==12
        assert db.query(UserOpportunity).filter_by(user_id=uid).count()==0
    s.worker_stop();s.redis_stop();s.redis_start()
    s.worker_start(queues='evaluation',extra_env={'EVALUATION_ENABLED':'true','EVALUATION_API_ORIGIN':settings.evaluation_api_origin,'EVALUATION_DEV_TARGETS':json.dumps(targets)})
    result=s.application.send_task('app.workers.tasks.process_evaluation_campaign',args=[cid],queue='evaluation')
    wait(lambda:result.ready(),15);assert result.get(timeout=2)=='BUSY_OR_FINISHED'
    # Kill a real worker during calculation, then resume from durable cursor.
    s.flags(evaluation_hold=True)
    with s.factory() as db:
        interrupted=p.create(db,uid,body(12));db.commit();interrupted_id=interrupted.id
    s.application.send_task('app.workers.tasks.process_evaluation_campaign',args=[interrupted_id],queue='evaluation')
    wait(s.entered,15);s.worker_stop(hard=True);s.flags()
    from datetime import timedelta
    with s.factory() as db:
        row=db.get(Campaign,interrupted_id);assert row.cursor==0
        assert db.query(Sample).filter_by(campaign_id=interrupted_id).count()==0
        # Lease expiry is advanced in the disposable DB to avoid a 120s wait.
        row.lease_until=p.now()-timedelta(seconds=1);db.commit()
    s.worker_start(queues='evaluation',extra_env={'EVALUATION_ENABLED':'true','EVALUATION_API_ORIGIN':settings.evaluation_api_origin,'EVALUATION_DEV_TARGETS':json.dumps(targets)})
    s.application.send_task('app.workers.tasks.process_evaluation_campaign',args=[interrupted_id],queue='evaluation')
    def resumed():
        with s.factory() as db:return db.get(Campaign,interrupted_id).state=='READY'
    wait(resumed,30)
    with s.factory() as db:
        assert db.query(Sample).filter_by(campaign_id=interrupted_id).count()==12
        assert db.query(UserOpportunity).filter_by(user_id=uid).count()==0
