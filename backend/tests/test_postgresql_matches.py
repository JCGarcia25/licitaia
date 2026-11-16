"""Integración real PG: fuente/vectores simulados, locks y conexiones reales."""
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from threading import Event
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker
from app.core.config import get_settings
from app.db.models import Base, CompanyProfile, MatchJob, MatchSlot, Opportunity, User, UserOpportunity
from app.services import match_jobs as jobs
from app.services.matcher import MatchResult
from app.services.match_versions import current_score_condition

URL = os.environ.get('MYSECOP_TEST_POSTGRES_URL', '')
pytestmark = pytest.mark.skipif(not URL, reason='Requiere PostgreSQL descartable explícito')

@pytest.fixture(scope='module')
def pg_factory():
    url = make_url(URL)
    if not url.drivername.startswith('postgresql') or not (url.database or '').startswith('mysecop_test_'):
        pytest.fail('Solo PostgreSQL descartable mysecop_test_*')
    engine = create_engine(URL)
    assert not inspect(engine).get_table_names(), 'Debe estar vacía'
    env = {**os.environ, 'DATABASE_URL':URL, 'ENVIRONMENT':'testing'}
    def migrate(*args):
        return subprocess.run([sys.executable, '-m', 'alembic', *args], env=env, capture_output=True, text=True)
    result = migrate('upgrade', 'head'); assert result.returncode == 0, result.stderr
    assert migrate('downgrade', '0010_sync_cursor').returncode == 0
    assert not inspect(engine).has_table('match_jobs')
    with engine.begin() as c:
        uid = c.execute(text("insert into users (email,hashed_password) values ('legacy-matching@example.invalid','fixture') returning id")).scalar_one()
        c.execute(text("insert into company_profiles (user_id,sector) values (:uid,'software')"), {'uid':uid})
        oid = c.execute(text("insert into opportunities (source,source_id,objeto,estado,cancelled) values ('qa','legacy-match','software','Publicado',false) returning id")).scalar_one()
        c.execute(text("insert into user_opportunities (user_id,opportunity_id,score,triage) values (:uid,:oid,88,'guardada')"), {'uid':uid,'oid':oid})
    result = migrate('upgrade', 'head'); assert result.returncode == 0, result.stderr
    for table in Base.metadata.tables.values():
        assert {c['name'] for c in inspect(engine).get_columns(table.name)} == set(table.columns.keys())
    with engine.connect() as c:
        assert c.execute(text('select score from user_opportunities where user_id=:uid'), {'uid':uid}).scalar_one() == 88
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as db:
        assert db.query(UserOpportunity).filter(current_score_condition()).count() == 0
    yield factory, migrate
    # El historial de una repetición no puede borrarse mediante downgrade.
    result = migrate('downgrade', '0010_sync_cursor')
    assert result.returncode != 0 and ('historial' in result.stderr or 'metadata de intentos fallidos' in result.stderr)
    assert inspect(engine).has_table('match_jobs')
    engine.dispose()

@pytest.fixture
def factory(pg_factory, monkeypatch):
    monkeypatch.setattr(get_settings(), 'match_batch_size', 2)
    monkeypatch.setattr(get_settings(), 'match_global_concurrency', 2)
    monkeypatch.setattr(get_settings(), 'embedding_dim', 4)
    monkeypatch.setattr(jobs, 'embed', lambda t: [1., 0., 0., 0.])
    monkeypatch.setattr(jobs, 'score_opportunity', lambda *a, **k: MatchResult(75, []))
    return pg_factory[0]

def new_job(factory):
    with factory() as db:
        user = User(email=f'{uuid4().hex}@example.invalid', hashed_password='fixture')
        db.add(user); db.flush()
        db.add(CompanyProfile(user_id=user.id, sector='software', keywords=['software']))
        db.add_all([Opportunity(source='qa', source_id=uuid4().hex, objeto='software', estado='Publicado') for _ in range(3)])
        db.commit()
        job = jobs.request_job(db, user.id); db.commit()
        return job.id, user.id

def finish(factory, jid):
    for _ in range(50):
        with factory() as db: result = jobs.process_batch(db, jid)
        if result['status'] != 'PENDING':
            assert result['status'] == 'COMPLETED', result
            return
    pytest.fail('No terminó')

def test_pg_dos_workers_perfil_cambiante_y_fencing(factory, monkeypatch):
    jid, uid = new_job(factory)
    entered, release, writing = Event(), Event(), Event()
    def scoring(*a, **k):
        entered.set(); assert release.wait(10)
        return MatchResult(75, [])
    monkeypatch.setattr(jobs, 'score_opportunity', scoring)
    def worker():
        with factory() as db: return jobs.process_batch(db, jid)
    def writer():
        with factory() as db:
            profile = db.query(CompanyProfile).filter_by(user_id=uid).one()
            profile.actividades = 'actividad nueva'
            writing.set(); db.commit()
    with ThreadPoolExecutor(max_workers=2) as pool:
        result = pool.submit(worker); assert entered.wait(10)
        with factory() as db: assert jobs.process_batch(db, jid)['status'] == 'BUSY'
        update = pool.submit(writer); assert writing.wait(10)
        update.result(timeout=2)  # escritura termina durante cálculo externo
        release.set(); assert result.result(timeout=10)['status'] == 'SUPERSEDED'
    with factory() as db:
        assert jobs.coverage(db, uid)['current_scores'] == 0
        assert db.get(MatchJob,jid).state == 'SUPERSEDED'
        new = jobs.request_job(db, uid); db.commit(); nextid = new.id
    finish(factory, nextid)
    with factory() as db: assert jobs.coverage(db, uid)['coverage_percent'] == 100

