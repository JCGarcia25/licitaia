"""Authenticated public purchase intelligence, separate from SECOP candidates."""
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from time import perf_counter
import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import String, func, or_
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.db.models import TvecPurchaseOrder as Order, TvecSourceMetadata as Metadata, TvecSyncState as State
from app.db.session import get_db
from app.services.tvec_client import DATASET, SOURCE_URL
from app.services.tvec_guard import configuration, require_target
from app.services.evaluation_guard import EnvironmentDenied

logger=logging.getLogger('mysecop.tvec.api')
router=APIRouter(prefix='/api/tvec',tags=['TVEC · compras registradas'])


def preflight():
    try:configuration()
    except EnvironmentDenied:raise HTTPException(404,'TVEC no habilitada en este ambiente')


def access(request:Request,_=Depends(preflight),user=Depends(get_current_user),db:Session=Depends(get_db)):
    try:require_target(db,origin=str(request.base_url).rstrip('/'))
    except EnvironmentDenied:raise HTTPException(404,'Destino TVEC no autorizado')
    return user


router.dependencies=[Depends(access)]


def filters(q:str|None=Query(None,max_length=200),buyer:str|None=Query(None,max_length=500),
            supplier:str|None=Query(None,max_length=500),instrument:str|None=Query(None,max_length=500),
            category:str|None=Query(None,max_length=500),department:str|None=Query(None,max_length=255),
            city:str|None=Query(None,max_length=255),status:str|None=Query(None,max_length=255),
            amount_min:Decimal|None=Query(None,ge=Decimal('-1e23'),le=Decimal('1e23')),
            amount_max:Decimal|None=Query(None,ge=Decimal('-1e23'),le=Decimal('1e23')),
            date_from:date|None=None,date_to:date|None=None):
    if amount_min is not None and amount_max is not None and amount_min>amount_max:raise HTTPException(422,'Rango de valor inválido')
    if date_from and date_to and date_from>date_to:raise HTTPException(422,'Periodo inválido')
    conditions=[]
    if q:
        value=q.replace('\\','\\\\').replace('%','\\%').replace('_','\\_')
        conditions.append(or_(*[c.ilike('%'+value+'%',escape='\\') for c in [Order.official_id,Order.description,Order.buyer,Order.supplier]]))
    for name,value in [('buyer',buyer),('supplier',supplier),('instrument',instrument),('category',category),('department',department),('city',city),('status',status)]:
        if value is not None:conditions.append(getattr(Order,name)==value)
    if amount_min is not None:conditions.append(Order.amount>=amount_min)
    if amount_max is not None:conditions.append(Order.amount<=amount_max)
    if date_from:conditions.append(Order.issued_at>=datetime.combine(date_from,time.min))
    if date_to:conditions.append(Order.issued_at<=datetime.combine(date_to,time.max))
    return conditions


def provenance(db):
    m=db.get(Metadata,DATASET);s=db.get(State,DATASET)
    count=db.query(func.count(Order.id)).scalar()
    return {'source':'TVEC','dataset_id':DATASET,'source_url':SOURCE_URL,'unit':'PURCHASE_ORDER',
        'usage':'HISTORICAL_MARKET_INTELLIGENCE','participation':'NOT_DETERMINED',
        'currency':None,'currency_note':'La fuente no informa moneda; no comparar ni interpretar como COP sin verificación.',
        'source_updated_at':m.source_updated_at if m else None,'metadata_checked_at':m.checked_at if m else None,
        'last_complete_at':s.last_complete_at if s else None,'local_orders':count,
        'source_count_at_check':m.source_count if m else None,'cycle_rows':s.cycle_rows if s else 0,
        'coverage_status':'HAS_HISTORICAL_COMPLETE_SCAN' if s and s.last_complete_at else 'PARTIAL_OR_NOT_SYNCED',
        'coverage_note':'Indicadores sólo sobre órdenes almacenadas; no son cobertura de oportunidades SECOP ni garantizan demanda futura.',
        'freshness_note':'Frecuencia declarada diaria; comprobar fecha real de actualización.'}


