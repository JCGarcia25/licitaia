"""Owner-scoped reminder management, independent of global alert preferences."""
from datetime import datetime,timezone
from fastapi import APIRouter,Depends,HTTPException
from pydantic import BaseModel,field_validator
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from app.core.security import get_current_user
from app.db.session import get_db
from app.db.models import OfferProject,OfferClosingReminder as Reminder,Opportunity,User
from app.services import offer_reminders as service

router=APIRouter(prefix='/api/offer-projects',tags=['recordatorios de ofertas'])
class ScheduleIn(BaseModel):
    scheduled_at:datetime
    @field_validator('scheduled_at')
    @classmethod
    def require_offset(cls,value):
        if value.utcoffset() is None:raise ValueError('Indica la zona horaria del envío')
        return value

def own(db,project_id,user):
    p=db.query(OfferProject).filter_by(id=project_id,user_id=user.id).first()
    if not p:raise HTTPException(404,'Oferta no encontrada')
    return p

@router.get('/{project_id}/closing-reminder')
def get_reminder(project_id:int,user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    return service.view(db,own(db,project_id,user),user)

@router.put('/{project_id}/closing-reminder')
def schedule(project_id:int,body:ScheduleIn,user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    p=own(db,project_id,user);code,message=service.unavailable(db,p,user)
    if code:raise HTTPException(409 if code not in {'EMAIL_UNAVAILABLE','PRO_REQUIRED'} else 503 if code=='EMAIL_UNAVAILABLE' else 402,detail={'code':code,'message':message})
    when=service.utc(body.scheduled_at);closing=service.utc(db.get(Opportunity,p.opportunity_id).fecha_cierre)
    if not service.now()<when<closing:raise HTTPException(422,'Elige una fecha y hora futuras, anteriores al cierre del proceso.')
    row=db.query(Reminder).filter_by(project_id=project_id).with_for_update().first()
    if row and row.status=='SENDING':raise HTTPException(409,'El recordatorio se está enviando. Espera unos minutos antes de modificarlo.')
    if row is None:row=Reminder(project_id=p.id,user_id=user.id);db.add(row)
    if row.status=='SCHEDULED' and service.utc(row.scheduled_at)==when and service.utc(row.deadline_at)==closing and row.recipient==user.email:
        return service.view(db,p,user)
    row.scheduled_at=when;row.deadline_at=closing;row.recipient=user.email
    row.status='SCHEDULED';row.attempts=0;row.claimed_at=None;row.claim_token=None;row.sent_at=None;row.last_error=None;row.retry_at=None
    try:db.commit()
    except IntegrityError:
        db.rollback();raise HTTPException(409,'Otro cambio acaba de actualizar este recordatorio. Vuelve a abrirlo.')
    return service.view(db,p,user)

@router.delete('/{project_id}/closing-reminder')
def cancel(project_id:int,user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    p=own(db,project_id,user);row=db.query(Reminder).filter_by(project_id=p.id).with_for_update().first()
    if row and row.status=='SENDING':raise HTTPException(409,'El recordatorio ya se está enviando y no puede cancelarse en este momento.')
    if row and row.status in {'SCHEDULED','RETRY'}:row.status='CANCELLED';row.claim_token=None;db.commit()
    return service.view(db,p,user)
