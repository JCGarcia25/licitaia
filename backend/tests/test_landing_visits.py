from datetime import datetime, timedelta
from uuid import uuid4

from app.db.models import LandingVisit


def test_visita_anonima_y_acceso_restringido(client, db, auth_headers):
    visit_id = str(uuid4())
    assert client.post('/api/admin/landing-visit', json={'id': 'invalid'}).status_code == 422
    assert client.post('/api/admin/landing-visit', json={'id': visit_id, 'visible': True}).status_code == 204
    visit = db.get(LandingVisit, visit_id)
    visit.last_seen_at = datetime.utcnow() - timedelta(seconds=20)
    db.commit()
    assert client.post('/api/admin/landing-visit', json={'id': visit_id, 'visible': False}).status_code == 204
    db.refresh(visit)
    assert 19 <= visit.duration_seconds <= 21
    assert visit.visible is False
    assert client.get('/api/admin/overview', headers=auth_headers).status_code == 403
