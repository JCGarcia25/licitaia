"""Endpoints de autenticación (registro, login JWT, perfil actual)."""
import secrets
import logging
from html import escape
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import create_access_token, get_current_user, hash_password, verify_password
from app.db.models import AlertPrefs, User
from app.db.session import get_db
from app.schemas import PasswordResetIn, PasswordResetRequestIn, RegisterIn, TokenOut, UserOut, VerifyEmailIn
from app.services.notifier import send_email

router = APIRouter(prefix="/api/auth", tags=["auth"])
logger = logging.getLogger("licitaia.auth")


def _welcome_email(full_name: str | None) -> tuple[str, str, str]:
    nombre = escape((full_name or "").strip() or "empresario/a")
    subject = "Bienvenido/a a MySECOP: empieza a encontrar mejores oportunidades"
    plain = (
        f"Hola {full_name or 'empresario/a'},\n\n"
        "Te damos la bienvenida a MySECOP, tu aliado para descubrir, analizar y priorizar oportunidades de contratación pública.\n\n"
        "Completa el perfil de tu empresa para recibir resultados más relevantes y consulta las oportunidades que mejor encajan con tus capacidades.\n\n"
        "Estamos aquí para ayudarte a competir con más información y confianza.\n\n"
        "Equipo MySECOP"
    )
    html = f'''<!doctype html><html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;background:#f4f7fb;font-family:Arial,Helvetica,sans-serif;color:#132238">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f4f7fb;padding:28px 12px"><tr><td align="center">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:620px;background:#fff;border:1px solid #dfe7f0;border-radius:16px;overflow:hidden">
<tr><td style="background:linear-gradient(135deg,#082b55,#0f766e);padding:28px 32px;color:#fff"><div style="font-size:20px;font-weight:700;letter-spacing:.2px"><span style="display:inline-block;background:#14b8a6;color:#062238;border-radius:8px;padding:7px 8px;font-size:13px;margin-right:8px">MS</span>MySECOP</div><div style="margin-top:24px;font-size:28px;line-height:1.2;font-weight:700">Tu próxima oportunidad empieza aquí</div></td></tr>
<tr><td style="padding:32px"><p style="margin:0 0 18px;font-size:18px;font-weight:700">¡Bienvenido/a, {nombre}!</p><p style="margin:0 0 16px;line-height:1.6;color:#52657d">Gracias por registrarte en MySECOP, tu aliado para descubrir, analizar y priorizar oportunidades de contratación pública.</p><p style="margin:0 0 22px;line-height:1.6;color:#52657d">Completa el perfil de tu empresa para que el sistema encuentre procesos más relevantes para tus capacidades, ubicación y presupuesto.</p><table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#eefaf8;border-radius:10px"><tr><td style="padding:16px;color:#0f766e;font-size:14px;line-height:1.5"><strong>Consejo para empezar:</strong><br>Describe con claridad tus actividades, productos y servicios. Esa información ayuda a mejorar tus coincidencias.</td></tr></table><p style="margin:24px 0 0;line-height:1.6;color:#52657d">Estamos aquí para ayudarte a competir con más información y confianza.</p><p style="margin:24px 0 0;font-weight:700">Equipo MySECOP</p></td></tr>
<tr><td style="padding:18px 32px;background:#f8fafc;color:#718096;font-size:11px;line-height:1.5">MySECOP es un producto independiente y no es una plataforma oficial del Gobierno colombiano. Consulta siempre la fuente oficial del proceso.</td></tr></table></td></tr></table></body></html>'''
    return subject, plain, html

