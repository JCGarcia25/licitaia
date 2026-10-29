"""Tareas asíncronas (Celery + Redis; con ejecución local si Redis no está disponible)."""
from __future__ import annotations

import logging

from app.core.config import get_settings

logger = logging.getLogger("licitaia.workers")
settings = get_settings()

try:
    from celery import Celery
    from celery.schedules import crontab

    celery_app = Celery(
        "licitaia",
        broker=settings.redis_url,
        backend=settings.redis_url,
        include=["app.workers.tasks"],
    )
    celery_app.conf.update(
        task_serializer="json",
        result_serializer="json",
        accept_content=["json"],
        timezone=settings.timezone,
        enable_utc=True,
    )
    celery_app.conf.beat_schedule = {
        "sincronizar-secop-cada-30-min": {
            "task": "app.workers.tasks.sync_secop_task",
            "schedule": settings.secop_sync_every_minutes * 60,
        },
        "recordatorios-cierre-cada-hora": {
            "task": "app.workers.tasks.close_reminders_task",
            "schedule": 3600,
        },
        # 07:00 America/Bogota (config digest_hour) vía crontab con zona horaria
        "resumen-diario-7am-bogota": {
            "task": "app.workers.tasks.daily_digest_task",
            "schedule": crontab(hour=settings.digest_hour, minute=0, timezone=settings.timezone),
            "options": {"expires": 3600},
        },
    }
except Exception as exc:  # Redis/Celery opcional en desarrollo
    celery_app = None
    logger.warning("Celery no disponible (%s): las tareas se ejecutarán en línea", exc)


def run_or_delay(task_name: str, fn, *args, **kwargs):
    """Ejecuta la tarea vía Celery si está disponible; si no, en línea (desarrollo)."""
    if celery_app is not None:
        try:
            return celery_app.send_task(task_name, args=args, kwargs=kwargs).id
        except Exception as exc:
            logger.warning("Cola no disponible (%s); ejecutando en línea", exc)
    return fn(*args, **kwargs)
