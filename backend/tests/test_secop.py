"""Conector SECOP: normalización de campos reales verificados e ingesta incremental."""
from datetime import datetime

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
