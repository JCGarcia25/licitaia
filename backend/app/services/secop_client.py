"""Cliente de Socrata para los datasets oficiales de SECOP en datos.gov.co.

Datasets verificados (2026-10, ver docs/fuentes-secop.md):
- SECOP II - Procesos de Contratación: p6dx-8zbt  (~9,4 M filas)
- SECOP II - Contratos Electrónicos:   jbjy-vk9h  (~5,7 M filas)
- SECOP I - 202002:                    e985-4d7e
- SECOP Integrado (referencia):        rpmr-utcd

Uso responsable:
- Header X-App-Token (config SECoP_APP_TOKEN) para un límite propio por aplicación.
- Paginación con $limit/$offset (default $limit = 1000, máximo del portal).
- Ingesta incremental con $where sobre fecha_de_ultima_publicaci y $order.
- Respeto de HTTP 429: reintento con backoff exponencial.
- NO se evaden CAPTCHAs ni restricciones; solo endpoints abiertos de datos.gov.co.
"""
from __future__ import annotations

import logging
import time
from datetime import datetime
from typing import Any
from urllib.parse import quote

import re

import httpx

from app.core.config import get_settings

logger = logging.getLogger("licitaia.secop")

DATASETS = {
    "secop2_procesos": "p6dx-8zbt",   # SECOP II - Procesos de Contratación
    "secop2_contratos": "jbjy-vk9h",  # SECOP II - Contratos Electrónicos
    "secop1": "e985-4d7e",            # SECOP I - 202002
}

# Mapeo de campos reales (verificados contra la API) -> modelo normalizado.
FIELD_MAP = {
    "secop2_procesos": {
        "source_id": "id_del_proceso",
        "entidad": "entidad",
        "nit_entidad": "nit_entidad",
        "departamento": "departamento_entidad",
        "ciudad": "ciudad_entidad",
        "objeto": "nombre_del_procedimiento",
        "descripcion": "descripci_n_del_procedimiento",
        "modalidad": "modalidad_de_contratacion",
        "tipo_contrato": "tipo_de_contrato",
        "unspsc_code": "codigo_principal_de_categoria",
        "valor": "precio_base",
        "estado": "estado_del_procedimiento",
        "fecha_publicacion": "fecha_de_publicacion_del",
        "url": "urlproceso",
        "watermark_field": "fecha_de_ultima_publicaci",
        # TODO(verificado): este dataset NO expone fecha de cierre del proceso.
    },
    "secop2_contratos": {
        "source_id": "id_contrato",
        "entidad": "nombre_entidad",
        "nit_entidad": "nit_entidad",
        "departamento": "departamento",
        "ciudad": "ciudad",
        "objeto": "objeto_del_contrato",
        "descripcion": "descripcion_del_proceso",
        "modalidad": "modalidad_de_contratacion",
        "tipo_contrato": "tipo_de_contrato",
        "unspsc_code": "codigo_de_categoria_principal",
        "valor": "valor_del_contrato",
        "estado": "estado_contrato",
        "fecha_publicacion": "fecha_de_firma",
        "url": "urlproceso",
        "watermark_field": "ultima_actualizacion",
    },
    "secop1": {
        # Dataset SECOP I - 202002: campos de proceso y adjudicación.
        "source_id": "id_del_portafolio",
        "entidad": "nom_entidad",
        "nit_entidad": "nit_entidad",
        "departamento": "departamento_entidad",
        "objeto": "objeto_a_contratar",
        "modalidad": "tipo_de_proceso",
        "valor": "cuantia_proceso",
        "estado": "estado_del_proceso",
        "fecha_publicacion": "fecha_de_publicacion",
        "watermark_field": "fecha_de_ultima_publi",  # TODO(verificar en tiempo de ejecución; fallback sin filtro)
    },
}

ESTADOS_CANCELADOS = {"cancelado", "cancelada", "retirado", "terminado sin liquidar", "enviado pnn"}


