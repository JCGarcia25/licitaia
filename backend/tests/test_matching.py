"""Agente 1: puntaje de compatibilidad con razones verificables (sin invenciones)."""
from app.services.matcher import score_opportunity

PERFIL_TECH = {
    "sector": "Tecnologías de la información",
    "actividades": "Desarrollo de software y soporte de aplicaciones",
    "productos_servicios": "Sistemas de información, interoperabilidad, transformación digital",
    "keywords": ["desarrollo de software", "sistemas de información", "interoperabilidad", "modernización tecnológica"],
    "unspsc_codes": ["81101500"],
    "departamentos": ["Bogotá D.C.", "Cundinamarca", "Valle del Cauca"],
    "presupuesto_min": 100_000_000,
    "presupuesto_max": 5_000_000_000,
    "modalidades": ["Licitación Pública", "Contratación Directa"],
    "experiencia": "10 años en proyectos públicos",
    "capacidades": "30 ingenieros",
    "certificaciones": ["ISO 9001"],
}

OPP_TECH = {
    "objeto": "Adquisición de licencias y desarrollo de software para la modernización tecnológica y el sistema de información",
    "descripcion": "Modernización del sistema de información, interoperabilidad entre plataformas y mantenimiento de aplicaciones.",
    "modalidad": "Licitación Pública",
    "tipo_contrato": "Compra y Venta",
    "unspsc_code": "81101500",
    "departamento": "Bogotá D.C.",
    "valor": 2_000_000_000,
    "estado": "En proceso",
    "cancelled": False,
    "_vector": None,
}

OPP_FARMA = {
    "objeto": "Suministro de medicamentos e insumos hospitalarios",
    "descripcion": "Compra de insumos de bajo y alto costo.",
    "modalidad": "Licitación Pública",
    "tipo_contrato": "Compra y Venta",
    "unspsc_code": "51400000",
    "departamento": "Antioquia",
    "valor": 1_200_000_000,
    "estado": "En proceso",
    "cancelled": False,
    "_vector": None,
}


def test_alta_compatibilidad_con_razones():
    result = score_opportunity(PERFIL_TECH, OPP_TECH)
    assert 60 <= result.score <= 100
    factores = {r["factor"] for r in result.reasons}
    assert "Palabras clave" in factores
    assert "Ubicación" in factores
    assert "Cuantía" in factores
    # toda razón tiene evidencia citada (nada inventado)
    assert all(r.get("evidencia") for r in result.reasons)


def test_baja_compatibilidad_para_sector_distinto():
    result = score_opportunity(PERFIL_TECH, OPP_FARMA)
    assert result.score < 40


def test_proceso_cancelado_penalizado():
    result = score_opportunity(PERFIL_TECH, {**OPP_TECH, "cancelled": True, "estado": "Cancelado"})
    assert result.score < 30
    assert any(r["factor"] == "Riesgo" for r in result.reasons)


def test_rango_por_fuera_baja_puntaje():
    bajo = score_opportunity(PERFIL_TECH, {**OPP_TECH, "valor": 10_000_000})
    en_rango = score_opportunity(PERFIL_TECH, OPP_TECH)
    assert bajo.score < en_rango.score


def test_estado_cerrado_reducido():
    cerrado = score_opportunity(PERFIL_TECH, {**OPP_TECH, "estado": "Adjudicado"})
    abierto = score_opportunity(PERFIL_TECH, OPP_TECH)
    assert cerrado.score < abierto.score
