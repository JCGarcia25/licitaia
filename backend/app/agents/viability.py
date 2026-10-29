"""AGENTE 3 — Evaluador de Viabilidad.

Responde: "¿Vale la pena que esta empresa participe en esta licitación?"

- Modelo configurable (pesos por factor; valores iniciales 30/25/20/15/10).
- Puntaje global 0-100 y recomendación: participar | revisar | descartar.
- Descargo obligatorio: el puntaje evalúa viabilidad de participación con pesos
  propios de LicitaIA; NO es una probabilidad de adjudicación ni un criterio
  oficial de ninguna entidad.
"""
from __future__ import annotations

from dataclasses import dataclass, field

PESOS_INICIALES = {
    "compatibilidad_tecnica": 30,
    "experiencia_acreditable": 25,
    "capacidad_financiera": 20,
    "viabilidad_operativa": 15,
    "riesgos": 10,
}
PESOS_DESCRIPCION = {
    "compatibilidad_tecnica": "Afinidad del objeto y requisitos técnicos con el perfil",
    "experiencia_acreditable": "Experiencia declarada en el perfil vs. experiencia exigida",
    "capacidad_financiera": "Capacidad financiera declarada vs. exigencias económicas",
    "viabilidad_operativa": "Capacidades operativas y tiempo disponible hasta el cierre",
    "riesgos": "Riesgos y restricciones identificados en el análisis",
}
DISCLAIMER = (
    "Puntaje de viabilidad de participación calculado con pesos configurables de LicitaIA "
    "(no oficiales). NO constituye una probabilidad de adjudicación, ni un criterio de evaluación "
    "de ninguna entidad contratante, ni una recomendación legal. Requiere validación humana."
)


@dataclass
class ResultadoViabilidad:
    global_score: float
    factors: dict = field(default_factory=dict)
    critical_failures: list = field(default_factory=list)
    fortalezas: list = field(default_factory=list)
    debilidades: list = field(default_factory=list)
    docs_faltantes: list = field(default_factory=list)
    riesgos: list = field(default_factory=list)
    costo_estimado: dict = field(default_factory=dict)
    recommendation: str = "revisar"


def _score_compatibilidad(perfil: dict, resumen: dict, requisitos: list[dict]) -> float:
    if not requisitos:
        return 50.0  # sin requisitos analizados: neutro, se refleja en el detalle
    con_afinidad = sum(1 for r in requisitos if "afinidad" in (r.get("observaciones") or "").lower())
    excluyentes = sum(1 for r in requisitos if r.get("es_excluyente"))
    base = 40 + 60 * (con_afinidad / max(1, len(requisitos))) - 15 * min(2, excluyentes)
    return max(0.0, min(100.0, base))


def _score_experiencia(perfil: dict, requisitos: list[dict]) -> float:
    exp = (perfil.get("experiencia") or "").strip()
    if not exp:
        return 25.0
    exp_low = exp.lower()
    hits = sum(1 for r in requisitos if r.get("tipo") == "experiencia" and any(
        w in exp_low for w in (r.get("descripcion") or "").lower().split() if len(w) > 4
    ))
    return max(30.0, min(95.0, 55 + 12 * hits))


def _score_financiera(perfil: dict, requisitos: list[dict]) -> float:
    caps = ((perfil.get("capacidades") or "") + " " + (perfil.get("experiencia") or "")).lower()
    if not caps.strip():
        return 45.0
    financieros = [r for r in requisitos if r.get("tipo") == "financiero"]
    menciona = any(k in caps for k in ("financier", "patrimonio", "estados financieros", "capital", "aval"))
    base = 70 if menciona else 45
    if financieros and not menciona:
        base -= 20
    return max(0.0, min(100.0, base))


def _score_operativa(perfil: dict, resumen: dict, dias_hasta_cierre: int | None) -> float:
    caps = (perfil.get("capacidades") or "").strip()
    base = 60 if caps else 40
    if dias_hasta_cierre is not None:
        if dias_hasta_cierre <= 5:
            base -= 30
        elif dias_hasta_cierre <= 10:
            base -= 15
        elif dias_hasta_cierre >= 30:
            base += 10
    return max(0.0, min(100.0, base))


