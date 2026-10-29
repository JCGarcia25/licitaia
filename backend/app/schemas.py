"""Esquemas Pydantic (contrato OpenAPI de la API)."""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field


class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(default="", max_length=255)


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    verification_token: Optional[str] = None  # solo cuando SMTP no está configurado (dev)


class UserOut(BaseModel):
    id: int
    email: EmailStr
    full_name: str
    is_active: bool
    role: str = "owner"
    company_id: Optional[int] = None
    email_verified: bool = False
    model_config = {"from_attributes": True}


class ProfileIn(BaseModel):
    nombre_comercial: str = ""
    razon_social: str = ""
    nit: str = ""
    sector: str = ""
    actividades: str = ""
    productos_servicios: str = ""
    keywords: list[str] = []
    unspsc_codes: list[str] = []
    departamentos: list[str] = []
    municipios: list[str] = []
    presupuesto_min: Optional[float] = None
    presupuesto_max: Optional[float] = None
    modalidades: list[str] = []
    experiencia: str = ""
    capacidades: str = ""
    certificaciones: list[str] = []
    acepta_consorcios: bool = False
    learning_weights: dict[str, float] = {}  # Fase 3: pesos de retroalimentación del usuario


class ProfileOut(ProfileIn):
    id: int
    updated_at: Optional[datetime] = None


class TriajeIn(BaseModel):
    triage: str = Field(pattern="^(guardada|descartada|proyecto|detectada)$")


class SyncIn(BaseModel):
    source: str = Field(default="secop2_procesos", pattern="^(secop2_procesos|secop2_contratos|secop1)$")
    max_pages: int = Field(default=5, ge=1, le=50)
    extra_where: Optional[str] = None  # cláusula SoQL adicional ($where), opcional


class AlertPrefsIn(BaseModel):
    email_enabled: bool = False
    high_score_threshold: int = Field(default=70, ge=0, le=100)
    close_days: list[int] = [10, 5, 1]
    digest_hour: int = Field(default=7, ge=0, le=23)


class ViabilityIn(BaseModel):
    pesos: Optional[dict[str, float]] = None


class ChecklistItemIn(BaseModel):
    index: int
    estado: Optional[str] = Field(default=None, pattern="^(pendiente|en_progreso|listo)$")
    evidencia: Optional[str] = None


class BorradorIn(BaseModel):
    tipo: str = Field(pattern="^(carta_presentacion|matriz_cumplimiento|respuestas_tecnicas)$")
    contenido: str = ""


class OfferStatusIn(BaseModel):
    status: str = Field(pattern="^(activo|en_revision|aprobado|presentado|archivado)$")
    approved_by: Optional[str] = None


class CommentIn(BaseModel):
    texto: str = Field(min_length=1, max_length=2000)


# --- Fase 3/5: retroalimentación, verificación, empresa, suscripción, contacto ---
class FeedbackIn(BaseModel):
    util: bool
    nota: str = Field(default="", max_length=500)


class VerifyEmailIn(BaseModel):
    token: str = Field(min_length=8, max_length=64)


class CompanyIn(BaseModel):
    nombre: str = Field(min_length=2, max_length=200)
    nit: str = ""
    sector: str = ""


class MemberIn(BaseModel):
    email: EmailStr
    role: str = Field(pattern="^(admin|analista|lector)$")


class MemberRoleIn(BaseModel):
    role: str = Field(pattern="^(owner|admin|analista|lector)$")


class SubscribeIn(BaseModel):
    plan: str = Field(pattern="^(explorador|profesional|corporativo)$")


class ContactIn(BaseModel):
    nombre: str = Field(min_length=2, max_length=120)
    email: EmailStr
    mensaje: str = Field(min_length=10, max_length=4000)
