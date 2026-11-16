"""Conector SECOP: normalización de campos reales verificados e ingesta incremental."""
from datetime import datetime

import pytest

from app.services.secop_client import SocrataClient, normalize_row

# Fila con los nombres de campo REALES verificados en p6dx-8zbt (2026-10-27)
FILA_P6DX = {
    "id_del_proceso": "CO1.TEST.777-1",
    "entidad": "Alcaldía Mayor de Bogotá D.C. (Secretaría Distrital de Gobierno)",
    "nit_entidad": "899999006-1",
    "departamento_entidad": "Bogotá D.C.",
    "ciudad_entidad": "Bogotá D.C.",
    "nombre_del_procedimiento": "Desarrollo de software para modernización tecnológica",
    "descripci_n_del_procedimiento": "Interoperabilidad y sistemas de información",
    "modalidad_de_contratacion": "Licitación Pública",
    "tipo_de_contrato": "Compra y Venta",
    "codigo_principal_de_categoria": "81101500",
    "precio_base": "2000000000",
    "estado_del_procedimiento": "En proceso",
    "fecha_de_publicacion_del": "2026-10-20T10:30:00",
    "fecha_de_ultima_publicaci": "2026-10-24T08:00:00",
    "urlproceso": "https://community.binpar.cloud/compra-bogota/secop2/ejemplo",
}


def test_normalizacion_secop2_procesos():
    data = normalize_row("secop2_procesos", FILA_P6DX)
    assert data["source_id"] == "CO1.TEST.777-1"
    assert data["entidad"].startswith("Alcaldía")
    assert data["departamento"] == "Bogotá D.C."
    assert data["modalidad"] == "Licitación Pública"
    assert data["unspsc_code"] == "81101500"
    assert data["valor"] == 2_000_000_000
    assert data["estado"] == "En proceso"
    assert data["cancelled"] is False
    assert data["fecha_publicacion"] == datetime(2026, 10, 20, 10, 30)
    assert data["fecha_cierre"] is None  # la fuente no expone cierre (verificado)
    assert data["url_oficial"].startswith("https://")


def test_normalizacion_cancelado():
    fila = {**FILA_P6DX, "estado_del_procedimiento": "Cancelado"}
    assert normalize_row("secop2_procesos", fila)["cancelled"] is True


def test_ingesta_incremental_paginada(monkeypatch):
    """Dos páginas completas + una parcial: $offset avanza y se acumulan filas."""
    page = [dict(FILA_P6DX) for _ in range(3)]
    llamadas = []

    def fake_get(url, params=None, headers=None, timeout=None):
        llamadas.append(dict(params or {}))
        class R:
            status_code = 200
            def raise_for_status(self):
                pass
            def json(self):
                offset = (params or {}).get("$offset", 0)
                if offset == 0:
                    return page
                if offset == 3:
                    return [dict(FILA_P6DX)]  # página parcial
                return []
        return R()

    monkeypatch.setattr("app.services.secop_client.httpx.get", fake_get)
    client = SocrataClient()
    client.page_size = 3  # página pequeña para probar el avance de $offset
    rows = client.fetch_incremental("secop2_procesos", max_pages=5)
    assert len(rows) == 4
    assert [c["$offset"] for c in llamadas] == [0, 3]


def test_ingesta_incremental_con_watermark(monkeypatch):
    """$where sobre la fecha de actualización del dataset (ingesta incremental)."""
    capturado = {}

    def fake_get(url, params=None, headers=None, timeout=None):
        capturado["$where"] = (params or {}).get("$where")
        class R:
            status_code = 200
            def raise_for_status(self):
                pass
            def json(self):
                return []
        return R()

    monkeypatch.setattr("app.services.secop_client.httpx.get", fake_get)
    client = SocrataClient()
    client.fetch_incremental("secop2_procesos", since=datetime(2026, 10, 20), max_pages=1)
    assert "fecha_de_ultima_publicaci > '2026-10-20T00:00:00'" in (capturado["$where"] or "")


