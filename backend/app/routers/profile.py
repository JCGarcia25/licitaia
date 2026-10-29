"""Perfil empresarial (entrada del Agente 1)."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.db.models import CompanyProfile, User
from app.db.session import get_db
from app.schemas import ProfileIn, ProfileOut

router = APIRouter(prefix="/api/profile", tags=["perfil"])


@router.get("", response_model=ProfileOut | None)
def get_profile(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.query(CompanyProfile).filter(CompanyProfile.user_id == user.id).first()


@router.put("", response_model=ProfileOut)
def upsert_profile(data: ProfileIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    profile = db.query(CompanyProfile).filter(CompanyProfile.user_id == user.id).first()
    if not profile:
        profile = CompanyProfile(user_id=user.id)
        db.add(profile)
    for field, value in data.model_dump().items():
        setattr(profile, field, value)
    db.commit()
    db.refresh(profile)
    return profile
