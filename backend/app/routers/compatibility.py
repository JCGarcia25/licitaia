"""Internal own-user diagnostics, unavailable by default and in production."""
from typing import Literal
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, field_validator
from app.compatibility_schemas import ShadowRunOut
from sqlalchemy.orm import Session
from app.core.config import get_settings
from app.core.security import get_current_user
from app.db.session import get_db
from app.db.models import User, Document, CompatibilityEvidenceProfile as Evidence, CompatibilityShadowRun as Run
from app.services import compatibility_shadow as shadow
from app.services.match_versions import digest

router=APIRouter(prefix='/api/internal/compatibility-v2',tags=['compatibilidad experimental privada'])


def shadow_preflight(request:Request,db:Session=Depends(get_db)):
    from app.services.evaluation_guard import require_environment,EnvironmentDenied
    if not shadow.enabled():raise HTTPException(404,'Diagnóstico no disponible')
    try:require_environment(db,api_origin=str(request.base_url).rstrip('/'),allow_shadow=True)
    except EnvironmentDenied:raise HTTPException(404,'Destino de diagnóstico no autorizado')


def authorized(_=Depends(shadow_preflight),user: User=Depends(get_current_user)):
    if user.role!='admin':raise HTTPException(403,'Diagnóstico reservado a administradores en DEV')
    return user


class Fact(BaseModel):
    model_config=ConfigDict(extra='forbid',allow_inf_nan=False)
    key: str=Field(min_length=1,max_length=150)
    value: str|float|bool
    unit: str|None=Field(default=None,max_length=40)
    level: Literal['DECLARED','STRUCTURED']='STRUCTURED'
    category: Literal['experience','financial','technical','certification','operational']='experience'

    @field_validator('value')
    @classmethod
    def bounded_value(cls, value):
        if isinstance(value,str) and len(value)>2000:raise ValueError('Value exceeds diagnostic limit')
        return value


class EvidenceIn(BaseModel):
    model_config=ConfigDict(extra='forbid')
    facts: list[Fact]=Field(default_factory=list,max_length=100)


class RunIn(BaseModel):
    model_config=ConfigDict(extra='forbid')
    limit: int=Field(default=20,ge=1,le=100)


@router.get('/runs')
def runs(user:User=Depends(authorized),db:Session=Depends(get_db)):
    return [{'id':r.id,'state':r.state,'processed':r.cursor,'total':len(r.snapshot['candidates'])} for r in db.query(Run).filter_by(user_id=user.id).order_by(Run.created_at.desc()).limit(20)]


@router.post('/runs',status_code=202,response_model=ShadowRunOut)
def create(body:RunIn,background:BackgroundTasks,user:User=Depends(authorized),db:Session=Depends(get_db)):
    try:run=shadow.create_run(db,user.id,body.limit)
    except ValueError as exc:raise HTTPException(409,str(exc))
    db.commit(); background.add_task(shadow.enqueue,run.id)
    return shadow.diagnostic(db,run)


def owned(db,identifier,user):
    run=db.query(Run).filter_by(id=identifier,user_id=user.id).one_or_none()
    if run is None:raise HTTPException(404,'Ejecución no encontrada')
    return run


@router.get('/runs/{identifier}',response_model=ShadowRunOut)
def result(identifier:str,user:User=Depends(authorized),db:Session=Depends(get_db)):
    return shadow.diagnostic(db,owned(db,identifier,user))


@router.post('/runs/{identifier}/resume',status_code=202,response_model=ShadowRunOut)
def resume(identifier:str,background:BackgroundTasks,user:User=Depends(authorized),db:Session=Depends(get_db)):
    run=owned(db,identifier,user)
    if run.state not in {'PENDING','RUNNING'}:raise HTTPException(409,'Ejecución terminada; crear nueva muestra')
    background.add_task(shadow.enqueue,run.id)
    return shadow.diagnostic(db,run)


@router.post('/evidence',status_code=201)
def evidence(body:EvidenceIn,user:User=Depends(authorized),db:Session=Depends(get_db)):
    payload=body.model_dump()
    previous=db.query(Evidence).filter_by(user_id=user.id).order_by(Evidence.id.desc()).first()
    if previous and previous.payload.get('observations'):payload['observations']=previous.payload['observations']
    row=Evidence(user_id=user.id,payload=payload,version=digest(payload))
    db.add(row);db.commit()
    return {'id':row.id,'version':row.version,'warning':'Declaración estructurada sin verificación documental o jurídica'}


@router.post('/documents/{document_id}/extract')
def document(document_id:int,user:User=Depends(authorized),db:Session=Depends(get_db)):
    from app.services.compatibility_documents import extract
    doc=db.query(Document).filter_by(id=document_id,user_id=user.id).one_or_none()
    if doc is None:raise HTTPException(404,'Documento no encontrado')
    try:payload=extract(doc,get_settings().storage_dir)
    except (ValueError,OSError):raise HTTPException(422,'Documento ilegible o fuera de límites de diagnóstico')
    previous=db.query(Evidence).filter_by(user_id=user.id).order_by(Evidence.id.desc()).first()
    snapshot=dict(previous.payload) if previous else {'facts':[]}
    observations=[o for o in snapshot.get('observations',[]) if o.get('source_ref',{}).get('document_id')!=doc.id]
    snapshot['observations']=(observations+payload['observations'])[-100:]
    row=Evidence(user_id=user.id,payload=snapshot,version=digest(snapshot));db.add(row);db.commit()
    return payload


@router.get('/runs/{identifier}/evaluation')
def export_evaluation(identifier:str,user:User=Depends(authorized),db:Session=Depends(get_db)):
    run=owned(db,identifier,user)
    try:return shadow.evaluation_export(db,run)
    except ValueError as exc:raise HTTPException(409,str(exc))
