"""Snapshot breve -> cálculo sin transacción -> confirmación con versiones/fencing."""
from copy import deepcopy
from datetime import timedelta
import json
import math
import resource
import sys
import threading
import time
from types import SimpleNamespace

from sqlalchemy import event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm.attributes import set_committed_value

from app.core.config import get_settings
from app.db.models import CompanyProfile, MatchJob, MatchSlot, MatchScoreHistory, Opportunity, OpportunityEmbedding, UserOpportunity
from app.services.match_versions import (algorithm_version, embedding_version, embedding_spec,
    embedding_model_label, embedding_content_version, opportunity_version, profile_version, current_score_condition)
from app.services.opportunity_status import potentially_current_condition


class InputsChanged(RuntimeError):
    pass


def renew_lease(factory, slot_id, job_id, token):
    from app.services.match_jobs import utc_now
    now = utc_now()
    until = now + timedelta(seconds=get_settings().match_lease_seconds)
    with factory() as db:
        slot = db.query(MatchSlot).filter(MatchSlot.id == slot_id, MatchSlot.token == token,
            MatchSlot.lease_until >= now).update({'lease_until':until}, synchronize_session=False)
        job = db.query(MatchJob).filter(MatchJob.id == job_id, MatchJob.lease_token == token,
            MatchJob.state == 'RUNNING', MatchJob.lease_until >= now).update({'lease_until':until}, synchronize_session=False)
        if slot != 1 or job != 1:
            db.rollback()
            return False
        db.commit()
        return True


def _heartbeat(factory, slot_id, job_id, token, stop):
    delay = max(1, min(30, get_settings().match_lease_seconds / 3))
    while not stop.wait(delay):
        try:
            if not renew_lease(factory, slot_id, job_id, token):
                return
        except Exception:
            # La confirmación exige titularidad y vigencia aunque falle un ping.
            pass


def prepare(db, job_id, token):
    from app.services.alerts import profile_dict
    job = db.query(MatchJob).filter_by(id=job_id, lease_token=token).populate_existing().one()
    profile = db.query(CompanyProfile).filter_by(user_id=job.user_id).populate_existing().one()
    rows = (db.query(Opportunity).filter(Opportunity.id > job.cursor_id, Opportunity.id <= job.max_id,
        potentially_current_condition()).order_by(Opportunity.id).limit(get_settings().match_batch_size).populate_existing().all())
    ids = [r.id for r in rows]
    vectors = {e.opportunity_id:e for e in db.query(OpportunityEmbedding).filter(OpportunityEmbedding.opportunity_id.in_(ids)).populate_existing()} if ids else {}
    valid = {i for (i,) in db.query(UserOpportunity.opportunity_id).filter(UserOpportunity.user_id == job.user_id,
        UserOpportunity.opportunity_id.in_(ids), current_score_condition())} if ids else set()
    from app.services.match_versions import OPPORTUNITY_FIELDS
    snapshot_rows = []
    for row in rows:
        emb = vectors.get(row.id)
        cached = SimpleNamespace(model=emb.model, content_version=emb.content_version, vector=deepcopy(emb.vector)) if emb else None
        opp = SimpleNamespace(id=row.id, embedding=cached, **{k:getattr(row,k) for k in OPPORTUNITY_FIELDS})
        snapshot_rows.append({'opp':opp, 'version':opportunity_version(opp), 'skip':row.id in valid})
    snapshot = {'user_id':job.user_id,'cursor':job.cursor_id,'rows':snapshot_rows,
        'profile':deepcopy(profile_dict(profile)), 'weights':deepcopy(profile.learning_weights),
        'profile_version':profile_version(profile), 'job_profile_version':job.profile_version,
        'algorithm':algorithm_version(), 'embedding':embedding_version(), 'job_algorithm':job.algorithm_version,
        'job_embedding':job.embedding_version, 'profile_vector':deepcopy(job.profile_vector)}
    db.rollback()  # liberar conexión y cualquier snapshot antes de llamadas externas
    return snapshot


