"""Sincronización con fuente simulada, sin llamadas de red."""
from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.models import Base, Opportunity, SyncCursor, User, UserOpportunity
from app.services.ingest import sync_source
from app.services.secop_client import SocrataClient


@pytest.fixture
def store(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path}/sync.db")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    yield factory
    engine.dispose()


def row(key, timestamp="2026-10-20T10:30:00", title="software"):
    return {"sync_row_id": key, "id_del_proceso": f"process-{key}",
            "fecha_de_ultima_publicaci": timestamp, "nombre_del_procedimiento": title,
            "precio_base": "100", "estado_del_procedimiento": "Publicado"}


def test_paginacion_empates_reanudacion_y_reintento(store, monkeypatch):
    pages = [[row("a"), row("b")], RuntimeError("red"), [row("c")]]
    requests = []
    def fetch(self, source, mode, timestamp, cursor_id):
        requests.append((mode, cursor_id))
        result = pages.pop(0)
        if isinstance(result, Exception):
            raise result
        return result
    monkeypatch.setattr(SocrataClient, "fetch_cursor_page", fetch)
    monkeypatch.setattr(SocrataClient, "__init__", lambda self: setattr(self, "page_size", 2))
    with store() as db:
        first = sync_source(db, "secop2_procesos", max_pages=2)
        cursor = db.get(SyncCursor, "secop2_procesos")
        assert first.errors == 1 and first.pages == 1 and cursor.cursor_id == "b"
        assert db.query(Opportunity).count() == 2
        second = sync_source(db, "secop2_procesos", max_pages=1)
        assert second.errors == 0 and second.upserted == 1
        assert requests == [("incremental", None), ("incremental", "b"), ("incremental", "b")]
        assert db.query(Opportunity).count() == 3


def test_fallo_persistencia_revierte_pagina_y_cursor(store, monkeypatch):
    monkeypatch.setattr(SocrataClient, "fetch_cursor_page", lambda *args: [row("a"), row("b")])
    monkeypatch.setattr(SocrataClient, "__init__", lambda self: setattr(self, "page_size", 2))
    def fail(*args):
        raise RuntimeError("fallo simulado")
    monkeypatch.setattr("app.services.ingest.embed", fail)
    with store() as db:
        run = sync_source(db, "secop2_procesos", max_pages=1)
        cursor = db.get(SyncCursor, "secop2_procesos")
        assert run.errors == 1 and cursor.cursor_id is None and cursor.cursor_time is None
        assert db.query(Opportunity).count() == 0


def test_reconciliacion_repite_actualiza_y_preserva_relacion(store, monkeypatch):
    data = [row("a")]
    monkeypatch.setattr(SocrataClient, "fetch_cursor_page", lambda *args: [item.copy() for item in data])
    monkeypatch.setattr(SocrataClient, "__init__", lambda self: setattr(self, "page_size", 10))
    with store() as db:
        assert sync_source(db, "secop2_procesos", max_pages=1).upserted == 1
        opp = db.query(Opportunity).one()
        user = User(email="qa@example.com", hashed_password="x")
        db.add(user)
        db.flush()
        db.add(UserOpportunity(user_id=user.id, opportunity_id=opp.id, triage="guardada"))
        db.commit()
        data[0]["nombre_del_procedimiento"] = "software actualizado"
        run = sync_source(db, "secop2_procesos", max_pages=1)
        db.refresh(opp)
        assert run.detail["updated"] == 1 and opp.objeto == "software actualizado"
        assert db.query(UserOpportunity).filter_by(opportunity_id=opp.id, triage="guardada").count() == 1
        run = sync_source(db, "secop2_procesos", max_pages=1)
        assert run.detail["unchanged"] == 1 and db.query(Opportunity).count() == 1


