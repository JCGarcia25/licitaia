"""Matching progresivo con oportunidades, matcher y vectores simulados."""
import time
from datetime import datetime, timedelta
from uuid import uuid4
import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from app.core.config import get_settings
from app.db.models import Base, CompanyProfile, MatchJob, MatchScoreHistory, MatchSlot, Opportunity, User, UserOpportunity, OpportunityEmbedding
from app.services import match_jobs as jobs
from app.services.match_versions import current_score_condition
from app.services.matcher import MatchResult

@pytest.fixture
def match_factory(tmp_path, monkeypatch):
    engine = create_engine(f'sqlite:///{tmp_path}/matching.db', connect_args={'check_same_thread':False})
    Base.metadata.create_all(engine)
    monkeypatch.setattr(get_settings(), 'match_batch_size', 200)
    monkeypatch.setattr(get_settings(), 'match_global_concurrency', 1)
    monkeypatch.setattr(get_settings(), 'embedding_dim', 4)
    monkeypatch.setattr(jobs, 'embed', lambda text: [1., 0., 0., 0.])
    monkeypatch.setattr(jobs, 'score_opportunity', lambda *a, **k: MatchResult(75, [{'factor':'Prueba'}]))
    yield sessionmaker(bind=engine, expire_on_commit=False)
    engine.dispose()

def prepare(factory, count=5):
    with factory() as db:
        user = User(email=f'{uuid4().hex}@example.invalid', hashed_password='fixture')
        db.add(user); db.flush()
        db.add(CompanyProfile(user_id=user.id, sector='software', keywords=['software']))
        db.add_all([Opportunity(source='qa', source_id=str(i), objeto='software', estado='Publicado') for i in range(count)])
        db.commit()
        return user.id

def run_job(factory, user_id):
    with factory() as db:
        job = jobs.request_job(db, user_id); db.commit(); identifier = job.id
    for _ in range(100):
        with factory() as db:
            result = jobs.process_batch(db, identifier)
        if result['status'] != 'PENDING':
            assert result['status'] == 'COMPLETED', result
            return identifier
    pytest.fail('No terminó el recorrido de prueba')

@pytest.mark.parametrize('size', [0, 17, 1601, 10000])
def test_universo_sin_limite_y_cobertura(match_factory, size):
    user_id = prepare(match_factory, size); started = time.monotonic()
    identifier = run_job(match_factory, user_id)
    with match_factory() as db:
        c = jobs.coverage(db, user_id); job = db.get(MatchJob, identifier)
        assert c['candidate_total'] == size == c['current_scores']
        assert c['pending_scores'] == c['stale_scores'] == c['failed_scores'] == 0
        assert c['coverage_percent'] == (100 if size else None)
        assert job.examined == size == job.scored
        assert job.batches == size // 200 + 1
        assert db.query(UserOpportunity).count() == size
        print(f'BENCH_SIMULATED rows={size} seconds={time.monotonic()-started:.3f} batches={job.batches}')

def test_parcial_reanudacion_y_omision(match_factory):
    uid = prepare(match_factory, 450)
    with match_factory() as db:
        job = jobs.request_job(db, uid); db.commit()
        reads = []
        def count_reads(conn, cursor, statement, parameters, context, executemany):
            if statement.lstrip().upper().startswith('SELECT'):
                reads.append(statement)
        event.listen(db.get_bind(), 'before_cursor_execute', count_reads)
        assert jobs.process_batch(db, job.id)['status'] == 'PENDING'
        event.remove(db.get_bind(), 'before_cursor_execute', count_reads)
        assert len(reads) < 20, 'Evitar lecturas N+1 por oportunidad'
        c = jobs.coverage(db, uid)
        assert c['current_scores'] == 200 and c['pending_scores'] == 250
        assert jobs.request_job(db, uid).id == job.id
        db.commit()
    first = run_job(match_factory, uid); second = run_job(match_factory, uid)
    with match_factory() as db:
        assert db.get(MatchJob, first).scored == 450
        assert db.get(MatchJob, second).skipped == 450
        assert db.get(MatchJob, second).scored == 0
        assert db.query(MatchScoreHistory).count() == 0

