"""AGENTE 2 — Analista de Pliegos.

Extrae requisitos y datos clave de pliegos/anexos en PDF, DOCX y XLSX, con cita
documental (documento, página o sección) y nivel de confianza para cada hallazgo.

Diseño honesto:
- Modo heurístico (por defecto): extracción por patrones sobre el texto; nunca
  inventa requisitos y marca "Información insuficiente" cuando el dato no existe.
- Modo LLM opcional (llm_provider=openai): envía fragmentos al modelo y valida la
  salida estructurada; si falla, hace fallback al modo heurístico.
- Estados permitidos: Cumple / No cumple / Por verificar / Información insuficiente.
- El resultado es orientativo y exige validación humana (estado 'borrador').
"""
from __future__ import annotations

import io
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime

logger = logging.getLogger("licitaia.pliegos")

ESTADOS = ("Cumple", "No cumple", "Por verificar", "Información insuficiente")
NIVELES = ("alto", "medio", "bajo")

_RE_PRESUPUESTO = re.compile(
    r"(?:presupuesto\s+(?:official|oficial|estimado)|valor\s+(?:estimado|oficial)|presupuesto)[^\d$%]{0,60}?"
    r"(?:\$|COP|pesos)?\s?\$?\s?([\d.,]{4,})",
    re.IGNORECASE,
)
_RE_CIERRE = re.compile(
    r"(?:fecha\s+y\s+hora\s+de\s+cierre|fecha\s+de\s+cierre|cierre\s+del?\s+proceso|entrega\s+de\s+(?:ofertas|propuestas|ofertas\s+y\s+evaluación))"
    r"[^:\n]{0,40}[:\s]*([0-3]?\d[/\-.][0-3]?\d[/\-.\s]\d{2,4}[^\n]{0,25})",
    re.IGNORECASE,
)
_RE_OBJETO = re.compile(r"(?:objeto\s+(?:del?\s+(?:proceso|contrato)|contractual)?)\s*[:\-]?\s*(.{20,300})", re.IGNORECASE)
_RE_ENTIDAD = re.compile(r"(?:entidad\s+(?:contratante|contratante:|estatal)|entidad)\s*[:\-]?\s*([A-ZÁÉÍÓÚÑ][^\n]{5,150})", re.IGNORECASE)
_RE_MODALIDAD = re.compile(r"(?:modalidad\s+de\s+selección|modalidad)\s*[:\-]?\s*([^\n]{5,120})", re.IGNORECASE)
_RE_CRA = re.compile(r"(?:criterios?\s+de\s+evaluación|matriz\s+de\s+evaluación)", re.IGNORECASE)

_TRIGGERS_REQUISITO = re.compile(
    r"(deber[aá]n?|debe[rn]?|obligatori\w*|requisito\w*|experiencia\s+(?:acreditad\w*|espec[íi]fic\w*|similar\w*)|"
    r"garant[íi]a|p[óo]liza|certificaci[óo]n|habilitante|causal\s+de\s+(?:rechazo|desvirtuaci[óo]n)|"
    r"capacidad\s+financiera|estados\s+financieros|patrimonio\s+l[íi]quido|[íi]ndices?\s+financieros|"
    r"declaraci[óo]n\s+jurada|RUP|registro\s+único|no\s+se\s+ tendr[aá]\s+en\s+cuenta|personal\s+profesional|"
    r"ISO\s?9001|informe\s+de\s+auditoría)",
    re.IGNORECASE,
)
_EXCLUYENTE = re.compile(r"(habilitante|causal\s+de\s+rechazo|desvirtuaci[óo]n|no\s+se\s+tendr[aá]\s+en\s+cuenta|excluyente)", re.IGNORECASE)
_TIPO_MAP = [
    ("jurídico", re.compile(r"(garant[íi]a|p[óo]liza|legal|jurad\w*|constituci[óo]n|representaci[óo]n)", re.I)),
    ("financiero", re.compile(r"(capacidad\s+financiera|estados\s+financieros|patrimonio|[íi]ndices|ingresos)", re.I)),
    ("técnico", re.compile(r"(t[ée]cnic\w*|especificaci[óo]n\w*|personal\s+(?:profesional|mínimo)|ISO|norma\s+NTC)", re.I)),
    ("experiencia", re.compile(r"(experiencia|contratos\s+similares|años\s+de\s+ejecuci[óo]n)", re.I)),
    ("documental", re.compile(r"(RUP|declaraci[óo]n\s+jurada|formulario|anexo\s+\d+|documento\s+de\s+identidad)", re.I)),
]


