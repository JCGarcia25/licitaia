from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from app.services.opportunity_status import classify_opportunity


def item(**kwargs):
    return SimpleNamespace(**({'estado': 'En proceso', 'cancelled': False, 'source': 'secop2_procesos',
                              'fecha_cierre': None, 'fecha_publicacion': None, 'updated_at': None} | kwargs))


def test_evidencia_de_cierre_y_estados():
    now = datetime(2026, 11, 14, tzinfo=timezone.utc)
    assert classify_opportunity(item(), now)['status'] == 'UNKNOWN'
    assert classify_opportunity(item(fecha_cierre=now + timedelta(days=1)), now)['status'] == 'OPEN'
    assert classify_opportunity(item(fecha_cierre=now - timedelta(seconds=1)), now)['status'] == 'CLOSED'
    assert classify_opportunity(item(estado=' En EJECUCIÓN '), now)['status'] == 'IN_EXECUTION'
    assert classify_opportunity(item(estado='Adjudicada'), now)['status'] == 'AWARDED'
    assert classify_opportunity(item(cancelled=True, fecha_cierre=now + timedelta(days=2)), now)['status'] == 'CANCELLED'
    assert classify_opportunity(item(source='secop2_contratos'), now)['status'] == 'IN_EXECUTION'
    assert classify_opportunity(item(fecha_publicacion=now + timedelta(days=1)), now)['status'] == 'UPCOMING'