def calculate(snapshot):
    from app.services import match_jobs as service
    pvector = snapshot['profile_vector']
    for row in snapshot['rows']:
        if row['skip']:
            continue
        opp, cached = row['opp'], row['opp'].embedding
        row['error'] = None
        try:
            if pvector is None:
                data = snapshot['profile']
                pvector = service.embed(' '.join(str(x) for x in [data['sector'],data['actividades'],data['productos_servicios'],' '.join(data['keywords'])]))
            dim = embedding_spec()[1]
            if len(pvector) != dim or not all(math.isfinite(x) for x in pvector):
                raise ValueError('PROFILE_EMBEDDING_DIMENSION')
            compatible = (cached is not None and cached.model == embedding_model_label()
                and cached.content_version == embedding_content_version(opp) and len(cached.vector or []) == dim)
            vector = cached.vector if compatible else service.embed(f'{opp.objeto or ""} {opp.descripcion or ""}')
            if len(vector) != dim or not all(math.isfinite(x) for x in vector):
                raise ValueError('OPPORTUNITY_EMBEDDING_DIMENSION')
            row['generated'] = None if compatible else SimpleNamespace(model=embedding_model_label(),
                content_version=embedding_content_version(opp),vector=vector)
            row['result_version'] = opportunity_version(opp, row['generated'] or cached)
            result = service.score_opportunity(snapshot['profile'], {**vars(opp),'_vector':vector},
                profile_vector=pvector,learning_weights=snapshot['weights'] or None)
            if not math.isfinite(result.score):
                raise ValueError('NON_FINITE_SCORE')
            row['result'] = result
        except (KeyboardInterrupt, SystemExit):
            raise
        except Exception as exc:
            from billiard.exceptions import SoftTimeLimitExceeded
            from sqlalchemy.exc import DBAPIError
            if isinstance(exc, (SoftTimeLimitExceeded, DBAPIError)):
                raise
            row['error'] = type(exc).__name__
            row['generated'] = None
            row['result_version'] = row['version']
    snapshot['profile_vector'] = pvector


def _confirm(db, snapshot, job_id, slot_id, token, elapsed, queries):
    from app.services.match_jobs import utc_now
    confirming = time.monotonic()
    now = utc_now()
    slot = db.query(MatchSlot).filter_by(id=slot_id).with_for_update().populate_existing().one()
    job = db.query(MatchJob).filter_by(id=job_id).with_for_update().populate_existing().one()
    if (slot.token != token or job.lease_token != token or job.state != 'RUNNING'
            or slot.lease_until is None or slot.lease_until < now or job.lease_until is None or job.lease_until < now):
        raise InputsChanged('LEASE_LOST')
    profile = db.query(CompanyProfile).filter_by(user_id=job.user_id).with_for_update().populate_existing().one()
    changed_profile = (profile_version(profile) != snapshot['profile_version']
        or snapshot['profile_version'] != job.profile_version or algorithm_version() != snapshot['algorithm']
        or job.algorithm_version != snapshot['algorithm'] or embedding_version() != snapshot['embedding']
        or job.embedding_version != snapshot['embedding'])
    if changed_profile:
        job.state, job.active_key, job.finished_at = 'SUPERSEDED', None, now
    else:
        if job.cursor_id != snapshot['cursor']:
            raise InputsChanged('CURSOR_CHANGED')
        ids = [r['opp'].id for r in snapshot['rows']]
        current = {o.id:(o, eligible) for o,eligible in db.query(Opportunity,potentially_current_condition()).filter(
            Opportunity.id.in_(ids)).with_for_update().populate_existing()} if ids else {}
        vectors = {e.opportunity_id:e for e in db.query(OpportunityEmbedding).filter(
            OpportunityEmbedding.opportunity_id.in_(ids)).with_for_update().populate_existing()} if ids else {}
        for row in snapshot['rows']:
            oid = row['opp'].id
            if oid not in current or not current[oid][1]:
                raise InputsChanged('OPPORTUNITY_CHANGED')
            actual = opportunity_version(current[oid][0], vectors.get(oid))
            acceptable = {row['version']}
            if not row['skip'] and not row['error']:
                acceptable.add(row['result_version'])
            if actual not in acceptable:
                raise InputsChanged('OPPORTUNITY_CHANGED')
        existing = {u.opportunity_id:u for u in db.query(UserOpportunity).filter(
            UserOpportunity.user_id == job.user_id,UserOpportunity.opportunity_id.in_(ids)).with_for_update().populate_existing()} if ids else {}
        updates, inserts, history = [], [], []
        for row in snapshot['rows']:
            opp = current[row['opp'].id][0]
            set_committed_value(opp,'embedding',vectors.get(opp.id))
            job.examined += 1
            if row['skip']:
                job.skipped += 1
                job.cursor_id = opp.id
                continue
            generated = row['generated']
            if generated:
                emb = vectors.get(opp.id)
                if emb is None:
                    emb = OpportunityEmbedding(opportunity=opp)
                    db.add(emb)
                emb.model, emb.content_version, emb.vector = generated.model, generated.content_version, generated.vector
            opp.match_version = row['result_version']
            old = existing.get(opp.id)
            values = {'match_state':'FAILED' if row['error'] else 'CURRENT', 'match_error':row['error'],
                'updated_at':now}
            attempt_versions={'profile_version':snapshot['profile_version'],'opportunity_version':row['result_version'],
                'algorithm_version':snapshot['algorithm'],'embedding_version':snapshot['embedding']}
            if row['error']:
                values['failed_input_versions']=attempt_versions
                job.failed += 1
            else:
                if old is not None and old.score is not None:
                    from app.services.match_jobs import _versions
                    history.append({'user_id':job.user_id,'opportunity_id':opp.id,'score':old.score,
                        'reasons':old.reasons,'versions':(_versions(old) if old.match_state!='FAILED' or old.failed_input_versions is not None
                            else {'provenance':'legacy_failed_score_versions_unverified'}),'recorded_at':now})
                values.update(attempt_versions)
                values.update(score=row['result'].score,reasons=row['result'].reasons,scored_at=now,failed_input_versions=None)
                job.scored += 1
            if old is None:
                inserts.append(dict(values,user_id=job.user_id,opportunity_id=opp.id))
            else:
                updates.append(dict(values,id=old.id))
            job.cursor_id = opp.id
        db.flush()  # versiones de caché antes de los scores; sin N+1
        if history:
            db.bulk_insert_mappings(MatchScoreHistory,history)
        if updates:
            db.bulk_update_mappings(UserOpportunity,updates)
        if inserts:
            db.bulk_insert_mappings(UserOpportunity,inserts)
        job.profile_vector = snapshot['profile_vector']
        job.state = 'COMPLETED' if len(snapshot['rows']) < get_settings().match_batch_size else 'PENDING'
        if job.state == 'COMPLETED':
            job.active_key, job.finished_at = None, now
        job.batches += 1
    job.lease_token, job.lease_until, job.updated_at = None, None, now
    slot.token, slot.lease_until = None, None
    measured = elapsed + time.monotonic() - confirming
    job.last_batch_seconds = measured
    job.processing_seconds += measured
    job.last_batch_queries = queries[0]
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    job.peak_rss_bytes = rss if sys.platform == 'darwin' else rss*1024
    state = job.state
    db.commit()
    return state


