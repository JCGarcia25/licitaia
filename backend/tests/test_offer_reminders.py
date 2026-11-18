"""API and delivery tests; synthetic mailbox, never sends real mail."""
from datetime import datetime,timedelta
from uuid import uuid4
import pytest
from app.db.models import User,Opportunity,OfferProject,OfferClosingReminder as Reminder,Subscription
from app.core.config import get_settings
from app.services import offer_reminders as service

@pytest.fixture
def offer(client,db,auth_headers,monkeypatch):
    u=db.query(User).filter_by(email=client.get('/api/auth/me',headers=auth_headers).json()['email']).one();u.email_verified=True
    db.add(Subscription(user_id=u.id,plan='profesional',status='activa',provider='test'))
    t=datetime(2026,12,1,12);monkeypatch.setattr(service,'now',lambda:t);monkeypatch.setattr(get_settings(),'smtp_host','synthetic.invalid')
    o=Opportunity(source='qa',source_id=uuid4().hex,objeto='Software QA',entidad='Entidad QA',estado='Publicado',fecha_cierre=t+timedelta(days=3),cancelled=False)
    db.add(o);db.flush();p=OfferProject(user_id=u.id,opportunity_id=o.id,name='Oferta QA',status='activo');db.add(p);db.commit()
    return p,o,u,t,auth_headers

def path(p):return f'/api/offer-projects/{p.id}/closing-reminder'
def request_at(t):return {'scheduled_at':(t+timedelta(days=1)).isoformat()+'Z'}
def due(p,u,t,db):
    db.add(Reminder(project_id=p.id,user_id=u.id,scheduled_at=t-timedelta(minutes=1),deadline_at=t+timedelta(days=3),recipient=u.email,status='SCHEDULED',attempts=0));db.commit()

def test_missing_closing_date_explained_and_never_scheduled(offer,client,db):
    p,o,u,t,h=offer;o.fecha_cierre=None;db.commit()
    v=client.get(path(p),headers=h).json();assert not v['can_schedule'] and v['reason']=='NO_CLOSING_DATE'
    assert 'no encontramos la fecha de cierre' in v['message']
    assert client.put(path(p),headers=h,json=request_at(t)).status_code==409 and db.get(Reminder,p.id) is None

def test_schedule_timezone_idempotence_reload_edit_cancel(offer,client,db):
    p,o,u,t,h=offer;body={'scheduled_at':'2026-12-02T09:30:00-05:00'}
    for _ in range(2):
        r=client.put(path(p),headers=h,json=body);assert r.status_code==200,r.text
        assert r.json()['reminder']['scheduled_at']=='2026-12-02T14:30:00Z'
    assert db.query(Reminder).filter_by(project_id=p.id).count()==1
    assert client.get(path(p),headers=h).json()['recipient']==u.email
    assert client.delete(path(p),headers=h).json()['reminder']['status']=='CANCELLED'
    assert client.put(path(p),headers=h,json=request_at(t)).json()['reminder']['status']=='SCHEDULED'

@pytest.mark.parametrize('value',['2026-12-01T11:00:00Z','2026-12-04T12:00:00Z','2026-12-05T12:00:00Z','2026-12-02T12:00:00'])
def test_invalid_times_rejected(offer,client,value):
    p,o,u,t,h=offer;assert client.put(path(p),headers=h,json={'scheduled_at':value}).status_code==422

def test_other_user_cannot_read_update_cancel(offer,client):
    p,o,u,t,h=offer;r=client.post('/api/auth/register',json={'email':f'{uuid4().hex}@example.com','password':'SyntheticPassword123','full_name':'Other QA'})
    other={'Authorization':'Bearer '+r.json()['access_token']}
    for method,kw in [('get',{}),('put',{'json':request_at(t)}),('delete',{})]:assert getattr(client,method)(path(p),headers=other,**kw).status_code==404
    assert client.get(path(p)).status_code==401

