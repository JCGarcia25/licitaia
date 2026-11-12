"""Panel operativo privado de MySECOP."""
from datetime import datetime, timedelta, timezone
from html import escape
import secrets
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.core.security import get_current_user
from app.db.models import AuditLog, CompanyProfile, LandingVisit, OfferProject, Subscription, User, UserOpportunity
from app.schemas import AdminLicenseUpdateIn, AdminUserCreateIn
from app.core.security import hash_password
from app.db.session import get_db
from app.services.notifier import send_email

router = APIRouter(prefix="/api/admin", tags=["administración"])
SUPERADMIN_EMAIL = "jorge@zorbagames.com"

def require_super_admin(user: User) -> None:
    if user.email.strip().lower() != SUPERADMIN_EMAIL:
        raise HTTPException(403, "Acceso restringido al super administrador")

@router.post("/landing-visit", status_code=204)
def landing_visit(payload: dict, db: Session = Depends(get_db)):
    try:
        visit_id = str(UUID(str(payload.get("id", ""))))
    except ValueError:
        raise HTTPException(422, "Identificador inválido")
    now = datetime.utcnow()
    visit = db.get(LandingVisit, visit_id)
    if visit is None:
        db.add(LandingVisit(id=visit_id, started_at=now, last_seen_at=now, duration_seconds=0, visible=payload.get("visible") is True))
    else:
        elapsed = max(0, min(45, int((now - visit.last_seen_at).total_seconds())))
        if visit.visible:
            visit.duration_seconds += elapsed
        visit.last_seen_at = now
        visit.visible = payload.get("visible") is True
    db.commit()

