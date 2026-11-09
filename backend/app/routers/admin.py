"""Panel operativo privado de MySECOP."""
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.core.security import get_current_user
from app.db.models import AuditLog, CompanyProfile, OfferProject, User, UserOpportunity
from app.db.session import get_db

router = APIRouter(prefix="/api/admin", tags=["administración"])
SUPERADMIN_EMAIL = "jorge@zorbagames.com"

def require_super_admin(user: User) -> None:
    if user.email.strip().lower() != SUPERADMIN_EMAIL:
        raise HTTPException(403, "Acceso restringido al super administrador")

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
    return {
        "generated_at": now,
        "metrics": {
            "usuarios": db.query(User).count(),
            "activos": len(active),
            "perfiles_completos": db.query(CompanyProfile).count(),
            "proyectos": db.query(OfferProject).count(),
            "busquedas_puntuadas": db.query(UserOpportunity).count(),
        },
        "usuarios_activos": [{"id": u.id, "email": u.email, "nombre": u.full_name or "", "ruta": u.current_path or "/", "ultimo_acceso": u.last_seen_at, "dispositivo": (u.last_user_agent or "Desconocido")[:100], "pro": bool(u.role == "admin")} for u in active],
        "usuarios": [{"id": u.id, "email": u.email, "nombre": u.full_name or "", "ruta": u.current_path or "—", "ultimo_acceso": u.last_seen_at, "creado": u.created_at, "activo": bool(u.is_active)} for u in users],
        "eventos": [{"accion": a.action, "entidad": a.entity, "fecha": a.created_at, "usuario_id": a.user_id} for a in db.query(AuditLog).order_by(AuditLog.created_at.desc()).limit(12).all()],
    }

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
