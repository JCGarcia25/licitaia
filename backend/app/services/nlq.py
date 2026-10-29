"""Buscador inteligente en lenguaje natural (dashboard).

Parser determinista en español para consultas como:
  "Busca procesos abiertos de desarrollo de software en Bogotá superiores a
   200 millones de pesos que cierren dentro de los próximos 20 días."

Devuelve filtros estructurados. Es una capa heurística auditable; puede
sustituirse por un LLM configurando llm_provider=openai (mismo contrato de salida).
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

DEPARTAMENTOS = [
    "Amazonas", "Antioquia", "Arauca", "Atlántico", "Bogotá D.C.", "Bolívar", "Boyacá",
    "Caldas", "Caquetá", "Casanare", "Cauca", "Cesar", "Chocó", "Córdoba", "Cundinamarca",
    "Guainía", "Guaviare", "Huila", "La Guajira", "Magdalena", "Meta", "Nariño",
    "Norte de Santander", "Putumayo", "Quindío", "Risaralda", "San Andrés y Providencia",
    "Santander", "Sucre", "Tolima", "Valle del Cauca", "Vaupés", "Vichada",
]

MODALIDADES = [
    "Licitación Pública", "Subasta", "Régimen Especial", "Contratación Directa",
    "Contratación Mínima Cuantía", "Selección Abreviada", "Selección Abreviada del Subastador",
    "Selección Abreviada de Menor Cuantía", "Acuerdo Marco de Precio", "Concurso de Méritos",
    "Selección Abreviada Servicios de Salud", "Contratación régimen especial",
]


def _norm(texto: str) -> str:
    """Minúsculas sin tildes para matching de alias."""
    return unicodedata.normalize("NFD", texto.lower()).encode("ascii", "ignore").decode()


_MODALIDAD_ALIAS = [
    ("licitacion publica", "Licitación Pública"),
    ("licitaciones publicas", "Licitación Pública"),
    ("seleccion abreviada", "Selección Abreviada"),
    ("contratacion directa", "Contratación Directa"),
    ("minima cuantia", "Contratación Mínima Cuantía"),
    ("concurso de meritos", "Concurso de Méritos"),
    ("regimen especial", "Régimen Especial"),
    ("subasta", "Subasta"),
    ("acuerdo marco", "Acuerdo Marco de Precio"),
]


@dataclass
class ParsedQuery:
    texto_libre: list[str] = field(default_factory=list)
    departamento: str | None = None
    modalidad: str | None = None
    valor_min: float | None = None
    valor_max: float | None = None
    estado_abierto: bool = False
    cierra_en_dias: int | None = None
    publicado_dias: int | None = None


def _parse_amount(num: str, unidad: str | None) -> float:
    value = float(num.replace(".", "").replace(",", ".")) if ("," in num and "." not in num) else float(num.replace(",", ""))
    unidad = (unidad or "").lower()
    if "mill" in unidad:
        return value * 1_000_000
    if "mil" in unidad and value < 10_000:
        return value * 1_000
    return value


def parse_query(q: str) -> ParsedQuery:
    p = ParsedQuery()
    text = (q or "").strip()
    low = text.lower()

    # departamentos: gana el alias más largo ("Valle del Cauca" antes que "Cauca")
    low_norm = _norm(text)
    candidatos = [d for d in DEPARTAMENTOS if d != "Bogotá D.C." and _norm(d) in low_norm]
    if candidatos:
        p.departamento = max(candidatos, key=len)
    elif "bogota" in low_norm:
        p.departamento = "Bogotá D.C."

    for alias, canonica in _MODALIDAD_ALIAS:
        if alias in _norm(text):
            p.modalidad = canonica
            break

    if re.search(r"\babiertos?\b|\ben proceso\b|\bactivos?\b", low):
        p.estado_abierto = True

    m = re.search(r"superiores? (?:a|de)\s\$?\s?([\d.,]+)\s*(millones?|mil)?", low)
    if m:
        p.valor_min = _parse_amount(m.group(1), m.group(2))
    m = re.search(r"inferiores? (?:a|de)\s\$?\s?([\d.,]+)\s*(millones?|mil)?", low)
    if m:
        p.valor_max = _parse_amount(m.group(1), m.group(2))
    m = re.search(r"(?:entre|entre \$?)\s\$?([\d.,]+)\s*(millones?|mil)? y\s\$?([\d.,]+)\s*(millones?|mil)?", low)
    if m:
        p.valor_min = _parse_amount(m.group(1), m.group(2))
        p.valor_max = _parse_amount(m.group(3), m.group(4))

    m = re.search(r"cierren? (?:dentro )?de los? próximos? (\d+) días?", low)
    if not m:
        m = re.search(r"cierren? en (\d+) días?", low)
    if m:
        p.cierra_en_dias = int(m.group(1))

    m = re.search(r"publicad[oa]s? (?:en )?los? últimos? (\d+) días?", low)
    if m:
        p.publicado_dias = int(m.group(1))

    # --- palabras libres: excluye lo ya capturado y términos estructurales ---
    resto = text
    stop = {_norm(w) for w in (
        "busca buscar procesos proceso licitaciones licitacion abiertos abiertas activos superiores "
        "inferiores entre millones mil pesos que cierren cierre dentro los proximos dias "
        "ultimos publicadas publicados estado valor cuantia menores mayores hasta desde despues cerca para de del en con"
    ).split()}
    if p.departamento:
        for w in p.departamento.lower().replace(".", "").split():
            stop.add(w)
    if p.modalidad:
        for w in _norm(p.modalidad).split():
            stop.add(w)
    if p.departamento:
        resto = resto.replace(p.departamento, " ")
        if p.departamento == "Bogotá D.C.":
            resto = resto.replace("Bogotá", " ").replace("Bogota", " ").replace("bogotá", " ")
    if p.modalidad:
        resto = resto.replace(p.modalidad, " ")
    palabras = [
        w for w in re.split(r"[^\wáéíóúñü]+", resto, flags=re.IGNORECASE)
        if len(w) > 3 and _norm(w) not in stop and not re.fullmatch(r"[\d.,]+", w)
    ]
    correcciones = {
        "aplicaicones": "aplicaciones",
        "aplicacion": "aplicaciones",
        "mobile": "moviles",
        "mobiles": "moviles",
        "móvil": "movil",
        "móviles": "moviles",
    }
    p.texto_libre = [correcciones.get(_norm(w), _norm(w)) for w in palabras[:8]]
    return p


def parsed_to_filters(p: ParsedQuery) -> dict:
    return {
        "q": " ".join(p.texto_libre) if p.texto_libre else None,
        "departamento": p.departamento,
        "modalidad": p.modalidad,
        "valor_min": p.valor_min,
        "valor_max": p.valor_max,
        "estado": "abiertos" if p.estado_abierto else None,
        "cierra_en_dias": p.cierra_en_dias,
        "publicado_dias": p.publicado_dias,
    }
