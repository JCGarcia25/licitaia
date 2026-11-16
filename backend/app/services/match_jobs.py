"""Coordinación durable y scoring por claves, sin límite del universo."""
import json
import logging
import math
import time
import resource
import sys
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy import and_, case, event, func, or_
from sqlalchemy.orm.attributes import set_committed_value
from sqlalchemy.exc import DBAPIError, IntegrityError
from billiard.exceptions import SoftTimeLimitExceeded

from app.core.config import get_settings
from app.db.models import (CompanyProfile, MatchJob, MatchScoreHistory, MatchSlot,
                           Opportunity, UserOpportunity)
from app.services.embeddings import embed
from app.services.matcher import score_opportunity
from app.services.match_versions import (algorithm_version, current_score_condition,
    embedding_spec, embedding_version, profile_version, opportunity_version, score_versions_condition, embedding_model_label, embedding_content_version, failed_score_condition)
from app.services.opportunity_status import potentially_current_condition

logger = logging.getLogger('licitaia.matches')
ACTIVE = ('PENDING', 'RUNNING', 'RETRY')


def utc_now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def coverage_percentage(current,total):
    if not total:
        return None
    rounded=round(100*current/total,2)
    return 99.99 if current<total and rounded==100 else rounded


def coverage(db, user_id):
    U = UserOpportunity
    query = (db.query(Opportunity).outerjoin(U, and_(U.opportunity_id == Opportunity.id, U.user_id == user_id))
             .outerjoin(CompanyProfile, CompanyProfile.user_id == user_id))
    eligible = potentially_current_condition()
    versions = and_(CompanyProfile.match_version.isnot(None), Opportunity.match_version.isnot(None),
        U.profile_version == CompanyProfile.match_version, U.opportunity_version == Opportunity.match_version,
        U.algorithm_version == algorithm_version(), U.embedding_version == embedding_version())
    current = and_(eligible, versions, U.match_state == 'CURRENT', U.score.isnot(None))
    def failed_version(key):
        return func.coalesce(U.failed_input_versions[key].as_string(),getattr(U,key))
    failed_versions = and_(CompanyProfile.match_version.isnot(None),Opportunity.match_version.isnot(None),
        failed_version('profile_version') == CompanyProfile.match_version,
        failed_version('opportunity_version') == Opportunity.match_version,
        failed_version('algorithm_version') == algorithm_version(), failed_version('embedding_version') == embedding_version())
    failure = and_(eligible, failed_versions, U.match_state == 'FAILED')
    stale = and_(eligible, ~func.coalesce(current, False), U.score.isnot(None), ~func.coalesce(failure, False))
    counts = query.with_entities(
        func.count(Opportunity.id), func.sum(case((eligible, 1), else_=0)),
        func.sum(case((current, 1), else_=0)), func.sum(case((failure, 1), else_=0)),
        func.sum(case((stale, 1), else_=0)),
    ).one()
    universe, total, current_count, failed, stale = [int(x or 0) for x in counts]
    excluded = universe - total
    return {'candidate_total': total, 'current_scores': current_count,
            'pending_scores': total - current_count - failed - stale, 'stale_scores': stale,
            'failed_scores': failed, 'excluded_total': excluded,
            'coverage_percent': coverage_percentage(current_count,total),
            'status': 'MEASURED' if total else 'NO_CANDIDATES',
            'measured_at': utc_now(), 'criterion': 'potentially_current_v1; per-user; live universe'}


def request_job(db, user_id):
    profile = db.query(CompanyProfile).filter_by(user_id=user_id).first()
    if profile is None:
        raise ValueError('Complete su perfil empresarial')
    # Serializa inicio concurrente por perfil, incluyendo creación del primer job.
    profile = db.query(CompanyProfile).filter_by(id=profile.id).with_for_update().populate_existing().one()
    existing = db.query(MatchJob).filter_by(active_key=user_id).first()
    if existing:
        return existing
    if profile.match_version != profile_version(profile):
        profile.match_version = profile_version(profile)
        db.flush()
    maximum = db.query(func.max(Opportunity.id)).scalar() or 0
    total = db.query(Opportunity).filter(Opportunity.id <= maximum).count()
    candidates = db.query(Opportunity).filter(Opportunity.id <= maximum, potentially_current_condition()).count()
    job = MatchJob(id=str(uuid4()), user_id=user_id, active_key=user_id, state='PENDING',
        profile_version=profile.match_version, algorithm_version=algorithm_version(),
        embedding_version=embedding_version(), max_id=maximum,
        candidate_total=candidates, excluded_total=total-candidates)
    try:
        with db.begin_nested():
            db.add(job)
            db.flush()
    except IntegrityError:
        return db.query(MatchJob).filter_by(active_key=user_id).one()
    return job


