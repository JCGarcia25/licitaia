"""Bounded reconciliation, durable runs, CAS leases and transactional cursors.

All HTTP happens outside a database transaction. Duplicate tasks are harmless.
An expired worker cannot commit. No beat schedule, matcher, or Opportunity write.
"""
from datetime import datetime, timedelta, timezone
from uuid import uuid4
import logging
from time import perf_counter

from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError

from app.core.config import get_settings
from app.db.models import TvecPurchaseOrder as Order, TvecOrderRevision as Revision
from app.db.models import TvecSyncRun as Run, TvecSyncState as State, TvecSourceMetadata as Metadata
from app.services.tvec_client import DATASET, TvecClient, now, normalize, validate_metadata
from app.services.tvec_guard import require_target, configuration
from app.services.match_versions import digest

logger = logging.getLogger('mysecop.tvec')


def create_run(db, max_pages=1):
    require_target(db,ingestion=True)
    if not 1 <= max_pages <= get_settings().tvec_max_pages:
        raise ValueError('TVEC page budget exceeded')
    run=Run(id=str(uuid4()),state='PENDING',max_pages=max_pages,created_at=now())
    db.add(run);db.flush()
    return run


def fence(db, token):
    instant=now()
    updated=db.query(State).filter(State.dataset_id==DATASET,State.lease_token==token,
        State.lease_until>instant).update({'lease_until':instant+timedelta(seconds=get_settings().tvec_lease_seconds)},synchronize_session=False)
    if updated!=1:raise RuntimeError('TVEC lease lost')
    return db.query(State).filter_by(dataset_id=DATASET).populate_existing().one()


def save_order(db, raw, cycle, existing=None):
    data=normalize(raw)
    order=existing.get(data['official_id']) if existing is not None else db.query(Order).filter_by(official_id=data['official_id']).one_or_none()
    result='inserted'
    if order:
        result='unchanged'
        if order.version!=data['version']:
            db.add(Revision(order_id=order.id,version=order.version,payload={**order.raw_json,'_socrata_row_id':order.source_row_id},recorded_at=now()))
            result='updated'
        for key,value in data.items():setattr(order,key,value)
    else:
        order=Order(**data);db.add(order)
        if existing is not None:existing[data['official_id']]=order
    order.synced_at=now();order.seen_cycle=cycle
    return result


def refresh_metadata(db, payload, count):
    columns=validate_metadata(payload)
    record=db.get(Metadata,DATASET)
    if record is None:record=Metadata(dataset_id=DATASET);db.add(record)
    record.columns=columns;record.schema_hash=digest(columns);record.checked_at=now()
    record.source_updated_at=datetime.fromtimestamp(payload['rowsUpdatedAt'],timezone.utc).replace(tzinfo=None) if payload.get('rowsUpdatedAt') else None
    frequency=payload.get('metadata',{}).get('custom_fields',{}).get('Información de Datos',{}).get('Frecuencia de Actualización')
    record.declared_frequency=frequency[:80] if isinstance(frequency,str) else None
    record.source_count=count


