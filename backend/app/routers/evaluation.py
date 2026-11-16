"""Allowlisted DEV only; reviewers never receive predictions, strata or peer labels."""
from fastapi import APIRouter,Depends,HTTPException,Request,BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from app.core.security import get_current_user
from app.db.session import get_db
from app.db.models import User,EvaluationCampaign as Campaign,EvaluationAssignment as Assignment,EvaluationReport as Report
from app.evaluation_schemas import CampaignIn,AssignIn,JudgmentIn,GrantIn
from app.services import evaluation_platform as service
from app.services.evaluation_guard import require_environment,EnvironmentDenied

router=APIRouter(prefix='/api/internal/evaluation',tags=['evaluación ciega DEV'])


def preflight(request:Request,db:Session=Depends(get_db)):
    from app.services.evaluation_guard import configured_target,database_identity
    from app.core.config import get_settings
    try:
        configured_target()
        if database_identity(str(db.get_bind().url))!=database_identity(get_settings().database_url):raise EnvironmentDenied('Session differs')
        if str(request.base_url).rstrip('/')!=get_settings().evaluation_api_origin.rstrip('/'):raise EnvironmentDenied('API differs')
    except EnvironmentDenied:raise HTTPException(404,'Destino de evaluación no autorizado')


def access(request:Request,_=Depends(preflight),user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    try:require_environment(db,api_origin=str(request.base_url).rstrip('/'))
    except EnvironmentDenied:raise HTTPException(404,'Evaluación no habilitada para este destino')
    if user.role not in {'admin','evaluation_reviewer'}:raise HTTPException(403,'Personal de evaluación autorizado requerido')
    return user


def admin(user:User=Depends(access)):
    if user.role!='admin':raise HTTPException(403,'Administración privada requerida')
    return user


def translate(fn):
    try:return fn()
    except LookupError:raise HTTPException(404,'Recurso no encontrado')
    except (ValueError,IntegrityError):raise HTTPException(409,'Operación incompatible con permisos, límites o estado sellado')


@router.get('/campaigns')
def campaigns(user:User=Depends(admin),db:Session=Depends(get_db)):
    return [service.summary(db,c) for c in db.query(Campaign).filter_by(owner_user_id=user.id).order_by(Campaign.created_at.desc()).limit(20)]


@router.post('/campaigns',status_code=202)
def create(body:CampaignIn,background:BackgroundTasks,user:User=Depends(admin),db:Session=Depends(get_db)):
    c=translate(lambda:service.create(db,user.id,body));db.commit();background.add_task(service.enqueue,c.id)
    return service.summary(db,c)


@router.get('/campaigns/{identifier}')
def detail(identifier:str,user:User=Depends(admin),db:Session=Depends(get_db)):
    c=translate(lambda:service.owned(db,identifier,user.id));return service.summary(db,c)


@router.post('/campaigns/{identifier}/resume',status_code=202)
def resume(identifier:str,background:BackgroundTasks,user:User=Depends(admin),db:Session=Depends(get_db)):
    c=translate(lambda:service.owned(db,identifier,user.id))
    if c.state not in {'PREPARING','SEMANTICS'}:raise HTTPException(409,'Campaña no reanudable')
    background.add_task(service.enqueue,c.id);return {'id':c.id,'state':c.state}


@router.post('/campaigns/{identifier}/assign',status_code=201)
def assign(identifier:str,body:AssignIn,user:User=Depends(admin),db:Session=Depends(get_db)):
    c=translate(lambda:service.owned(db,identifier,user.id,lock=True));translate(lambda:service.assign(db,c,user.id,body));db.commit();return {'assigned':True}


@router.post('/campaigns/{identifier}/close')
def close(identifier:str,user:User=Depends(admin),db:Session=Depends(get_db)):
    from app.services.evaluation_reporting import close
    c=translate(lambda:service.owned(db,identifier,user.id,lock=True));r=translate(lambda:close(db,c,user.id));db.commit();return {'id':r.id,'version':r.version,'report':r.payload}


@router.get('/campaigns/{identifier}/report')
def report(identifier:str,user:User=Depends(admin),db:Session=Depends(get_db)):
    c=translate(lambda:service.owned(db,identifier,user.id));r=db.query(Report).filter_by(campaign_id=c.id).one_or_none()
    if not r:raise HTTPException(409,'El informe requiere cerrar la campaña y sellar las evaluaciones')
    return {'version':r.version,'report':r.payload}


@router.get('/assignments')
def assignments(user:User=Depends(access),db:Session=Depends(get_db)):
    if user.role!='evaluation_reviewer':raise HTTPException(403,'El administrador no puede autoevaluar')
    # No campaign ID, strata, predictions or other identities in reviewer listing.
    from app.db.models import EvaluationSample as Sample
    from app.services.evaluation_platform import now
    return [{'id':a.id,'kind':a.kind} for a in db.query(Assignment).join(Sample,Sample.id==Assignment.sample_id).join(Campaign,Campaign.id==Sample.campaign_id).filter(Assignment.evaluator_user_id==user.id,Campaign.state=='READY',Campaign.expires_at>now()).limit(200)]


@router.get('/assignments/{identifier}')
def blind(identifier:str,user:User=Depends(access),db:Session=Depends(get_db)):
    if user.role!='evaluation_reviewer':raise HTTPException(403,'Revisor independiente requerido')
    return translate(lambda:service.blind_view(db,identifier,user.id))


@router.post('/assignments/{identifier}/judgments',status_code=201)
def judgment(identifier:str,body:JudgmentIn,user:User=Depends(access),db:Session=Depends(get_db)):
    if user.role!='evaluation_reviewer':raise HTTPException(403,'Revisor independiente requerido')
    row=translate(lambda:service.submit(db,identifier,user.id,body.model_dump()));db.commit()
    return {'id':row.id,'sealed':True,'criteria_version':row.criteria_version}


@router.post('/data-grants',status_code=201)
def grant(body:GrantIn,_=Depends(preflight),user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    row=translate(lambda:service.create_grant(db,user.id,body));db.commit();return {'id':row.id,'expires_at':row.expires_at.isoformat()}


@router.post('/data-grants/{identifier}/revoke')
def revoke(identifier:str,_=Depends(preflight),user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    from app.db.models import EvaluationDataGrant
    require_environment(db)
    row=db.query(EvaluationDataGrant).filter_by(id=identifier,owner_user_id=user.id).with_for_update().one_or_none()
    if not row:raise HTTPException(404,'Autorización no encontrada')
    row.state='REVOKED';service.audit(db,user.id,'revoke',identifier);db.commit();return {'revoked':True}


@router.post('/campaigns/{identifier}/stop-semantics')
def stop_semantics(identifier:str,user:User=Depends(admin),db:Session=Depends(get_db)):
    c=translate(lambda:service.owned(db,identifier,user.id,lock=True))
    if c.state not in {'PREPARING','SEMANTICS'}:raise HTTPException(409,'La preparación ya terminó')
    c.semantic_disabled_at=service.now();service.audit(db,user.id,'semantic_stop',c.id);db.commit()
    return {'stopped':True,'warning':'No inicia nuevas llamadas; una petición ya en vuelo puede haber consumido tokens y se audita.'}
