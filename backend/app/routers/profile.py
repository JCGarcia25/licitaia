"""Perfil empresarial (entrada del Agente 1)."""
from fastapi import APIRouter, BackgroundTasks, Depends
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.db.models import CompanyProfile, User
from app.db.session import get_db
from app.schemas import ProfileIn, ProfileOut

router = APIRouter(prefix="/api/profile", tags=["perfil"])


@router.get("", response_model=ProfileOut | None)
def get_profile(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    profile = db.query(CompanyProfile).filter(CompanyProfile.user_id == user.id).first()
    if profile:
        for field in ("keywords", "unspsc_codes", "departamentos", "municipios", "modalidades", "certificaciones"):
            if getattr(profile, field, None) is None: setattr(profile, field, [])
        if profile.learning_weights is None: profile.learning_weights = {}
        db.commit()
    return profile


@router.put("", response_model=ProfileOut)
def upsert_profile(data: ProfileIn, background: BackgroundTasks, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    profile = db.query(CompanyProfile).filter(CompanyProfile.user_id == user.id).first()
    if not profile:
        profile = CompanyProfile(user_id=user.id)
        db.add(profile)
    old_version = profile.match_version
    for field, value in data.model_dump().items():
        setattr(profile, field, value)
    db.commit()
    db.refresh(profile)
    if old_version != profile.match_version:
        from app.services.match_jobs import request_job, enqueue
        job = request_job(db, user.id)
        db.commit()
        background.add_task(enqueue, job.id)
    return profile
