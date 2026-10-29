"""Buscador NLQ: la consulta de ejemplo de la sección 10 del enunciado."""
from app.services.nlq import parse_query, parsed_to_filters

Q = ("Busca procesos abiertos de desarrollo de software en Bogotá superiores a "
     "200 millones de pesos que cierren dentro de los próximos 20 días.")


def test_consulta_ejemplo_enunciado():
    p = parse_query(Q)
    assert p.departamento == "Bogotá D.C."
    assert p.estado_abierto is True
    assert p.valor_min == 200_000_000
    assert p.cierra_en_dias == 20
    libre = " ".join(p.texto_libre)
    assert "software" in libre


def test_filtros_estructurados():
    filtros = parsed_to_filters(parse_query(Q))
    assert filtros["departamento"] == "Bogotá D.C."
    assert filtros["valor_min"] == 200_000_000
    assert filtros["estado"] == "abiertos"
    assert filtros["cierra_en_dias"] == 20


def test_consulta_con_modalidad_y_rango():
    p = parse_query("Licitaciones públicas en Valle del Cauca entre 100 millones y 500 millones publicadas en los últimos 7 días")
    assert p.departamento == "Valle del Cauca"
    assert p.modalidad == "Licitación Pública"
    assert p.valor_min == 100_000_000
    assert p.valor_max == 500_000_000
    assert p.publicado_dias == 7


def test_consulta_sin_coincidencias_no_explota():
    p = parse_query("hola")
    assert p.departamento is None
    assert p.valor_min is None
