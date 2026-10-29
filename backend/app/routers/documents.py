"""Documentos privados: carga de pliegos/anexos (PDF, DOCX, XLSX) por oportunidad."""
import os
import re
import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import get_current_user
from app.db.models import Document, Opportunity, User
from app.db.session import get_db

router = APIRouter(prefix="/api/documents", tags=["documentos"])

ALLOWED = {".pdf", ".docx", ".xlsx"}
MAX_SIZE = 25 * 1024 * 1024  # 25 MB


def _secure_name(name: str) -> str:
    base = os.path.basename(name or "documento")
    base = re.sub(r"[^\w\-. áéíóúñÁÉÍÓÚÑ]", "_", base)
    return base[:200]


@router.post("")
async def upload_document(
    file: UploadFile = File(...),
    opportunity_id: int | None = Form(default=None),
    source_url: str = Form(default=""),
    document_type: str = Form(default="otro", pattern="^(pliego|anexo|rup|rut|camara_comercio|experiencia|otro)$"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED:
        raise HTTPException(415, f"Formato no soportado ({ext}). Permitidos: PDF, DOCX, XLSX.")
    if opportunity_id:
        opp = db.query(Opportunity).filter(Opportunity.id == opportunity_id).first()
        if not opp:
            raise HTTPException(404, "Oportunidad no encontrada")
    data = await file.read()
    if len(data) > MAX_SIZE:
        raise HTTPException(413, "El archivo supera el límite de 25 MB")

    settings = get_settings()
    safe = _secure_name(file.filename)
    rel_dir = os.path.join(settings.storage_dir, str(user.id))
    os.makedirs(rel_dir, exist_ok=True)
    rel_path = os.path.join(rel_dir, f"{uuid.uuid4().hex[:8]}-{safe}")
    with open(rel_path, "wb") as fh:
        fh.write(data)

    doc = Document(
        user_id=user.id, company_id=user.company_id, opportunity_id=opportunity_id, filename=safe,
        storage_path=rel_path, mime_type=file.content_type or "application/octet-stream",
        source_url=source_url, document_type=document_type,
    )
    db.add(doc)
    db.commit()
    return {"id": doc.id, "filename": doc.filename, "uploaded_at": doc.uploaded_at}


@router.get("")
def list_documents(opportunity_id: int | None = None, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    query = db.query(Document)
    query = (query.filter(or_(Document.user_id == user.id, Document.company_id == user.company_id))
             if user.company_id else query.filter(Document.user_id == user.id))
    if opportunity_id:
        query = query.filter(Document.opportunity_id == opportunity_id)
    return [{
        "id": d.id, "filename": d.filename, "opportunity_id": d.opportunity_id,
        "mime_type": d.mime_type, "source_url": d.source_url, "uploaded_at": d.uploaded_at,
        "document_type": d.document_type,
    } for d in query.order_by(Document.uploaded_at.desc()).limit(100).all()]
