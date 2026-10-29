"""AGENTE 1 — Cazador de Oportunidades.

Combina búsqueda léxica (palabras clave, UNSPSC, ubicación, cuantía, modalidad)
con búsqueda semántica (similitud coseno entre el perfil y el objeto contractual)
para reconocer equivalencias aunque se usen términos distintos (p. ej. "modernización
tecnológica" ↔ "desarrollo de software").

Salida: puntaje de compatibilidad 0-100 + razones verificables que citan campos
reales del registro SECOP (nunca razones inventadas).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

from app.services.embeddings import cosine_similarity, embed, lexical_overlap

logger = logging.getLogger("licitaia.matcher")

PESOS = {
    "semantico": 30,
    "keywords_unspsc": 30,
    "ubicacion": 15,
    "cuantia": 15,
    "modalidad": 10,
}

ESTADOS_ABIERTOS = {"en proceso", "convocatoria", "publicada", "abierto", "activo", "en adquisición"}


@dataclass
class MatchResult:
    score: float
    reasons: list[dict] = field(default_factory=list)


def _estado_abierto(estado: str | None) -> bool:
    return (estado or "").strip().lower() in ESTADOS_ABIERTOS


def score_opportunity(profile: dict, opp: dict, profile_vector: list[float] | None = None) -> MatchResult:
    """Puntúa una oportunidad normalizada contra el perfil empresarial.

    `profile` y `opp` son dicts con los campos del modelo (compatibles con SQLAlchemy).
    """
    reasons: list[dict] = []
    score = 0.0

    keywords = [k.lower() for k in (profile.get("keywords") or [])]
    unspsc = set(profile.get("unspsc_codes") or [])
    depts = {d.lower() for d in (profile.get("departamentos") or [])}
    modalidades = {m.lower() for m in (profile.get("modalidades") or [])}
    pmin, pmax = profile.get("presupuesto_min"), profile.get("presupuesto_max")

    texto_objeto = " ".join(
        str(opp.get(k) or "") for k in ("objeto", "descripcion", "modalidad", "tipo_contrato")
    )
    sem_text = f"{opp.get('objeto') or ''} {opp.get('descripcion') or ''}"

    # --- Búsqueda semántica ---
    pvec = profile_vector if profile_vector is not None else embed(_profile_text(profile))
    ovec = opp.get("_vector") or embed(sem_text)
    sem = cosine_similarity(pvec, ovec)
    if sem >= 0.30:
        parcial = round(PESOS["semantico"] * min(1.0, sem / 0.6), 1)
        score += parcial
        reasons.append({
            "factor": "Coincidencia semántica",
            "detalle": f"El objeto contractual es semánticamente afín al perfil (similitud {sem:.2f}).",
            "evidencia": (opp.get("objeto") or "")[:220],
        })

    # --- Palabras clave y UNSPSC (verificables en el registro) ---
    hits = lexical_overlap(" ".join(keywords), texto_objeto)
    kw_parcial = 0.0
    if keywords and hits:
        kw_parcial = PESOS["keywords_unspsc"] * min(1.0, len(hits) / max(1, min(3, len(keywords))))
        score += kw_parcial
        reasons.append({
            "factor": "Palabras clave",
            "detalle": f"Coincidencias léxicas del perfil en el objeto: {', '.join(hits)}.",
            "evidencia": (opp.get("objeto") or "")[:220],
        })
    opp_unspsc = str(opp.get("unspsc_code") or "")
    if opp_unspsc and opp_unspsc in unspsc:
        score += PESOS["keywords_unspsc"] * 0.5
        reasons.append({
            "factor": "Código UNSPSC",
            "detalle": f"La categoría principal del proceso ({opp_unspsc}) está en el perfil.",
            "evidencia": f"codigo_principal_de_categoria={opp_unspsc}",
        })
    if not kw_parcial and not (opp_unspsc and opp_unspsc in unspsc):
        pass  # sin coincidencia léxica: no se suman puntos ni se inventan razones

    # --- Ubicación ---
    dept = (opp.get("departamento") or "").strip().lower()
    if dept and dept in depts:
        score += PESOS["ubicacion"]
        reasons.append({
            "factor": "Ubicación",
            "detalle": f"El proceso pertenece a un departamento de interés ({opp.get('departamento')}).",
            "evidencia": f"departamento_entidad={opp.get('departamento')}",
        })

    # --- Cuantía dentro del rango ---
    valor = opp.get("valor")
    if valor and pmin and pmax:
        if pmin <= valor <= pmax:
            score += PESOS["cuantia"]
            reasons.append({
                "factor": "Cuantía",
                "detalle": f"El valor estimado está dentro del rango del perfil ({pmin:,.0f} – {pmax:,.0f} COP).",
                "evidencia": f"precio_base={valor:,.0f} COP",
            })
        elif valor < pmin * 0.5:
            score -= 5
    elif valor:
        parcial = PESOS["cuantia"] * 0.5
        score += parcial

    # --- Modalidad preferida ---
    mod = (opp.get("modalidad") or "").strip().lower()
    if mod and mod in modalidades:
        score += PESOS["modalidad"]
        reasons.append({
            "factor": "Modalidad",
            "detalle": f"La modalidad ({opp.get('modalidad')}) es de las preferidas por la empresa.",
            "evidencia": f"modalidad_de_contratacion={opp.get('modalidad')}",
        })

    # --- Estado y penalizaciones ---
    if opp.get("cancelled"):
        score -= 90  # proceso cancelado/retirado: fuera de consideración práctica
        reasons.append({
            "factor": "Riesgo",
            "detalle": "El proceso aparece cancelado o retirado en la fuente.",
            "evidencia": f"estado={opp.get('estado')}",
        })
    elif not _estado_abierto(opp.get("estado")):
        score *= 0.6  # procesos cerrados/adjudicados bajan de prioridad

    final = max(0.0, min(100.0, score))
    if not reasons:
        reasons.append({
            "factor": "Sin coincidencias fuertes",
            "detalle": "No se detectaron coincidencias suficientes con el perfil.",
            "evidencia": (opp.get("objeto") or "")[:220],
        })
    return MatchResult(score=round(final, 1), reasons=reasons)


def _profile_text(profile: dict) -> str:
    partes = [
        profile.get("sector") or "",
        profile.get("actividades") or "",
        profile.get("productos_servicios") or "",
        " ".join(profile.get("keywords") or []),
        profile.get("experiencia") or "",
        profile.get("capacidades") or "",
    ]
    return " ".join(str(p) for p in partes)