def process_run(db, identifier, client=None):
    require_target(db,ingestion=True)
    run=db.get(Run,identifier)
    if run is None:raise LookupError('TVEC run absent')
    if run.state=='DONE':db.rollback();return 'DONE'
    max_pages,pages=run.max_pages,run.pages
    db.rollback()
    try:
        if db.get(State,DATASET) is None:
            db.add(State(dataset_id=DATASET,cycle_id=str(uuid4()),status='IDLE'));db.commit()
        else:db.rollback()
    except IntegrityError:db.rollback()
    token=str(uuid4());instant=now()
    acquired=db.query(State).filter(State.dataset_id==DATASET,
        or_(State.lease_until.is_(None),State.lease_until<=instant)).update(
        {'lease_token':token,'lease_until':instant+timedelta(seconds=get_settings().tvec_lease_seconds),'status':'RUNNING'},synchronize_session=False)
    db.commit()
    if not acquired:return 'BUSY'
    current=db.get(Run,identifier,populate_existing=True)
    pages=current.pages
    if current.state=='DONE':
        state=fence(db,token);state.lease_token=None;state.lease_until=None;state.status='IDLE';db.commit()
        return 'DONE'
    db.rollback()
    client=client or TvecClient()
    started=perf_counter()
    try:
        # Remote I/O after the claim commit, without retaining a read transaction.
        metadata=client.metadata();count=client.count();generation=digest(metadata.get('rowsUpdatedAt'))
        require_target(db,ingestion=True)
        state=fence(db,token);refresh_metadata(db,metadata,count)
        if state.source_generation!=generation:
            state.cursor_id=None;state.cycle_rows=0;state.cycle_id=str(uuid4());state.source_generation=generation
        run=db.get(Run,identifier);run.state='RUNNING';run.error_type=None
        db.commit()
        for _ in range(max_pages-pages):
            state=db.get(State,DATASET);after,cycle=state.cursor_id,state.cycle_id
            db.rollback()
            rows=client.page(after)
            complete=len(rows)<client.page_size
            if complete and digest(client.metadata().get('rowsUpdatedAt'))!=generation:
                raise ValueError('Source changed during reconciliation')
            require_target(db,ingestion=True);state=fence(db,token)
            run=db.query(Run).filter_by(id=identifier).with_for_update().populate_existing().one()
            previous=after
            keys=[raw.get('identificador_de_la_orden') for raw in rows]
            if any(not isinstance(key,str) or not key or len(key)>255 for key in keys):
                raise ValueError('Invalid order IDs')
            existing={order.official_id:order for order in db.query(Order).filter(Order.official_id.in_(keys)).all()} if keys else {}
            for raw in rows:
                key=raw.get('identificador_de_la_orden')
                if not isinstance(key,str) or (previous is not None and key<=previous):
                    raise ValueError('Duplicate or unordered TVEC order ID')
                result=save_order(db,raw,cycle,existing);setattr(run,result,getattr(run,result)+1);previous=key
            if rows:
                state.cursor_id=previous;state.cycle_rows+=len(rows);run.processed+=len(rows)
            run.pages+=1
            if complete:
                if state.cycle_rows!=count:raise ValueError('Reconciliation count differs; review source')
                state.completed_cycles+=1;state.last_complete_at=now();state.cursor_id=None
                state.cycle_rows=0;state.cycle_id=str(uuid4())
            db.flush()
            fence(db,token) # recheck expiry after writes; rollback the entire page if lost
            db.commit() # order/revision/counts/cursor are a single transaction
            if complete:break
        state=fence(db,token);state.lease_token=None;state.lease_until=None;state.status='IDLE'
        run=db.get(Run,identifier);run.state='DONE';run.finished_at=now();db.commit()
        logger.info('tvec_run_complete run=%s duration=%.3f',identifier,perf_counter()-started)
        return 'DONE'
    except Exception as error:
        db.rollback()
        # Only the current owner can mutate the run after failure. Lost workers
        # neither clear another lease nor overwrite the successor's DONE state.
        owned=db.query(State).filter_by(dataset_id=DATASET,lease_token=token).update(
            {'lease_token':None,'lease_until':None,'status':'ERROR','error_count':State.error_count+1},synchronize_session=False)
        if owned:
            run=db.get(Run,identifier);run.state='FAILED';run.error_type=type(error).__name__;db.commit()
        else:db.rollback()
        logger.warning('tvec_run_failed run=%s error_type=%s',identifier,type(error).__name__)
        return 'FAILED'


def enqueue(identifier):
    s,_,_=configuration(ingestion=True)
    from app.workers.celery_app import celery_app
    from app.services.evaluation_guard import broker_identity
    if celery_app is None or broker_identity(celery_app.conf.broker_url)!=broker_identity(s.redis_url):
        raise ValueError('TVEC worker broker differs')
    return celery_app.send_task('app.workers.tasks.sync_tvec_orders',args=[identifier],queue='tvec',retry=False,
                               soft_time_limit=90,time_limit=120).id
