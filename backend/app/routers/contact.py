"""Fase 5 — Formulario de contacto público funcional."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models import ContactMessage
from app.db.session import get_db
from app.schemas import ContactIn
from app.services.notifier import send_email

router = APIRouter(prefix="/api", tags=["contacto"])


@router.post("/contact", status_code=201)
def contact(data: ContactIn, db: Session = Depends(get_db)):
    msg = ContactMessage(nombre=data.nombre, email=data.email, mensaje=data.mensaje)
    db.add(msg)
    db.commit()
    settings = get_settings()
    enviado = send_email(settings.contact_email, f"Contacto web: {data.nombre}",
                         f"De: {data.nombre} <{data.email}>\n\n{data.mensaje}")
    return {
        "id": msg.id,
        "recibido": True,
        "correo_entregado": enviado,
        "nota": None if enviado else "El mensaje quedó registrado; el envío por correo requiere SMTP configurado.",
    }
