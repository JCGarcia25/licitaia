"""Tareas programadas: ingesta SECOP, re-scoring, recordatorios y resumen diario."""
from __future__ import annotations

import logging
from datetime import datetime

logger = logging.getLogger("licitaia.tasks")


def sync_secop() -> dict:
    """Ingesta incremental de los datasets SECOP II configurados."""
    from app.db.session import SessionLocal
    from app.services.ingest import sync_source

    results = {}
    db = SessionLocal()
    try:
        # watermark: última fecha de actualización registrada por fuente
        from app.db.models import SyncRun

        for source in ("secop2_procesos", "secop2_contratos"):
            last = db.query(SyncRun).filter(SyncRun.dataset == source, SyncRun.finished_at.isnot(None)).order_by(
                SyncRun.started_at.desc()).first()
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
    from app.db.models import UserOpportunity
    from app.db.session import SessionLocal
    from app.services.alerts import close_reminders

    db = SessionLocal()
    try:
        created = 0
        for (user_id,) in db.query(UserOpportunity.user_id).distinct().all():
            created += close_reminders(db, user_id)
        return created
    finally:
        db.close()


def daily_digest() -> dict:
    from app.db.models import AlertPrefs, User
    from app.db.session import SessionLocal
    from app.services.notifier import send_email

    db = SessionLocal()
    try:
        sent, skipped = 0, 0
        for prefs in db.query(AlertPrefs).filter(AlertPrefs.email_enabled.is_(True)).all():
            user = db.query(User).filter(User.id == prefs.user_id).first()
            if not user:
                continue
            cuerpo = [
                "Resumen diario LicitaIA",
                f"Umbral de alta compatibilidad: {prefs.high_score_threshold}%",
                f"Recordatorios de cierre activos: D-{', D-'.join(str(d) for d in (prefs.close_days or [10, 5, 1]))}",
                "",
                "Revise su panel en LicitaIA. La fuente oficial de referencia es siempre el expediente en SECOP.",
            ]
            if send_email(user.email, "LicitaIA — Resumen diario", "\n".join(cuerpo)):
                sent += 1
            else:
                skipped += 1
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
except Exception:
    pass
