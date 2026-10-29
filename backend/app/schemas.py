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


class UserOut(BaseModel):
    id: int
    email: EmailStr
    full_name: str
    is_active: bool


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
