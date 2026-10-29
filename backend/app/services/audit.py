"""Fase 5 — Registro de auditoría de acciones."""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.db.models import AuditLog, User


def log_action(db: Session, user: User, action: str, entity: str,
               entity_id: int | None = None, detail: dict | None = None) -> None:
    db.add(AuditLog(
        user_id=user.id, company_id=user.company_id, action=action,
        entity=entity, entity_id=entity_id, detail=detail or {},
    ))
    db.commit()
