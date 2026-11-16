"""Servicio de ingesta: Socrata → normalización → PostgreSQL (upsert sin duplicados)."""
from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError

from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
from app.db.models import Opportunity, OpportunityEmbedding, SyncCursor, SyncRun
from app.services.embeddings import embed
from app.services.match_versions import embedding_model_label, embedding_content_version
from app.services.secop_client import DATASETS, FIELD_MAP, SocrataClient, _parse_date, normalize_row

logger = logging.getLogger("licitaia.ingest")
LEASE_HEARTBEAT_SECONDS = 60

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


def _save_row(db: Session, source: str, raw: dict) -> str:
    """Upsert local; la transacción y el cursor pertenecen al llamador."""
    row = {key: value for key, value in raw.items() if key != "sync_row_id"}
    data = normalize_row(source, row)
    if not data["source_id"]:
        raise ValueError("La fuente devolvió un registro sin identificador del proceso")
    current = db.query(Opportunity).filter_by(source=source, source_id=data["source_id"]).first()
    if current:
        old_text = (current.objeto, current.descripcion)
        changed = False
        for field in ("entidad", "nit_entidad", "departamento", "ciudad", "objeto", "descripcion",
                      "modalidad", "tipo_contrato", "unspsc_code", "valor", "estado", "cancelled",
                      "url_oficial", "fecha_publicacion", "published_at", "raw_json"):
            if getattr(current, field) != data[field]:
                setattr(current, field, data[field])
                changed = True
        if data["fecha_cierre"] is not None and current.fecha_cierre != data["fecha_cierre"]:
            current.fecha_cierre = data["fecha_cierre"]
            changed = True
        if (old_text != (current.objeto, current.descripcion) or not current.embedding
                or current.embedding.model != embedding_model_label()
                or current.embedding.content_version != embedding_content_version(current)):
            changed = True
            vector = embed(f"{current.objeto or ''} {current.descripcion or ''}")
            settings = get_settings()
            if current.embedding:
                current.embedding.vector = vector
                current.embedding.model = embedding_model_label()
                current.embedding.content_version = embedding_content_version(current)
            else:
                db.add(OpportunityEmbedding(opportunity=current, vector=vector,
                       model=embedding_model_label(), content_version=embedding_content_version(current)))
        return "updated" if changed else "unchanged"
    current = Opportunity(**data)
    db.add(current)
    db.flush()
    settings = get_settings()
    db.add(OpportunityEmbedding(opportunity=current,
        model=embedding_model_label(), content_version=embedding_content_version(current),
        vector=embed(f"{current.objeto or ''} {current.descripcion or ''}")))
    return "inserted"


def _renew_lease(factory, source: str, token: str) -> bool:
    """Renueva únicamente una concesión todavía vigente y del mismo trabajador."""
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    with factory() as session:
        changed = session.query(SyncCursor).filter(
            SyncCursor.source == source, SyncCursor.lease_token == token,
            SyncCursor.lease_until >= now,
        ).update({SyncCursor.lease_until: now + timedelta(minutes=10)}, synchronize_session=False)
        session.commit()
        return changed == 1


def _heartbeat(factory, source: str, token: str, stop: threading.Event) -> None:
    while not stop.wait(LEASE_HEARTBEAT_SECONDS):
        try:
            if not _renew_lease(factory, source, token):
                logger.warning("La sincronización %s ya no posee un arrendamiento vigente", source)
                return
        except Exception:
            # La confirmación del lote sigue verificando el token y vencimiento.
            logger.warning("No se pudo renovar el arrendamiento de %s", source, exc_info=True)