def test_invalidacion_y_estados_comerciales(match_factory):
    uid = prepare(match_factory, 3); run_job(match_factory, uid)
    with match_factory() as db:
        profile = db.query(CompanyProfile).one(); old = profile.match_version
        profile.nombre_comercial = 'Nombre sin impacto'
        uo = db.query(UserOpportunity).first(); uo.triage, uo.feedback_note = 'proyecto', 'conservar'
        db.commit()
        assert profile.match_version == old
        assert jobs.coverage(db, uid)['current_scores'] == 3
        profile.actividades = 'Nueva actividad'; db.commit()
        assert jobs.coverage(db, uid)['stale_scores'] == 3
    run_job(match_factory, uid)
    with match_factory() as db:
        uo = db.query(UserOpportunity).first()
        assert uo.triage == 'proyecto' and uo.feedback_note == 'conservar'
        assert db.query(MatchScoreHistory).count() == 3
        opp = db.get(Opportunity, uo.opportunity_id); opp.raw_json = {'sin_impacto':'valor'}; db.commit()
        assert jobs.coverage(db, uid)['current_scores'] == 3
        opp.objeto = 'objeto actualizado'; db.commit()
        assert jobs.coverage(db, uid)['stale_scores'] == 1
        opp.source = 'secop1'; db.commit()
        assert jobs.coverage(db, uid)['excluded_total'] == 1
        assert jobs.coverage(db, uid)['candidate_total'] == 2

def test_fallo_individual(match_factory, monkeypatch):
    uid = prepare(match_factory, 3); original = jobs.score_opportunity; counter = iter(range(3))
    def score(*a, **k):
        if next(counter) == 1: raise ValueError('fallo ficticio')
        return original(*a, **k)
    monkeypatch.setattr(jobs, 'score_opportunity', score); run_job(match_factory, uid)
    with match_factory() as db:
        c = jobs.coverage(db, uid)
        assert c['current_scores'] == 2 and c['failed_scores'] == 1
        assert c['pending_scores'] == c['stale_scores'] == 0
        assert c['coverage_percent'] == 66.67
    monkeypatch.setattr(jobs, 'score_opportunity', original); run_job(match_factory, uid)
    with match_factory() as db: assert jobs.coverage(db, uid)['current_scores'] == 3

def test_persistencia_fallida_revierte_lote(match_factory):
    uid = prepare(match_factory, 4)
    with match_factory() as db:
        job = jobs.request_job(db, uid); db.commit(); fired = []
        def fail(conn, cursor, statement, parameters, context, executemany):
            if not fired and statement.lstrip().upper().startswith('INSERT INTO USER_OPPORTUNITIES'):
                fired.append(True); raise RuntimeError('persistencia interrumpida')
        event.listen(db.get_bind(), 'before_cursor_execute', fail)
        assert jobs.process_batch(db, job.id)['status'] == 'RETRY'
        db.expire_all()
        assert db.get(MatchJob, job.id).cursor_id == 0
        assert db.query(UserOpportunity).count() == 0
        assert jobs.process_batch(db, job.id)['status'] == 'COMPLETED'
        assert db.query(UserOpportunity).count() == 4

def test_cambio_perfil_y_cancelacion(match_factory):
    uid = prepare(match_factory)
    with match_factory() as db:
        job = jobs.request_job(db, uid); db.commit()
        profile = db.query(CompanyProfile).one(); profile.keywords = ['otra actividad']; db.commit()
        assert jobs.process_batch(db, job.id)['status'] == 'SUPERSEDED'
        newer = jobs.request_job(db, uid); db.commit(); jobs.cancel_job(db, newer); db.commit()
        assert jobs.process_batch(db, newer.id)['status'] == 'BUSY'
        assert db.query(UserOpportunity).count() == 0
        assert jobs.resume_job(db, newer).id != newer.id

