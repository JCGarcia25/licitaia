"""Sistema de alertas: in-app, preferencias y resumen diario (SMTP opcional)."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.db.models import Alert, AlertPrefs, User, UserOpportunity, Opportunity
from app.db.session import get_db
from app.schemas import AlertPrefsIn
from app.services import alerts as alerts_service
from app.services.notifier import send_email

router = APIRouter(prefix="/api/alerts", tags=["alertas"])


@router.get("")
def list_alerts(solo_no_leidas: bool = False, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    query = db.query(Alert).filter(Alert.user_id == user.id)
    if solo_no_leidas:
        query = query.filter(Alert.read_at.is_(None))
    rows = query.order_by(Alert.created_at.desc()).limit(50).all()
    return [{
        "id": a.id, "tipo": a.tipo, "title": a.title, "body": a.body,
        "opportunity_id": a.opportunity_id, "read_at": a.read_at, "created_at": a.created_at,
    } for a in rows]


@router.post("/{alert_id}/read")
def mark_read(alert_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    alert = db.query(Alert).filter(Alert.id == alert_id, Alert.user_id == user.id).first()
    if not alert:
        return {"ok": False}
    from datetime import datetime
    alert.read_at = datetime.utcnow()
    db.commit()
    return {"ok": True}


@router.post("/read-all")
def mark_all_read(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    from datetime import datetime
    db.query(Alert).filter(Alert.user_id == user.id, Alert.read_at.is_(None)).update({"read_at": datetime.utcnow()})
    db.commit()
    return {"ok": True}


@router.get("/prefs")
def get_prefs(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    prefs = db.query(AlertPrefs).filter(AlertPrefs.user_id == user.id).first()
    if not prefs:
        prefs = AlertPrefs(user_id=user.id)
        db.add(prefs)
        db.commit()
    return {"email_enabled": prefs.email_enabled, "high_score_threshold": prefs.high_score_threshold,
            "close_days": prefs.close_days or [10, 5, 1], "digest_hour": prefs.digest_hour}


@router.put("/prefs")
def put_prefs(data: AlertPrefsIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    prefs = db.query(AlertPrefs).filter(AlertPrefs.user_id == user.id).first()
    if not prefs:
        prefs = AlertPrefs(user_id=user.id)
        db.add(prefs)
    prefs.email_enabled = data.email_enabled
    prefs.high_score_threshold = data.high_score_threshold
    prefs.close_days = data.close_days
    prefs.digest_hour = data.digest_hour
    db.commit()
    return {"ok": True, **data.model_dump()}


@router.post("/digest")
def run_digest_now(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Ejecuta el ciclo de alertas ahora (alta compatibilidad, recordatorios, resumen)."""
    prefs = db.query(AlertPrefs).filter(AlertPrefs.user_id == user.id).first()
    threshold = prefs.high_score_threshold if prefs else 70
    created = alerts_service.create_alerts_for_user(db, user.id, high_score=threshold)
    reminders = alerts_service.close_reminders(db, user.id, days=(prefs.close_days if prefs else None) or [10, 5, 1])
    # resumen por correo solo si está habilitado
    sent = False
    if prefs and prefs.email_enabled and user.email_verified:
        uos = db.query(UserOpportunity).filter(UserOpportunity.user_id == user.id).all()
        alta = [u for u in uos if u.score >= threshold]
        cuerpo = [
            f"Resumen LicitaIA para {user.email}",
            f"Oportunidades puntuadas: {len(uos)}",
            f"Alta compatibilidad (>= {threshold}%): {len(alta)}",
            f"Alertas nuevas creadas: {created + reminders}",
            "",
            "La fuente oficial de referencia es siempre el expediente en SECOP.",
        ]
        sent = send_email(user.email, "LicitaIA — Resumen diario", "\n".join(cuerpo))
    return {"alertas_creadas": created, "recordatorios_cierre": reminders, "correo_enviado": sent}
