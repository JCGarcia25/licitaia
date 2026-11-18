"""Durable opt-in reminders. A due row is claimed before contacting SMTP.

SMTP acceptance cannot be atomic with PostgreSQL. Ambiguous sends are UNKNOWN,
never retried automatically; a crashed claim is quarantined for user review.
"""
from datetime import datetime,timedelta,timezone
from uuid import uuid4
from email.message import EmailMessage
import smtplib
from sqlalchemy import or_
from app.core.config import get_settings
from app.db.models import OfferClosingReminder as Reminder,OfferProject,Opportunity,User
from app.services.quota import get_subscription,subscription_is_pro

ZONE='America/Bogota'
NO_DATE='No podemos programar este recordatorio porque no encontramos la fecha de cierre del proceso. Consulta el expediente en SECOP; podrás crear la alerta cuando la fecha esté disponible.'

def now():return datetime.now(timezone.utc).replace(tzinfo=None)

def utc(value):
    if value is None:return None
    return value.astimezone(timezone.utc).replace(tzinfo=None) if value.tzinfo else value

def iso(value):return utc(value).isoformat()+'Z' if value else None

def unavailable(db,project,user):
    opp=db.get(Opportunity,project.opportunity_id)
    if not opp or not opp.fecha_cierre:return 'NO_CLOSING_DATE',NO_DATE
    if utc(opp.fecha_cierre)<=now() or opp.cancelled:return 'CLOSED','El plazo del proceso terminó o fue cancelado. No es posible programar un recordatorio de cierre.'
    if project.status in {'archivado','presentado'}:return 'INACTIVE_OFFER','La oferta está archivada o presentada. No se puede programar un recordatorio de cierre.'
    if not subscription_is_pro(get_subscription(db,user)):return 'PRO_REQUIRED','Esta función está disponible con MySECOP Pro.'
    if not user.email_verified:return 'EMAIL_UNVERIFIED','Verifica el correo de tu cuenta antes de programar el recordatorio.'
    if not get_settings().smtp_host:return 'EMAIL_UNAVAILABLE','El servicio de correo no está disponible. Inténtalo más tarde o comunícate con soporte.'
    return None,None

def view(db,project,user):
    code,message=unavailable(db,project,user);r=db.get(Reminder,project.id);opp=db.get(Opportunity,project.opportunity_id)
    reminder={'status':r.status,'scheduled_at':iso(r.scheduled_at),'sent_at':iso(r.sent_at),'retry_at':iso(r.retry_at),'last_error':r.last_error} if r else None
    if reminder and r.status in {'SCHEDULED','RETRY'} and opp and utc(opp.fecha_cierre)!=utc(r.deadline_at):
        reminder.update(status='BLOCKED',last_error='CLOSING_DATE_CHANGED' if opp.fecha_cierre else 'NO_CLOSING_DATE')
    return {'can_schedule':code is None,'can_cancel':bool(r and r.status in {'SCHEDULED','RETRY'}),'reason':code,'message':message,'timezone':ZONE,
            'closing_at':iso(opp.fecha_cierre) if opp else None,'recipient':user.email,'reminder':reminder}

def send(recipient,subject,body):
    """Single recipient. Distinguish known rejection from ambiguous DATA failure."""
    s=get_settings();server=None;started=False
    try:
        server=smtplib.SMTP(s.smtp_host,s.smtp_port,timeout=15)
        server.starttls()
        if s.smtp_user:server.login(s.smtp_user,s.smtp_password)
        msg=EmailMessage();msg.set_content(body);msg['Subject']=subject
        msg['From']=s.alerts_from_email;msg['To']=recipient
        started=True
        refused=server.sendmail(s.alerts_from_email,[recipient],msg.as_bytes())
        return ('FAILED','RECIPIENT_REJECTED') if refused else ('SENT',None)
    except smtplib.SMTPRecipientsRefused:return 'FAILED','RECIPIENT_REJECTED'
    except smtplib.SMTPAuthenticationError:return 'FAILED','EMAIL_CONFIGURATION'
    except smtplib.SMTPDataError as error:
        return ('RETRY','TEMPORARY_REJECTION') if 400<=error.smtp_code<500 else ('FAILED','MESSAGE_REJECTED')
    except Exception:
        return ('UNKNOWN','DELIVERY_UNCONFIRMED') if started else ('RETRY','EMAIL_CONNECTION')
    finally:
        if server:
            try:server.quit()
            except Exception:pass  # A failed QUIT cannot undo confirmed acceptance.

