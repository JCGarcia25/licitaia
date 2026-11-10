"""Fase 5 — Límites de consumo de IA por suscripción (por usuario/puesto)."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.core.config import get_settings
from app.db.models import Subscription, UsageCounter, User


def get_plan_limits() -> dict[str, int]:
    s = get_settings()
    return {
        "explorador": s.quota_free_analyses,
        "profesional": s.quota_pro_analyses,
        "corporativo": s.quota_pro_analyses * 4,
    }


def month_key() -> str:
    return datetime.utcnow().strftime("%Y-%m")


def get_subscription(db: Session, user: User) -> Subscription:
    """Suscripción vigente: la de la empresa si pertenece a una; si no, la individual."""
    if user.company_id:
        sub = (
            db.query(Subscription)
            .filter((Subscription.company_id == user.company_id) | (Subscription.user_id == user.id))
            .order_by(Subscription.created_at.desc())
            .first()
        )
    else:
        sub = (
            db.query(Subscription)
            .filter(Subscription.user_id == user.id)
            .order_by(Subscription.created_at.desc())
            .first()
        )
    if not sub:
        sub = Subscription(user_id=user.id, company_id=user.company_id, plan="explorador",
                           status="activa", provider="manual")
        db.add(sub)
        db.commit()
    return sub


def subscription_is_pro(sub: Subscription, now: datetime | None = None) -> bool:
    """Pro permanece activo hasta el fin del periodo ya pagado."""
    if sub.plan not in {"profesional", "corporativo"}:
        return False
    # Las pruebas y las suscripciones con periodo explícito expiran sin una
    # tarea destructiva: el siguiente acceso simplemente deja de ser Pro.
    current_time = now or datetime.utcnow()
    if sub.current_period_end is not None and sub.current_period_end <= current_time:
        return False
    if sub.status == "activa":
        return True
    return sub.status == "cancelada_pendiente" and sub.current_period_end is not None and sub.current_period_end > current_time


def check_quota(db: Session, user: User) -> dict:
    """Estado de consumo del mes. No consume: solo consulta."""
    sub = get_subscription(db, user)
    limit = get_plan_limits().get(sub.plan, get_settings().quota_free_analyses)
    month = month_key()
    counter = (
        db.query(UsageCounter)
        .filter(UsageCounter.user_id == user.id, UsageCounter.month == month)
        .first()
    )
    used = counter.analyses if counter else 0
    return {
        "plan": sub.plan,
        "status": sub.status,
        "month": month,
        "used": used,
        "limit": limit,
        "allowed": used < limit,
    }


def require_pro(db: Session, user: User) -> Subscription:
    """Bloquea capacidades de alto valor para cuentas Free."""
    sub = get_subscription(db, user)
    if not subscription_is_pro(sub):
        raise HTTPException(402, "Esta función es exclusiva de MySECOP Pro. Actualiza tu plan para continuar.")
    return sub


def consume(db: Session, user: User, kind: str = "analyses", amount: int = 1) -> None:
    """Registra consumo del mes (solo se llama tras una operación exitosa de IA)."""
    month = month_key()
    counter = (
        db.query(UsageCounter)
        .filter(UsageCounter.user_id == user.id, UsageCounter.month == month)
        .first()
    )
    if not counter:
        counter = UsageCounter(user_id=user.id, month=month, analyses=0)
        db.add(counter)
    counter.analyses += amount
    db.commit()
