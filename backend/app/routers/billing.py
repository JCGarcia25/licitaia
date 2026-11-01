"""Suscripciones y planes, con integración segura de Mercado Pago."""
import hashlib
import hmac
import httpx
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import get_current_user
from app.db.models import Subscription, User
from app.db.session import get_db
from app.schemas import SubscribeIn
from app.services.audit import log_action
from app.services.quota import check_quota, get_plan_limits, get_subscription, subscription_is_pro

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
        "nombre": "MySECOP Pro" if subscription_is_pro(sub) else "MySECOP Free",
        "es_pro": subscription_is_pro(sub),
        "precio_cop_mes": 59900 if sub.plan == "profesional" else (149900 if sub.plan == "corporativo" else 0),
        "status": sub.status,
        "provider": sub.provider,
        "checkout_url": sub.checkout_url,
        "external_id": sub.external_id,
        "usage": quota,
        "nota": "El acceso Pro solo se activa cuando Mercado Pago confirma la suscripción.",
        "periodo_hasta": sub.current_period_end.isoformat() if subscription_is_pro(sub) and sub.current_period_end else None,
    }


@router.post("/refresh")
def refresh_subscription(external_id: str | None = None, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Reconcilia el retorno del checkout con el estado oficial de Mercado Pago."""
    settings = get_settings()
    sub = get_subscription(db, user)
    provider_id = external_id or sub.external_id
    if provider_id and sub.external_id != provider_id:
        sub.external_id = provider_id
        sub.provider = "mercadopago"
        sub.plan = "profesional"
        sub.status = "pendiente_pago"
        db.commit()
    if settings.billing_provider != "mercadopago" or not provider_id:
        return current(user, db)
    from app.workers.tasks import sync_mercadopago_subscription
    try:
        sync_mercadopago_subscription(str(provider_id))
    except Exception as exc:
        raise HTTPException(502, "No fue posible verificar todavía el pago con Mercado Pago.") from exc
    db.expire_all()
    return current(user, db)


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
        # Con credenciales de prueba siempre usamos el checkout sandbox. Si se
        # usa init_point en lugar de sandbox_init_point, Mercado Pago puede
        # mostrar "Algo salió mal" al combinarlo con una tarjeta de prueba.
        checkout_url = (remote.get("sandbox_init_point") or remote.get("init_point")) if settings.mercadopago_sandbox else remote.get("init_point")
        sub.external_id, sub.checkout_url = remote.get("id"), checkout_url
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


@router.post("/cancel")
def cancel_subscription(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Da de baja la suscripción activa y cancela la renovación en Mercado Pago."""
    settings = get_settings()
    sub = get_subscription(db, user)
    if sub.plan not in {"profesional", "corporativo"} or sub.status != "activa":
        raise HTTPException(400, "No tienes una suscripción Pro activa para cancelar.")
    if sub.provider == "mercadopago" and sub.external_id:
        try:
            response = httpx.put(
                f"https://api.mercadopago.com/preapproval/{sub.external_id}",
                json={"status": "cancelled"},
                headers={"Authorization": f"Bearer {settings.mercadopago_access_token}"},
                timeout=15,
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise HTTPException(502, "No fue posible cancelar la suscripción en Mercado Pago. Intenta nuevamente.") from exc
    sub.status = "cancelada_pendiente"
    if not sub.current_period_end or sub.current_period_end <= datetime.utcnow():
        sub.current_period_end = datetime.utcnow() + timedelta(days=30)
    sub.checkout_url = None
    db.commit()
    log_action(db, user, "cancelar_suscripcion", "subscription", sub.id, {"provider": sub.provider})
    result = current(user, db)
    result["mensaje_cancelacion"] = f"Tu suscripción seguirá activa hasta el {sub.current_period_end:%d/%m/%Y}. Después de esa fecha pasarás automáticamente a MySECOP Free."
    return result


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
    from app.workers.celery_app import run_or_delay
    from app.workers.tasks import sync_mercadopago_subscription
    task = run_or_delay("app.workers.tasks.sync_mercadopago_subscription_task",
                        sync_mercadopago_subscription, str(remote_id))
    return {"ok": True, "queued": task, "message": "Actualización de suscripción programada."}
