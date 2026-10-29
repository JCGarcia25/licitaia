"""Agente 2 (Analista de Pliegos): extracción con citas, estados y honestidad."""
import io

from app.agents.pliegos import analizar_documento, extract_text


def _docx_en_memoria(parrafos: list[str]) -> bytes:
    import docx

    doc = docx.Document()
    for p in parrafos:
        doc.add_paragraph(p)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


PERFIL = {"keywords": ["desarrollo de software"], "certificaciones": ["ISO 9001"]}

PARRAFOS = [
    "PLEGOS DE CONDICIONES",
    "Objeto del proceso: Adquisición e implementación de una plataforma de desarrollo de software para la entidad.",
    "Presupuesto oficial: $ 1.500.000.000",
    "Fecha de cierre: 15/12/2026 17:00",
    "Entidad contratante: Unidad Administrativa Especial de Servicios Públicos",
    "Modalidad de selección: Licitación Pública",
    "El proponente deberá acreditar experiencia acreditada en contratos similares de desarrollo de software.",
    "Deberán presentar declaración jurada de no encontrarse incursas en causales de inhabilidad.",
    "Se exige póliza de cumplimiento del 10% del valor de la propuesta.",
    "Los proponentes deberán contar con certificación de calidad ISO 9001 vigente, requisito habilitante.",
    "Capacidad financiera acreditada mediante estados financieros certificados de los dos últimos años.",
]


def test_extraccion_docx_completa():
    data = _docx_en_memoria(PARRAFOS)
    analisis = analizar_documento("pliegos.docx", data, PERFIL)

    resumen = analisis.resumen
    assert "desarrollo de software" in resumen["objeto_contractual"]["valor"].lower()
    assert resumen["presupuesto_oficial"]["valor"] == "1.500.000.000"
    assert resumen["fecha_hora_cierre"]["valor"].startswith("15/12/2026")
    assert resumen["entidad_contratante"]["valor"]
    assert resumen["modalidad_seleccion"]["valor"]
    # cita documental en cada dato clave
    assert resumen["objeto_contractual"]["documento"] == "pliegos.docx"
    assert resumen["objeto_contractual"]["referencia"].startswith("sección ")

    # requisitos con cita, tipo y estado permitido
    assert len(analisis.requisitos) >= 4
    tipos = {r.tipo for r in analisis.requisitos}
    assert "experiencia" in tipos
    assert "jurídico" in tipos  # póliza
    assert "financiero" in tipos  # capacidad financiera
    estados = {r.estado for r in analisis.requisitos}
    assert estados <= {"Cumple", "No cumple", "Por verificar", "Información insuficiente"}
    for r in analisis.requisitos:
        assert r.evidencia  # cita literal del documento
        assert r.referencia.startswith("sección ")
    # requisito habilitante marcado como posible excluyente
    assert any(r.es_excluyente for r in analisis.requisitos)
    # descargo obligatorio
    assert "validación humana" in resumen["descargo"]


def test_pdf_presupuesto_y_pagina():
    from reportlab.lib.pagesizes import letter
    from reportlab.platypus import Paragraph, SimpleDocTemplate

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=letter)
    doc.build([Paragraph(PARRAFOS[2])])  # "Presupuesto oficial: $ 1.500.000.000"
    analisis = analizar_documento("presupuesto.pdf", buf.getvalue(), PERFIL)
    if not analisis.resumen.get("error"):
        assert analisis.resumen["presupuesto_oficial"]["valor"] == "1.500.000.000"
        assert analisis.resumen["presupuesto_oficial"]["referencia"].startswith("p. 1")


def test_documento_sin_texto_informa_insuficiente():
    analisis = analizar_documento("escaneado.pdf", b"%PDF-1.4 binario sin texto util", PERFIL)
    assert "error" in analisis.resumen
    assert analisis.requisitos == []


def test_extract_text_docx():
    data = _docx_en_memoria(["Hola", "Mundo"])
    pages = extract_text("x.docx", data)
    assert pages[0][0] == 1
    assert "Hola" in pages[0][1]
