"""Fase 5 — Empresas, miembros, roles, auditoría y métricas administrativas."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.db.models import Analysis, AuditLog, Company, Document, OfferProject, User, UserOpportunity
from app.db.session import get_db
from app.schemas import CompanyIn, MemberIn, MemberRoleIn
from app.services.audit import log_action
from app.services.quota import check_quota

router = APIRouter(prefix="/api", tags=["empresas"])

ROLES = ("owner", "admin", "analista", "lector")
_JERARQUIA = {r: i for i, r in enumerate(reversed(ROLES))}  # lector=0 < analista < admin < owner


def require_role(user: User, minimum: str) -> None:
    """Verifica el rol del usuario en su empresa. Jerarquía: owner > admin > analista > lector."""
    if not user.company_id:
        raise HTTPException(400, "El usuario no pertenece a ninguna empresa")
    if _JERARQUIA.get(user.role, -1) < _JERARQUIA[minimum]:
        raise HTTPException(403, f"Esta acción requiere rol {minimum} o superior")


@router.post("/companies", status_code=201)
def create_company(data: CompanyIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if user.company_id:
        raise HTTPException(409, "El usuario ya pertenece a una empresa")
    company = Company(nombre=data.nombre, nit=data.nit or "", sector=data.sector or "", owner_user_id=user.id)
    db.add(company)
    db.flush()
    user.company_id = company.id
    user.role = "owner"
    db.commit()
    log_action(db, user, "crear_empresa", "company", company.id, {"nombre": data.nombre})
    return {"id": company.id, "nombre": company.nombre, "rol": user.role}


@router.get("/companies/members")
def list_members(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    require_role(user, "lector")
    members = db.query(User).filter(User.company_id == user.company_id).all()
    return [{"id": m.id, "email": m.email, "full_name": m.full_name, "role": m.role,
             "email_verified": m.email_verified} for m in members]


@router.post("/companies/members", status_code=201)
def add_member(data: MemberIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    require_role(user, "admin")
    member = db.query(User).filter(User.email == data.email).first()
    if not member:
        raise HTTPException(404, "El usuario debe registrarse primero con ese correo")
    if member.company_id and member.company_id != user.company_id:
        raise HTTPException(409, "El usuario ya pertenece a otra empresa")
    member.company_id = user.company_id
    member.role = data.role
    db.commit()
    log_action(db, user, "agregar_miembro", "user", member.id, {"role": data.role})
    return {"id": member.id, "email": member.email, "role": member.role}


@router.patch("/companies/members/{member_id}")
def change_role(member_id: int, data: MemberRoleIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    require_role(user, "owner")
    member = db.query(User).filter(User.id == member_id, User.company_id == user.company_id).first()
    if not member:
        raise HTTPException(404, "Miembro no encontrado")
    if member.id == user.id:
        raise HTTPException(400, "No puedes cambiar tu propio rol")
    member.role = data.role
    db.commit()
    log_action(db, user, "cambiar_rol", "user", member.id, {"role": data.role})
    return {"id": member.id, "role": member.role}


@router.get("/audit")
def audit(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    require_role(user, "admin")
    q = db.query(AuditLog)
    q = q.filter(AuditLog.company_id == user.company_id) if user.company_id else q.filter(AuditLog.user_id == user.id)
    rows = q.order_by(AuditLog.created_at.desc()).limit(100).all()
    return [{"id": a.id, "action": a.action, "entity": a.entity, "entity_id": a.entity_id,
             "detail": a.detail, "user_id": a.user_id, "created_at": a.created_at} for a in rows]


@router.get("/admin/metrics")
def admin_metrics(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Dashboard administrativo: métricas de producto por empresa (Fase 5)."""
    require_role(user, "admin")
    cid = user.company_id
    member_ids = [m.id for m in db.query(User.id).filter(User.company_id == cid).all()] if cid else [user.id]
    _in_users = UserOpportunity.user_id.in_(member_ids)
    filtro_empresa = (lambda model_col: model_col == cid) if cid else (lambda model_col: model_col.in_(member_ids))
    quota = check_quota(db, user)
    return {
        "miembros": len(member_ids),
        "oportunidades_puntuadas": db.query(UserOpportunity).filter(_in_users).count(),
        "alta_compatibilidad": db.query(UserOpportunity).filter(_in_users, UserOpportunity.score >= 70).count(),
        "analisis_documentales": db.query(Analysis).filter(filtro_empresa(Analysis.company_id) if cid else _in_users).count(),
        "proyectos_oferta": db.query(OfferProject).filter(filtro_empresa(OfferProject.company_id) if cid else _in_users).count(),
        "documentos": db.query(Document).filter(filtro_empresa(Document.company_id) if cid else _in_users).count(),
        "consumo_ia": quota,
        "auditoria_registros": db.query(AuditLog).filter(AuditLog.company_id == cid).count() if cid else db.query(AuditLog).filter(AuditLog.user_id.in_(member_ids)).count(),
    }