def serialize(row):
    fields=['id','official_id','buyer','supplier','description','instrument','category','department','city',
            'amount','currency','issued_at','expires_at','initial_request_at','status','official_url','synced_at','version']
    result={key:getattr(row,key) for key in fields}
    result['amount']=str(row.amount) if row.amount is not None else None
    result.update(source='TVEC',record_type='PURCHASE_ORDER',participation='NOT_DETERMINED',source_url=SOURCE_URL)
    return result # no requesting person, raw JSON, NITs, or private user data


@router.get('/orders')
def orders(db:Session=Depends(get_db),conditions=Depends(filters),limit:int=Query(20,ge=1,le=50),offset:int=Query(0,ge=0,le=100000)):
    started=perf_counter();query=db.query(Order).filter(*conditions)
    total=query.count();items=query.order_by(Order.issued_at.desc().nullslast(),Order.official_id.asc()).offset(offset).limit(limit).all()
    elapsed=round((perf_counter()-started)*1000,3)
    logger.info('tvec_list duration_ms=%.3f rows=%d',elapsed,len(items))
    return {'items':[serialize(row) for row in items],'total':total,'limit':limit,'offset':offset,
            'provenance':provenance(db),'query_ms':elapsed}


@router.get('/orders/{identifier}')
def detail(identifier:int,db:Session=Depends(get_db)):
    row=db.get(Order,identifier)
    if row is None:raise HTTPException(404,'Orden de compra no encontrada')
    return {'order':serialize(row),'provenance':provenance(db)}


@router.get('/summary')
def summary(db:Session=Depends(get_db),conditions=Depends(filters)):
    query=db.query(Order).filter(*conditions)
    count,valued,buyers,suppliers=query.with_entities(func.count(Order.id),func.count(Order.amount),func.count(func.distinct(Order.buyer)),func.count(func.distinct(Order.supplier))).one()
    # Unknown currency -> deliberately no monetary sum or financial trend.
    period=func.substr(func.cast(Order.issued_at,String),1,7)
    periods=query.with_entities(period,func.count(Order.id)).filter(Order.issued_at.isnot(None)).group_by(period).order_by(period.desc()).limit(12).all()
    return {'orders':count,'orders_with_value':valued,'buyers':buyers,'suppliers':suppliers,
            'monetary_total':None,'monetary_total_reason':'MONEDA_NO_INFORMADA',
            'periods':[{'period':p,'orders':n} for p,n in periods],'provenance':provenance(db)}


def groups(db,conditions,column,limit,offset):
    query=db.query(column.label('name'),func.count(Order.id).label('orders'),func.min(Order.issued_at).label('first_order'),func.max(Order.issued_at).label('last_order'),func.count(func.distinct(Order.buyer)).label('buyers'),func.count(func.distinct(Order.supplier)).label('suppliers'),func.count(func.distinct(Order.category)).label('categories')).filter(*conditions,column.isnot(None)).group_by(column)
    total=query.count();rows=query.order_by(func.count(Order.id).desc(),column.asc()).offset(offset).limit(limit).all()
    return {'items':[dict(r._mapping,monetary_total=None,participation='NOT_DETERMINED') for r in rows],
            'total':total,'limit':limit,'offset':offset,'provenance':provenance(db)}


@router.get('/buyers')
def buyers(db:Session=Depends(get_db),conditions=Depends(filters),limit:int=Query(10,ge=1,le=50),offset:int=Query(0,ge=0,le=100000)):
    return groups(db,conditions,Order.buyer,limit,offset)


@router.get('/suppliers')
def suppliers(db:Session=Depends(get_db),conditions=Depends(filters),limit:int=Query(10,ge=1,le=50),offset:int=Query(0,ge=0,le=100000)):
    return groups(db,conditions,Order.supplier,limit,offset)


