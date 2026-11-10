"""Exportador del Agente 4: checklist y matrices a DOCX / XLSX / PDF."""
from __future__ import annotations

import io
from datetime import datetime


def _logo_png() -> bytes:
    """Genera el isotipo MS en PNG para incrustarlo en los reportes."""
    from PIL import Image, ImageDraw
    image = Image.new("RGBA", (256, 256), "#082f52")
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((0, 0, 255, 255), radius=48, fill="#082f52")
    draw.text((42, 70), "MS", fill="#35d0c0", stroke_width=1)
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    return buf.getvalue()


def _formato_cop(valor: float | None) -> str:
    if valor is None:
        return "N/D"
    return f"$ {valor:,.0f} COP"


def export_docx(titulo: str, secciones: list[tuple[str, list[list[str]]]]) -> bytes:
    """Genera un .docx con secciones y tablas (carta, checklist, matriz)."""
    import docx

    doc = docx.Document()
    doc.add_picture(io.BytesIO(_logo_png()), width=docx.shared.Inches(0.55))
    doc.add_heading(titulo, level=0)
    doc.add_paragraph(f"Generado por MySECOP · {datetime.utcnow():%d/%m/%Y %H:%M} UTC · Documento borrador: requiere revisión y aprobación humana.")
    for nombre, filas in secciones:
        if not filas:
            continue
        doc.add_heading(nombre, level=1)
        if len(filas[0]) > 1:
            table = doc.add_table(rows=len(filas), cols=len(filas[0]))
            table.style = "Light Grid Accent 1"
            for i, fila in enumerate(filas):
                for j, celda in enumerate(fila):
                    table.cell(i, j).text = str(celda)
        else:
            for fila in filas:
                doc.add_paragraph(fila[0])
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def export_xlsx(hojas: dict[str, list[list]]) -> bytes:
    """Genera un .xlsx con hojas (checklist, matriz de cumplimiento)."""
    import openpyxl
    from openpyxl.drawing.image import Image as XLImage

    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    for nombre, filas in hojas.items():
        ws = wb.create_sheet(title=nombre[:31])
        if nombre == "Proceso":
            logo = XLImage(io.BytesIO(_logo_png()))
            logo.width, logo.height = 42, 42
            ws.add_image(logo, "D1")
        for fila in filas:
            ws.append(list(fila))
        for column_cells in ws.columns:
            width = max(len(str(c.value or "")) for c in column_cells)
            ws.column_dimensions[column_cells[0].column_letter].width = min(60, max(12, width + 2))
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def export_pdf_matriz(titulo: str, secciones: list[tuple[str, list[list[str]]]]) -> bytes:
    """Genera un PDF de la oferta con el estilo visual de MySECOP."""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter, landscape
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=landscape(letter), title=titulo)
    styles = getSampleStyleSheet()
    logo = Image(io.BytesIO(_logo_png()), width=42, height=42)
    story = [logo, Paragraph("MySECOP", styles["Heading2"]), Paragraph(titulo, styles["Title"]),
             Paragraph(f"Generado por MySECOP · {datetime.utcnow():%d/%m/%Y} · Borrador sujeto a revisión humana.", styles["Normal"]),
             Spacer(1, 12)]
    for nombre, filas in secciones:
        if not filas:
            continue
        story.append(Paragraph(nombre, styles["Heading2"]))
        if len(filas[0]) == 1:
            story.extend([Paragraph(str(fila[0]), styles["Normal"]) for fila in filas])
        else:
            data = [[Paragraph(str(c), styles["Normal"]) for c in fila] for fila in filas]
            table = Table(data, repeatRows=1)
            table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0B3B67")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#B8C7D9")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("FONTSIZE", (0, 0), (-1, -1), 7),
            ]))
            story.append(table)
        story.append(Spacer(1, 8))
    doc.build(story)
    return buf.getvalue()