def sync_source(db: Session, source: str, user_id: int | None = None,
                since: datetime | None = None, max_pages: int = 5,
                extra_where: str | None = None) -> SyncRun:
    """Procesa páginas confirmando cada cursor junto con sus registros."""
    if source not in DATASETS:
        raise ValueError("Fuente SECOP desconocida")
    if since or extra_where:
        raise ValueError("Las consultas parciales no pueden actualizar el cursor compartido")
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    token = str(uuid4())
    try:
        if not db.get(SyncCursor, source):
            db.add(SyncCursor(source=source, dataset_id=DATASETS[source],
                              mode="reconcile" if source == "secop1" else "incremental"))
            db.commit()
    except IntegrityError:
        db.rollback()  # otra ejecución creó la fila
    acquired = db.query(SyncCursor).filter(
        SyncCursor.source == source, SyncCursor.dataset_id == DATASETS[source],
        or_(SyncCursor.lease_until.is_(None), SyncCursor.lease_until < now),
    ).update({SyncCursor.lease_token: token, SyncCursor.lease_until: now + timedelta(minutes=10),
              SyncCursor.status: "running"}, synchronize_session=False)
    db.commit()
    if not acquired:
        raise RuntimeError("Ya hay una sincronización en curso o el dataset no coincide con el cursor")
    run = SyncRun(dataset=source, user_id=user_id, detail={"max_pages": max_pages, "owner_user_id": user_id})
    db.add(run)
    db.commit()
    client = SocrataClient()
    counts = {"inserted": 0, "updated": 0, "unchanged": 0}
    stop_heartbeat = threading.Event()
    heartbeat = threading.Thread(target=_heartbeat,
        args=(sessionmaker(bind=db.get_bind()), source, token, stop_heartbeat), daemon=True)
    heartbeat.start()
    try:
        for _ in range(max_pages):
            cursor = db.get(SyncCursor, source)
            mode, cursor_time, cursor_id = cursor.mode, cursor.cursor_time, cursor.cursor_id
            rows = client.fetch_cursor_page(source, mode, cursor_time, cursor_id)
            previous = (cursor_time, cursor_id or "") if mode == "incremental" and cursor_time else (None, cursor_id or "")
            local_counts = dict.fromkeys(counts, 0)
            for row in rows:
                row_id = str(row.get("sync_row_id") or "")
                row_time = _parse_date(row.get(FIELD_MAP[source].get("watermark_field", ""))) if mode == "incremental" else None
                if not row_id or (mode == "incremental" and row_time is None):
                    raise ValueError("Registro sin clave estable o marca temporal válida")
                key = (row_time, row_id)
                if previous[0] is not None and key <= previous or mode == "reconcile" and row_id <= previous[1]:
                    raise ValueError("La fuente devolvió una página fuera de orden o claves repetidas")
                local_counts[_save_row(db, source, row)] += 1
                previous = key
            now = datetime.now(timezone.utc).replace(tzinfo=None)
            # Una ejecución que perdió su arrendamiento no puede confirmar datos.
            updated = db.query(SyncCursor).filter(SyncCursor.source == source,
                SyncCursor.lease_token == token, SyncCursor.lease_until >= now).update(
                {SyncCursor.lease_until: now + timedelta(minutes=10)}, synchronize_session=False)
            if not updated:
                raise RuntimeError("La sincronización perdió el bloqueo de ejecución")
            db.refresh(cursor)
            if rows:
                cursor.cursor_id = previous[1]
                if mode == "incremental":
                    cursor.cursor_time = previous[0]
                    cursor.high_watermark = max(filter(None, (cursor.high_watermark, previous[0])))
                cursor.processed += len(rows)
                run.pages += 1
                run.upserted += local_counts["inserted"]
                run.duplicates += local_counts["updated"] + local_counts["unchanged"]
                for name in counts:
                    counts[name] += local_counts[name]
            if len(rows) < client.page_size:
                if mode == "incremental":
                    cursor.mode, cursor.cursor_time, cursor.cursor_id = "reconcile", None, None
                elif source != "secop1":
                    cursor.mode = "incremental"
                    cursor.cursor_time = cursor.high_watermark - timedelta(minutes=15) if cursor.high_watermark else None
                    cursor.cursor_id = None
                else:
                    cursor.cursor_id = None  # siguiente barrido completo
                cursor.last_success_at = now
            run.watermark = cursor.high_watermark
            run.detail = {**(run.detail or {}), **counts, "mode": mode}
            db.commit()  # registros, contadores y cursor son una unidad
            if len(rows) < client.page_size:
                break
        db.query(SyncCursor).filter_by(source=source, lease_token=token).update(
            {SyncCursor.status: "idle", SyncCursor.lease_token: None, SyncCursor.lease_until: None}, synchronize_session=False)
        run.finished_at = datetime.now(timezone.utc).replace(tzinfo=None)
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("Error durante sincronización SECOP %s", source)
        db.query(SyncCursor).filter_by(source=source, lease_token=token).update(
            {SyncCursor.status: "error", SyncCursor.errors: SyncCursor.errors + 1,
             SyncCursor.lease_token: None, SyncCursor.lease_until: None}, synchronize_session=False)
        run = db.get(SyncRun, run.id)
        run.errors += 1
        run.finished_at = datetime.now(timezone.utc).replace(tzinfo=None)
        run.detail = {**(run.detail or {}), "error": "No se pudo completar la sincronización; se conserva el último progreso confirmado."}
        db.commit()
    finally:
        stop_heartbeat.set()
        heartbeat.join(timeout=2)
    db.refresh(run)
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
