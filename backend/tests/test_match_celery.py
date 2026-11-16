"""Worker Celery real con transporte de memoria; Redis opt-in por socket aislado."""
import os
from pathlib import Path
import time
from uuid import uuid4

import pytest
from celery import Celery
from celery.contrib.testing.worker import start_worker
from test_match_jobs import match_factory, prepare
from app.db.models import MatchJob
from app.services import match_jobs as jobs
from app.workers.tasks import process_match_batch

@pytest.mark.parametrize('transport', ['memory', 'redis'])
def test_celery_worker_lotes_y_redelivery(match_factory, monkeypatch, transport):
    broker = 'memory://'
    backend = 'cache+memory://'
    if transport == 'redis':
        broker = os.environ.get('MYSECOP_TEST_REDIS_URL', '')
        if not broker:
            pytest.skip('Redis temporal no disponible; establecer MYSECOP_TEST_REDIS_URL')
        assert broker.startswith('redis+socket:///'), 'Solo socket local descartable'
        path = Path(broker.split('://',1)[1].split('?',1)[0]).resolve()
        assert path.parent.name.startswith('mysecop-test-redis-') and path.name == 'redis.sock'
        backend = broker
    application = Celery(f'mysecop-test-{uuid4().hex}', broker=broker, backend=backend)
    queue = f'mysecop-test-{uuid4().hex}'
    application.conf.update(task_default_queue=queue, worker_prefetch_multiplier=1,
        broker_transport_options={'global_keyprefix':f'{queue}:'},
        result_backend_transport_options={'global_keyprefix':f'{queue}:'})
    application.task(name='app.workers.tasks.process_match_batch')(process_match_batch)
    import app.db.session
    monkeypatch.setattr(app.db.session, 'SessionLocal', match_factory)
    monkeypatch.setattr(jobs, 'enqueue', lambda jid, countdown=0: application.send_task(
        'app.workers.tasks.process_match_batch', args=[jid], queue=queue, countdown=countdown).id)
    uid = prepare(match_factory, 450)
    with match_factory() as db:
        job = jobs.request_job(db, uid); db.commit(); jid = job.id
    with start_worker(application, pool='solo', concurrency=1, queues=[queue], perform_ping_check=False, shutdown_timeout=10):
        one = application.send_task('app.workers.tasks.process_match_batch', args=[jid], queue=queue)
        application.send_task('app.workers.tasks.process_match_batch', args=[jid], queue=queue)
        one.get(timeout=20)
        until = time.monotonic() + 20
        while time.monotonic() < until:
            with match_factory() as db:
                state = db.get(MatchJob, jid).state
                if state == 'COMPLETED':
                    assert jobs.coverage(db, uid)['current_scores'] == 450
                    assert db.get(MatchJob, jid).scored == 450
                    break
            time.sleep(.1)
        else:
            pytest.fail(f'Worker no terminó: {state}')
    application.close()