class SocrataClient:
    """Cliente HTTP mínimo y robusto para SoQL (SODA 2.x)."""

    def __init__(self, domain: str | None = None, app_token: str | None = None):
        settings = get_settings()
        self.domain = domain or settings.secop_domain
        self.app_token = app_token or settings.secop_app_token
        self.page_size = min(settings.secop_page_size, 1000)  # $limit máximo del portal
        self.max_pages = settings.secop_max_pages_per_run

    def _headers(self) -> dict[str, str]:
        headers = {"Accept": "application/json", "User-Agent": "LicitaIA/1.0 (+https://licitaia.co)"}
        if self.app_token:
            headers["X-App-Token"] = self.app_token  # límite por aplicación, no por IP
        return headers

    def query(self, dataset: str, params: dict[str, Any]) -> list[dict]:
        url = f"https://{self.domain}/resource/{dataset}.json"
        backoff = 2.0
        for attempt in range(4):
            resp = httpx.get(url, params=params, headers=self._headers(), timeout=60)
            if resp.status_code == 429:  # throttling: backoff exponencial, nunca evasión
                logger.warning("Socrata 429 en %s; reintento en %.0fs", dataset, backoff)
                time.sleep(backoff)
                backoff *= 2
                continue
            resp.raise_for_status()
            return resp.json()
        raise RuntimeError(f"Socrata respondió 429 de forma persistente para {dataset}")

    def fetch_incremental(
        self,
        source: str,
        since: datetime | None = None,
        max_pages: int | None = None,
        extra_where: str | None = None,
    ) -> list[dict]:
        """Ingesta incremental: $where fecha > watermark, $order ascendente, paginación $offset."""
        mapping = FIELD_MAP[source]
        dataset = DATASETS[source]
        where_parts: list[str] = []
        if since and mapping.get("watermark_field"):
            field = mapping["watermark_field"]
            iso = since.strftime("%Y-%m-%dT%H:%M:%S")
            where_parts.append(f"{field} > '{iso}'")
        if extra_where:
            where_parts.append(extra_where)
        watermark = mapping.get("watermark_field")
        params: dict[str, Any] = {"$limit": self.page_size, "$offset": 0}
        if watermark:
            # Primera ingesta: registros más recientes primero; incremental: ascendente por watermark
            params["$order"] = f"{watermark} {'ASC' if since else 'DESC'}"
        else:
            params["$order"] = ":id"
        if where_parts:
            params["$where"] = " AND ".join(where_parts)
        max_pages = max_pages or self.max_pages
        rows: list[dict] = []
        for page in range(max_pages):
            params["$offset"] = page * self.page_size
            batch = self.query(dataset, params)
            if not batch:
                break
            rows.extend(batch)
            if len(batch) < self.page_size:
                break
        return rows


def _parse_date(value: str | None) -> datetime | None:
    if not value:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%d"):
        try:
            return datetime.strptime(value[: len(fmt) + 3], fmt)
        except (ValueError, TypeError):
            continue
    return None


def _to_float(value: Any) -> float | None:
    if value in (None, "", "No Definido"):
        return None
    try:
        return float(str(value).replace(",", "").replace("$", ""))
    except ValueError:
        return None


def _as_str(value) -> str | None:
    """Coacciona a texto: la fuente puede entregar dicts (p. ej. urlproceso como {'url': ...})."""
    if isinstance(value, dict):
        value = value.get("url") or value.get("href") or ""
    if value in (None, ""):
        return None
    return str(value)


def _clean(value) -> str | None:
    """Texto limpio: valores centinela de la fuente ('No Definido') se normalizan a None."""
    s = _as_str(value)
    if s and s.strip().lower() in ("no definido", "no definida", "n/d", "-"):
        return None
    return s


def normalize_row(source: str, row: dict) -> dict:
    """Normaliza una fila cruda de Socrata al modelo Opportunity."""
    m = FIELD_MAP[source]
    estado = (_as_str(row.get(m["estado"])) or "").strip()
    unspsc = _clean(row.get(m.get("unspsc_code", "")))
    if unspsc and not re.fullmatch(r"\d{2,10}", unspsc):
        unspsc = None  # la fuente a veces entrega valores no-UNSPSC (p. ej. 'V1.80111701')
    return {
        "source": source,
        "source_id": _as_str(row.get(m["source_id"])) or "",
        "entidad": _clean(row.get(m["entidad"])),
        "nit_entidad": _clean(row.get(m.get("nit_entidad", ""))),
        "departamento": _clean(row.get(m["departamento"])),
        "ciudad": _clean(row.get(m.get("ciudad", ""))),
        "objeto": _clean(row.get(m["objeto"])),
        "descripcion": _clean(row.get(m.get("descripcion", ""))),
        "modalidad": _clean(row.get(m["modalidad"])),
        "tipo_contrato": _clean(row.get(m.get("tipo_contrato", ""))),
        "unspsc_code": unspsc,
        "valor": _to_float(row.get(m["valor"])),
        "estado": estado,
        "fecha_publicacion": _parse_date(_as_str(row.get(m["fecha_publicacion"]))),
        "fecha_cierre": None,  # no expuesta por la fuente (ver docs/fuentes-secop.md)
        "url_oficial": _clean(row.get(m.get("url", ""))),
        "raw_json": row,
        "published_at": _parse_date(_as_str(row.get(m["fecha_publicacion"]))),
        "cancelled": estado.lower() in ESTADOS_CANCELADOS,
    }
