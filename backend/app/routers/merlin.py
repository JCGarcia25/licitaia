"""Merlín: guía conversacional acotada a MySECOP y contratación pública."""
import re
import unicodedata
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from app.core.security import get_current_user
from app.db.models import User

router = APIRouter(prefix="/api/merlin", tags=["merlin"])

class MerlinIn(BaseModel):
    message: str = Field(min_length=1, max_length=1200)

def norm(value: str) -> str:
    return unicodedata.normalize("NFD", value.lower()).encode("ascii", "ignore").decode()

def answer(message: str) -> str:
    q = norm(message)
    allowed = ("secop", "licit", "contrat", "pliego", "oferta", "propuesta", "modalidad", "publica", "entidad", "presupuesto", "cronograma", "alerta", "documento", "unspsc", "ley", "decreto", "seleccion", "subasta", "merito", "minima cuantia", "regimen especial")
    if not any(term in q for term in allowed):
        return "Estoy aquí para acompañarte con MySECOP y la contratación pública en Colombia. 🌿 Centrémonos en licitaciones: pregúntame por modalidades, SECOP, pliegos, requisitos, cronogramas u oportunidades."
    if "modalidad" in q or "subasta" in q or "minima cuantia" in q:
        return "En MySECOP puedes comparar modalidades como licitación pública, selección abreviada, mínima cuantía, contratación directa, concurso de méritos, subasta y régimen especial. La modalidad aplicable siempre debe confirmarse en los documentos oficiales del proceso."
    if "pliego" in q or "documento" in q:
        return "Los pliegos y anexos contienen requisitos jurídicos, técnicos, financieros y económicos. Cárgalos en el detalle de la oportunidad para analizarlos y revisa siempre el documento oficial publicado en SECOP antes de presentar una oferta."
    if "ley" in q or "decreto" in q or "legisl" in q:
        return "Puedo orientarte de forma general sobre contratación pública colombiana, pero no sustituyo la revisión jurídica. Para una respuesta precisa, indícame la modalidad y el tema concreto (por ejemplo: requisitos habilitantes, garantías, experiencia o evaluación)."
    return "Puedo ayudarte a interpretar esta oportunidad en MySECOP, revisar sus filtros, documentos, modalidad y cronograma. La fuente definitiva y vigente siempre es SECOP. ¿Qué parte deseas revisar?"

@router.post("/ask")
def ask(data: MerlinIn, user: User = Depends(get_current_user)):
    return {"answer": answer(data.message), "scope": "mysecop-contratacion-publica"}
