"""Explicit DEV-only bounded refresh via real Celery, followed by HTTPS smoke."""
import argparse
import json
from pathlib import Path
import ssl
import sys
import time
from datetime import timedelta
import urllib.request
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--refresh',action='store_true',required=True)
    p.add_argument('--acknowledge-isolated-dev',action='store_true',required=True)
    p.parse_args()
    try:
        import certifi
        from sqlalchemy import text,select
        from app.db.models import TvecQuotationSnapshot as Snapshot,User
        from app.db.session import SessionLocal
        from app.services.tvec_quotations import configured,SOURCE
        from app.services.tvec_guard import require_target
        from app.services.tvec_client import now
        from app.services.evaluation_guard import broker_identity
        from app.workers.celery_app import celery_app
        from app.core.security import create_access_token
        from app.routers.admin import SUPERADMIN_EMAIL
        s=configured(refresh=True)
        assert s.environment=='development' and s.tvec_api_origin=='https://dev.mysecop.co'
        assert broker_identity(celery_app.conf.broker_url)==broker_identity(s.redis_url)
        with SessionLocal() as db:
            require_target(db)
            revision=db.execute(text('SELECT version_num FROM alembic_version')).scalar_one()
            assert revision in {'0017_tvec_full_scan','0018_offer_closing_reminders'}
            if revision=='0018_offer_closing_reminders':
                from sqlalchemy import inspect
                schema=inspect(db.get_bind())
                assert schema.has_table('offer_closing_reminders')
                assert 'is_saved' in {c['name'] for c in schema.get_columns('user_opportunities')}
        if revision=='0018_offer_closing_reminders':
            registered=celery_app.control.inspect(timeout=5).registered() or {}
            worker_ready=any('app.workers.tasks.deliver_offer_reminders' in tasks for tasks in registered.values())
            schedule=celery_app.conf.beat_schedule.get('offer-closing-reminders-every-minute',{})
            assert worker_ready and schedule.get('task')=='app.workers.tasks.deliver_offer_reminders' and schedule.get('schedule')==60
            print(json.dumps({'status':'OFFER_REMINDERS_DEV_READY','revision':revision,
                'worker_registered':worker_ready,'scheduler_seconds':60,'smtp_configured':bool(s.smtp_host),
                'read_only_check':True,'emails_requested':0}),flush=True)
        with SessionLocal() as db:
            email=db.execute(select(User.email).where(User.email==SUPERADMIN_EMAIL,User.is_active.is_(True))).scalar_one()
        def browser_request(path,post=False):
            token=create_access_token(email,expires_minutes=1)
            request=urllib.request.Request(s.tvec_api_origin+path,data=b'{}' if post else None,
                headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'},method='POST' if post else 'GET')
            with urllib.request.urlopen(request,context=ssl.create_default_context(cafile=certifi.where()),timeout=20) as response:
                assert response.status in {200,202};return json.load(response)
        operation_started=now()
        manual=browser_request('/api/tvec/quotations/refresh',post=True)
        duplicate=browser_request('/api/tvec/quotations/refresh',post=True)
        assert duplicate['accepted'] is False
        assert manual['state'] in {'PENDING','RUNNING','COOLDOWN'}
        result={'status':'DONE' if manual['state']=='COOLDOWN' or duplicate['state']=='COOLDOWN' else 'MORE'}
        last_kick=time.monotonic();last_pages=None;progress={};error_since=None
        for _ in range(400):
            with SessionLocal() as db:
                require_target(db);snapshot=db.get(Snapshot,SOURCE)
                progress=dict(snapshot.scan_progress or {}) if snapshot else {}
                if progress.get('published_complete') and snapshot.checked_at and (snapshot.checked_at>=operation_started or (result['status']=='DONE' and snapshot.checked_at>=now()-timedelta(minutes=5))):break
                db_error=bool(snapshot and snapshot.status=='ERROR')
                pages=progress.get('next_page',0)
                if pages!=last_pages:
                    print(json.dumps({'status':'QUOTATION_SCAN_PROGRESS','pages':pages,'total_pages':progress.get('total_pages'),'rows':progress.get('counts',{}).get('rows',0)}),flush=True)
                    last_pages=pages
                can_resume=not snapshot or not snapshot.lease_until or snapshot.lease_until<=now()
            if db_error:
                if error_since is None:error_since=time.monotonic()
            else:error_since=None
            # Allow the worker's bounded transient retries (10/20/40 seconds)
            # before declaring the preserved cursor terminally failed.
            if db_error and time.monotonic()-error_since>120:
                current_request=browser_request('/api/tvec/quotations/refresh-status')
                if current_request['state']=='ERROR':
                    print(json.dumps({'status':'QUOTATION_SCAN_FAILED','scan_id':progress.get('id'),
                        'pages':progress.get('next_page',0),'total_pages':progress.get('total_pages'),
                        'error_type':snapshot.error_type,'cursor_preserved':True}),flush=True)
                    raise RuntimeError('Full traversal failed; cursor preserved')
            if can_resume and not db_error and time.monotonic()-last_kick>30:
                celery_app.send_task('app.workers.tasks.refresh_tvec_quotations',args=[progress.get('id')],queue='tvec',retry=False,soft_time_limit=180,time_limit=210)
                last_kick=time.monotonic()
            time.sleep(3)
        else:raise RuntimeError('Full traversal still incomplete; no full-coverage claim')
        with SessionLocal() as db:
            email=db.execute(select(User.email).where(User.email==SUPERADMIN_EMAIL,User.is_active.is_(True))).scalar_one()
        token=create_access_token(email,expires_minutes=1)
        request=urllib.request.Request(s.tvec_api_origin+'/api/tvec/quotations?limit=50',headers={'Authorization':'Bearer '+token})
        with urllib.request.urlopen(request,context=ssl.create_default_context(cafile=certifi.where()),timeout=20) as response:
            assert response.status==200;payload=json.load(response)
        assert payload['provenance']['freshness']=='RECENT_PUBLIC_SNAPSHOT'
        assert payload['provenance']['coverage']=='OFFICIAL_LISTING_TRAVERSED'
        assert snapshot.scanned_rows==sum(progress['published_counts'][k] for k in ['rfi','unknown','unavailable','detail_failed','qualified'])
        for item in payload['items']:
            assert item['kind']=='RFQ' and item['eligibility']=='PENDING_VERIFICATION'
        manual_status=browser_request('/api/tvec/quotations/refresh-status')
        assert manual_status['state'] in {'COOLDOWN','IDLE','RUNNING'}
        print(json.dumps({'status':'QUOTATIONS_DEV_VERIFIED','manual_button_verified':True,'manual_request':manual,'duplicate_request':duplicate,'manual_status':manual_status,'available_rfq':payload['total'],
            'ids':[r['official_id'] for r in payload['items']], 'provenance':payload['provenance'],
            'full_listing_traversal':True,'counts':progress.get('published_counts'),'scanned_pages':snapshot.scanned_pages,'automatic_refresh_seconds':900,'historical_order_ingestion_requested':False}))
        return 0
    except Exception as error:
        print(json.dumps({'status':'DENIED_OR_FAILED','error_type':type(error).__name__}))
        return 2

if __name__=='__main__':sys.exit(main())
