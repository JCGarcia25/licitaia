"""Fase 5 — Suscripciones y planes.

La cobranza real requiere credenciales de la pasarela (STRIPE_API_KEY): sin ellas
el cambio de plan queda en estado 'pendiente_pago' y el webhook responde 501.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import get_current_user
from app.db.models import Subscription, User
from app.db.session import get_db
from app.schemas import SubscribeIn
from app.services.audit import log_action
from app.services.quota import check_quota, get_plan_limits, get_subscription

router = APIRouter(prefix="/api/billing", tags=["suscripciones"])


@router.get("/plans")
def plans():
    return [{"plan": p, "analyses_por_mes": limit} for p, limit in get_plan_limits().items()]


@router.get("")
def current(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    sub = get_subscription(db, user)
    quota = check_quota(db, user)
    return {
        "plan": sub.plan,
        "status": sub.status,
        "provider": sub.provider,
        "usage": quota,
        "nota": "Pasarela de pago pendiente de credenciales: el cambio de plan queda en estado pendiente_pago.",
    }


@router.post("/subscribe")
def subscribe(data: SubscribeIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    settings = get_settings()
    if settings.billing_provider == "stripe" and not settings.stripe_api_key:
        raise HTTPException(501, "Stripe configurado pero sin credenciales (STRIPE_API_KEY). Pendiente de credenciales externas.")
    sub = get_subscription(db, user)
    sub.plan = data.plan
    sub.status = "pendiente_pago"
    sub.provider = settings.billing_provider
    db.commit()
    log_action(db, user, "cambiar_plan", "subscription", sub.id, {"plan": data.plan})
    return {
        "plan": sub.plan,
        "status": sub.status,
        "nota": "Suscripción registrada en estado pendiente_pago: la cobranza requiere integrar la pasarela (credenciales pendientes).",
    }


@router.post("/webhook")
def webhook():
    settings = get_settings()
    if settings.billing_provider != "stripe" or not settings.stripe_api_key:
        raise HTTPException(501, "Webhook de pagos pendiente de credenciales de la pasarela.")
    raise HTTPException(501, "Implementación del webhook pendiente de credenciales y verificación de firma.")
