"""Trabajos privados del perfil del usuario autenticado."""
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.db.models import MatchJob, User
from app.db.session import get_db
from app.schemas import MatchCoverageOut, MatchJobOut
from app.services.match_jobs import cancel_job, coverage, enqueue, job_progress, resume_job

router = APIRouter(prefix='/api', tags=['matching'])


def owned_job(db, identifier, user_id):
    job = db.query(MatchJob).filter_by(id=identifier, user_id=user_id).first()
    if job is None:
        raise HTTPException(404, 'Trabajo no encontrado')
    return job


@router.get('/matches/coverage', response_model=MatchCoverageOut)
def match_coverage(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return coverage(db, user.id)


@router.get('/match-jobs/current', response_model=MatchJobOut | None)
def latest_job(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    job = db.query(MatchJob).filter_by(user_id=user.id).order_by(MatchJob.created_at.desc(), MatchJob.id.desc()).first()
    return job_progress(db, job) if job else None


@router.get('/match-jobs/{identifier}', response_model=MatchJobOut)
def progress(identifier: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return job_progress(db, owned_job(db, identifier, user.id))


@router.post('/match-jobs/{identifier}/cancel', response_model=MatchJobOut)
def cancel(identifier: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    job = cancel_job(db, owned_job(db, identifier, user.id))
    db.commit()
    return job_progress(db, job)


@router.post('/match-jobs/{identifier}/resume', status_code=202, response_model=MatchJobOut)
def resume(identifier: str, background: BackgroundTasks, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    job = resume_job(db, owned_job(db, identifier, user.id))
    db.commit()
    background.add_task(enqueue, job.id)
    return job_progress(db, job)


@router.get('/matches/metrics')
def metrics(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    from app.services.match_metrics import operational_metrics
    return operational_metrics(db,user.id)
