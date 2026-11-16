"""Fail closed BEFORE opening a connection to a destination absent from the allowlist."""
from pathlib import Path
from urllib.parse import urlsplit,unquote
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError
from app.core.config import get_settings
from app.services.match_versions import digest

class EnvironmentDenied(ValueError):
    pass


def database_identity(value):
    u=make_url(value)
    if u.get_backend_name()=='sqlite':
        if u.query:raise EnvironmentDenied('SQLite query overrides forbidden')
        return ['sqlite',str(Path(u.database or '').resolve())]
    if u.get_backend_name()!='postgresql':raise EnvironmentDenied('Unsupported evaluation database')
    if not (u.host or u.query.get('host')) or not u.database or not u.username:
        raise EnvironmentDenied('Explicit PostgreSQL host/socket, database and user required; ambient PG defaults forbidden')
    # Driver query values may change actual destination; preserve ALL in identity.
    return ['postgresql',u.host or '',u.port or 5432,u.database,u.username,dict(u.query)]


def broker_identity(value):
    u=make_url(value)
    if u.drivername not in {'redis','rediss','redis+socket'}:raise EnvironmentDenied('Unsupported broker')
    if u.drivername=='redis+socket':
        socket=unquote(urlsplit(value).path)
        if u.host or not socket or not Path(socket).is_absolute():raise EnvironmentDenied('Explicit absolute Redis socket required')
        return ['redis+socket',str(Path(socket).resolve()),dict(u.query)]
    elif not u.host or u.database is None:
        raise EnvironmentDenied('Explicit Redis host and database required')
    return [u.drivername,u.host,u.port or (6379 if u.host else None),u.database,dict(u.query)]


def destination(settings=None):
    s=settings or get_settings()
    origin=s.evaluation_api_origin.rstrip('/')
    u=urlsplit(origin)
    if u.scheme not in {'http','https'} or not u.hostname or u.username or u.password or u.query or u.fragment or u.path not in {'','/'}:
        raise EnvironmentDenied('Exact API origin required')
    return [database_identity(s.database_url),broker_identity(s.redis_url),origin]


def configured_target(settings=None,*,require_evaluation_enabled=True):
    s=settings or get_settings()
    if (require_evaluation_enabled and not s.evaluation_enabled) or s.environment not in {'development','testing','isolated-integration'}:
        raise EnvironmentDenied('Evaluation disabled or environment prohibited')
    if not isinstance(s.secret_key,str) or len(s.secret_key)<32:
        raise EnvironmentDenied('Evaluation requires a reviewed installation secret of at least 32 characters')
    actual=destination(s)
    for t in s.evaluation_dev_targets:
        if set(t)!={'database','broker','api_origin','identity'}:continue
        try:expected=[database_identity(t['database']),broker_identity(t['broker']),t['api_origin'].rstrip('/')]
        except (ValueError,TypeError):continue
        if actual==expected and len(t['identity'])==36:return t['identity'],digest(actual)
    raise EnvironmentDenied('DB/broker/API tuple not explicitly authorized')


def require_environment(db,*,api_origin=None,allow_shadow=False):
    s=get_settings();identifier,fingerprint=configured_target(s,require_evaluation_enabled=not allow_shadow)
    if database_identity(str(db.get_bind().url))!=database_identity(s.database_url):
        # SQLAlchemy's display URL redacts passwords, which are not destination identity.
        raise EnvironmentDenied('Actual session destination differs')
    if api_origin and api_origin.rstrip('/')!=s.evaluation_api_origin.rstrip('/'):
        raise EnvironmentDenied('Request API origin differs')
    from app.db.models import EvaluationEnvironmentIdentity
    try:marker=db.get(EvaluationEnvironmentIdentity,identifier)
    except DBAPIError:
        db.rollback();raise EnvironmentDenied('Environment identity schema unavailable') from None
    if not marker or marker.fingerprint!=fingerprint or marker.purpose!='isolated-development':
        raise EnvironmentDenied('Database identity marker missing or different')
    if db.get_bind().dialect.name=='postgresql':
        from sqlalchemy import text
        database=db.execute(text('SELECT current_database()')).scalar_one()
        if database!=make_url(s.database_url).database:raise EnvironmentDenied('Server database identity differs')
    return fingerprint
