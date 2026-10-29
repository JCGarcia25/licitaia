"""Fase 3 — Elegibilidad (jurídica, financiera y técnica) separada de la compatibilidad comercial.

La compatibilidad comercial (Agente 1) responde "qué tanto encaja el proceso con la empresa".
La elegibilidad responde "puede habilitarse la empresa para este proceso según la evidencia
disponible". Sin evidencia suficiente la dimensión queda en 'informacion_insuficiente':
nunca se declara elegibilidad sin soporte documental.
"""
from __future__ import annotations

DESCARGO = (
    "Evaluación orientativa de elegibilidad, separada de la compatibilidad comercial. "
    "No constituye concepto jurídico, garantía de habilitación ni asesoría legal; "
    "exige validación humana con los documentos oficiales del proceso."
)


def _dimension(perfil: dict, requisitos: list[dict], tipo: str, campos_perfil: list[str]) -> dict:
    rel = [r for r in requisitos if (r.get("tipo") or "") == tipo]
    if not rel:
        return {
            "score": None,
            "estado": "informacion_insuficiente",
            "razones": [f"Sin requisitos de tipo {tipo} en el análisis: no se declara elegibilidad sin evidencia."],
        }

    razones: list[str] = []
    score = 60.0
    afines = [r for r in rel if "afinidad" in (r.get("observaciones") or "").lower()]
    excluyentes = [r for r in rel if r.get("es_excluyente")]
    excl_sin_evid = [r for r in excluyentes if r.get("estado") in ("No cumple", "Información insuficiente")]
    no_cumplen = [r for r in rel if r.get("estado") == "No cumple"]

    if afines:
        score += 15
        razones.append(f"{len(afines)} requisito(s) afines al perfil declarado.")

    texto = " ".join(str(perfil.get(c) or "") for c in campos_perfil).lower()
    if texto.strip():
        relacionadas = sum(
            1 for r in rel
            if any(w in (r.get("descripcion") or "").lower() for w in texto.split() if len(w) > 4)
        )
        if relacionadas:
            score += 10
            razones.append(f"El perfil declara capacidades que se relacionan con {relacionadas} requisito(s) de {tipo}.")
    else:
        razones.append(f"El perfil no declara información para la dimensión {tipo}.")

    if excl_sin_evid:
        score -= 40
        razones.append(f"{len(excl_sin_evid)} requisito(s) excluyente(s) sin evidencia suficiente.")
    if no_cumplen:
        score -= 30
        razones.append(f"{len(no_cumplen)} requisito(s) en estado 'No cumple'.")

    score = max(0.0, min(100.0, score))
    if excl_sin_evid or no_cumplen:
        estado = "no_elegible" if score < 40 else "condicionada"
    elif score >= 70:
        estado = "elegible"
    else:
        estado = "condicionada"
    return {"score": round(score, 1), "estado": estado, "razones": razones or ["Sin hallazgos específicos en esta dimensión."]}


def evaluar_elegibilidad(perfil: dict, requisitos: list[dict]) -> dict:
    dims = {
        "juridica": _dimension(perfil, requisitos, "jurídico", ["certificaciones", "experiencia"]),
        "financiera": _dimension(perfil, requisitos, "financiero", ["capacidades", "experiencia"]),
        "tecnica": _dimension(perfil, requisitos, "técnico", ["productos_servicios", "actividades", "experiencia"]),
    }
    estados = [d["estado"] for d in dims.values()]
    if all(e == "informacion_insuficiente" for e in estados):
        resumen = "informacion_insuficiente"
    elif "no_elegible" in estados:
        resumen = "no_elegible"
    elif "condicionada" in estados or "informacion_insuficiente" in estados:
        resumen = "condicionada"
    else:
        resumen = "elegible"
    return {**dims, "resumen": resumen, "descargo": DESCARGO}