def test_segunda_ejecucion_bloqueada_y_secop1_reconciliacion(store, monkeypatch):
    monkeypatch.setattr(SocrataClient, "fetch_cursor_page", lambda *args: [])
    with store() as db:
        db.add(SyncCursor(source="secop2_procesos", dataset_id="p6dx-8zbt", status="running",
                          lease_token="otro", lease_until=datetime.utcnow() + timedelta(minutes=1)))
        db.commit()
        with pytest.raises(RuntimeError, match="curso"):
            sync_source(db, "secop2_procesos")
        run = sync_source(db, "secop1", max_pages=1)
        assert run.errors == 0 and run.detail["mode"] == "reconcile"


def test_ejecuciones_simultaneas_usan_un_solo_cursor(store, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event
    entered, release = Event(), Event()
    def fetch(*args):
        entered.set()
        assert release.wait(5)
        return []
    monkeypatch.setattr(SocrataClient, "fetch_cursor_page", fetch)
    def first():
        with store() as db:
            return sync_source(db, "secop2_procesos", max_pages=1).errors
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(first)
        assert entered.wait(5)
        try:
            with store() as db, pytest.raises(RuntimeError, match="curso"):
                sync_source(db, "secop2_procesos", max_pages=1)
        finally:
            release.set()
        assert future.result() == 0


def test_consulta_usa_clave_compuesta_sin_offset(monkeypatch):
    captured = {}
    def query(self, dataset, params):
        captured.update(params)
        return []
    monkeypatch.setattr(SocrataClient, "query", query)
    client = SocrataClient()
    client.fetch_cursor_page("secop2_procesos", "incremental", datetime(2026, 10, 20), "row-2")
    assert "$offset" not in captured
    assert captured["$order"] == "fecha_de_ultima_publicaci ASC, :id ASC"
    assert ":id > 'row-2'" in captured["$where"]
    assert "fecha_de_ultima_publicaci = '2026-10-20T00:00:00.000000'" in captured["$where"]


def test_trabajador_que_pierde_arrendamiento_no_confirma_lote(store, monkeypatch):
    def fetch(*args):
        with store() as other:
            cursor = other.get(SyncCursor, "secop2_procesos")
            cursor.lease_token = "nuevo-trabajador"
            cursor.lease_until = datetime.utcnow() + timedelta(minutes=5)
            other.commit()
        return [row("a")]
    monkeypatch.setattr(SocrataClient, "fetch_cursor_page", fetch)
    with store() as db:
        run = sync_source(db, "secop2_procesos", max_pages=1)
        cursor = db.get(SyncCursor, "secop2_procesos")
        db.refresh(cursor)
        assert run.errors == 1 and cursor.lease_token == "nuevo-trabajador"
        assert cursor.cursor_id is None and db.query(Opportunity).count() == 0


def test_arrendamiento_vencido_permitem_reanudar(store, monkeypatch):
    monkeypatch.setattr(SocrataClient, "fetch_cursor_page", lambda *args: [])
    with store() as db:
        db.add(SyncCursor(source="secop2_procesos", dataset_id="p6dx-8zbt", status="running",
                          lease_token="anterior", lease_until=datetime.utcnow() - timedelta(minutes=1),
                          cursor_time=datetime(2026, 10, 20), cursor_id="anterior"))
        db.commit()
        result = sync_source(db, "secop2_procesos", max_pages=1)
        assert result.errors == 0
        db.expire_all()
        assert db.get(SyncCursor, "secop2_procesos").status == "idle"


def test_arrendamiento_se_renueva_durante_consulta_lenta(store, monkeypatch):
    from threading import Event
    from time import sleep
    observed = []
    def fetch(*args):
        with store() as reader:
            observed.append(reader.get(SyncCursor, "secop2_procesos").lease_until)
        sleep(0.15)
        with store() as reader:
            observed.append(reader.get(SyncCursor, "secop2_procesos").lease_until)
        return []
    monkeypatch.setattr("app.services.ingest.LEASE_HEARTBEAT_SECONDS", 0.02)
    monkeypatch.setattr(SocrataClient, "fetch_cursor_page", fetch)
    with store() as db:
        assert sync_source(db, "secop2_procesos", max_pages=1).errors == 0
    assert observed[1] > observed[0]
