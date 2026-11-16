"""Integración opt-in: solo una base PostgreSQL descartable de nombre mysecop_test_*.

MYSECOP_TEST_POSTGRES_URL=... pytest tests/test_postgresql_sync.py
"""
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from threading import Event

import pytest
from alembic.migration import MigrationContext
from sqlalchemy import Column, UniqueConstraint, create_engine, inspect, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

from app.db.models import Base, Opportunity, SyncCursor, User, UserOpportunity
from app.services.ingest import _renew_lease, sync_source
from app.services.secop_client import SocrataClient

URL = os.environ.get("MYSECOP_TEST_POSTGRES_URL", "")
pytestmark = pytest.mark.skipif(not URL, reason="Requiere PostgreSQL descartable configurado explícitamente")


@pytest.fixture(scope="module")
def factory():
    url = make_url(URL)
    if not url.drivername.startswith("postgresql") or not (url.database or "").startswith("mysecop_test_"):
        pytest.fail("Solo se permite una base PostgreSQL descartable mysecop_test_*")
    engine = create_engine(URL)
    if inspect(engine).get_table_names():
        pytest.fail("La base PostgreSQL de prueba debe estar vacía")
    env = {**os.environ, "DATABASE_URL": URL, "ENVIRONMENT": "testing", "SECRET_KEY": "local-test-secret-key-32-characters-long"}
    # 0001 utiliza los modelos actuales: 0002 ya contiene columnas de
    # revisiones posteriores. Probar explícitamente la transición existente.
    subprocess.run([sys.executable, "-m", "alembic", "upgrade", "0002_mercadopago_subscription"], check=True, env=env)
    subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], check=True, env=env)
    inspector = inspect(engine)
    for table in Base.metadata.sorted_tables:
        assert inspector.has_table(table.name)
        assert {c.name for c in table.columns} <= {c["name"] for c in inspector.get_columns(table.name)}
    # Ejercitar también las ramas que crean columnas/tablas ausentes.
    # Solo se revierte el esquema descartable, antes de insertar datos.
    subprocess.run([sys.executable, "-m", "alembic", "downgrade", "0002_mercadopago_subscription"], check=True, env=env)
    assert "password_reset_token" not in {c["name"] for c in inspect(engine).get_columns("users")}
    assert not inspect(engine).has_table("sync_usage")
    with engine.begin() as connection:
        connection.execute(text("insert into users (email, hashed_password) values (:email, :password)"),
                           {"email": "legacy@example.invalid", "password": "fixture-only"})
    subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], check=True, env=env)
    inspector = inspect(engine)
    with engine.connect() as connection:
        type_comparator = MigrationContext.configure(connection).impl.compare_type
        assert connection.execute(text("select hashed_password from users where email = 'legacy@example.invalid'")).scalar_one() == "fixture-only"
    for table in Base.metadata.tables.values():
        columns = {c["name"]: c for c in inspector.get_columns(table.name)}
        assert set(columns) == set(table.columns.keys())
        for column in table.columns:
            actual = columns[column.name]
            assert actual["nullable"] == column.nullable, (table.name, column.name)
            assert not type_comparator(Column(column.name, actual["type"]), column), (table.name, column.name)
        assert set(inspector.get_pk_constraint(table.name)["constrained_columns"]) == {c.name for c in table.primary_key}
        actual_indexes = {(tuple(i["column_names"]), bool(i["unique"])) for i in inspector.get_indexes(table.name)}
        assert {(tuple(c.name for c in i.columns), bool(i.unique)) for i in table.indexes} <= actual_indexes
        actual_fks = {(tuple(f["constrained_columns"]), f["referred_table"], tuple(f["referred_columns"])) for f in inspector.get_foreign_keys(table.name)}
        assert {(tuple(c.parent.name for c in f.elements), f.referred_table.name, tuple(c.column.name for c in f.elements)) for f in table.foreign_key_constraints} <= actual_fks
        actual_unique = {tuple(c["column_names"]) for c in inspector.get_unique_constraints(table.name)}
        assert {tuple(c.name for c in constraint.columns) for constraint in table.constraints if isinstance(constraint, UniqueConstraint)} <= actual_unique
    yield sessionmaker(bind=engine, expire_on_commit=False)
    subprocess.run([sys.executable, "-m", "alembic", "downgrade", "0009_landing_visits"], check=True, env=env)
    assert not inspect(engine).has_table("sync_cursors")
    subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], check=True, env=env)
    assert inspect(engine).has_table("sync_cursors")
    with engine.connect() as connection:
        assert connection.execute(text("select count(*) from users where email = :email"),
                                  {"email": "postgres-test@example.invalid"}).scalar_one() == 1
    engine.dispose()


def row(key, title="software"):
    return {"sync_row_id": key, "id_del_proceso": f"pg-{key}", "fecha_de_ultima_publicaci": "2026-10-20T10:30:00", "nombre_del_procedimiento": title, "estado_del_procedimiento": "Publicado"}