def _verification_email(full_name: str | None, link: str) -> tuple[str, str, str]:
    nombre = escape((full_name or "").strip() or "usuario/a")
    subject = "Verifica tu correo en MySECOP"
    plain = f"Hola {full_name or 'usuario/a'},\n\nConfirma tu correo para activar los envíos de alertas de MySECOP:\n{link}\n\nEste enlace solo puede utilizarse una vez."
    html = f'''<!doctype html><html lang="es"><body style="margin:0;background:#f4f7fb;font-family:Arial;color:#132238"><table width="100%" cellpadding="0" cellspacing="0" style="padding:28px 12px"><tr><td align="center"><table width="100%" style="max-width:600px;background:#fff;border-radius:16px;overflow:hidden"><tr><td style="background:#082b55;padding:26px 30px;color:#fff;font-size:21px;font-weight:bold"><span style="background:#14b8a6;color:#062238;border-radius:8px;padding:7px;font-size:13px">MS</span> MySECOP</td></tr><tr><td style="padding:30px"><h2 style="margin-top:0">Verifica tu correo</h2><p style="color:#52657d;line-height:1.6">Hola {nombre}, confirma tu dirección para recibir resúmenes y recordatorios de alertas.</p><p><a href="{link}" style="display:inline-block;background:#14b8a6;color:#062238;text-decoration:none;font-weight:bold;padding:13px 22px;border-radius:8px">Verificar mi correo</a></p><p style="font-size:12px;color:#718096">Si no creaste esta cuenta, puedes ignorar este mensaje.</p></td></tr></table></td></tr></table></body></html>'''
    return subject, plain, html


def _reset_email(name: str | None, link: str) -> tuple[str, str, str]:
    subject = "Restablece tu contraseña de MySECOP"
    plain = f"Hola {name or 'usuario/a'},\n\nRecibimos una solicitud para cambiar tu contraseña de MySECOP. Usa este enlace antes de 30 minutos:\n{link}\n\nSi no solicitaste este cambio, ignora este mensaje."
    html = f'''<!doctype html><html lang="es"><body style="margin:0;background:#f4f7fb;font-family:Arial;color:#132238"><table width="100%" cellpadding="0" cellspacing="0" style="padding:28px 12px"><tr><td align="center"><table width="100%" style="max-width:600px;background:#fff;border-radius:16px;overflow:hidden"><tr><td style="background:#082b55;padding:26px 30px;color:#fff;font-size:21px;font-weight:bold"><span style="background:#14b8a6;color:#062238;border-radius:8px;padding:7px;font-size:13px">MS</span> MySECOP</td></tr><tr><td style="padding:30px"><h2 style="margin-top:0">Restablece tu contraseña</h2><p style="color:#52657d;line-height:1.6">Hola {escape(name or 'usuario/a')}, recibimos una solicitud para cambiar tu contraseña.</p><p style="color:#52657d;line-height:1.6">El enlace es válido durante 30 minutos y solo puede utilizarse una vez.</p><p><a href="{link}" style="display:inline-block;background:#14b8a6;color:#062238;text-decoration:none;font-weight:bold;padding:13px 22px;border-radius:8px">Restablecer contraseña</a></p><p style="font-size:12px;color:#718096">Si no solicitaste este cambio, puedes ignorar este correo.</p></td></tr></table></td></tr></table></body></html>'''
    return subject, plain, html


@router.post("/register", response_model=TokenOut, status_code=201)
def register(data: RegisterIn, db: Session = Depends(get_db)):
    email = str(data.email).strip().lower()
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(409, "El correo ya está registrado")
    token_ver = secrets.token_hex(16)
    user = User(email=email, hashed_password=hash_password(data.password), full_name=data.full_name,
                verification_token=token_ver)
    db.add(user)
    db.flush()
    db.add(AlertPrefs(user_id=user.id))
    db.commit()
    settings = get_settings()
    enviado = False
    if settings.smtp_host:
        welcome_subject, welcome_plain, welcome_html = _welcome_email(data.full_name)
        # El registro envía únicamente la bienvenida. No enviamos tokens
        # técnicos al usuario: la verificación se mantiene disponible para
        # flujos internos/dev mediante el token de la respuesta.
        enviado = send_email(email, welcome_subject, welcome_plain, html_body=welcome_html)
        # El enlace siempre se genera con el dominio del ambiente configurado
        # (DEV, STG o producción); nunca debe quedar fijado al dominio de DEV.
        verification_link = f"{settings.frontend_url.rstrip('/')}/verificar-correo?token={token_ver}"
        verify_subject, verify_plain, verify_html = _verification_email(data.full_name, verification_link)
        send_email(email, verify_subject, verify_plain, html_body=verify_html)
    # Sin SMTP el token se devuelve en la respuesta (dev); con SMTP se envía por correo
    return TokenOut(access_token=create_access_token(user.email),
                    verification_token=None if enviado else token_ver)


