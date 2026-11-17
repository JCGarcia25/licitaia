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
            assert db.execute(text('SELECT version_num FROM alembic_version')).scalar_one()=='0017_tvec_full_scan'
        operation_started=now()
        task=celery_app.send_task('app.workers.tasks.refresh_tvec_quotations',queue='tvec',retry=False,soft_time_limit=180,time_limit=210)
        result=task.get(timeout=240,propagate=False)
        assert isinstance(result,dict) and result['status'] in {'DONE','MORE','BUSY'}
        last_kick=time.monotonic();last_pages=None;progress={}
        for _ in range(400):
            with SessionLocal() as db:
                require_target(db);snapshot=db.get(Snapshot,SOURCE)
                progress=dict(snapshot.scan_progress or {}) if snapshot else {}
                if progress.get('published_complete') and snapshot.checked_at and (snapshot.checked_at>=operation_started or (result['status']=='DONE' and snapshot.checked_at>=now()-timedelta(minutes=2))):break
                if snapshot and snapshot.status=='ERROR':raise RuntimeError('Full traversal failed; cursor preserved')
                pages=progress.get('next_page',0)
                if pages!=last_pages:
                    print(json.dumps({'status':'QUOTATION_SCAN_PROGRESS','pages':pages,'total_pages':progress.get('total_pages'),'rows':progress.get('counts',{}).get('rows',0)}),flush=True)
                    last_pages=pages
                can_resume=not snapshot or not snapshot.lease_until or snapshot.lease_until<=now()
            if can_resume and time.monotonic()-last_kick>30:
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
        print(json.dumps({'status':'QUOTATIONS_DEV_VERIFIED','task_id':task.id,'available_rfq':payload['total'],
            'ids':[r['official_id'] for r in payload['items']], 'provenance':payload['provenance'],
            'full_listing_traversal':True,'counts':progress.get('published_counts'),'scanned_pages':snapshot.scanned_pages,'automatic_refresh_seconds':900,'historical_order_ingestion_requested':False}))
        return 0
    except Exception as error:
        print(json.dumps({'status':'DENIED_OR_FAILED','error_type':type(error).__name__}))
        return 2

if __name__=='__main__':sys.exit(main())
