"""Endpoints de autenticación (registro, login JWT, perfil actual)."""
import secrets

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
        enviado = send_email(email, "Verifica tu correo en LicitaIA",
                             f"Tu token de verificación: {token_ver}")
    # Sin SMTP el token se devuelve en la respuesta (dev); con SMTP se envía por correo
    return TokenOut(access_token=create_access_token(user.email),
                    verification_token=None if enviado else token_ver)


@router.post("/login", response_model=TokenOut)
def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    email = form.username.strip().lower()
    user = db.query(User).filter(User.email == email).first()
    try:
        valid = bool(user and verify_password(form.password, user.hashed_password))
    except (ValueError, TypeError):
        # Hashes corruptos o heredados deben comportarse como credenciales
        # inválidas, nunca tumbar el endpoint con un 500.
        valid = False
    if not valid:
        raise HTTPException(401, "Credenciales inválidas")
    return TokenOut(access_token=create_access_token(user.email))


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
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