def deliver_due(factory,send_message=None):
    from zoneinfo import ZoneInfo
    if send_message is None:send_message=send
    counts={'sent':0,'blocked':0,'retry':0,'failed':0,'unknown':0};instant=now()
    with factory() as db:
        db.query(Reminder).filter(Reminder.status=='SENDING',Reminder.claimed_at<instant-timedelta(minutes=5)).update(
            {'status':'UNKNOWN','last_error':'DELIVERY_UNCONFIRMED','claim_token':None},synchronize_session=False)
        db.commit()
        due=[identifier for identifier, in db.query(Reminder.project_id).filter(or_((Reminder.status=='SCHEDULED') & (Reminder.scheduled_at<=instant),(Reminder.status=='RETRY') & (Reminder.retry_at<=instant))).order_by(Reminder.scheduled_at,Reminder.project_id).limit(100).all()]
    for identifier in due:
        with factory() as db:
            token=str(uuid4())
            claimed=db.query(Reminder).filter(Reminder.project_id==identifier,or_((Reminder.status=='SCHEDULED') & (Reminder.scheduled_at<=now()),(Reminder.status=='RETRY') & (Reminder.retry_at<=now()))).update(
                {'status':'SENDING','claim_token':token,'claimed_at':now(),'attempts':Reminder.attempts+1},synchronize_session=False)
            db.commit()
            if not claimed:continue
            reminder=db.get(Reminder,identifier);project=db.get(OfferProject,identifier);user=db.get(User,reminder.user_id)
            opp=db.get(Opportunity,project.opportunity_id) if project else None
            error=None
            if not project or not user or project.user_id!=user.id or not user.is_active:error='OFFER_UNAVAILABLE'
            elif not opp or not opp.fecha_cierre:error='NO_CLOSING_DATE'
            elif utc(opp.fecha_cierre)!=utc(reminder.deadline_at):error='CLOSING_DATE_CHANGED'
            elif opp.cancelled or utc(opp.fecha_cierre)<=now():error='PROCESS_CLOSED'
            elif project.status in {'archivado','presentado'}:error='INACTIVE_OFFER'
            elif not user.email_verified or reminder.recipient!=user.email:error='ACCOUNT_EMAIL_CHANGED'
            elif not subscription_is_pro(get_subscription(db,user)):error='PRO_REQUIRED'
            if error:
                reminder.status='BLOCKED';reminder.last_error=error;reminder.claim_token=None;db.commit();counts['blocked']+=1;continue
            recipient=reminder.recipient;attempts=reminder.attempts
            closing=utc(opp.fecha_cierre).replace(tzinfo=timezone.utc).astimezone(ZoneInfo(ZONE)).strftime('%d/%m/%Y a las %H:%M')
            subject='MySECOP — Recordatorio de cierre de tu oferta'
            body=(f'Recordatorio que programaste para tu oferta: {project.name}\n\n'
                  f'Proceso: {opp.objeto or "Proceso sin título"}\nEntidad: {opp.entidad or "Sin información"}\nCierre identificado: {closing} (hora de Colombia).\n\n'
                  'Confirma el plazo y sus modificaciones en el expediente oficial. MySECOP no presenta ofertas ni garantiza la recepción de propuestas.\n'
                  f'Revisa tu oferta: {get_settings().frontend_url.rstrip("/")}/app/ofertas?oferta={identifier}')
            db.rollback()  # No transaction or row lock is held across SMTP.
            if not get_settings().smtp_host:status,error='RETRY','EMAIL_UNAVAILABLE'
            else:
                try:status,error=send_message(recipient,subject,body)
                except Exception:status,error='UNKNOWN','DELIVERY_UNCONFIRMED'
            if status=='RETRY' and attempts>=3:status='FAILED'
            if status=='RETRY':counts['retry']+=1
            elif status=='SENT':counts['sent']+=1
            elif status=='UNKNOWN':counts['unknown']+=1
            else:counts['failed']+=1
            values={'status':status,'last_error':error,'claim_token':None,'updated_at':now()}
            if status=='SENT':values['sent_at']=now()
            if status=='RETRY':values['retry_at']=now()+timedelta(minutes=5)
            db.query(Reminder).filter_by(project_id=identifier,claim_token=token,status='SENDING').update(values,synchronize_session=False)
            db.commit()
    return counts
