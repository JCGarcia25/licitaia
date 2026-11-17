"""Explicit DEV-only bounded refresh via real Celery, followed by HTTPS smoke."""
import argparse
import json
from pathlib import Path
import ssl
import sys
import time
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
        from app.services.tvec_quotations import configured,SOURCE,MAX_PAGES,PAGE_SIZE
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
            assert db.execute(text('SELECT version_num FROM alembic_version')).scalar_one()=='0016_tvec_quotations'
        task=celery_app.send_task('app.workers.tasks.refresh_tvec_quotations',queue='tvec',retry=False,soft_time_limit=180,time_limit=210)
        result=task.get(timeout=240,propagate=False)
        assert result in {'DONE','BUSY'}
        for _ in range(40):
            with SessionLocal() as db:
                require_target(db);snapshot=db.get(Snapshot,SOURCE)
                if snapshot and snapshot.checked_at and snapshot.status=='IDLE':break
            time.sleep(3)
        else:raise RuntimeError('No completed bounded snapshot')
        with SessionLocal() as db:
            email=db.execute(select(User.email).where(User.email==SUPERADMIN_EMAIL,User.is_active.is_(True))).scalar_one()
        token=create_access_token(email,expires_minutes=1)
        request=urllib.request.Request(s.tvec_api_origin+'/api/tvec/quotations?limit=50',headers={'Authorization':'Bearer '+token})
        with urllib.request.urlopen(request,context=ssl.create_default_context(cafile=certifi.where()),timeout=20) as response:
            assert response.status==200;payload=json.load(response)
        assert payload['provenance']['freshness']=='RECENT_PUBLIC_SNAPSHOT'
        assert payload['provenance']['scanned_rows']<=MAX_PAGES*PAGE_SIZE
        for item in payload['items']:
            assert item['kind']=='RFQ' and item['eligibility']=='PENDING_VERIFICATION'
        print(json.dumps({'status':'QUOTATIONS_DEV_VERIFIED','task_id':task.id,'available_rfq':payload['total'],
            'ids':[r['official_id'] for r in payload['items']], 'provenance':payload['provenance'],
            'automatic_refresh_seconds':900,'historical_order_ingestion_requested':False}))
        return 0
    except Exception as error:
        print(json.dumps({'status':'DENIED_OR_FAILED','error_type':type(error).__name__}))
        return 2

if __name__=='__main__':sys.exit(main())
