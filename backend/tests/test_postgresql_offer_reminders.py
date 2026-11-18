"""Real PostgreSQL only via owned disposable runner; no real SMTP."""
import os,subprocess,sys
from datetime import datetime,timedelta
from threading import Event
from concurrent.futures import ThreadPoolExecutor
import pytest
from sqlalchemy import create_engine,inspect,text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.engine import make_url
from app.db.models import OfferClosingReminder as Reminder
from app.services import offer_reminders as service
from app.core.config import get_settings

URL=os.environ.get('MYSECOP_TEST_POSTGRES_URL','')
pytestmark=pytest.mark.skipif(not URL,reason='Requires isolated PostgreSQL runner')

@pytest.fixture(scope='module')
def pg():
    assert make_url(URL).database.startswith('mysecop_test_')
    engine=create_engine(URL);assert not inspect(engine).get_table_names()
    env={**os.environ,'DATABASE_URL':URL,'ENVIRONMENT':'testing'}
    def migrate(action,target):return subprocess.run([sys.executable,'-m','alembic',action,target],env=env,capture_output=True,text=True)
    assert migrate('upgrade','0017_tvec_full_scan').returncode==0
    # 0001 uses current metadata: remove only the new structures in this empty
    # disposable DB to reproduce an actual pre-0018 installation.
    with engine.begin() as c:
        c.execute(text('DROP TABLE offer_closing_reminders'))
        c.execute(text('ALTER TABLE user_opportunities DROP COLUMN is_saved'))
        uid=c.execute(text("INSERT INTO users(email,hashed_password,is_active,email_verified) VALUES('offer-qa@example.com','synthetic',true,true) RETURNING id")).scalar_one()
        oid=c.execute(text("INSERT INTO opportunities(source,source_id,objeto,entidad,estado,cancelled,fecha_cierre) VALUES('qa','offer-qa','Synthetic software','QA','Publicado',false,:closing) RETURNING id"),{'closing':datetime.utcnow()+timedelta(days=3)}).scalar_one()
        c.execute(text("INSERT INTO subscriptions(user_id,plan,status,provider) VALUES(:u,'profesional','activa','test')"),{'u':uid})
        c.execute(text("INSERT INTO user_opportunities(user_id,opportunity_id,score,triage) VALUES(:u,:o,81,'guardada')"),{'u':uid,'o':oid})
        pid=c.execute(text("INSERT INTO offer_projects(user_id,opportunity_id,name,status) VALUES(:u,:o,'Synthetic offer','activo') RETURNING id"),{'u':uid,'o':oid}).scalar_one()
    result=migrate('upgrade','head');assert result.returncode==0,result.stderr
    yield engine,sessionmaker(bind=engine),uid,pid,oid,migrate
    engine.dispose()

def test_pg_legacy_saved_migration_and_empty_round_trip(pg):
    engine,factory,uid,pid,oid,migrate=pg
    with engine.connect() as c:
        assert c.execute(text('SELECT is_saved FROM user_opportunities WHERE user_id=:u'),{'u':uid}).scalar_one() is True
        assert c.execute(text('SELECT score FROM user_opportunities WHERE user_id=:u'),{'u':uid}).scalar_one()==81
    assert migrate('downgrade','0017_tvec_full_scan').returncode==0
    assert migrate('upgrade','head').returncode==0

def test_pg_two_workers_do_not_send_twice_and_populated_downgrade_blocked(pg,monkeypatch):
    engine,factory,uid,pid,oid,migrate=pg;monkeypatch.setattr(get_settings(),'smtp_host','synthetic.invalid')
    with factory() as db:
        closing=db.execute(text('SELECT fecha_cierre FROM opportunities WHERE id=:o'),{'o':oid}).scalar_one()
        db.add(Reminder(project_id=pid,user_id=uid,scheduled_at=service.now()-timedelta(minutes=1),deadline_at=closing,recipient='offer-qa@example.com',status='SCHEDULED',attempts=0));db.commit()
    entered=Event();release=Event();sent=[]
    def mail(*args):sent.append(args);entered.set();assert release.wait(10);return 'SENT',None
    with ThreadPoolExecutor(max_workers=2) as pool:
        first=pool.submit(service.deliver_due,factory,mail);assert entered.wait(10)
        second=pool.submit(service.deliver_due,factory,mail);assert second.result(timeout=10)['sent']==0
        # The first connection is not holding a row lock over SMTP.
        with factory() as db:
            db.execute(text("SET LOCAL lock_timeout='500ms'"));db.execute(text('UPDATE opportunities SET entidad=entidad WHERE id=:o'),{'o':oid});db.commit()
        release.set();assert first.result(timeout=10)['sent']==1
    assert len(sent)==1
    result=migrate('downgrade','0017_tvec_full_scan');assert result.returncode!=0 and 'populated downgrade forbidden' in result.stderr
    with factory() as db:assert db.get(Reminder,pid).status=='SENT'