@router.post("/presence")
def presence(payload: dict, request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    path = str(payload.get("path") or "/")[:255]
    user.last_seen_at = datetime.now(timezone.utc)
    user.current_path = path
    user.last_user_agent = (request.headers.get("user-agent") or "")[:255]
    db.commit()
    return {"ok": True}

@router.get("/overview")
def overview(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    require_super_admin(user)
    now = datetime.now(timezone.utc)
    threshold = now - timedelta(minutes=2)
    users = db.query(User).order_by(User.last_seen_at.desc().nullslast(), User.created_at.desc()).limit(500).all()
    active = [u for u in users if u.last_seen_at and u.last_seen_at.replace(tzinfo=timezone.utc) >= threshold]
    from zoneinfo import ZoneInfo
    local_now = now.astimezone(ZoneInfo("America/Bogota"))
    start_today = local_now.replace(hour=0, minute=0, second=0, microsecond=0).astimezone(timezone.utc).replace(tzinfo=None)
    visits_today = db.query(LandingVisit).filter(LandingVisit.started_at >= start_today)
    return {
        "generated_at": now,
        "landing": {"visitas_hoy": visits_today.count(), "activos": db.query(LandingVisit).filter(LandingVisit.visible.is_(True), LandingVisit.last_seen_at >= (now - timedelta(seconds=45)).replace(tzinfo=None)).count(), "duracion_media_segundos": round(visits_today.with_entities(func.avg(LandingVisit.duration_seconds)).scalar() or 0)},
        "metrics": {
            "usuarios": db.query(User).count(),
            "activos": len(active),
            "perfiles_completos": db.query(CompanyProfile).count(),
            "proyectos": db.query(OfferProject).count(),
            "busquedas_puntuadas": db.query(UserOpportunity).count(),
        },
        "usuarios_activos": [{"id": u.id, "email": u.email, "nombre": u.full_name or "", "ruta": u.current_path or "/", "ultimo_acceso": u.last_seen_at, "dispositivo": (u.last_user_agent or "Desconocido")[:100], "pro": bool(u.role == "admin")} for u in active],
        "usuarios": [{"id": u.id, "email": u.email, "nombre": u.full_name or "", "ruta": u.current_path or "—", "ultimo_acceso": u.last_seen_at, "creado": u.created_at, "activo": bool(u.is_active), "rol": u.role or "owner", "licencia": _license_for(db, u)} for u in users],
        "eventos": [{"accion": a.action, "entidad": a.entity, "fecha": a.created_at, "usuario_id": a.user_id} for a in db.query(AuditLog).order_by(AuditLog.created_at.desc()).limit(12).all()],
    }


def _license_for(db: Session, user: User) -> dict:
    sub = db.query(Subscription).filter(Subscription.user_id == user.id).order_by(Subscription.created_at.desc()).first()
    if not sub:
        return {"plan": "explorador", "status": "activa", "provider": "manual", "periodo_hasta": None}
    return {"id": sub.id, "plan": sub.plan, "status": sub.status, "provider": sub.provider, "periodo_hasta": sub.current_period_end}


@router.post("/users", status_code=201)
def create_user(data: AdminUserCreateIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    require_super_admin(user)
    email = str(data.email).strip().lower()
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(409, "El correo ya está registrado")
    target = User(email=email, hashed_password=hash_password(data.password), full_name=data.full_name.strip(),
                  role=data.role, is_active=True, email_verified=False)
    db.add(target)
    db.flush()
    db.add(Subscription(user_id=target.id, plan=data.plan, status=data.license_status, provider="manual"))
    db.commit()
    log_action(db, user, "crear_usuario", "user", target.id, {"role": target.role, "plan": data.plan})
    return {"id": target.id, "email": target.email, "nombre": target.full_name, "rol": target.role,
            "licencia": _license_for(db, target), "email_verificado": False}


@router.patch("/users/{user_id}/license")
def update_license(user_id: int, data: AdminLicenseUpdateIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    require_super_admin(user)
    target = db.query(User).filter(User.id == user_id).first()
    if not target:
        raise HTTPException(404, "Usuario no encontrado")
    sub = db.query(Subscription).filter(Subscription.user_id == target.id).order_by(Subscription.created_at.desc()).first()
    if not sub:
        sub = Subscription(user_id=target.id, provider="manual")
        db.add(sub)
    sub.plan, sub.status, sub.provider = data.plan, data.status, "manual"
    db.commit()
    log_action(db, user, "gestionar_licencia", "subscription", sub.id, {"plan": data.plan, "status": data.status, "user_id": target.id})
    return {"id": target.id, "licencia": _license_for(db, target)}

@router.patch("/users/{user_id}/status")
def change_user_status(user_id: int, payload: dict, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    require_super_admin(user)
    target = db.query(User).filter(User.id == user_id).first()
    if not target:
        raise HTTPException(404, "Usuario no encontrado")
    if target.id == user.id:
        raise HTTPException(400, "No puedes desactivar tu propio usuario administrador")
    activo = bool(payload.get("activo"))
    target.is_active = activo
    db.commit()
    return {"id": target.id, "activo": activo, "mensaje": "Usuario activado" if activo else "Usuario desactivado"}

@router.post("/users/{user_id}/welcome")
def send_welcome_email(user_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Envía una bienvenida de prueba con verificación de correo y credenciales de acceso."""
    require_super_admin(user)
    target = db.query(User).filter(User.id == user_id).first()
    if not target:
        raise HTTPException(404, "Usuario no encontrado")
    if not target.is_active:
        raise HTTPException(400, "Activa el usuario antes de enviarle la bienvenida")

    target.verification_token = secrets.token_hex(16)
    db.flush()

    from app.core.config import get_settings
    settings = get_settings()
    base_url = settings.admin_welcome_frontend_url.rstrip("/")
    verify_url = f"{base_url}/verificar-correo?token={target.verification_token}"
    display_name = target.full_name or "equipo"
    safe_name = escape(display_name)
    subject = "Bienvenido a MySECOP"
    plain = (
        f"Hola {display_name},\n\nBienvenido a MySECOP, tu aliado para encontrar y preparar mejores oportunidades de contratación pública.\n\n"
        f"Usuario: {target.email}\n\n"
        f"Verifica tu correo: {verify_url}\n\n"
        "Estamos para acompañarte,\nEquipo MySECOP"
    )
    html = f"""<!doctype html><html lang=\"es\"><body style=\"margin:0;background:#f4f7fb;font-family:Arial,sans-serif;color:#18324b\"><div style=\"max-width:620px;margin:32px auto;background:#fff;border-radius:16px;overflow:hidden;box-shadow:0 8px 24px rgba(16,42,67,.12)\"><div style=\"background:#0d3565;padding:28px 32px;color:#fff\"><div style=\"font-size:24px;font-weight:700\"><span style=\"display:inline-block;background:#18c1b0;color:#06314f;border-radius:8px;padding:7px 9px;margin-right:8px\">MS</span>MySECOP</div></div><div style=\"padding:32px\"><h1 style=\"margin:0 0 14px;font-size:26px;color:#0d3565\">¡Bienvenido, {safe_name}!</h1><p style=\"font-size:16px;line-height:1.6\">Nos alegra acompañarte a encontrar oportunidades y preparar propuestas con más claridad. Tu trabajo puede convertirse en la próxima gran contratación.</p><div style=\"background:#eef7f7;border:1px solid #bde9e3;border-radius:12px;padding:18px;margin:22px 0\"><p style=\"margin:0\"><strong>Usuario:</strong> {escape(target.email)}</p></div><p style=\"margin:22px 0\"><a href=\"{verify_url}\" style=\"display:inline-block;background:#18bfae;color:#062f4e;text-decoration:none;font-weight:700;padding:13px 20px;border-radius:8px\">Verificar mi correo</a></p><p style=\"font-size:14px;line-height:1.6;margin-top:24px\">Estamos para acompañarte,<br><strong>Equipo MySECOP</strong></p></div></div></body></html>"""
    if not send_email(target.email, subject, plain, html_body=html):
        db.rollback()
        raise HTTPException(503, "No fue posible enviar la bienvenida. Verifica la configuración de correo del servidor.")
    db.commit()
    return {"enviado": True, "email": target.email, "ambiente": "stg"}
