"""Ingesta SECOP (protegida por JWT) y auditoría de sincronizaciones."""
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.db.models import SyncRun, SyncUsage, User
from app.db.session import get_db
from app.schemas import SyncIn
from app.services.ingest import sync_source
from app.services.quota import get_subscription, subscription_is_pro

router = APIRouter(prefix="/api/sync", tags=["secop"])


@router.post("/secop")
def run_sync(data: SyncIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Ejecuta una ingesta incremental del dataset solicitado (paginación + upsert idempotente)."""
    is_pro = subscription_is_pro(get_subscription(db, user))
    month = datetime.utcnow().strftime("%Y-%m")
    usage = db.query(SyncUsage).filter(SyncUsage.user_id == user.id, SyncUsage.month == month).first()
    used = usage.successful_runs if usage else 0
    if not is_pro and used >= 3:
        raise HTTPException(402, "Has utilizado tus 3 sincronizaciones gratuitas de este mes. Actualiza a MySECOP Pro para mantener tus oportunidades actualizadas.")
    try:
        run = sync_source(db, data.source, user_id=user.id, max_pages=data.max_pages, extra_where=data.extra_where)
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=502, detail=f"No fue posible consultar SECOP: {str(exc)[:300]}") from exc
    if not is_pro and run.errors == 0:
        if not usage:
            usage = SyncUsage(user_id=user.id, month=month, successful_runs=0)
            db.add(usage)
        usage.successful_runs += 1
        db.commit()
        used += 1
    return {
        "id": run.id, "dataset": run.dataset, "upserted": run.upserted,
        "duplicates": run.duplicates, "errors": run.errors,
        "started_at": run.started_at, "finished_at": run.finished_at,
        "detail": run.detail,
        "sync_free_used": used if not is_pro else None,
        "sync_free_limit": 3 if not is_pro else None,
    }


@router.get("/runs")
def list_runs(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    # Las oportunidades y sus ingestas son un catálogo compartido de SECOP.
    # El límite Free sí es por usuario (ver /usage), pero el historial no debe
    # desaparecer al cambiar de cuenta: cualquier usuario autenticado puede
    # consultar las últimas corridas globales.
    runs = db.query(SyncRun).order_by(SyncRun.started_at.desc()).limit(20).all()
    return [{
        "id": r.id, "dataset": r.dataset, "started_at": r.started_at, "finished_at": r.finished_at,
        "pages": r.pages, "upserted": r.upserted, "duplicates": r.duplicates, "errors": r.errors,
        "watermark": r.watermark,
    } for r in runs]

@router.get("/usage")
def sync_usage(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    month = datetime.utcnow().strftime("%Y-%m")
    usage = db.query(SyncUsage).filter(SyncUsage.user_id == user.id, SyncUsage.month == month).first()
    is_pro = subscription_is_pro(get_subscription(db, user))
    return {"es_pro": is_pro, "used": usage.successful_runs if usage else 0, "limit": None if is_pro else 3, "remaining": None if is_pro else max(0, 3 - (usage.successful_runs if usage else 0))}
