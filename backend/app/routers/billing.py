"""Suscripciones y planes, con integración segura de Mercado Pago."""
import hashlib
import hmac
import httpx
from fastapi import APIRouter, Depends, Header, HTTPException, Query
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
    limits = get_plan_limits()
    return [
        {
            "plan": "explorador",
            "nombre": "MySECOP Free",
            "precio_cop_mes": 0,
            "analyses_por_mes": limits["explorador"],
            "funcionalidades": ["Búsqueda de oportunidades", "Compatibilidad básica", "Guardar oportunidades"],
        },
        {
            "plan": "profesional",
            "nombre": "MySECOP Pro",
            "precio_cop_mes": 59900,
            "analyses_por_mes": limits["profesional"],
            "funcionalidades": ["Todo Free", "Análisis de pliegos", "Evaluación de viabilidad", "Alertas por correo", "Preparador y exportación de ofertas", "Importación de documentos públicos"],
        },
        {
            "plan": "corporativo",
            "nombre": "MySECOP Pro Equipo",
            "precio_cop_mes": 149900,
            "analyses_por_mes": limits["corporativo"],
            "funcionalidades": ["Todo Pro", "Usuarios y auditoría de empresa", "Mayor capacidad mensual"],
        },
    ]


@router.get("")
def current(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    sub = get_subscription(db, user)
    quota = check_quota(db, user)
    return {
        "plan": sub.plan,
        "nombre": "MySECOP Pro" if sub.plan in {"profesional", "corporativo"} and sub.status == "activa" else "MySECOP Free",
        "es_pro": sub.plan in {"profesional", "corporativo"} and sub.status == "activa",
        "precio_cop_mes": 59900 if sub.plan == "profesional" else (149900 if sub.plan == "corporativo" else 0),
        "status": sub.status,
        "provider": sub.provider,
        "checkout_url": sub.checkout_url,
        "usage": quota,
        "nota": "El acceso Pro solo se activa cuando Mercado Pago confirma la suscripción.",
    }


@router.post("/subscribe")
def subscribe(data: SubscribeIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    settings = get_settings()
    if data.plan == "explorador":
        sub = get_subscription(db, user)
        sub.plan, sub.status, sub.provider, sub.checkout_url = "explorador", "activa", "manual", None
        db.commit()
        return {"plan": sub.plan, "status": sub.status, "checkout_url": None}
    if settings.billing_provider == "mercadopago":
        if not settings.mercadopago_access_token:
            raise HTTPException(503, "Mercado Pago no está configurado todavía en el servidor.")
        sub = get_subscription(db, user)
        payload = {
            "reason": "MySECOP Pro",
            "external_reference": f"mysecop-user-{user.id}",
            "payer_email": settings.mercadopago_test_payer_email or user.email,
            "back_url": settings.mercadopago_back_url,
            "auto_recurring": {"frequency": 1, "frequency_type": "months", "transaction_amount": 59900, "currency_id": "COP"},
            "status": "pending",
        }
        try:
            response = httpx.post("https://api.mercadopago.com/preapproval", json=payload,
                                 headers={"Authorization": f"Bearer {settings.mercadopago_access_token}"}, timeout=15)
            response.raise_for_status()
            remote = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise HTTPException(502, "Mercado Pago no pudo crear la suscripción de prueba.") from exc
        sub.plan, sub.status, sub.provider = "profesional", "pendiente_pago", "mercadopago"
        sub.external_id, sub.checkout_url = remote.get("id"), remote.get("init_point") or remote.get("sandbox_init_point")
        db.commit()
        log_action(db, user, "iniciar_suscripcion", "subscription", sub.id, {"provider_id": sub.external_id})
        return {"plan": sub.plan, "status": sub.status, "checkout_url": sub.checkout_url, "external_id": sub.external_id}
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


@router.post("/mercadopago/webhook")
def mercadopago_webhook(payload: dict | None = None, type: str | None = None,
                        data_id: str | None = Query(default=None, alias="data.id"),
                        x_signature: str | None = Header(default=None),
                        x_request_id: str | None = Header(default=None),
                        db: Session = Depends(get_db)):
    settings = get_settings()
    if settings.billing_provider != "mercadopago" or not settings.mercadopago_access_token:
        raise HTTPException(503, "Mercado Pago no está habilitado.")
    body = payload or {}
    event_type = type or body.get("type") or body.get("action")
    remote_id = data_id or (body.get("data") or {}).get("id")
    # Mercado Pago firma cada webhook como ts=...,v1=... usando el template
    # documentado. En producción una firma ausente o inválida nunca puede
    # cambiar el plan de un usuario.
    if settings.environment == "production" and not settings.mercadopago_webhook_secret:
        raise HTTPException(503, "Falta configurar MERCADOPAGO_WEBHOOK_SECRET.")
    if settings.mercadopago_webhook_secret and x_signature:
        parts = dict(item.split("=", 1) for item in x_signature.split(",") if "=" in item)
        ts, received = parts.get("ts"), parts.get("v1")
        if not ts or not received or not x_request_id or not remote_id:
            raise HTTPException(401, "Firma de webhook inválida")
        template = f"id:{str(remote_id).lower()};request-id:{x_request_id};ts:{ts};"
        expected = hmac.new(settings.mercadopago_webhook_secret.encode(), template.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, received):
            raise HTTPException(401, "Firma de webhook inválida")
    elif settings.environment == "production":
        raise HTTPException(401, "Firma de webhook ausente")
    if event_type not in {"subscription_preapproval", "subscription_authorized_payment", "preapproval"} or not remote_id:
        return {"ok": True, "ignored": True}
    try:
        response = httpx.get(f"https://api.mercadopago.com/preapproval/{remote_id}",
                            headers={"Authorization": f"Bearer {settings.mercadopago_access_token}"}, timeout=15)
        response.raise_for_status(); remote = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise HTTPException(502, "No fue posible verificar el evento en Mercado Pago.") from exc
    reference = str(remote.get("external_reference") or "")
    user_id = reference.removeprefix("mysecop-user-")
    sub = db.query(Subscription).filter(Subscription.external_id == str(remote_id)).first()
    if not sub and user_id.isdigit():
        sub = db.query(Subscription).filter(Subscription.user_id == int(user_id)).order_by(Subscription.created_at.desc()).first()
    if not sub:
        return {"ok": True, "ignored": True}
    status = remote.get("status")
    sub.status = "activa" if status == "authorized" else ("cancelada" if status in {"cancelled", "paused"} else "pendiente_pago")
    sub.plan = "profesional" if sub.status == "activa" else sub.plan
    db.commit()
    return {"ok": True, "subscription_id": sub.id, "status": sub.status}
