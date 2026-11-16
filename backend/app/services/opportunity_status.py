"""Clasificación conservadora de la vigencia con evidencia disponible."""
from datetime import datetime, timezone
import unicodedata

from sqlalchemy import and_, func, or_

from app.db.models import Opportunity


def normalize_text(value):
    text = unicodedata.normalize('NFKD', (value or '').strip().casefold())
    return ' '.join(''.join(c for c in text if not unicodedata.combining(c)).split())


STATES = {
    'cancelado': 'CANCELLED', 'cancelada': 'CANCELLED', 'retirado': 'CANCELLED',
    'cerrado': 'CLOSED', 'cerrada': 'CLOSED', 'terminado': 'CLOSED',
    'terminado sin liquidar': 'CLOSED', 'desierto': 'CLOSED', 'desierta': 'CLOSED',
    'finalizado': 'CLOSED', 'liquidado': 'CLOSED', 'suspendido': 'CLOSED',
    'adjudicado': 'AWARDED', 'adjudicada': 'AWARDED',
    'en ejecucion': 'IN_EXECUTION',
}
OPEN_STATES = {'abierto', 'abierta', 'en proceso', 'convocatoria', 'activo', 'activa'}


def classify_opportunity(opportunity, now=None):
    now = now or datetime.now(timezone.utc)
    def utc(value):
        return value.replace(tzinfo=timezone.utc) if value and value.tzinfo is None else value
    estado = normalize_text(opportunity.estado)
    closing = utc(opportunity.fecha_cierre)
    published = utc(opportunity.fecha_publicacion)
    if opportunity.cancelled:
        code, reason = 'CANCELLED', 'La fuente indica que el proceso fue cancelado.'
    elif getattr(opportunity, 'source', None) == 'secop2_contratos':
        code, reason = 'IN_EXECUTION', 'El registro corresponde a un contrato, no a una convocatoria abierta.'
    elif getattr(opportunity, 'source', None) == 'secop1':
        code, reason = 'HISTORICAL', 'La fuente registra relaciones entre procesos y adjudicaciones; no confirma una convocatoria abierta.'
    elif estado in STATES:
        code, reason = STATES[estado], 'Clasificación según el estado de la fuente.'
    elif closing and closing <= now:
        code, reason = 'CLOSED', 'La fecha de cierre registrada ya pasó.'
    elif published and published > now:
        code, reason = 'UPCOMING', 'La fecha de publicación es futura.'
    elif estado in OPEN_STATES and closing:
        code, reason = 'OPEN', 'El estado indica apertura y la fecha de cierre registrada es futura.'
    else:
        code, reason = 'UNKNOWN', 'No hay evidencia suficiente para confirmar que recibe ofertas.'
    return {'status': code, 'reason': reason, 'original_state': opportunity.estado,
            'source': getattr(opportunity, 'source', None), 'closing_date': opportunity.fecha_cierre,
            'updated_at': getattr(opportunity, 'updated_at', None)}


def potentially_current_condition():
    """Excluir terminales conocidos; UNKNOWN permanece explícitamente desconocido."""
    state = func.lower(func.trim(func.coalesce(Opportunity.estado, '')))
    for accented, plain in (('á', 'a'), ('é', 'e'), ('í', 'i'), ('ó', 'o'), ('ú', 'u')):
        state = func.replace(state, accented, plain)
    return and_(or_(Opportunity.cancelled.is_(False), Opportunity.cancelled.is_(None)),
                or_(Opportunity.source.is_(None), Opportunity.source.notin_(['secop2_contratos', 'secop1'])),
                ~state.in_(tuple(STATES)),
                or_(Opportunity.fecha_publicacion.is_(None), Opportunity.fecha_publicacion <= datetime.utcnow()),
                or_(Opportunity.fecha_cierre.is_(None), Opportunity.fecha_cierre > datetime.utcnow()))
