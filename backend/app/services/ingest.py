"""Servicio de ingesta: Socrata → normalización → PostgreSQL (upsert sin duplicados)."""
from __future__ import annotations

import logging
from datetime import datetime

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models import Opportunity, OpportunityEmbedding, SyncRun
from app.services.embeddings import embed
from app.services.secop_client import SocrataClient, normalize_row

logger = logging.getLogger("licitaia.ingest")

# La fuente oficial es la referencia definitiva: se conserva published_at (fuente),
# captured_at (ingesta) y updated_at, y el enlace urlproceso al expediente original.
UNIQUE_STATE_FIELDS = ("estado_resumen", "estado_de_apertura_del_proceso", "estado_del_procedimiento")


def _row_date(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.strptime(value[:19], "%Y-%m-%dT%H:%M:%S")
    except (ValueError, TypeError):
        try:
            return datetime.strptime(value[:10], "%Y-%m-%d")
        except (ValueError, TypeError):
            return None


def sync_source(
    db: Session,
    source: str,
    since: datetime | None = None,
    max_pages: int = 5,
    extra_where: str | None = None,
) -> SyncRun:
    """Ingesta incremental y upsert idempotente de un dataset SECOP verificado."""
    settings = get_settings()
    run = SyncRun(dataset=source, detail={"max_pages": max_pages, "extra_where": extra_where})
    db.add(run)
    db.commit()

    client = SocrataClient()
    try:
        rows = client.fetch_incremental(source, since=since, max_pages=max_pages, extra_where=extra_where)
    except Exception as exc:  # error de red/API: se registra, no se rompe el sistema
        run.errors += 1
        run.detail["error"] = str(exc)[:500]
        run.finished_at = datetime.utcnow()
        db.commit()
        logger.error("Error de ingesta %s: %s", source, exc)
        return run

    # watermark: última fecha de actualización procesada del propio dataset
    watermark_field = {
        "secop2_procesos": "fecha_de_ultima_publicaci",
        "secop2_contratos": "ultima_actualizacion",
        "secop1": "fecha_de_ultima_publi",
    }.get(source)
    for row in rows:
        run.pages = max(run.pages, 1)
        data = normalize_row(source, row)
        if not data["source_id"]:
            run.errors += 1
            continue
        existing = (
            db.query(Opportunity)
            .filter(Opportunity.source == source, Opportunity.source_id == data["source_id"])
            .first()
        )
        if existing:
            run.duplicates += 1
            # actualizar campos que cambian en la fuente (estado, cancelación, valores)
            for field in ("estado", "cancelled", "valor", "url_oficial"):
                setattr(existing, field, data[field])
            updated = _row_date(row.get(watermark_field))
            if updated:
                existing.updated_at = updated
            continue
        opp = Opportunity(**data)
        db.add(opp)
        db.flush()
        db.add(OpportunityEmbedding(
            opportunity_id=opp.id,
            model=f"{settings.embedding_provider}-{settings.embedding_dim}",
            vector=embed(f"{opp.objeto or ''} {opp.descripcion or ''}"),
        ))
        run.upserted += 1

    run.finished_at = datetime.utcnow()
    db.commit()
    logger.info("Ingesta %s: %s nuevas, %s duplicadas, %s errores", source, run.upserted, run.duplicates, run.errors)
    return run


def seed_sample(db: Session, rows: list[tuple[str, dict]]) -> int:
    """Carga filas de ejemplo ya normalizadas (para pruebas y demo sin red)."""
    created = 0
    for source, row in rows:
        data = normalize_row(source, row)
        exists = db.query(Opportunity).filter(
            Opportunity.source == source, Opportunity.source_id == data["source_id"]
        ).first()
        if exists:
            continue
        opp = Opportunity(**data)
        db.add(opp)
        db.flush()
        db.add(OpportunityEmbedding(
            opportunity_id=opp.id,
            vector=embed(f"{opp.objeto or ''} {opp.descripcion or ''}"),
        ))
        created += 1
    db.commit()
    return created
