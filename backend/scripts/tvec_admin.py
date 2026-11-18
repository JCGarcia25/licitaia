"""Offline by default. Writes/publishing require explicit isolated DEV acknowledgment.

Never migrates, deploys, imports real data, or discovers credentials automatically.
"""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    actions=p.add_mutually_exclusive_group()
    actions.add_argument('--verify-database',action='store_true')
    actions.add_argument('--register-identity')
    actions.add_argument('--create-run',action='store_true')
    actions.add_argument('--resume')
    p.add_argument('--max-pages',type=int,default=1)
    p.add_argument('--acknowledge-isolated-dev',action='store_true')
    a=p.parse_args()
    try:
        from app.services.tvec_guard import configuration,require_target
        settings,identity,fingerprint=configuration(ingestion=a.create_run or bool(a.resume))
        if not any([a.verify_database,a.register_identity,a.create_run,a.resume]):
            print(json.dumps({'status':'ALLOWLIST_MATCH_OFFLINE','connections_opened':0}));return 0
        if (a.register_identity or a.create_run or a.resume) and not a.acknowledge_isolated_dev:
            raise ValueError('Explicit isolated DEV acknowledgment required')
        if a.register_identity and a.register_identity!=identity:raise ValueError('Identity differs')
        from app.db.session import SessionLocal
        from app.db.models import EvaluationEnvironmentIdentity,AuditLog
        from sqlalchemy import text
        with SessionLocal() as db:
            revision=db.execute(text('SELECT version_num FROM alembic_version')).scalar_one()
            if revision not in {'0015_tvec_orders','0016_tvec_quotations','0017_tvec_full_scan','0018_offer_closing_reminders'}:
                raise ValueError('Expected reviewed 0015/0016/0017; review different revision before operating')
            if a.register_identity:
                marker=db.get(EvaluationEnvironmentIdentity,identity)
                if marker and (marker.fingerprint!=fingerprint or marker.purpose!='isolated-development'):raise ValueError('Identity mismatch; no overwrite')
                if not marker:
                    db.add(EvaluationEnvironmentIdentity(id=identity,fingerprint=fingerprint,purpose='isolated-development'))
                    db.add(AuditLog(action='tvec_identity_provision',entity='tvec',detail={'identity':identity}));db.commit()
            require_target(db,ingestion=a.create_run or bool(a.resume))
            if a.create_run or a.resume:
                from app.services.tvec_ingest import create_run,enqueue
                identifier=a.resume
                if a.create_run:
                    run=create_run(db,a.max_pages);identifier=run.id;db.commit()
                task=enqueue(identifier)
                print(json.dumps({'run_id':identifier,'task_id':task,'queue':'tvec'}))
            else:print(json.dumps({'status':'VERIFIED_DEV','revision':revision,'identity':identity}))
        return 0
    except Exception as error:
        # Do not print exception messages containing connection strings/SQL values.
        print(json.dumps({'status':'DENIED','error_type':type(error).__name__,'detail':'Review flags, tuple, marker, migration and explicit operation budget.'}));return 2

if __name__=='__main__':sys.exit(main())
