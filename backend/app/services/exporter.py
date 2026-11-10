"""Exportador del Agente 4: checklist y matrices a DOCX / XLSX / PDF."""
from __future__ import annotations

import io
import re
from datetime import datetime


def _logo_png() -> bytes:
    """Genera el isotipo MS en PNG para incrustarlo en los reportes."""
    from PIL import Image, ImageDraw
    image = Image.new("RGBA", (256, 256), "#082f52")
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((0, 0, 255, 255), radius=48, fill="#082f52")
    # Construcción vectorial simple para que el isotipo se vea nítido incluso
    # cuando el servidor no tiene fuentes tipográficas instaladas.
    teal = "#35d0c0"
    draw.line((36, 184, 36, 74, 78, 124, 120, 74, 120, 184), fill=teal, width=16, joint="curve")
    draw.arc((126, 70, 220, 145), 190, 350, fill=teal, width=16)
    draw.arc((108, 110, 202, 188), 10, 170, fill=teal, width=16)
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

    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.shared import Inches, Pt, RGBColor
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn

    doc = docx.Document()
    section = doc.sections[0]
    section.top_margin = Inches(0.65)
    section.bottom_margin = Inches(0.65)
    section.left_margin = Inches(0.7)
    section.right_margin = Inches(0.7)
    normal = doc.styles["Normal"]
    normal.font.name = "Aptos"
    normal.font.size = Pt(9)
    normal.font.color.rgb = RGBColor(31, 49, 69)
    doc.add_picture(io.BytesIO(_logo_png()), width=docx.shared.Inches(0.55))
    doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.LEFT
    heading = doc.add_heading(titulo, level=0)
    heading.runs[0].font.color.rgb = RGBColor(8, 47, 82)
    heading.runs[0].font.size = Pt(22)
    meta = doc.add_paragraph(f"Generado por MySECOP  ·  {datetime.utcnow():%d/%m/%Y %H:%M} UTC")
    meta.runs[0].font.color.rgb = RGBColor(53, 208, 192)
    note = doc.add_paragraph("DOCUMENTO BORRADOR · Requiere revisión y aprobación humana antes de su presentación.")
    note.runs[0].bold = True
    note.runs[0].font.color.rgb = RGBColor(150, 92, 18)
    for nombre, filas in secciones:
        if not filas:
            continue
        h = doc.add_heading(nombre, level=1)
        h.runs[0].font.color.rgb = RGBColor(8, 47, 82)
        if len(filas[0]) > 1:
            column_count = max(len(fila) for fila in filas)
            table = doc.add_table(rows=len(filas), cols=column_count)
            table.style = "Table Grid"
            table.autofit = False
            widths = {2: [Inches(2.0), Inches(4.0)], 3: [Inches(1.6), Inches(1.2), Inches(3.2)], 4: [Inches(2.2), Inches(1.1), Inches(1.1), Inches(1.6)], 5: [Inches(0.3), Inches(2.2), Inches(1.1), Inches(1.1), Inches(1.3)]}.get(column_count)
            if widths:
                twips = [int(width.inches * 1440) for width in widths]
                tbl_pr = table._tbl.tblPr
                tbl_w = tbl_pr.find(qn("w:tblW"))
                if tbl_w is not None:
                    tbl_w.set(qn("w:type"), "dxa")
                    tbl_w.set(qn("w:w"), str(sum(twips)))
                grid = table._tbl.tblGrid
                for grid_col, width in zip(grid.gridCol_lst, twips):
                    grid_col.set(qn("w:w"), str(width))
                for row in table.rows:
                    for cell, width in zip(row.cells, twips):
                        cell.width = Inches(width / 1440)
                        tc_pr = cell._tc.get_or_add_tcPr()
                        tc_w = tc_pr.find(qn("w:tcW"))
                        if tc_w is None:
                            tc_w = OxmlElement("w:tcW")
                            tc_pr.append(tc_w)
                        tc_w.set(qn("w:type"), "dxa")
                        tc_w.set(qn("w:w"), str(width))
            for i, fila in enumerate(filas):
                for j, celda in enumerate(fila):
                    table.cell(i, j).text = str(celda)
                    for paragraph in table.cell(i, j).paragraphs:
                        paragraph.paragraph_format.space_after = Pt(2)
                        for run in paragraph.runs:
                            run.font.size = Pt(8)
                    if i == 0 or (len(fila) == 2 and j == 0):
                        shading = OxmlElement("w:shd")
                        shading.set(qn("w:fill"), "0B3B67")
                        table.cell(i, j)._tc.get_or_add_tcPr().append(shading)
                        for paragraph in table.cell(i, j).paragraphs:
                            for run in paragraph.runs:
                                run.font.bold = True
                                run.font.color.rgb = RGBColor(255, 255, 255)
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
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side

    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    teal = "35D0C0"
    navy = "0B3B67"
    soft = "EAF4F5"
    thin = Side(style="thin", color="C8D7E5")
    for nombre, filas in hojas.items():
        ws = wb.create_sheet(title=nombre[:31])
        if nombre == "Proceso":
            logo = XLImage(io.BytesIO(_logo_png()))
            logo.width, logo.height = 42, 42
            ws.add_image(logo, "D1")
        for fila in filas:
            ws.append(list(fila))
        ws.freeze_panes = "A2"
        ws.sheet_view.showGridLines = False
        for cell in ws[1]:
            cell.fill = PatternFill("solid", fgColor=navy)
            cell.font = Font(color="FFFFFF", bold=True)
            cell.alignment = Alignment(vertical="center")
        for row in ws.iter_rows():
            for cell in row:
                cell.border = Border(bottom=thin)
                cell.alignment = Alignment(vertical="top", wrap_text=True)
        if nombre == "Cronograma" and len(filas) > 1:
            ws["A1"].fill = PatternFill("solid", fgColor=teal)
            ws["A1"].font = Font(color="082F52", bold=True)
            ws["B1"].fill = PatternFill("solid", fgColor=soft)
            ws["B1"].font = Font(color="082F52", bold=True)
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
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=landscape(letter), title=titulo)
    styles = getSampleStyleSheet()
    header_style = ParagraphStyle("MySECOPHeader", parent=styles["Normal"], textColor=colors.white, fontName="Helvetica-Bold", fontSize=7, leading=9)
    body_style = ParagraphStyle("MySECOPBody", parent=styles["Normal"], textColor=colors.HexColor("#1F3145"), fontSize=7, leading=9)
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
            progress_row = filas[0] if "avance" in str(filas[0][0]).lower() else None
            table_rows = filas[1:] if progress_row else filas
            if progress_row:
                match = re.search(r"(\d{1,3})", " ".join(str(c) for c in progress_row))
                percent = max(0, min(100, int(match.group(1)))) if match else 0
                filled = int(round(percent / 10))
                bar = ["█" if i < filled else "░" for i in range(10)]
                progress = Table([[Paragraph("Avance total", body_style), Paragraph(f"{percent}%", body_style)], [Paragraph("".join(bar), ParagraphStyle("Progress", parent=body_style, textColor=colors.HexColor("#0B8F86"), fontSize=15, leading=15)), Paragraph("Tareas completadas / tareas totales", body_style)]], colWidths=[260, 210])
                progress.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#EAF4F5")), ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#35D0C0")), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LEFTPADDING", (0, 0), (-1, -1), 8), ("RIGHTPADDING", (0, 0), (-1, -1), 8), ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]))
                story.append(progress)
            data = [[Paragraph(str(c), header_style if row_index == 0 else body_style) for c in fila] for row_index, fila in enumerate(table_rows)]
            table = Table(data, repeatRows=1)
            table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0B3B67")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#B8C7D9")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("FONTSIZE", (0, 0), (-1, -1), 7),
                ("LEFTPADDING", (0, 0), (-1, -1), 7),
                ("RIGHTPADDING", (0, 0), (-1, -1), 7),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]))
            story.append(table)
        story.append(Spacer(1, 8))
    doc.build(story)
    return buf.getvalue()
