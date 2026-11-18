"""Real Celery/Redis/PostgreSQL; mailbox capture is test-only."""
import json,os
from datetime import timedelta
from uuid import uuid4
import pytest
from app.db.models import User,Subscription,Opportunity,OfferProject,OfferClosingReminder as Reminder
from app.services.offer_reminders import now
from test_redis_operations import services,wait
pytestmark=pytest.mark.skipif(not os.environ.get('MYSECOP_TEST_POSTGRES_URL') or not os.environ.get('MYSECOP_RUN_REDIS_TESTS'),reason='Requires isolated PG/Redis')

def test_real_worker_duplicate_delivery_and_future_schedule(services):
    s=services;mailbox=s.directory/'reminder-mailbox.jsonl'
    s.worker_stop();s.worker_start(queues='celery',extra_env={'MYSECOP_OFFER_REMINDER_MAILBOX':str(mailbox),'SMTP_HOST':'synthetic.invalid'})
    with s.factory() as db:
        u=User(email=uuid4().hex+'@example.com',hashed_password='synthetic-only',email_verified=True,is_active=True);db.add(u);db.flush()
        db.add(Subscription(user_id=u.id,plan='profesional',status='activa',provider='test'))
        o=Opportunity(source='qa',source_id=uuid4().hex,objeto='Synthetic offer',entidad='QA',fecha_cierre=now()+timedelta(days=3),cancelled=False);db.add(o);db.flush()
        p=OfferProject(user_id=u.id,opportunity_id=o.id,name='Synthetic offer',status='activo');db.add(p);db.flush();pid=p.id
        db.add(Reminder(project_id=pid,user_id=u.id,scheduled_at=now()+timedelta(days=1),deadline_at=o.fecha_cierre,recipient=u.email,status='SCHEDULED',attempts=0));db.commit()
    first=s.application.send_task('app.workers.tasks.deliver_offer_reminders',queue='celery');first.get(timeout=15)
    assert not mailbox.exists()
    with s.factory() as db:db.get(Reminder,pid).scheduled_at=now()-timedelta(seconds=1);db.commit()
    a=s.application.send_task('app.workers.tasks.deliver_offer_reminders',queue='celery');b=s.application.send_task('app.workers.tasks.deliver_offer_reminders',queue='celery')
    a.get(timeout=20);b.get(timeout=20)
    rows=[json.loads(x) for x in mailbox.read_text().splitlines()]
    assert len(rows)==1 and 'Cierre identificado' in rows[0]['body']
    with s.factory() as db:assert db.get(Reminder,pid).status=='SENT'