def test_429_reintenta_con_backoff(monkeypatch):
    intentos = {"n": 0}
    dormidos = []

    def fake_sleep(s):
        dormidos.append(s)

    class R429:
        status_code = 429

    class R200:
        status_code = 200
        def raise_for_status(self):
            pass
        def json(self):
            return [dict(FILA_P6DX)]

    def fake_get(url, params=None, headers=None, timeout=None):
        intentos["n"] += 1
        return R429() if intentos["n"] == 1 else R200()

    monkeypatch.setattr("app.services.secop_client.httpx.get", fake_get)
    monkeypatch.setattr("app.services.secop_client.time.sleep", fake_sleep)
    rows = SocrataClient().fetch_incremental("secop2_procesos", max_pages=1)
    assert len(rows) == 1
    assert intentos["n"] == 2
    assert dormidos  # hubo backoff, sin evasión


def test_app_token_en_headers(monkeypatch):
    capturado = {}

    def fake_get(url, params=None, headers=None, timeout=None):
        capturado.update(headers or {})
        class R:
            status_code = 200
            def raise_for_status(self):
                pass
            def json(self):
                return []
        return R()

    monkeypatch.setattr("app.services.secop_client.httpx.get", fake_get)
    SocrataClient(app_token="token-de-prueba").query("p6dx-8zbt", {"$limit": 1})
    assert capturado.get("X-App-Token") == "token-de-prueba"


def test_url_como_diccionario_y_valores_no_definidos():
    """Calidad de datos verificada contra la API real: urlproceso puede llegar como dict
    y campos como departamento_entidad llegan con 'No Definido' (evidencia E2E 2026-10-29)."""
    fila = dict(FILA_P6DX)
    fila["urlproceso"] = {"url": "https://community.secop.gov.co/Public/Tendering/OpportunityDetail/Index?noticeUID=CO1.NTC.401"}
    fila["departamento_entidad"] = "No Definido"
    data = normalize_row("secop2_procesos", fila)
    assert data["url_oficial"].startswith("https://")
    assert data["departamento"] is None


def test_unspsc_no_estandar_se_descarta():
    fila = dict(FILA_P6DX)
    fila["codigo_principal_de_categoria"] = "V1.80111701"  # valor real observado, no es UNSPSC
    data = normalize_row("secop2_procesos", fila)
    assert data["unspsc_code"] is None


def test_fecha_con_zona_horaria_y_fecha_invalida():
    fila = {**FILA_P6DX, "fecha_de_publicacion_del": "2026-10-20T10:30:00-05:00"}
    assert normalize_row("secop2_procesos", fila)["fecha_publicacion"] == datetime(2026, 10, 20, 15, 30)
    fila["fecha_de_publicacion_del"] = "fecha desconocida"
    assert normalize_row("secop2_procesos", fila)["fecha_publicacion"] is None


def test_secop1_relacion_proceso_adjudicacion_no_es_convocatoria():
    from types import SimpleNamespace
    from app.services.opportunity_status import classify_opportunity
    fila = {"uid": "CONST-123-ADJ-2", "numero_de_constancia": "CONST-123",
            "numero_de_proceso": "PROC-9", "id_adjudicacion": "ADJ-2",
            "numero_de_contrato": "CON-4", "nombre_entidad": "Entidad de prueba",
            "nit_de_la_entidad": "900000000", "departamento_entidad": "Meta",
            "municipio_entidad": "Villavicencio", "objeto_a_contratar": "Suministros",
            "detalle_del_objeto_a_contratar": "Suministros de prueba",
            "modalidad_de_contratacion": "Licitación Pública", "cuantia_proceso": "1000000",
            "estado_del_proceso": "Publicado", "fecha_de_cargue_en_el_secop": "2026-01-10T00:00:00",
            "ultima_actualizacion": "2026-01-11T00:00:00",
            "ruta_proceso_en_secop_i": {"url": "https://www.colombiacompra.gov.co/proceso"}}
    data = normalize_row("secop1", fila)
    assert data["source_id"] == "CONST-123-ADJ-2" and data["entidad"] == "Entidad de prueba"
    assert data["raw_json"]["numero_de_constancia"] == "CONST-123"
    assert data["raw_json"]["id_adjudicacion"] == "ADJ-2"
    assert data["ciudad"] == "Villavicencio" and data["modalidad"] == "Licitación Pública"
    assert data["fecha_publicacion"] == datetime(2026, 1, 10) and data["valor"] == 1_000_000
    assert classify_opportunity(SimpleNamespace(**data, updated_at=None))["status"] == "HISTORICAL"