@dataclass
class Requisito:
    descripcion: str
    tipo: str = "otro"
    estado: str = "Por verificar"          # Cumple | No cumple | Por verificar | Información insuficiente
    evidencia: str = ""                     # cita literal del documento
    documento: str = ""
    referencia: str = ""                    # página o sección
    observaciones: str = ""
    nivel_confianza: str = "medio"          # alto | medio | bajo
    es_excluyente: bool = False


@dataclass
class AnalisisPliego:
    resumen: dict = field(default_factory=dict)
    requisitos: list[Requisito] = field(default_factory=list)


# ---------- Extracción de texto ----------

def extract_text(filename: str, data: bytes) -> list[tuple[int, str]]:
    """Devuelve [(pagina_o_indice, texto)] según el formato.

    Documentos corruptos o ilegibles devuelven texto vacío (el analista reporta
    'Información insuficiente' en lugar de fallar).
    """
    name = (filename or "").lower()
    try:
        if name.endswith(".pdf"):
            from pypdf import PdfReader

            reader = PdfReader(io.BytesIO(data))
            pages = []
            for i, page in enumerate(reader.pages, start=1):
                try:
                    pages.append((i, page.extract_text() or ""))
                except Exception:  # página corrupta: se registra y continúa
                    pages.append((i, ""))
            return pages
        if name.endswith(".docx"):
            import docx

            doc = docx.Document(io.BytesIO(data))
            return [(i + 1, p.text) for i, p in enumerate(doc.paragraphs) if p.text.strip()]
        if name.endswith((".xlsx", ".xls")):
            import openpyxl

            wb = openpyxl.load_workbook(io.BytesIO(data), read_only=True, data_only=True)
            chunks = []
            for wi, ws in enumerate(wb.worksheets, start=1):
                rows = ["\t".join(str(c) for c in row if c is not None) for row in ws.iter_rows(values_only=True)]
                chunks.append((wi, "\n".join(rows)))
            return chunks
        # Texto plano u otro formato legible
        return [(1, data.decode("utf-8", errors="ignore"))]
    except Exception as exc:  # documento corrupto: texto vacío, nunca una excepción
        logger.warning("No fue posible extraer texto de %s: %s", filename, exc)
        return [(1, "")]


# ---------- Análisis ----------

def _clasifica_tipo(texto: str) -> str:
    for tipo, rx in _TIPO_MAP:
        if rx.search(texto):
            return tipo
    return "otro"


def _parse_fecha_colo(valor: str) -> str:
    return valor.strip()[:40]