@router.get('/instruments')
def instruments(db:Session=Depends(get_db),conditions=Depends(filters),limit:int=Query(10,ge=1,le=50),offset:int=Query(0,ge=0,le=100000)):
    result=groups(db,conditions,Order.instrument,limit,offset)
    result['instrument_validity']='NOT_VERIFIED_FROM_ORDERS'
    return result


@router.get('/sync-status')
def sync_status(db:Session=Depends(get_db)):
    state=db.get(State,DATASET)
    return {'status':state.status if state else 'NOT_SYNCED','last_complete_at':state.last_complete_at if state else None,
            'errors':state.error_count if state else 0,'provenance':provenance(db)}


@router.get('/quotations')
def quotations(db:Session=Depends(get_db),q:str=Query('',max_length=200),
               limit:int=Query(20,ge=1,le=50),offset:int=Query(0,ge=0,le=1000)):
    from datetime import timedelta
    from app.db.models import TvecQuotationEvent as Event,TvecQuotationSnapshot as Snapshot
    from app.services.tvec_quotations import configured,SOURCE,SOURCE_URL,FRESH_MINUTES
    from app.services.tvec_client import now
    try:configured()
    except EnvironmentDenied:raise HTTPException(404,'Cotizaciones TVEC no habilitadas')
    instant=now();snapshot=db.get(Snapshot,SOURCE)
    fresh=bool(snapshot and snapshot.checked_at and snapshot.checked_at>=instant-timedelta(minutes=FRESH_MINUTES))
    query=db.query(Event).filter(Event.snapshot_id==snapshot.published_snapshot if snapshot and fresh else False,
        Event.kind=='RFQ',Event.detail_verified.is_(True),Event.status=='Producción',
        Event.opens_at<=instant,Event.closes_at>instant)
    if q:
        value=q.replace('\\','\\\\').replace('%','\\%').replace('_','\\_')
        query=query.filter(or_(*[c.ilike('%'+value+'%',escape='\\') for c in [Event.title,Event.buyer,Event.instrument,Event.official_id]]))
    total=query.count();rows=query.order_by(Event.closes_at,Event.official_id).offset(offset).limit(limit).all()
    return {'items':[{'official_id':r.official_id,'title':r.title,'buyer':r.buyer,'instrument':r.instrument,
        'opens_at':r.opens_at.isoformat()+'Z','closes_at':r.closes_at.isoformat()+'Z',
        'kind':'RFQ','kind_evidence':r.kind_evidence,'status':r.status,
        'eligibility':'PENDING_VERIFICATION','eligibility_note':'Verifica que tu empresa esté habilitada en el instrumento, categoría o región antes de cotizar.',
        'official_url':r.official_url,'checked_at':r.checked_at.isoformat()+'Z'} for r in rows],
        'total':total,'limit':limit,'offset':offset,'provenance':{
            'source_url':SOURCE_URL,'checked_at':snapshot.checked_at.isoformat()+'Z' if snapshot and snapshot.checked_at else None,
            'freshness':'RECENT_PUBLIC_SNAPSHOT' if fresh else 'REFRESH_PENDING',
            'refresh_status':snapshot.status if snapshot else 'NOT_SYNCED',
            'scanned_pages':snapshot.scanned_pages if snapshot else 0,'scanned_rows':snapshot.scanned_rows if snapshot else 0,
            'excluded_rfi':snapshot.excluded_rfi if snapshot else 0,'excluded_unknown':snapshot.excluded_unknown if snapshot else 0,
            'coverage':'BOUNDED_RECENT_PAGES_NOT_EXHAUSTIVE','type_evidence':'Marcador RFQ explícito en título y detalle coincidente; no es un campo estructurado oficial.',
            'notice':'Consulta pública con actualización diferida. Confirma el plazo y la participación en TVEC; no se garantiza recepción de ofertas en tiempo real.',
            'timezone':'America/Bogota (interpretación de las fechas publicadas sin offset)',
            'freshness_minutes':FRESH_MINUTES}}