def enqueue(job_id, countdown=0):
    """Solo publica después de commit. La tabla de jobs es la cola recuperable."""
    if get_settings().environment == 'testing':
        return False
    from app.workers.celery_app import celery_app
    if celery_app is None:
        return False
    try:
        celery_app.send_task('app.workers.tasks.process_match_batch', args=[job_id],
                             queue='matches', retry=False, countdown=countdown,
                             soft_time_limit=max(5, get_settings().match_lease_seconds - 10),
                             time_limit=get_settings().match_lease_seconds)
        return True
    except Exception:
        logger.warning('match_queue_unavailable job_id=%s', job_id)
        return False


def _acquire(db, job_id):
    settings = get_settings()
    now, token = utc_now(), str(uuid4())
    until = now + timedelta(seconds=settings.match_lease_seconds)
    # Orden fijo slot -> job evita interbloqueos entre ejecutores.
    slot_id = None
    for index in range(1, settings.match_global_concurrency + 1):
        if not db.get(MatchSlot, index):
            try:
                with db.begin_nested():
                    db.add(MatchSlot(id=index))
                    db.flush()
            except IntegrityError:
                pass
        updated = db.query(MatchSlot).filter(MatchSlot.id == index,
            or_(MatchSlot.lease_until.is_(None), MatchSlot.lease_until < now)).update(
                {'token': token, 'lease_until': until}, synchronize_session=False)
        if updated:
            slot_id = index
            break
    if slot_id is None:
        db.rollback()
        return None
    updated = db.query(MatchJob).filter(MatchJob.id == job_id, MatchJob.state.in_(ACTIVE),
        or_(MatchJob.lease_until.is_(None), MatchJob.lease_until < now)).update(
            {'state': 'RUNNING', 'lease_token': token, 'lease_until': until,
             'updated_at': now}, synchronize_session=False)
    if not updated:
        db.rollback()
        return None
    db.commit()
    return slot_id, token


def _versions(uo):
    return {key: getattr(uo, key) for key in ('profile_version', 'opportunity_version',
                                           'algorithm_version', 'embedding_version')}


def process_batch(db, job_id):
    from app.services.match_execution import process
    try:
        return process(db, job_id)
    except DBAPIError as exc:
        db.rollback()
        logger.error(json.dumps({'event':'match_acquire_failed','job_id':job_id,'error_type':type(exc).__name__}))
        return {'status':'RETRY','job_id':job_id}


def cancel_job(db, job):
    job = db.query(MatchJob).filter_by(id=job.id).with_for_update().populate_existing().one()
    if job.state in ACTIVE or job.state == 'FAILED':
        job.state, job.active_key = 'CANCELLED', None
        job.finished_at = utc_now()
        # Slot se libera por vencimiento si se canceló entre adquisición y lote.
        job.lease_token, job.lease_until = None, None
    return job


def resume_job(db, job):
    if job.state not in ('FAILED', 'RETRY', 'PENDING', 'RUNNING'):
        return request_job(db, job.user_id)
    job.state = 'PENDING' if job.state != 'RUNNING' else job.state
    job.retries, job.error = 0, None
    return job


def job_progress(db, job):
    return {key: getattr(job, key) for key in ('id','state','cursor_id','max_id','candidate_total',
        'excluded_total','examined','scored','skipped','failed','batches','retries','error',
        'created_at','updated_at','finished_at','last_batch_seconds','processing_seconds',
        'last_batch_queries','peak_rss_bytes')} | {'coverage': coverage(db, job.user_id)}