def test_secop1_adjudicaciones_distintas_mismo_proceso_no_se_fusionan(client, db, monkeypatch):
    from uuid import uuid4
    from app.db.models import Opportunity, SyncCursor
    from app.services.ingest import sync_source
    marker = uuid4().hex
    filas = [{"sync_row_id": f"{marker}-{i}", "uid": f"{marker}-const-adj-{i}",
              "numero_de_constancia": f"{marker}-const", "id_adjudicacion": str(i),
              "nombre_entidad": "Entidad ficticia", "objeto_a_contratar": "Suministros",
              "estado_del_proceso": "Publicado"} for i in (1, 2)]
    db.query(SyncCursor).filter_by(source="secop1").delete()
    db.commit()
    monkeypatch.setattr(SocrataClient, "fetch_cursor_page", lambda *args, **kwargs: filas)
    run = sync_source(db, "secop1", max_pages=1)
    assert run.errors == 0 and run.upserted == 2
    assert db.query(Opportunity).filter(Opportunity.source == "secop1", Opportunity.source_id.like(f"{marker}%")).count() == 2


@pytest.mark.parametrize("identity", [None, ""])
def test_secop1_sin_uid_no_usa_proceso_como_identidad(client, db, monkeypatch, identity):
    from uuid import uuid4
    from app.db.models import Opportunity, SyncCursor
    from app.services.ingest import sync_source

    marker = uuid4().hex
    filas = [{"sync_row_id": f"{marker}-1", "uid": f"{marker}-adj-1",
              "numero_de_constancia": marker, "objeto_a_contratar": "Prueba ficticia"},
             {"sync_row_id": f"{marker}-2", "uid": identity,
              "numero_de_constancia": marker, "id_adjudicacion": "2"}]
    db.query(SyncCursor).filter_by(source="secop1").delete()
    db.commit()
    monkeypatch.setattr(SocrataClient, "fetch_cursor_page", lambda *args: filas)
    run = sync_source(db, "secop1", max_pages=1)
    assert run.errors == 1
    db.expire_all()
    assert db.get(SyncCursor, "secop1").cursor_id is None
    assert db.query(Opportunity).filter_by(source="secop1", source_id=f"{marker}-adj-1").count() == 0


def test_reingesta_actualiza_datos_y_vector_sin_perder_cierre(client, db, monkeypatch):
    from datetime import timedelta
    from uuid import uuid4
    from app.db.models import Opportunity
    from app.services.ingest import sync_source

    source_id = f"qa-{uuid4().hex}"
    row = {**FILA_P6DX, "id_del_proceso": source_id}
    monkeypatch.setattr(SocrataClient, "fetch_cursor_page", lambda *args, **kwargs: [{**row, "sync_row_id": source_id}])
    first = sync_source(db, "secop2_procesos", max_pages=1)
    assert first.upserted == 1
    opp = db.query(Opportunity).filter_by(source_id=source_id).one()
    original_id, vector = opp.id, opp.embedding.vector
    opp.fecha_cierre = datetime.utcnow() + timedelta(days=3)
    db.commit()
    row["nombre_del_procedimiento"] = "Suministro de equipos agrícolas"
    row["descripci_n_del_procedimiento"] = "Cultivos y fertilizantes"
    second = sync_source(db, "secop2_procesos", max_pages=1)
    db.refresh(opp)
    assert second.duplicates == 1 and opp.id == original_id
    assert opp.objeto == row["nombre_del_procedimiento"] and opp.fecha_cierre is not None
    assert opp.embedding.vector != vector
    third = sync_source(db, "secop2_procesos", max_pages=1)
    assert third.upserted == 0
    assert db.query(Opportunity).filter_by(source_id=source_id).count() == 1