def test_due_delivery_once_and_message(offer,db):
    p,o,u,t,h=offer;due(p,u,t,db);sent=[];from app.db.session import SessionLocal
    def mail(to,subject,body):sent.append((to,subject,body));return 'SENT',None
    assert service.deliver_due(SessionLocal,mail)['sent']==1
    assert service.deliver_due(SessionLocal,mail)['sent']==0 and len(sent)==1
    db.expire_all();assert db.get(Reminder,p.id).status=='SENT'
    assert 'hora de Colombia' in sent[0][2] and f'oferta={p.id}' in sent[0][2]

@pytest.mark.parametrize('change,expected',[('no_date','NO_CLOSING_DATE'),('changed','CLOSING_DATE_CHANGED'),('closed','PROCESS_CLOSED'),('archived','INACTIVE_OFFER')])
def test_revalidate_before_send(offer,db,change,expected):
    p,o,u,t,h=offer;due(p,u,t,db)
    if change=='no_date':o.fecha_cierre=None
    elif change=='changed':o.fecha_cierre+=timedelta(hours=1)
    elif change=='closed':o.cancelled=True
    else:p.status='archivado'
    db.commit();from app.db.session import SessionLocal
    def forbidden(*a):pytest.fail('Must not send')
    assert service.deliver_due(SessionLocal,forbidden)['blocked']==1
    db.expire_all();assert db.get(Reminder,p.id).last_error==expected

def test_uncertain_delivery_and_crash_not_resent(offer,db):
    p,o,u,t,h=offer;due(p,u,t,db);from app.db.session import SessionLocal
    assert service.deliver_due(SessionLocal,lambda *a:('UNKNOWN','DELIVERY_UNCONFIRMED'))['unknown']==1
    assert service.deliver_due(SessionLocal,lambda *a:pytest.fail('No resend'))['sent']==0
    db.expire_all();r=db.get(Reminder,p.id);r.status='SENDING';r.claimed_at=t-timedelta(minutes=6);r.claim_token='old';db.commit()
    service.deliver_due(SessionLocal,lambda *a:pytest.fail('No resend after crash'))
    db.expire_all();assert db.get(Reminder,p.id).status=='UNKNOWN'

def test_temporary_failure_bounded_keeps_user_time(offer,db,monkeypatch):
    p,o,u,t,h=offer;due(p,u,t,db);from app.db.session import SessionLocal
    for i in range(3):
        monkeypatch.setattr(service,'now',lambda i=i:t+timedelta(minutes=6*i))
        service.deliver_due(SessionLocal,lambda *a:('RETRY','EMAIL_CONNECTION'))
    db.expire_all();r=db.get(Reminder,p.id)
    assert r.status=='FAILED' and r.attempts==3 and r.scheduled_at==t-timedelta(minutes=1)

def test_not_due_and_mail_not_configured(offer,client,db,monkeypatch):
    p,o,u,t,h=offer;assert client.put(path(p),headers=h,json=request_at(t)).status_code==200
    from app.db.session import SessionLocal
    assert service.deliver_due(SessionLocal,lambda *a:pytest.fail('Not due'))['sent']==0
    monkeypatch.setattr(get_settings(),'smtp_host','')
    assert client.put(path(p),headers=h,json=request_at(t)).status_code==503

def test_celery_minute_schedule():
    from app.workers.celery_app import celery_app
    assert celery_app.conf.beat_schedule['offer-closing-reminders-every-minute']['schedule']==60

@pytest.mark.parametrize('mode,expected',[('connect','RETRY'),('data_disconnect','UNKNOWN'),('refused','FAILED'),('accepted_quit_failure','SENT')])
def test_smtp_acceptance_and_ambiguity(monkeypatch,mode,expected):
    import smtplib
    class FakeSMTP:
        def __init__(self,*a,**kw):
            if mode=='connect':raise OSError('synthetic connect')
        def starttls(self):pass
        def login(self,*a):pass
        def sendmail(self,*a):
            if mode=='data_disconnect':raise smtplib.SMTPServerDisconnected('synthetic after DATA')
            if mode=='refused':raise smtplib.SMTPRecipientsRefused({'synthetic@example.com':(550,b'no')})
            return {}
        def quit(self):raise OSError('synthetic QUIT')
    monkeypatch.setattr(service.smtplib,'SMTP',FakeSMTP)
    assert service.send('synthetic@example.com','QA','Synthetic fixture')[0]==expected