def _score_riesgos(requisitos: list[dict]) -> float:
    if not requisitos:
        return 60.0
    excluyentes = [r for r in requisitos if r.get("es_excluyente")]
    insuficientes = sum(1 for r in requisitos if r.get("estado") == "Información insuficiente")
    return max(0.0, min(100.0, 85 - 20 * len(excluyentes) - 5 * min(4, insuficientes)))


def evaluar_viabilidad(
    perfil: dict,
    resumen: dict,
    requisitos: list[dict],
    pesos: dict | None = None,
    dias_hasta_cierre: int | None = None,
) -> ResultadoViabilidad:
    pesos = {**PESOS_INICIALES, **(pesos or {})}
    # normalizar pesos a 100
    total = sum(pesos.values()) or 1
    pesos_n = {k: 100.0 * v / total for k, v in pesos.items()}

    scores = {
        "compatibilidad_tecnica": _score_compatibilidad(perfil, resumen, requisitos),
        "experiencia_acreditable": _score_experiencia(perfil, requisitos),
        "capacidad_financiera": _score_financiera(perfil, requisitos),
        "viabilidad_operativa": _score_operativa(perfil, resumen, dias_hasta_cierre),
        "riesgos": _score_riesgos(requisitos),
    }
    global_score = round(sum(scores[k] * pesos_n[k] for k in scores) / 100.0, 1)

    critical_failures = [
        r for r in requisitos
        if r.get("es_excluyente") and r.get("estado") in ("No cumple", "Información insuficiente")
    ]
    fortalezas = [f"{PESOS_DESCRIPCION[k]}: {scores[k]:.0f}/100" for k in sorted(scores, key=scores.get, reverse=True)[:2]]
    debilidades = [f"{PESOS_DESCRIPCION[k]}: {scores[k]:.0f}/100" for k in sorted(scores, key=scores.get)[:2]]
    docs_faltantes = [
        r["referencia"] + " — " + (r.get("descripcion") or "")[:120]
        for r in requisitos
        if r.get("tipo") == "documental" and r.get("estado") in ("Por verificar", "Información insuficiente")
    ][:8]
    riesgos = [
        "Existe al menos un requisito posiblemente excluyente sin evidencia suficiente." if critical_failures else None,
        "El análisis se basa en documentos adjuntos; verificar pliegos oficiales completos." if requisitos else
        "No hay análisis de pliegos: la evaluación usa solo el perfil y los datos del proceso.",
    ]
    riesgos = [r for r in riesgos if r]

    if critical_failures:
        recommendation = "revisar" if global_score >= 45 else "descartar"
    elif global_score >= 70:
        recommendation = "participar"
    elif global_score >= 45:
        recommendation = "revisar"
    else:
        recommendation = "descartar"

    # Costo estimado de preparar la oferta (solo si hay información suficiente)
    costo: dict = {}
    if len(requisitos) >= 3:
        docs = sum(1 for r in requisitos if r.get("tipo") == "documental")
        horas = 8 + 3 * docs + 2 * len([r for r in requisitos if r.get("tipo") == "técnico"])
        costo = {
            "horas_estimadas": horas,
            "tarifa_por_hora_cop": 60000,
            "estimado_cop": horas * 60000,
            "nota": "Estimación configurable y orientativa de esfuerzo interno; no incluye garantías ni costos del contrato.",
        }

    return ResultadoViabilidad(
        global_score=global_score,
        factors={k: {"score": round(v, 1), "peso": round(pesos_n[k], 1), "detalle": PESOS_DESCRIPCION[k]} for k, v in scores.items()},
        critical_failures=[(r.get("descripcion") or "")[:250] for r in critical_failures][:10],
        fortalezas=fortalezas,
        debilidades=debilidades,
        docs_faltantes=docs_faltantes,
        riesgos=riesgos,
        costo_estimado=costo,
        recommendation=recommendation,
    )