def test_dos_ejecutores_y_vencimiento(match_factory):
    uid = prepare(match_factory, 3)
    with match_factory() as first, match_factory() as second:
        job = jobs.request_job(first, uid); first.commit()
        assert jobs._acquire(first, job.id)
        assert jobs._acquire(second, job.id) is None
        first.query(MatchSlot).update({'lease_until':datetime.utcnow()-timedelta(seconds=1)})
        first.query(MatchJob).filter_by(id=job.id).update({'lease_until':datetime.utcnow()-timedelta(seconds=1)})
        first.commit()
        assert jobs.process_batch(second, job.id)['status'] == 'COMPLETED'

def test_embedding_incompatible_y_cambios(match_factory, monkeypatch):
    uid = prepare(match_factory, 1)
    with match_factory() as db:
        opp = db.query(Opportunity).one()
        db.add(OpportunityEmbedding(opportunity_id=opp.id, model='modelo-anterior', vector=[1., 0.])); db.commit()
    run_job(match_factory, uid)
    with match_factory() as db:
        assert jobs.coverage(db, uid)['current_scores'] == 1
        emb = db.query(OpportunityEmbedding).one(); emb.vector = [0., 1.]; db.commit()
        assert jobs.coverage(db, uid)['stale_scores'] == 1
        monkeypatch.setattr(get_settings(), 'match_algorithm_version', 'revision-nueva')
        assert db.query(UserOpportunity).filter(current_score_condition()).count() == 0

def test_texto_actualizado_regenera_cache_y_preserva_matcher(match_factory, monkeypatch):
    uid = prepare(match_factory, 1)
    run_job(match_factory, uid)
    calls = []
    def embed_text(text):
        calls.append(text)
        return [0., 1., 0., 0.]
    monkeypatch.setattr(jobs, 'embed', embed_text)
    with match_factory() as db:
        opp = db.query(Opportunity).one()
        opp.objeto = 'texto contractual actualizado'
        db.commit()
    run_job(match_factory, uid)
    assert 'texto contractual actualizado ' in calls
    with match_factory() as db:
        from app.services.match_versions import embedding_content_version
        opp = db.query(Opportunity).one()
        assert opp.embedding.content_version == embedding_content_version(opp)
        assert opp.embedding.vector == [0., 1., 0., 0.]

def test_limite_global_por_usuarios_y_reintentos_acotados(match_factory):
    uid = prepare(match_factory, 2)
    with match_factory() as db:
        first = jobs.request_job(db, uid); db.commit()
        other = User(email=f'{uuid4().hex}@example.invalid', hashed_password='fixture')
        db.add(other); db.flush()
        db.add(CompanyProfile(user_id=other.id, sector='software')); db.commit()
        second = jobs.request_job(db, other.id); db.commit()
        assert jobs._acquire(db, first.id)
        assert jobs.process_batch(db, second.id)['status'] == 'BUSY'
        db.query(MatchSlot).update({'lease_until':datetime.utcnow()-timedelta(seconds=1)})
        db.commit()
        def fail(conn, cursor, statement, parameters, context, executemany):
            if statement.lstrip().upper().startswith('INSERT INTO USER_OPPORTUNITIES'):
                raise RuntimeError('persistencia no disponible')
        event.listen(db.get_bind(), 'before_cursor_execute', fail)
        assert jobs.process_batch(db, second.id)['status'] == 'RETRY'
        assert jobs.process_batch(db, second.id)['status'] == 'RETRY'
        assert jobs.process_batch(db, second.id)['status'] == 'FAILED'
        assert db.get(MatchJob, second.id).retries == 3
        assert jobs.process_batch(db, second.id)['status'] == 'BUSY'
        event.remove(db.get_bind(), 'before_cursor_execute', fail)
        jobs.resume_job(db, second); db.commit()
        assert jobs.process_batch(db, second.id)['status'] == 'COMPLETED'