def test_postgres_concurrencia_reanudacion_renovacion_y_relaciones(factory, monkeypatch):
    entered, release = Event(), Event()
    pages = [[row("a"), row("b")], RuntimeError("interrupción")]
    def fetch(*args):
        entered.set()
        assert release.wait(10)
        value = pages.pop(0)
        if isinstance(value, Exception):
            raise value
        return value
    monkeypatch.setattr(SocrataClient, "__init__", lambda self: setattr(self, "page_size", 2))
    monkeypatch.setattr(SocrataClient, "fetch_cursor_page", fetch)
    def worker():
        with factory() as db:
            run = sync_source(db, "secop2_procesos", max_pages=2)
            return run.errors
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(worker)
        assert entered.wait(10)
        with factory() as second:
            with pytest.raises(RuntimeError, match="curso"):
                sync_source(second, "secop2_procesos", max_pages=1)
        release.set()
        assert future.result() == 1
    with factory() as db:
        cursor = db.get(SyncCursor, "secop2_procesos")
        assert cursor.cursor_id == "b" and db.query(Opportunity).count() == 2
        cursor.status = "running"
        cursor.lease_token = "vencido"
        cursor.lease_until = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(seconds=1)
        db.commit()
    assert not _renew_lease(factory, "secop2_procesos", "vencido")
    monkeypatch.setattr(SocrataClient, "fetch_cursor_page", lambda *args: [row("c")])
    with factory() as db:
        run = sync_source(db, "secop2_procesos", max_pages=1)
        assert run.errors == 0 and db.query(Opportunity).count() == 3
        opp = db.query(Opportunity).filter_by(source_id="pg-a").one()
        user = User(email="postgres-test@example.invalid", hashed_password="test")
        db.add(user); db.flush()
        db.add(UserOpportunity(user_id=user.id, opportunity_id=opp.id, triage="guardada")); db.commit()
        monkeypatch.setattr(SocrataClient, "fetch_cursor_page", lambda *args: [row("a", "actualizado")])
        run = sync_source(db, "secop2_procesos", max_pages=1)
        db.refresh(opp)
        assert run.errors == 0 and opp.objeto == "actualizado"
        assert db.query(UserOpportunity).filter_by(opportunity_id=opp.id, triage="guardada").count() == 1
        assert sync_source(db, "secop2_procesos", max_pages=1).errors == 0
        assert db.query(Opportunity).count() == 3


def test_postgres_rollback_al_perder_conexion(factory):
    engine = factory.kw["bind"]
    with factory() as victim:
        pid = victim.execute(text("select pg_backend_pid()")).scalar_one()
        victim.add(Opportunity(source="qa", source_id="conexion-perdida"))
        cursor = victim.get(SyncCursor, "secop2_procesos")
        previous = cursor.cursor_id
        cursor.cursor_id = "no-confirmado"
        victim.flush()
        with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as admin:
            assert admin.execute(text("select pg_terminate_backend(:pid)"), {"pid": pid}).scalar_one()
        with pytest.raises(Exception):
            victim.commit()
        victim.rollback()
    with factory() as db:
        assert db.query(Opportunity).filter_by(source_id="conexion-perdida").count() == 0
        assert db.get(SyncCursor, "secop2_procesos").cursor_id == previous


def test_postgres_renovacion_y_token_perdido(factory, monkeypatch):
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    with factory() as db:
        cursor = db.get(SyncCursor, "secop2_procesos")
        cursor.lease_token = "propietario"
        cursor.lease_until = now + timedelta(minutes=1)
        db.commit()
    assert _renew_lease(factory, "secop2_procesos", "propietario")
    assert not _renew_lease(factory, "secop2_procesos", "otro")
    with factory() as db:
        cursor = db.get(SyncCursor, "secop2_procesos")
        assert cursor.lease_until > now + timedelta(minutes=9)
        cursor.lease_until = now - timedelta(minutes=1)
        db.commit()
    def fetch(*args):
        with factory() as other:
            replacement = other.get(SyncCursor, "secop2_procesos")
            replacement.lease_token = "nuevo"
            replacement.lease_until = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(minutes=1)
            other.commit()
        return [row("z")]
    monkeypatch.setattr(SocrataClient, "fetch_cursor_page", fetch)
    with factory() as db:
        before = db.get(SyncCursor, "secop2_procesos").cursor_id
        result = sync_source(db, "secop2_procesos", max_pages=1)
        assert result.errors == 1
        db.expire_all()
        assert db.get(SyncCursor, "secop2_procesos").cursor_id == before
        assert db.query(Opportunity).filter_by(source_id="pg-z").count() == 0


def test_postgres_fallo_de_pagina_no_avanza_cursor(factory, monkeypatch):
    import app.services.ingest as ingest
    original = ingest._save_row
    def fail_second(db, source, data):
        if data["sync_row_id"] == "b":
            raise RuntimeError("fallo simulado en segunda fila")
        return original(db, source, data)
    monkeypatch.setattr(ingest, "_save_row", fail_second)
    monkeypatch.setattr(SocrataClient, "fetch_cursor_page", lambda *args: [
        {"sync_row_id": "a", "uid": "historico-a", "objeto_a_contratar": "uno"},
        {"sync_row_id": "b", "uid": "historico-b", "objeto_a_contratar": "dos"},
    ])
    with factory() as db:
        result = sync_source(db, "secop1", max_pages=1)
        assert result.errors == 1
        db.expire_all()
        assert db.get(SyncCursor, "secop1").cursor_id is None
        assert db.query(Opportunity).filter(Opportunity.source_id.in_(["historico-a", "historico-b"])).count() == 0
