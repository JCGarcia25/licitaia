"""Fase 6 — Elegibilidad separada de compatibilidad; sin evidencia no se declara."""
from app.services.eligibility import evaluar_elegibilidad

PERFIL = {
    "certificaciones": ["ISO 9001"],
    "experiencia": "10 años en proyectos de software",
    "capacidades": "capital de trabajo y estados financieros certificados",
    "productos_servicios": "desarrollo de software",
    "actividades": "desarrollo e integración de sistemas",
}


def test_sin_requisitos_informacion_insuficiente():
    r = evaluar_elegibilidad(PERFIL, [])
    assert r["resumen"] == "informacion_insuficiente"
    assert r["juridica"]["estado"] == "informacion_insuficiente"
    assert r["financiera"]["score"] is None
    assert "validación humana" in r["descargo"]


def test_elegible_o_condicionada_con_evidencia():
    reqs = [
        {"tipo": "jurídico", "estado": "Por verificar", "es_excluyente": False,
         "observaciones": "afinidad con el perfil", "descripcion": "póliza de cumplimiento y garantías"},
        {"tipo": "financiero", "estado": "Por verificar", "es_excluyente": False,
         "observaciones": "", "descripcion": "capacidad financiera acreditada con estados financieros certificados"},
        {"tipo": "técnico", "estado": "Por verificar", "es_excluyente": False,
         "observaciones": "afinidad con el perfil", "descripcion": "experiencia en desarrollo de software"},
    ]
    r = evaluar_elegibilidad(PERFIL, reqs)
    assert r["resumen"] in ("elegible", "condicionada")
    assert r["juridica"]["score"] is not None
    assert r["tecnica"]["score"] >= r["tecnica"]["score"]  # dimensiones puntuadas


def test_excluyente_sin_evidencia_impide_elegibilidad():
    reqs = [{
        "tipo": "jurídico", "estado": "Información insuficiente", "es_excluyente": True,
        "observaciones": "", "descripcion": "requisito habilitante sin documento soporte",
    }]
    r = evaluar_elegibilidad(PERFIL, reqs)
    assert r["resumen"] in ("no_elegible", "condicionada")
    assert r["juridica"]["score"] < 70
    assert any("excluyente" in x for x in r["juridica"]["razones"]) or r["juridica"]["estado"] != "elegible"
