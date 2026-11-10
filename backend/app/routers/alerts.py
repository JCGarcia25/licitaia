"""Sistema de alertas: in-app, preferencias y resumen diario (SMTP opcional)."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.db.models import Alert, AlertPrefs, CompanyProfile, User, UserOpportunity, Opportunity
from app.db.session import get_db
from app.schemas import AlertPrefsIn
from app.services import alerts as alerts_service
from app.services.notifier import send_email
from app.services.quota import require_pro
import re
from app.core.config import get_settings

router = APIRouter(prefix="/api/alerts", tags=["alertas"])

def _recipients(value: str | None, fallback: str) -> list[str]:
    candidates = [x.strip() for x in re.split(r"[,;\n]+", value or "") if x.strip()]
    valid = [x for x in candidates if re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", x)]
    return valid or [fallback]


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
    return {"email_enabled": prefs.email_enabled, "email_to": prefs.email_to or user.email, "high_score_threshold": prefs.high_score_threshold,
            "close_days": prefs.close_days or [10, 5, 1], "digest_hour": prefs.digest_hour}


@router.put("/prefs")
def put_prefs(data: AlertPrefsIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    prefs = db.query(AlertPrefs).filter(AlertPrefs.user_id == user.id).first()
    if not prefs:
        prefs = AlertPrefs(user_id=user.id)
        db.add(prefs)
    prefs.email_enabled = data.email_enabled
    prefs.email_to = data.email_to or user.email
    prefs.high_score_threshold = data.high_score_threshold
    prefs.close_days = data.close_days
    prefs.digest_hour = data.digest_hour
    db.commit()
    # En cuentas nuevas puede no existir todavía ningún score. Calculamos el
    # perfil una sola vez al guardar preferencias para que la bandeja pueda
    # generar alertas inmediatamente, sin esperar al ciclo del worker.
    tiene_scores = db.query(UserOpportunity.id).filter(
        UserOpportunity.user_id == user.id,
        UserOpportunity.score.isnot(None),
        UserOpportunity.score > 0,
    ).first()
    if not tiene_scores and db.query(CompanyProfile.id).filter(CompanyProfile.user_id == user.id).first():
        alerts_service.rescore_user(db, user.id)
    # Recalcula las alertas de compatibilidad con el nuevo umbral para que la
    # bandeja se actualice inmediatamente, sin esperar al worker programado.
    created = alerts_service.create_alerts_for_user(db, user.id, high_score=data.high_score_threshold)
    return {"ok": True, "alertas_creadas": created, **data.model_dump(), "email_to": prefs.email_to}


@router.delete("/prefs")
def delete_prefs(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Restablece las preferencias de alertas a sus valores iniciales."""
    prefs = db.query(AlertPrefs).filter(AlertPrefs.user_id == user.id).first()
    if prefs:
        db.delete(prefs)
        db.commit()
    return {"ok": True, "message": "Preferencias restablecidas."}


@router.post("/digest")
def run_digest_now(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Ejecuta el ciclo de alertas ahora (alta compatibilidad, recordatorios, resumen)."""
    require_pro(db, user)
    prefs = db.query(AlertPrefs).filter(AlertPrefs.user_id == user.id).first()
    threshold = prefs.high_score_threshold if prefs else 70
    created = alerts_service.create_alerts_for_user(db, user.id, high_score=threshold)
    reminders = alerts_service.close_reminders(db, user.id, days=(prefs.close_days if prefs else None) or [10, 5, 1])
    # resumen por correo solo si está habilitado
    sent = False
    reason = "desactivado"
    if prefs and prefs.email_enabled and not user.email_verified:
        reason = "correo_no_verificado"
    elif prefs and prefs.email_enabled and user.email_verified:
        reason = "envio_no_confirmado"
        uos = db.query(UserOpportunity).filter(UserOpportunity.user_id == user.id).all()
        alta = [u for u in uos if u.score >= threshold]
        cuerpo = ["Estas son las oportunidades compatibles visibles en tu bandeja de MySECOP:"]
        alert_rows = db.query(Alert).filter(Alert.user_id == user.id).order_by(Alert.created_at.desc()).limit(20).all()
        if alert_rows:
            cuerpo.extend([f"• {a.title} — {a.body}" for a in alert_rows])
        else:
            cuerpo.append("No hay oportunidades nuevas en este momento. Revisa tu bandeja para consultar las oportunidades disponibles.")
        cuerpo.append("La fuente oficial de referencia es siempre el expediente en SECOP.")
        texto = "\n".join(cuerpo)
        for destinatario in _recipients(prefs.email_to, user.email):
            try:
                enviado = send_email(destinatario, "MySECOP — Tus oportunidades compatibles", texto,
                                     html_body=alerts_service.email_html("Tus oportunidades compatibles", cuerpo,
                                         f"{get_settings().frontend_url.rstrip('/')}/app/alertas"))
            except TypeError:
                enviado = send_email(destinatario, "MySECOP — Tus oportunidades compatibles", texto)
            sent = sent or enviado
        reason = "enviado" if sent else ("smtp_no_configurado" if not get_settings().smtp_host else "error_smtp")
    return {"alertas_creadas": created, "recordatorios_cierre": reminders, "correo_enviado": sent, "correo_motivo": reason}
