"""Read-only preflight by default. Explicit marker registration only after approved DEV migration.
Never prints credentials; no migration, deployment or service installation.
"""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.core.config import get_settings
from app.services.evaluation_guard import configured_target,destination,database_identity,require_environment,EnvironmentDenied


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--verify-database',action='store_true')
    parser.add_argument('--register-identity',metavar='EXACT_ALLOWLIST_UUID')
    parser.add_argument('--acknowledge-isolated-dev',action='store_true')
    args=parser.parse_args();s=get_settings()
    try:
        identifier,fingerprint=configured_target()
        info={'configuration':'ALLOWLIST_MATCH','environment':s.environment,'identity':identifier,'fingerprint':fingerprint,'connections_opened':False}
        if args.verify_database or args.register_identity:
            if args.register_identity and (not args.acknowledge_isolated_dev or args.register_identity!=identifier):raise EnvironmentDenied('Explicit isolated DEV acknowledgment and matching UUID required')
            from app.db.session import SessionLocal
            from app.db.models import EvaluationEnvironmentIdentity as Identity,AuditLog
            from sqlalchemy import text
            with SessionLocal() as db:
                if database_identity(str(db.get_bind().url))!=database_identity(s.database_url):raise EnvironmentDenied('Session target differs')
                revision=db.execute(text('SELECT version_num FROM alembic_version')).scalar_one()
                if revision not in {'0014_evaluation_platform','0015_tvec_orders'}:raise EnvironmentDenied('Expected reviewed migration 0014 or additive 0015; review other revisions manually')
                if args.register_identity:
                    existing=db.get(Identity,identifier)
                    if existing and (existing.fingerprint!=fingerprint or existing.purpose!='isolated-development'):raise EnvironmentDenied('Existing identity differs; no overwrite')
                    if not existing:
                        db.add(Identity(id=identifier,fingerprint=fingerprint,purpose='isolated-development'))
                        db.add(AuditLog(action='evaluation_identity_provision',entity='evaluation',detail={'identity':identifier,'fingerprint':fingerprint}));db.commit()
                require_environment(db)
                info.update(connections_opened=True,database_identity='VERIFIED',alembic_revision=revision)
        print(json.dumps(info,indent=2));return 0
    except EnvironmentDenied as exc:
        print(json.dumps({'status':'DENIED','reason':str(exc),'operational_action':'not performed'}));return 2
    except Exception:
        print(json.dumps({'status':'DENIED','reason':'Database verification failed; no deployment or migration performed'}));return 2

if __name__=='__main__':sys.exit(main())
