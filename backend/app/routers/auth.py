"""Endpoints de autenticación (registro, login JWT, perfil actual)."""
import secrets
import logging
from html import escape

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import create_access_token, get_current_user, hash_password, verify_password
from app.db.models import AlertPrefs, User
from app.db.session import get_db
from app.schemas import RegisterIn, TokenOut, UserOut, VerifyEmailIn
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
        enviado = send_email(email, "Verifica tu correo en MySECOP",
                             f"Tu token de verificación: {token_ver}")
        welcome_subject, welcome_plain, welcome_html = _welcome_email(data.full_name)
        send_email(email, welcome_subject, welcome_plain, html_body=welcome_html)
    # Sin SMTP el token se devuelve en la respuesta (dev); con SMTP se envía por correo
    return TokenOut(access_token=create_access_token(user.email),
                    verification_token=None if enviado else token_ver)


@router.post("/login", response_model=TokenOut)
def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
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
    return TokenOut(access_token=create_access_token(user.email))


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