@router.post("/login", response_model=TokenOut)
def login(form: OAuth2PasswordRequestForm = Depends(), remember: bool = Query(False), db: Session = Depends(get_db)):
    email = form.username.strip().lower()
    user = db.query(User).filter(User.email == email).first()
    try:
        valid = bool(user and verify_password(form.password, user.hashed_password))
    except Exception as exc:
        # Hashes corruptos o heredados deben comportarse como credenciales
        # inválidas, nunca tumbar el endpoint con un 500.
        logger.warning("No fue posible verificar la contraseña para %s: %s", email, type(exc).__name__)
        valid = False
    if not valid:
        raise HTTPException(401, "Credenciales inválidas")
    # Una sesión recordada dura 30 días; la sesión normal conserva el plazo
    # corto configurado por seguridad.
    return TokenOut(access_token=create_access_token(user.email, 60 * 24 * 30 if remember else None))


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    # Users created before the role/email verification fields were added may
    # still have NULL values in PostgreSQL. Normalize them at the API boundary
    # so the response contract remains stable without requiring a destructive
    # data migration.
    if user.role is None:
        user.role = "owner"
    if user.email_verified is None:
        user.email_verified = False
    return user


@router.post("/verify-email")
def verify_email(data: VerifyEmailIn, db: Session = Depends(get_db)):
    """Fase 5: verificación de correo. El envío del token requiere SMTP configurado."""
    user = db.query(User).filter(User.verification_token == data.token).first()
    if not user:
        raise HTTPException(400, "Token de verificación inválido o ya utilizado")
    user.email_verified = True
    user.verification_token = None
    db.commit()
    return {"verificado": True, "email": user.email}

@router.post("/resend-verification")
def resend_verification(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Reenvía el enlace de verificación al correo de la sesión actual."""
    if user.email_verified:
        return {"enviado": False, "ya_verificado": True}
    settings = get_settings()
    if not settings.smtp_host:
        return {"enviado": False, "smtp_configurado": False}
    user.verification_token = secrets.token_hex(16)
    db.commit()
    link = f"{settings.frontend_url.rstrip('/')}/verificar-correo?token={user.verification_token}"
    subject, plain, html = _verification_email(user.full_name, link)
    return {"enviado": send_email(user.email, subject, plain, html_body=html), "smtp_configurado": True}


@router.post("/forgot-password")
def forgot_password(data: PasswordResetRequestIn, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == str(data.email).strip().lower()).first()
    # Respuesta uniforme para no revelar qué correos están registrados.
    if user:
        token = secrets.token_urlsafe(32)[:64]
        user.password_reset_token = token
        user.password_reset_expires_at = datetime.now(timezone.utc) + timedelta(minutes=30)
        db.commit()
        settings = get_settings()
        link = f"{settings.frontend_url.rstrip('/')}/restablecer-contrasena?token={token}"
        subject, plain, html = _reset_email(user.full_name, link)
        send_email(user.email, subject, plain, html_body=html)
    return {"solicitud_recibida": True, "mensaje": "Si el correo está registrado, recibirás un enlace para restablecer tu contraseña."}


@router.post("/reset-password")
def reset_password(data: PasswordResetIn, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.password_reset_token == data.token).first()
    now = datetime.now(timezone.utc)
    expires_at = user.password_reset_expires_at if user else None
    # SQLite puede devolver DateTime sin zona horaria aunque el valor se haya
    # guardado en UTC; normalizamos antes de comparar para evitar un 500.
    if expires_at and expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if not user or not expires_at or expires_at < now:
        raise HTTPException(400, "El enlace no es válido o ya expiró")
    user.hashed_password = hash_password(data.password)
    user.password_reset_token = None
    user.password_reset_expires_at = None
    db.commit()
    return {"restablecida": True}
