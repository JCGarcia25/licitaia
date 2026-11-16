"""Agregados operativos privados; fuentes SECOP solo con metadatos públicos."""
from sqlalchemy import func
from app.db.models import MatchJob, SyncRun, SyncCursor
from app.services.match_jobs import coverage, utc_now


def operational_metrics(db,user_id):
    now=utc_now()
    jobs=db.query(MatchJob).filter(MatchJob.user_id==user_id)
    counts={state:count for state,count in jobs.with_entities(MatchJob.state,func.count()).group_by(MatchJob.state)}
    oldest=jobs.filter(MatchJob.state.in_(['PENDING','RETRY'])).with_entities(func.min(MatchJob.created_at)).scalar()
    seconds,batches,retries=jobs.with_entities(func.sum(MatchJob.processing_seconds),func.sum(MatchJob.batches),func.sum(MatchJob.retries)).one()
    errors={error:count for error,count in jobs.filter(MatchJob.error.isnot(None)).with_entities(MatchJob.error,func.count()).group_by(MatchJob.error)}
    sync=db.query(SyncRun).filter(SyncRun.user_id==user_id)
    last_sync=sync.with_entities(func.max(SyncRun.finished_at)).scalar()
    sync_errors=sync.with_entities(func.sum(SyncRun.errors)).scalar() or 0
    return {'measured_at':now,'jobs_by_state':counts,'pending_jobs':counts.get('PENDING',0)+counts.get('RETRY',0),
        'running_jobs':counts.get('RUNNING',0),'failed_jobs':counts.get('FAILED',0),
        'expired_running_jobs':jobs.filter(MatchJob.state=='RUNNING',MatchJob.lease_until<now).count(),
        'oldest_pending_seconds':max(0,(now-oldest).total_seconds()) if oldest else None,
        'processing_seconds':float(seconds or 0),'confirmed_batches':int(batches or 0),
        'average_batch_seconds':float(seconds)/batches if batches else None,
        'retries':int(retries or 0),'errors_by_component':{'matching':errors,'user_sync_errors':int(sync_errors)},
        'user_sync_age_seconds':max(0,(now-last_sync).total_seconds()) if last_sync else None,
        'public_source_sync':[{'source':c.source,'last_success_at':c.last_success_at,
            'age_seconds':max(0,(now-c.last_success_at).total_seconds()) if c.last_success_at else None}
            for c in db.query(SyncCursor).order_by(SyncCursor.source)],
        'coverage':coverage(db,user_id)}
