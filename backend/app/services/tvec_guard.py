"""TVEC is DEV-only, opt-in, with the existing isolated installation identity."""
from sqlalchemy import text
from app.core.config import get_settings
from app.db.models import EvaluationEnvironmentIdentity
from app.services.evaluation_guard import configured_target, database_identity, EnvironmentDenied


def configuration(*, ingestion=False):
    s = get_settings()
    if not s.tvec_enabled or (ingestion and not s.tvec_ingest_enabled):
        raise EnvironmentDenied('TVEC disabled')
    adapted = s.model_copy(update={'evaluation_dev_targets':s.tvec_dev_targets,
                                   'evaluation_api_origin':s.tvec_api_origin})
    identifier,fingerprint = configured_target(adapted,require_evaluation_enabled=False)
    return s,identifier,fingerprint


def require_target(db, *, ingestion=False, origin=None):
    s,identifier,fingerprint = configuration(ingestion=ingestion)
    if origin and origin.rstrip('/') != s.tvec_api_origin.rstrip('/'):
        raise EnvironmentDenied('TVEC request origin differs')
    if database_identity(str(db.get_bind().url)) != database_identity(s.database_url):
        raise EnvironmentDenied('TVEC session destination differs')
    marker = db.get(EvaluationEnvironmentIdentity,identifier)
    if not marker or marker.fingerprint != fingerprint or marker.purpose != 'isolated-development':
        raise EnvironmentDenied('TVEC isolated identity absent')
    if db.bind.dialect.name == 'postgresql':
        expected=database_identity(s.database_url)[3]
        if db.execute(text('SELECT current_database()')).scalar_one()!=expected:
            raise EnvironmentDenied('TVEC database differs')
    return fingerprint
