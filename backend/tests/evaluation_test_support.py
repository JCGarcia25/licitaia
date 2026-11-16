"""Explicit identity provisioning ONLY in disposable test sessions; never imported by app."""
from uuid import uuid4
from app.core.config import get_settings
from app.db.models import EvaluationEnvironmentIdentity as Identity
from app.services.evaluation_guard import destination
from app.services.match_versions import digest


def authorize(db,monkeypatch,*,database=None,broker=None,origin='http://testserver'):
    s=get_settings()
    monkeypatch.setattr(s,'database_url',database or str(db.get_bind().url))
    if broker is not None:monkeypatch.setattr(s,'redis_url',broker)
    monkeypatch.setattr(s,'evaluation_api_origin',origin)
    fp=digest(destination(s));row=db.query(Identity).filter_by(fingerprint=fp).one_or_none()
    if not row:row=Identity(id=str(uuid4()),fingerprint=fp,purpose='isolated-development');db.add(row);db.commit()
    target={'database':s.database_url,'broker':s.redis_url,'api_origin':origin,'identity':row.id}
    monkeypatch.setattr(s,'evaluation_dev_targets',[target]);return target
