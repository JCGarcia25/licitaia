"""Documentos privados: carga de pliegos/anexos (PDF, DOCX, XLSX) por oportunidad."""
import os
import re
import uuid
from urllib.parse import urlparse
import httpx

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import get_current_user
from app.db.models import Document, Opportunity, User
from app.db.session import get_db

router = APIRouter(prefix="/api/documents", tags=["documentos"])

ALLOWED = {".pdf", ".docx", ".xlsx"}
MAX_SIZE = 25 * 1024 * 1024  # 25 MB
PUBLIC_HOSTS = {"community.secop.gov.co", "www.datos.gov.co", "datos.gov.co"}


def _public_urls(value):
    found = []
    if isinstance(value, dict):
        for item in value.values(): found.extend(_public_urls(item))
    elif isinstance(value, list):
        for item in value: found.extend(_public_urls(item))
    elif isinstance(value, str) and value.startswith(("http://", "https://")):
        parsed = urlparse(value)
        if parsed.hostname in PUBLIC_HOSTS and os.path.splitext(parsed.path.lower())[1] in ALLOWED:
            found.append(value)
    return list(dict.fromkeys(found))


@router.post("/import-public/{opportunity_id}")
def import_public_documents(opportunity_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    opp = db.query(Opportunity).filter(Opportunity.id == opportunity_id).first()
    if not opp:
        raise HTTPException(404, "Oportunidad no encontrada")
    urls = _public_urls(opp.raw_json or {})
    settings = get_settings()
    directory = os.path.join(settings.storage_dir, str(user.id)); os.makedirs(directory, exist_ok=True)
    imported, skipped = [], []
    for url in urls[:20]:
        if db.query(Document).filter(Document.user_id == user.id, Document.source_url == url).first():
            skipped.append({"url": url, "motivo": "ya descargado"}); continue
        try:
            response = httpx.get(url, timeout=20, follow_redirects=True)
            response.raise_for_status()
            data = response.content
            if len(data) > MAX_SIZE: raise ValueError("supera 25 MB")
            ext = os.path.splitext(urlparse(str(response.url)).path)[1].lower()
            if ext not in ALLOWED: skipped.append({"url": url, "motivo": "formato no soportado"}); continue
            name = _secure_name(os.path.basename(urlparse(str(response.url)).path) or f"documento{ext}")
            path = os.path.join(directory, f"{uuid.uuid4().hex[:8]}-{name}")
            with open(path, "wb") as fh: fh.write(data)
            doc = Document(user_id=user.id, company_id=user.company_id, opportunity_id=opportunity_id, filename=name, storage_path=path, mime_type=response.headers.get("content-type", ""), source_url=url, document_type="pliego" if "pliego" in name.lower() else "anexo")
            db.add(doc); imported.append({"filename": name, "source_url": url})
        except Exception as exc:
            skipped.append({"url": url, "motivo": str(exc)[:160]})
    db.commit()
    return {"importados": imported, "omitidos": skipped, "nota": "Solo se descargan archivos públicos; documentos con sesión o captcha deben cargarse manualmente."}


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


@router.get("/{document_id}/content")
def document_content(document_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    doc = db.query(Document).filter(Document.id == document_id, Document.user_id == user.id).first()
    if not doc or not os.path.exists(doc.storage_path):
        raise HTTPException(404, "Documento no encontrado")
    return FileResponse(doc.storage_path, media_type=doc.mime_type or "application/octet-stream", filename=doc.filename)
