"""Ingesta SECOP (protegida por JWT) y auditoría de sincronizaciones."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.db.models import SyncRun, User
from app.db.session import get_db
from app.schemas import SyncIn
from app.services.ingest import sync_source

router = APIRouter(prefix="/api/sync", tags=["secop"])


@router.post("/secop")
def run_sync(data: SyncIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Ejecuta una ingesta incremental del dataset solicitado (paginación + upsert idempotente)."""
    run = sync_source(db, data.source, max_pages=data.max_pages, extra_where=data.extra_where)
    return {
        "id": run.id, "dataset": run.dataset, "upserted": run.upserted,
        "duplicates": run.duplicates, "errors": run.errors,
        "started_at": run.started_at, "finished_at": run.finished_at,
        "detail": run.detail,
    }


@router.get("/runs")
def list_runs(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    runs = db.query(SyncRun).order_by(SyncRun.started_at.desc()).limit(20).all()
    return [{
        "id": r.id, "dataset": r.dataset, "started_at": r.started_at, "finished_at": r.finished_at,
        "pages": r.pages, "upserted": r.upserted, "duplicates": r.duplicates, "errors": r.errors,
        "watermark": r.watermark,
    } for r in runs]
