"""Bounded literal extraction. Documentary observations remain unverified."""
from hashlib import sha256
from io import BytesIO
from pathlib import Path
import re
from zipfile import ZipFile
from app.agents.pliegos import extract_text

PATTERNS = {
    'contract_type':r'tipo\s+de\s+contrato\s*:\s*([^\n]{2,200})',
    'object':r'objeto(?:\s+contractual)?\s*:\s*([^\n]{3,500})',
    'amount_literal':r'(?:cuantía|cuantia|valor)\s*:\s*([^\n]{2,100})',
    'dates_literal':r'(?:fecha|plazo)\s*:\s*([^\n]{2,120})',
    'contracting_entity':r'contratante\s*:\s*([^\n]{2,200})',
    'activities':r'actividades\s*:\s*([^\n]{2,500})',
    'certifications':r'certificaci(?:ón|on|ones)\s*:\s*([^\n]{2,200})',
}


def extract(document, storage_root):
    path=Path(document.storage_path).resolve(); root=Path(storage_root).resolve()
    if not path.is_relative_to(root) or path.stat().st_size>25*1024*1024:
        raise ValueError('Document outside private storage or too large')
    data=path.read_bytes()
    if path.suffix.lower() in {'.docx','.xlsx'}:
        with ZipFile(BytesIO(data)) as archive:
            if sum(i.file_size for i in archive.infolist())>40*1024*1024:
                raise ValueError('Expanded document too large')
    if path.suffix.lower()=='.pdf':
        from pypdf import PdfReader
        reader=PdfReader(BytesIO(data))
        if len(reader.pages)>50:raise ValueError('Diagnostic limited to 50 pages')
    pages=extract_text(document.filename,data)[:50]
    observations=[]; budget=20000
    for reference,text in pages:
        text=text[:budget]; budget-=len(text)
        for key,pattern in PATTERNS.items():
            for match in list(re.finditer(pattern,text,re.I))[:5]:
                observations.append({'key':key,'value':match.group(1).strip(),'level':'DOCUMENTED','source_ref':{'document_id':document.id,'file_hash':sha256(data).hexdigest(),'reference':reference,'quote':match.group(0)},'warning':'Extracción literal; vigencia, atribución y suficiencia sin verificar'})
        if budget<=0:break
    return {'observations':observations,'document_id':document.id,'file_hash':sha256(data).hexdigest(),'limited':True,'review_status':'PENDING_VERIFICATION'}
