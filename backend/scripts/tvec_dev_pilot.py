"""Explicit, one-off DEV authorization: <=100 orders via the real Celery worker.

The stable run ID survives workflow retries. Redelivering DONE verifies idempotency
without opening another source page. No accounts or existing source rows are deleted.
"""
import argparse
import json
from pathlib import Path
import sys
from uuid import NAMESPACE_URL, uuid5

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
RUN_ID = str(uuid5(NAMESPACE_URL, 'mysecop:dev:tvec:authorized-pilot:2026-11-17:100'))


def snapshot(db):
    from sqlalchemy import func
    from app.db.models import TvecPurchaseOrder as Order, TvecSyncRun as Run, TvecSyncState as State
    from app.services.tvec_client import DATASET
    run = db.get(Run, RUN_ID)
    state = db.get(State, DATASET)
    return {
        'total': db.query(func.count(Order.id)).scalar(),
        'distinct': db.query(func.count(func.distinct(Order.official_id))).scalar(),
        'max_id': db.query(func.max(Order.official_id)).scalar(),
        'cursor': state.cursor_id if state else None,
        'cycle_rows': state.cycle_rows if state else 0,
        'run_state': run.state if run else None,
        'pages': run.pages if run else 0,
        'processed': run.processed if run else 0,
        'inserted': run.inserted if run else 0,
        'updated': run.updated if run else 0,
        'unchanged': run.unchanged if run else 0,
    }


def execute():
    from app.core.config import get_settings
    from app.db.session import SessionLocal
    from app.db.models import TvecSyncRun as Run, TvecSyncState as State
    from app.services.tvec_guard import require_target
    from app.services.tvec_client import DATASET, now
    from app.services.tvec_ingest import enqueue
    from app.workers.celery_app import celery_app

    s = get_settings()
    assert s.environment == 'development' and s.tvec_api_origin == 'https://dev.mysecop.co'
    assert s.tvec_enabled and s.tvec_ingest_enabled
    assert s.tvec_page_size == 100 and s.tvec_max_pages == 1
    with SessionLocal() as db:
        require_target(db, ingestion=True)
        before = snapshot(db)
        # A different unfinished run cannot be included in this authorization.
        assert db.query(Run).filter(Run.id != RUN_ID, Run.state.in_(['PENDING', 'RUNNING'])).count() == 0
        run = db.get(Run, RUN_ID)
        if run is None:
            run = Run(id=RUN_ID, state='PENDING', max_pages=1, created_at=now())
            db.add(run)
            db.commit()
        assert run.max_pages == 1 and run.pages <= 1 and run.processed <= 100
    # All waits happen after closing the database session.
    task_id = enqueue(RUN_ID)
    result = celery_app.AsyncResult(task_id).get(timeout=240, propagate=False)
    if result != 'DONE':
        with SessionLocal() as db:
            run = db.get(Run, RUN_ID)
            print(json.dumps({'status': 'PILOT_FAILED', 'run_id': RUN_ID,
                              'state': run.state, 'error_type': run.error_type,
                              'pages': run.pages, 'processed': run.processed}))
        raise RuntimeError('Pilot did not complete; no new run or extra budget authorized')
    with SessionLocal() as db:
        require_target(db, ingestion=True)
        after = snapshot(db)
        state = db.get(State, DATASET)
        assert after['run_state'] == 'DONE' and after['pages'] == 1
        assert 0 < after['processed'] <= 100
        assert after['inserted'] + after['updated'] + after['unchanged'] == after['processed']
        assert after['total'] == after['distinct']
        assert after['total'] - before['total'] == after['inserted'] - before['inserted']
        assert state.status == 'IDLE' and state.lease_token is None and state.lease_until is None
        if state.cycle_rows:
            assert after['cursor'] == after['max_id']
    duplicate_task_id = enqueue(RUN_ID)
    assert celery_app.AsyncResult(duplicate_task_id).get(timeout=60, propagate=False) == 'DONE'
    with SessionLocal() as db:
        require_target(db, ingestion=True)
        assert snapshot(db) == after
    print(json.dumps({'status': 'PILOT_VERIFIED', 'run_id': RUN_ID,
                      'task_id': task_id, 'duplicate_task_id': duplicate_task_id,
                      'page_budget': 1, 'page_size': 100, 'before': before, 'after': after,
                      'duplicate_delivery': 'DONE_WITHOUT_CHANGES',
                      'ingestion_enabled': True, 'automatic_schedule': False}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--acknowledge-isolated-dev', action='store_true', required=True)
    parser.parse_args()
    try:
        execute()
        return 0
    except Exception as error:
        # Connection errors and task exceptions can contain URLs; never print them.
        print(json.dumps({'status': 'DENIED_OR_FAILED', 'run_id': RUN_ID,
                          'error_type': type(error).__name__,
                          'detail': 'Review pilot state and worker logs; preserve the same run and budget.'}))
        return 2


if __name__ == '__main__':
    sys.exit(main())
