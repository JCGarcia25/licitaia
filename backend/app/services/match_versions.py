"""Identidades deterministas de entradas e invalidación dentro de la transacción."""
import hashlib
import json
from pathlib import Path

from sqlalchemy import and_, event, inspect, select
from sqlalchemy.orm import Session, object_session

from app.core.config import get_settings

PROFILE_FIELDS = ('sector', 'actividades', 'productos_servicios', 'keywords', 'unspsc_codes',
                  'departamentos', 'presupuesto_min', 'presupuesto_max', 'modalidades',
                  'experiencia', 'capacidades', 'learning_weights')
OPPORTUNITY_FIELDS = ('objeto', 'descripcion', 'modalidad', 'tipo_contrato', 'unspsc_code',
                      'departamento', 'valor', 'estado', 'cancelled', 'source',
                      'fecha_publicacion', 'fecha_cierre')
EMBEDDING_CODE = hashlib.sha256(Path(__file__).with_name('embeddings.py').read_bytes()).hexdigest()
ALGORITHM_CODE = hashlib.sha256(Path(__file__).with_name('matcher.py').read_bytes()).hexdigest()


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     separators=(',', ':'), default=str).encode()).hexdigest()


def algorithm_version():
    return digest([get_settings().match_algorithm_version, ALGORITHM_CODE])


def embedding_spec():
    settings = get_settings()
    external = settings.embedding_provider == 'openai' and bool(settings.openai_api_key)
    return ('openai-text-embedding-3-small', 1536) if external else ('fake-hash-v1', settings.embedding_dim)


def embedding_version():
    return digest([embedding_spec(), EMBEDDING_CODE])


def embedding_model_label():
    return f'match:{embedding_version()}'


def profile_version(profile):
    arrays = {'keywords', 'unspsc_codes', 'departamentos', 'modalidades'}
    value = {}
    for key in PROFILE_FIELDS:
        item = getattr(profile, key)
        value[key] = (item or []) if key in arrays else ((item or {}) if key == 'learning_weights' else item)
    # Anticipa defaults solo para filas nuevas; en filas existentes str(None)
    # y str('') producen textos diferentes en el vector del flujo heredado.
    for key in ('sector', 'actividades', 'productos_servicios', 'experiencia', 'capacidades'):
        if inspect(profile).pending or inspect(profile).transient:
            value[key] = value[key] or ''
    return digest(value)


def embedding_content_version(opportunity):
    return digest([opportunity.objeto or '', opportunity.descripcion or ''])


_UNSET = object()


def opportunity_version(opportunity, embedding=_UNSET):
    vector = opportunity.embedding if embedding is _UNSET else embedding
    values = {key: getattr(opportunity, key) for key in OPPORTUNITY_FIELDS}
    values['cancelled'] = bool(values['cancelled'])
    values['source'] = values['source'] or 'secop2_procesos'
    return digest([values, [vector.model, vector.content_version, vector.vector] if vector is not None else None])


def score_versions_condition(failed=False):
    from app.db.models import CompanyProfile, Opportunity, UserOpportunity as U
    from app.services.opportunity_status import potentially_current_condition
    def version(key):
        return U.failed_input_versions[key].as_string() if failed else getattr(U,key)
    profile = select(CompanyProfile.id).where(
        CompanyProfile.user_id == U.user_id,
        CompanyProfile.match_version == version('profile_version'),
        CompanyProfile.match_version.isnot(None),
    ).correlate(U).exists()
    opportunity = select(Opportunity.id).where(
        Opportunity.id == U.opportunity_id,
        Opportunity.match_version == version('opportunity_version'),
        Opportunity.match_version.isnot(None), potentially_current_condition(),
    ).correlate(U).exists()
    return and_(profile, opportunity, version('algorithm_version') == algorithm_version(),
                version('embedding_version') == embedding_version())


def failed_score_condition():
    from sqlalchemy import or_
    from app.db.models import UserOpportunity as U
    # Compatibilidad explícita con fallos anteriores a la metadata separada.
    return and_(U.match_state == 'FAILED', or_(
        and_(U.failed_input_versions.isnot(None),score_versions_condition(failed=True)),
        and_(U.failed_input_versions.is_(None),score_versions_condition())))


def current_score_condition():
    from app.db.models import UserOpportunity as U
    return and_(U.match_state == 'CURRENT', U.score.isnot(None), score_versions_condition())


def calculation_state(uo):
    if uo is None:
        return 'PENDING'
    valid = getattr(uo, '_match_current', None)
    if valid is None:
        db = object_session(uo)
        valid = bool(db and db.query(current_score_condition()).filter(type(uo).id == uo.id).scalar())
    if valid:
        return 'CURRENT'
    if uo.match_state == 'FAILED':
        db = object_session(uo)
        compatible = getattr(uo, '_match_failed_current', None)
        if compatible is None and db:
            compatible = db.query(failed_score_condition()).filter(type(uo).id == uo.id).scalar()
        if compatible:
            return 'FAILED'
    return 'STALE' if uo.score is not None else 'PENDING'


def update_versions(session, flush_context, instances):
    from app.db.models import CompanyProfile, Opportunity, OpportunityEmbedding
    # Incluye embeddings añadidos/cambiados sin depender de backrefs en memoria.
    changed = list(session.new) + list(session.dirty) + list(session.deleted)
    for obj in changed:
        if isinstance(obj, CompanyProfile):
            fingerprint = profile_version(obj)
            if obj.match_version != fingerprint:
                obj.match_version = fingerprint
        elif isinstance(obj, Opportunity):
            state = inspect(obj)
            if obj in session.new or any(state.attrs[k].history.has_changes() for k in OPPORTUNITY_FIELDS):
                obj.match_version = opportunity_version(obj)
        elif isinstance(obj, OpportunityEmbedding):
            opportunity = obj.opportunity or (session.get(Opportunity, obj.opportunity_id) if obj.opportunity_id else None)
            if opportunity is not None:
                fingerprint = opportunity_version(opportunity, None if obj in session.deleted else obj)
                if opportunity.match_version != fingerprint:
                    opportunity.match_version = fingerprint


def install_version_events():
    if not event.contains(Session, 'before_flush', update_versions):
        event.listen(Session, 'before_flush', update_versions)