def process(db, job_id):
    from app.services import match_jobs as service
    acquired = service._acquire(db,job_id)
    if acquired is None:
        return {'status':'BUSY'}
    slot_id, token = acquired
    started, committed, state = time.monotonic(), False, 'RETRY'
    stop = threading.Event()
    heartbeat = None
    queries, reads = [0],[0]
    owner = threading.get_ident()
    engine = db.get_bind()
    def count(conn,cursor,statement,parameters,context,executemany):
        if threading.get_ident() == owner:
            queries[0] += 1
            reads[0] += int(statement.lstrip().upper().startswith('SELECT'))
    event.listen(engine,'before_cursor_execute',count)
    try:
        snapshot = prepare(db,job_id,token)
        prepared = time.monotonic()
        if (snapshot['profile_version'] == snapshot['job_profile_version'] and snapshot['algorithm'] == snapshot['job_algorithm']
                and snapshot['embedding'] == snapshot['job_embedding']):
            heartbeat = threading.Thread(target=_heartbeat,args=(sessionmaker(bind=engine),slot_id,job_id,token,stop),daemon=True)
            heartbeat.start()
            calculate(snapshot)
        else:
            snapshot['rows'] = []
        calculated = time.monotonic()
        stop.set()
        if heartbeat:
            heartbeat.join(timeout=2)
        # Ninguna conexión de escritura está abierta durante calculate().
        state = _confirm(db,snapshot,job_id,slot_id,token,time.monotonic()-started,queries)
        committed = True
        service.logger.info(json.dumps({'event':'match_batch','job_id':job_id,'state':state,
            'prepare_seconds':prepared-started,'compute_seconds':calculated-prepared,
            'confirm_seconds':time.monotonic()-calculated,'queries':queries[0],'read_queries':reads[0],
            'rows':len(snapshot['rows']),'seconds':time.monotonic()-started}))
        return {'status':state,'job_id':job_id}
    except Exception as exc:
        try:
            db.rollback()
        except Exception:
            db.close()
        if committed:
            return {'status':state,'job_id':job_id}
        try:
            durable = db.get(MatchJob,job_id)
            if durable and durable.lease_token != token and durable.state in ('PENDING','COMPLETED','SUPERSEDED','CANCELLED'):
                durable_state=durable.state
                db.query(MatchSlot).filter_by(id=slot_id,token=token).update({'token':None,'lease_until':None},synchronize_session=False)
                db.commit()
                return {'status':durable_state,'job_id':job_id}
            slot = db.query(MatchSlot).filter_by(id=slot_id,token=token).with_for_update().one_or_none()
            job = db.query(MatchJob).filter_by(id=job_id,lease_token=token).with_for_update().one_or_none()
            if job is not None:
                job.retries += 1
                job.state = 'FAILED' if job.retries >= get_settings().match_max_retries else 'RETRY'
                state,job.error = job.state,type(exc).__name__
                job.lease_token,job.lease_until,job.updated_at = None,None,service.utc_now()
            if slot is not None:
                slot.token,slot.lease_until = None,None
            db.commit()
        except Exception:
            db.rollback()
        service.logger.error(json.dumps({'event':'match_batch_failed','job_id':job_id,'error_type':type(exc).__name__}))
        return {'status':state,'job_id':job_id}
    finally:
        stop.set()
        if heartbeat:
            heartbeat.join(timeout=2)
        event.remove(engine,'before_cursor_execute',count)