def test_pg_perdida_conexion_revierte_cursor_y_recupera(factory, monkeypatch):
    jid, uid = new_job(factory)
    with factory() as victim:
        once = []
        def kill(*a, **k):
            if not once:
                once.append(True)
                pid = victim.execute(text('select pg_backend_pid()')).scalar_one()
                with factory.kw['bind'].connect().execution_options(isolation_level='AUTOCOMMIT') as killer:
                    assert killer.execute(text('select pg_terminate_backend(:pid)'), {'pid':pid}).scalar_one()
            return MatchResult(75, [])
        monkeypatch.setattr(jobs, 'score_opportunity', kill)
        assert jobs.process_batch(victim, jid)['status'] == 'RETRY'
    with factory() as db:
        assert db.get(MatchJob, jid).cursor_id == 0
        assert db.query(UserOpportunity).filter_by(user_id=uid).count() == 0
    monkeypatch.setattr(jobs, 'score_opportunity', lambda *a, **k: MatchResult(75, []))
    finish(factory, jid)
    with factory() as db: assert jobs.coverage(db, uid)['coverage_percent'] == 100

def test_pg_oportunidad_actualizada_y_repeticion_preserva_relacion(factory, monkeypatch):
    jid, uid = new_job(factory)
    finish(factory, jid)
    with factory() as db:
        uo = db.query(UserOpportunity).filter_by(user_id=uid).first()
        uo.triage, uo.feedback_note = 'guardada', 'conservar'
        oid, original_id = uo.opportunity_id, uo.id
        opp = db.get(Opportunity, oid); opp.valor = 123456
        db.commit()
        assert jobs.coverage(db, uid)['stale_scores'] == 1
        job = jobs.request_job(db, uid); db.commit(); nextid = job.id
    finish(factory, nextid)
    with factory() as db:
        uo = db.query(UserOpportunity).filter_by(user_id=uid, opportunity_id=oid).one()
        assert uo.id == original_id and uo.triage == 'guardada' and uo.feedback_note == 'conservar'
        from app.db.models import MatchScoreHistory
        assert db.query(MatchScoreHistory).filter_by(user_id=uid, opportunity_id=oid).count() == 1
        plan = db.execute(text('EXPLAIN SELECT * FROM opportunities WHERE id > :id ORDER BY id LIMIT 200'), {'id':oid}).all()
        print('KEYSET_PLAN', [r[0] for r in plan])

def test_pg_interrupcion_en_lote_y_arrendamiento(factory, monkeypatch):
    jid, uid = new_job(factory)
    class Interrupted(BaseException): pass
    def interrupt(*a, **k): raise Interrupted()
    monkeypatch.setattr(jobs, 'score_opportunity', interrupt)
    with pytest.raises(Interrupted):
        with factory() as db: jobs.process_batch(db, jid)
    with factory() as db:
        assert db.get(MatchJob, jid).cursor_id == 0
        assert db.query(UserOpportunity).filter_by(user_id=uid).count() == 0
        db.query(MatchSlot).update({'lease_until':datetime.utcnow()-timedelta(seconds=1)})
        db.query(MatchJob).filter_by(id=jid).update({'lease_until':datetime.utcnow()-timedelta(seconds=1)})
        db.commit()
    monkeypatch.setattr(jobs, 'score_opportunity', lambda *a, **k: MatchResult(75, []))
    finish(factory, jid)

def test_pg_oportunidad_modificada_durante_lote(factory, monkeypatch):
    jid, uid = new_job(factory)
    from app.services.opportunity_status import potentially_current_condition
    with factory() as db:
        oid = db.query(Opportunity.id).filter(potentially_current_condition()).order_by(Opportunity.id).first()[0]
    entered, release, writing = Event(), Event(), Event()
    def score(*a, **k):
        entered.set(); assert release.wait(10)
        return MatchResult(75, [])
    monkeypatch.setattr(jobs, 'score_opportunity', score)
    def worker():
        with factory() as db: return jobs.process_batch(db, jid)
    def writer():
        with factory() as db:
            opp = db.get(Opportunity, oid)
            opp.descripcion = f'texto actualizado {uuid4().hex}'
            writing.set(); db.commit()
    with ThreadPoolExecutor(max_workers=2) as pool:
        result = pool.submit(worker); assert entered.wait(10)
        update = pool.submit(writer); assert writing.wait(10)
        update.result(timeout=2)
        release.set(); assert result.result(timeout=10)['status'] == 'RETRY'
    with factory() as db: assert db.query(UserOpportunity).filter_by(user_id=uid).count() == 0
    finish(factory, jid)
    with factory() as db:
        assert jobs.coverage(db, uid)['coverage_percent'] == 100
        following = jobs.request_job(db, uid); db.commit(); following_id = following.id
    finish(factory, following_id)
    with factory() as db: assert jobs.coverage(db, uid)['coverage_percent'] == 100

def test_pg_failed_input_metadata_guard(factory,pg_factory,monkeypatch):
    jid,uid=new_job(factory)
    def fail(*args,**kwargs):raise RuntimeError('provider failed')
    monkeypatch.setattr(jobs,'score_opportunity',fail)
    finish(factory,jid)
    with factory() as db:
        row=db.query(UserOpportunity).filter_by(user_id=uid).first()
        assert row.score is None and row.failed_input_versions is not None
        assert jobs.coverage(db,uid)['failed_scores']>0
    result=pg_factory[1]('downgrade','0011_match_jobs')
    assert result.returncode!=0 and 'metadata de intentos fallidos' in result.stderr
