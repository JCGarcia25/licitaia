"""Agente 3: pesos configurables, recomendación y descargo de no-adjudicación."""
from app.agents.viability import DISCLAIMER, evaluar_viabilidad

PERFIL = {
    "sector": "TI",
    "actividades": "Desarrollo de software",
    "productos_servicios": "Sistemas de información",
    "keywords": ["desarrollo de software"],
    "unspsc_codes": ["81101500"],
    "departamentos": ["Bogotá D.C."],
    "presupuesto_min": 100000000,
    "presupuesto_max": 5000000000,
    "modalidades": ["Licitación Pública"],
    "experiencia": "10 años en modernización tecnológica y desarrollo de software",
    "capacidades": "30 ingenieros, capacidad financiera, estados financieros",
    "certificaciones": ["ISO 9001"],
}

REQUISITOS = [
    {"descripcion": "Experiencia en desarrollo de software", "tipo": "experiencia", "estado": "Por verificar",
     "evidencia": "x", "referencia": "p. 3", "es_excluyente": False, "observaciones": "afinidad con el perfil"},
    {"descripcion": "Declaración jurada", "tipo": "documental", "estado": "Por verificar",
     "evidencia": "x", "referencia": "p. 4", "es_excluyente": False, "observaciones": ""},
    {"descripcion": "Capacidad financiera con estados financieros", "tipo": "financiero", "estado": "Por verificar",
     "evidencia": "x", "referencia": "p. 5", "es_excluyente": False, "observaciones": ""},
]


def test_evaluacion_basica():
    r = evaluar_viabilidad(PERFIL, {}, REQUISITOS, dias_hasta_cierre=20)
    assert 0 <= r.global_score <= 100
    assert r.recommendation in ("participar", "revisar", "descartar")
    assert set(r.factors.keys()) == {"compatibilidad_tecnica", "experiencia_acreditable",
                                     "capacidad_financiera", "viabilidad_operativa", "riesgos"}
    suma_pesos = sum(f["peso"] for f in r.factors.values())
    assert abs(suma_pesos - 100) < 0.5  # pesos normalizados a 100
    assert "adjudicación" in DISCLAIMER.lower()


def test_pesos_configurables():
    base = evaluar_viabilidad(PERFIL, {}, REQUISITOS)
    custom = evaluar_viabilidad(PERFIL, {}, REQUISITOS, pesos={"riesgos": 40})
    assert custom.factors["riesgos"]["peso"] > base.factors["riesgos"]["peso"]


def test_requisito_excluyente_sin_evidencia_baja_recomendacion():
    reqs = REQUISITOS + [{
        "descripcion": "Requisito habilitante sin evidencia", "tipo": "jurídico",
        "estado": "Información insuficiente", "evidencia": "x", "referencia": "p. 9",
        "es_excluyente": True, "observaciones": "",
    }]
    r = evaluar_viabilidad(PERFIL, {}, reqs)
    assert r.critical_failures
    assert r.recommendation in ("revisar", "descartar")
    assert any("excluyente" in x.lower() for x in r.riesgos)


def test_costo_estimado_solo_con_informacion():
    sin_info = evaluar_viabilidad(PERFIL, {}, REQUISITOS[:1])
    con_info = evaluar_viabilidad(PERFIL, {}, REQUISITOS)
    assert not sin_info.costo_estimado or "horas_estimadas" not in sin_info.costo_estimado or sin_info.costo_estimado == {}
    assert con_info.costo_estimado.get("horas_estimadas", 0) > 0
    assert con_info.costo_estimado.get("estimado_cop", 0) > 0


def test_sin_analisis_previo_igual_evalua():
    r = evaluar_viabilidad(PERFIL, {}, [])
    assert 0 <= r.global_score <= 100
    assert any("sin análisis" in x.lower() or "No hay análisis" in x for x in r.riesgos)