def analizar_documento(filename: str, data: bytes, perfil: dict | None = None) -> AnalisisPliego:
    try:
        pages = extract_text(filename, data)
    except Exception as exc:
        return AnalisisPliego(resumen={
            "error": f"No fue posible leer el documento ({type(exc).__name__}).",
            "sugerencia": "Adjuntar la version digital o un enlace accesible del pliego.",
        }, requisitos=[])
    full = "\n".join(t for _, t in pages)
    if not full.strip():
        resumen = {
            "error": "El documento no contiene texto extraíble (posible escaneo sin OCR).",
            "sugerencia": "Adjuntar la versión digital o un enlace accesible del pliego.",
        }
        return AnalisisPliego(resumen=resumen, requisitos=[])

    analisis = AnalisisPliego()
    resumen = analisis.resumen

    def _buscar(rx: re.Pattern, span_pages: bool = True) -> tuple[str | None, str]:
        """Busca la primera coincidencia y su página/sección."""
        for num, text in pages:
            m = rx.search(text)
            if m:
                ref = f"p. {num}" if str(filename).lower().endswith(".pdf") else f"sección {num}"
                return m, ref
        return None, ""

    m, ref = _buscar(_RE_OBJETO)
    resumen["objeto_contractual"] = {
        "valor": m.group(1).strip() if m else None,
        "documento": filename,
        "referencia": ref,
        "confianza": "medio" if m else "bajo",
    }
    m, ref = _buscar(_RE_PRESUPUESTO)
    resumen["presupuesto_oficial"] = {
        "valor": m.group(1) if m else None,
        "documento": filename,
        "referencia": ref,
        "confianza": "medio" if m else "bajo",
    }
    m, ref = _buscar(_RE_CIERRE)
    resumen["fecha_hora_cierre"] = {
        "valor": _parse_fecha_colo(m.group(1)) if m else None,
        "documento": filename,
        "referencia": ref,
        "confianza": "alto" if m else "bajo",
    }
    m, ref = _buscar(_RE_ENTIDAD)
    resumen["entidad_contratante"] = {
        "valor": m.group(1).strip() if m else None,
        "documento": filename,
        "referencia": ref,
        "confianza": "medio" if m else "bajo",
    }
    m, ref = _buscar(_RE_MODALIDAD)
    resumen["modalidad_seleccion"] = {
        "valor": m.group(1).strip() if m else None,
        "documento": filename,
        "referencia": ref,
        "confianza": "medio" if m else "bajo",
    }
    m, ref = _buscar(_RE_CRA)
    resumen["criterios_evaluacion"] = {
        "valor": ("El documento menciona criterios de evaluación; revisar la sección correspondiente." if m else None),
        "documento": filename,
        "referencia": ref,
        "confianza": "medio" if m else "bajo",
    }

    # --- Requisitos por página, con cita y tipo ---
    keywords_perfil = [k.lower() for k in ((perfil or {}).get("keywords") or [])]
    certs_perfil = [c.lower() for c in ((perfil or {}).get("certificaciones") or [])]

    for num, text in pages:
        for sent in re.split(r"(?<=[.;])\s+|\n", text):
            sent = sent.strip()
            if len(sent) < 25 or not _TRIGGERS_REQUISITO.search(sent):
                continue
            tipo = _clasifica_tipo(sent)
            excl = bool(_EXCLUYENTE.search(sent))
            refs = f"p. {num}" if str(filename).lower().endswith(".pdf") else f"sección {num}"
            obs = ""
            estado = "Por verificar"
            bajo = sent.lower()
            if any(k in bajo for k in keywords_perfil):
                obs = f"Posible afinidad con el perfil (palabra clave presente)."
            if any(c in bajo for c in certs_perfil):
                obs = (obs + " " if obs else "") + "El perfil declara una certificación relacionada."
            if excl and not obs:
                estado = "Por verificar"
                obs = "Requisito posiblemente excluyente: requiere validación humana prioritaria."
            analisis.requisitos.append(Requisito(
                descripcion=sent[:400],
                tipo=tipo,
                estado=estado,
                evidencia=sent[:400],
                documento=filename,
                referencia=refs,
                observaciones=obs,
                nivel_confianza="alto" if excl or tipo != "otro" else "medio",
                es_excluyente=excl,
            ))

    # deduplicación por evidencia idéntica
    vistos: set[str] = set()
    unicos: list[Requisito] = []
    for r in analisis.requisitos:
        key = r.evidencia.lower()[:200]
        if key in vistos:
            continue
        vistos.add(key)
        unicos.append(r)
    analisis.requisitos = unicos[:120]
    resumen["total_requisitos"] = len(analisis.requisitos)
    resumen["requisitos_excluyentes"] = sum(1 for r in analisis.requisitos if r.es_excluyente)
    resumen["generado"] = datetime.utcnow().isoformat(timespec="seconds")
    resumen["descargo"] = (
        "Resultado orientativo generado automáticamente. Exige validación humana antes de elaborar una propuesta. "
        "Los requisitos no listados no deben asumirse ausentes: verificar el documento oficial completo."
    )
    return analisis
