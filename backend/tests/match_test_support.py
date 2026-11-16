"""Utilidades explícitas de fixtures para el contrato asíncrono/versionado."""
from app.db.models import CompanyProfile, MatchJob, Opportunity, UserOpportunity
from app.services.match_jobs import process_batch
from app.services.match_versions import algorithm_version, embedding_version


def stamp_fixture_scores(db, user_id):
    """Scores sintéticos del test de ordenamiento, con entradas identificadas."""
    db.flush()
    profile = db.query(CompanyProfile).filter_by(user_id=user_id).one()
    for uo in db.query(UserOpportunity).filter_by(user_id=user_id):
        uo.match_state = 'CURRENT'
        uo.profile_version = profile.match_version
        uo.opportunity_version = db.get(Opportunity, uo.opportunity_id).match_version
        uo.algorithm_version = algorithm_version()
        uo.embedding_version = embedding_version()
    db.commit()


def finish_job(db, identifier):
    for _ in range(100):
        result = process_batch(db, identifier)
        if result['status'] != 'PENDING':
            assert result['status'] == 'COMPLETED', result
            db.expire_all()
            return db.get(MatchJob, identifier)
    raise AssertionError('Trabajo de prueba no finalizó')
