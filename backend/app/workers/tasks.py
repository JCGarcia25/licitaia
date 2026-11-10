"""Tareas programadas: ingesta SECOP, re-scoring, recordatorios y resumen diario."""
from __future__ import annotations

import logging
import httpx
from datetime import datetime

logger = logging.getLogger("licitaia.tasks")


def sync_mercadopago_subscription(external_id: str) -> dict:
    """Consulta Mercado Pago y refleja el estado autorizado/cancelado en DB.

    Es idempotente: los reintentos del webhook solo vuelven a escribir el
    mismo estado y nunca conceden Pro sin confirmación oficial.
    """
    from app.core.config import get_settings
    from app.db.models import Subscription
    from app.db.session import SessionLocal
    from app.services.audit import log_action

    settings = get_settings()
    if not settings.mercadopago_access_token:
        raise RuntimeError("MERCADOPAGO_ACCESS_TOKEN no configurado")
    response = httpx.get(
        f"https://api.mercadopago.com/preapproval/{external_id}",
        headers={"Authorization": f"Bearer {settings.mercadopago_access_token}"}, timeout=15,
    )
    response.raise_for_status()
    remote = response.json()
    db = SessionLocal()
    try:
        sub = db.query(Subscription).filter(Subscription.external_id == str(external_id)).first()
        if not sub:
            return {"ok": True, "ignored": True, "reason": "subscription_not_found"}
        remote_status = remote.get("status")
        # Mercado Pago reports a cancelled preapproval immediately after the
        # user disables renewal. Keep Pro access through the already-paid
        # period instead of downgrading the account on the next webhook.
        if remote_status == "authorized":
            new_status = "activa"
        elif remote_status in {"cancelled", "paused"}:
            new_status = (
                "cancelada_pendiente"
                if sub.current_period_end and sub.current_period_end > datetime.utcnow()
                else "cancelada"
            )
        else:
            new_status = "pendiente_pago"
        sub.status = new_status
        if new_status == "activa":
            sub.plan = "profesional"
        db.commit()
        user = getattr(sub, "user", None)
        if user:
            log_action(db, user, "sincronizar_pago_mercadopago", "subscription", sub.id,
                       {"external_id": str(external_id), "status": new_status})
        return {"ok": True, "subscription_id": sub.id, "status": new_status}
    finally:
        db.close()


def sync_secop() -> dict:
    """Ingesta incremental de los datasets SECOP II configurados."""
    from app.db.session import SessionLocal
    from app.services.ingest import sync_source

    results = {}
    db = SessionLocal()
    try:
        for source in ("secop2_procesos", "secop2_contratos"):
            run = sync_source(db, source, max_pages=10)
            results[source] = {"upserted": run.upserted, "duplicates": run.duplicates, "errors": run.errors}
    finally:
        db.close()
    logger.info("sync_secop: %s", results)
    return results


def rescore_all() -> dict:
    from app.db.models import CompanyProfile, User
    from app.db.session import SessionLocal
    from app.services.alerts import rescore_user, create_alerts_for_user

    db = SessionLocal()
    try:
        total, alerts = 0, 0
        for (user_id,) in db.query(CompanyProfile.user_id).all():
            total += rescore_user(db, user_id)
            alerts += create_alerts_for_user(db, user_id, high_score=70)
        return {"puntuadas": total, "alertas": alerts}
    finally:
        db.close()


def close_reminders_all() -> int:
    from app.db.models import UserOpportunity, AlertPrefs, User
    from app.db.session import SessionLocal
    from app.services.alerts import close_reminders
    from app.services.notifier import send_email
    from app.services.alerts import email_html

    db = SessionLocal()
    try:
        created = 0
        for (user_id,) in db.query(UserOpportunity.user_id).distinct().all():
            count = close_reminders(db, user_id)
            created += count
            if count:
                prefs = db.query(AlertPrefs).filter(AlertPrefs.user_id == user_id, AlertPrefs.email_enabled.is_(True)).first()
                user = db.query(User).filter(User.id == user_id, User.email_verified.is_(True)).first()
                if prefs and user:
                    body = [f"Se generaron {count} recordatorio(s) de cierre según tus preferencias.", "Revisa las oportunidades en MySECOP para consultar fechas y documentos."]
                    import re
                    recipients = [x.strip() for x in re.split(r"[,;\n]+", prefs.email_to or "") if x.strip()] or [user.email]
                    for recipient in recipients:
                        send_email(recipient, "MySECOP — Recordatorios de cierre", "\n".join(body), email_html("Recordatorios de cierre", body))
        return created
    finally:
        db.close()


def daily_digest() -> dict:
    from app.core.config import get_settings
    from app.db.models import AlertPrefs, User
    from app.db.session import SessionLocal
    from app.services.notifier import send_email
    from app.services.alerts import email_html

    db = SessionLocal()
    try:
        sent, skipped = 0, 0
        rows = (db.query(AlertPrefs, User)
                .join(User, User.id == AlertPrefs.user_id)
                .filter(AlertPrefs.email_enabled.is_(True), User.email_verified.is_(True))
                .all())
        for prefs, user in rows:
            from app.db.models import Alert
            cuerpo = ["Estas son las oportunidades compatibles visibles en tu bandeja de MySECOP:"]
            rows_alert = db.query(Alert).filter(Alert.user_id == user.id).order_by(Alert.created_at.desc()).limit(20).all()
            cuerpo.extend([f"• {a.title} — {a.body}" for a in rows_alert] or ["No hay oportunidades nuevas en este momento."])
            cuerpo.append("La fuente oficial de referencia es siempre el expediente en SECOP.")
            import re
            recipients = [x.strip() for x in re.split(r"[,;\n]+", prefs.email_to or "") if x.strip()] or [user.email]
            delivered = False
            for destinatario in recipients:
                if send_email(
                    destinatario,
                    "MySECOP — Resumen de tus oportunidades compatibles",
                    "\n".join(cuerpo),
                    html_body=email_html(
                        "Tus oportunidades compatibles",
                        cuerpo,
                        f"{get_settings().frontend_url.rstrip('/')}/app/alertas",
                    ),
                ):
                    delivered = True
            if delivered: sent += 1
            else: skipped += 1
        return {"correos_enviados": sent, "omitidos": skipped}
    finally:
        db.close()


# Registro de tareas para Celery
try:
    from app.workers.celery_app import celery_app  # noqa: E402

    celery_app.task(name="app.workers.tasks.sync_secop_task")(sync_secop)
    celery_app.task(name="app.workers.tasks.rescore_all_task")(rescore_all)
    celery_app.task(name="app.workers.tasks.close_reminders_task")(close_reminders_all)
    celery_app.task(name="app.workers.tasks.daily_digest_task")(daily_digest)
    celery_app.task(name="app.workers.tasks.sync_mercadopago_subscription_task")(sync_mercadopago_subscription)
except Exception:
    pass
