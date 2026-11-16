"""Filtros explícitos compartidos por resultados, dashboard y alertas."""
import unicodedata
from sqlalchemy import or_
from app.db.models import Opportunity

def _location_variants(value: str) -> list[str]:
    """Acepta nombres de SECOP con/sin tildes y abreviaturas habituales."""
    raw = value.strip()
    folded = "".join(c for c in unicodedata.normalize("NFD", raw) if unicodedata.category(c) != "Mn")
    variants = {raw, folded}
    key = folded.lower().replace(".", "").strip()
    if key in {"bogota", "bogota dc", "bogota d c"}:
        variants.update({"Bogotá", "Bogotá D.C.", "Bogota", "Bogota D.C."})
    return [v for v in variants if v]


def _location_condition(column, value: str):
    return or_(*[column.ilike(f"%{variant}%") for variant in _location_variants(value)])


def _text_variants(value: str) -> list[str]:
    folded = "".join(c for c in unicodedata.normalize("NFD", value) if unicodedata.category(c) != "Mn")
    return list({value, folded})


def _modality_variants(value: str) -> list[str]:
    """Reconoce el nombre corto del selector y la denominación SECOP."""
    variants = set(_text_variants(value))
    folded = "".join(c for c in unicodedata.normalize("NFD", value) if unicodedata.category(c) != "Mn").lower()
    if "minima cuantia" in folded:
        variants.update({"Mínima Cuantía", "Mínima cuantía", "Contratación Mínima Cuantía"})
    if "seleccion abreviada" in folded:
        variants.update({"Selección Abreviada", "Selección Abreviada de Menor Cuantía", "Selección Abreviada de Mayor Cuantía"})
    if "contratacion directa" in folded:
        variants.update({"Contratación Directa", "Contratación Directa (con ofertas)"})
    if "concurso de meritos" in folded:
        variants.update({"Concurso de Méritos", "Concurso de méritos abierto"})
    if "regimen especial" in folded:
        variants.update({"Régimen Especial", "Contratación régimen especial"})
    if "subasta" in folded:
        variants.update({"Subasta", "Subasta Inversa Electrónica"})
    return [v for v in variants if v]


def _modality_condition(value: str):
    return or_(*[Opportunity.modalidad.ilike(f"%{variant}%") for variant in _modality_variants(value)])


def profile_constraints(profile, departamento=None, municipio=None, modalidad=None, valor_min=None, valor_max=None):
    if profile is None:
        return []
    conditions = []
    for field, column, override, wildcard in (
        ('departamentos', Opportunity.departamento, departamento, 'toda'),
        ('municipios', Opportunity.ciudad, municipio, 'todo'),
        ('modalidades', Opportunity.modalidad, modalidad, 'toda')):
        values = [v for v in (getattr(profile, field) or []) if v and wildcard not in v.lower()]
        if not override and values:
            conditions.append(or_(*[(_modality_condition(v) if field == 'modalidades' else _location_condition(column, v)) for v in values]))
    if valor_min is None and profile.presupuesto_min is not None:
        conditions.append(Opportunity.valor >= profile.presupuesto_min)
    if valor_max is None and profile.presupuesto_max is not None:
        conditions.append(Opportunity.valor <= profile.presupuesto_max)
    return conditions
