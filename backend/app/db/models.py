"""Modelos de LicitaIA.

Notas de diseño:
- Los embeddings se almacenan como JSON (lista de floats). En producción con
  PostgreSQL se usa pgvector (ver docs/decisiones-arquitectonicas.md, ADR-004);
  la búsqueda vectorial de respaldo se resuelve en proceso con similitud coseno.
- Cada oportunidad conserva fecha de publicación (fuente), fecha de captura
  (nuestra ingesta) y última actualización, y su URL oficial original.
"""
from datetime import date, datetime, timezone

from sqlalchemy import (
    JSON, Boolean, Column, Date, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.db.session import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255), default="")
    is_active = Column(Boolean, default=True)
    role = Column(String(20), default="owner")              # owner | admin | analista | lector (Fase 5)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=True, index=True)
    email_verified = Column(Boolean, default=False)         # verificación de correo (Fase 5)
    verification_token = Column(String(64), nullable=True)
    created_at = Column(DateTime, default=utcnow)
    profile = relationship("CompanyProfile", back_populates="user", uselist=False)
    alert_prefs = relationship("AlertPrefs", back_populates="user", uselist=False)


class CompanyProfile(Base):
    """Perfil empresarial que alimenta al Agente 1 (Cazador de Oportunidades)."""
    __tablename__ = "company_profiles"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    nombre_comercial = Column(String(255), default="")
    razon_social = Column(String(255), default="")
    nit = Column(String(50), default="")
    sector = Column(String(120), default="")
    actividades = Column(Text, default="")
    productos_servicios = Column(Text, default="")
    keywords = Column(JSON, default=list)          # ["desarrollo de software", ...]
    unspsc_codes = Column(JSON, default=list)      # ["81101500", ...]
    departamentos = Column(JSON, default=list)     # ["Cundinamarca", ...]
    municipios = Column(JSON, default=list)
    presupuesto_min = Column(Float, nullable=True)
    presupuesto_max = Column(Float, nullable=True)
    modalidades = Column(JSON, default=list)
    experiencia = Column(Text, default="")
    capacidades = Column(Text, default="")
    certificaciones = Column(JSON, default=list)
    acepta_consorcios = Column(Boolean, default=False)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=True, index=True)
    learning_weights = Column(JSON, default=dict)           # retroalimentación del usuario (Fase 3)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)
    user = relationship("User", back_populates="profile")


class Opportunity(Base):
    """Oportunidad normalizada de SECOP (u otra fuente pública verificada)."""
    __tablename__ = "opportunities"
    __table_args__ = (UniqueConstraint("source", "source_id", name="uq_oportunidad_fuente"),)
    id = Column(Integer, primary_key=True)
    source = Column(String(40), default="secop2_procesos")  # secop2_procesos | secop2_contratos | secop1
    source_id = Column(String(255), index=True)             # id_del_proceso / id_contrato / etc.
    entidad = Column(String(400), index=True)
    nit_entidad = Column(String(50))
    departamento = Column(String(120), index=True)
    ciudad = Column(String(120))
    objeto = Column(Text)                                   # nombre del procedimiento / objeto del contrato
    descripcion = Column(Text)
    modalidad = Column(String(200), index=True)
    tipo_contrato = Column(String(200))
    unspsc_code = Column(String(50), index=True)            # código principal de categoría
    valor = Column(Float, nullable=True)                    # precio_base o valor_del_contrato (COP)
    estado = Column(String(120), index=True)
    fecha_publicacion = Column(DateTime, nullable=True, index=True)
    fecha_cierre = Column(DateTime, nullable=True)          # NULL si la fuente no la expone
    url_oficial = Column(String(800))                       # urlproceso (expediente original)
    raw_json = Column(JSON, default=dict)
    published_at = Column(DateTime)                         # fecha de publicación en la fuente
    captured_at = Column(DateTime, default=utcnow)          # fecha de ingesta
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)
    cancelled = Column(Boolean, default=False)              # proceso cancelado/retirado
    embedding = relationship("OpportunityEmbedding", back_populates="opportunity", uselist=False)


class OpportunityEmbedding(Base):
    __tablename__ = "opportunity_embeddings"
    id = Column(Integer, primary_key=True)
    opportunity_id = Column(Integer, ForeignKey("opportunities.id"), unique=True, nullable=False)
    model = Column(String(80), default="fake-hash-768")
    vector = Column(JSON)                                   # lista de floats (pgvector en producción)
    opportunity = relationship("Opportunity", back_populates="embedding")


class UserOpportunity(Base):
    """Relación usuario-oportunidad: score, razones y estados de triage."""
    __tablename__ = "user_opportunities"
    __table_args__ = (UniqueConstraint("user_id", "opportunity_id", name="uq_user_oportunidad"),)
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    opportunity_id = Column(Integer, ForeignKey("opportunities.id"), index=True, nullable=False)
    score = Column(Float, default=0)                        # 0-100 compatibilidad
    reasons = Column(JSON, default=list)                    # razones verificables [{factor, detalle, evidencia}]
    triage = Column(String(20), default="detectada")        # detectada|guardada|descartada|proyecto
    feedback = Column(Boolean, nullable=True)               # retroalimentación: útil / no útil (Fase 3)
    feedback_note = Column(String(500), default="")
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)
    opportunity = relationship("Opportunity")


class Document(Base):
    """Documento privado del usuario (pliego, anexo, etc.). Ruta en storage privado."""
    __tablename__ = "documents"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    opportunity_id = Column(Integer, ForeignKey("opportunities.id"), nullable=True, index=True)
    filename = Column(String(400))
    storage_path = Column(String(800))                      # compatible con S3 en producción
    mime_type = Column(String(120))
    source_url = Column(String(800), default="")            # si se adjuntó desde un enlace público
    document_type = Column(String(40), default="otro")      # pliego|anexo|rup|rut|camara_comercio|experiencia|otro
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=True, index=True)
    uploaded_at = Column(DateTime, default=utcnow)


class Analysis(Base):
    """Resultado del Agente 2 (Analista de Pliegos)."""
    __tablename__ = "analyses"
    id = Column(Integer, primary_key=True)
    opportunity_id = Column(Integer, ForeignKey("opportunities.id"), index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    resumen_ejecutivo = Column(JSON, default=dict)
    requisitos = Column(JSON, default=list)  # ver schemas: descripcion, tipo, estado, cita, pagina, confianza...
    estado = Column(String(30), default="borrador")         # borrador|revisado
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=True, index=True)
    created_at = Column(DateTime, default=utcnow)


class Viability(Base):
    """Resultado del Agente 3 (Evaluador de Viabilidad). Pesos configurables."""
    __tablename__ = "viability_results"
    id = Column(Integer, primary_key=True)
    opportunity_id = Column(Integer, ForeignKey("opportunities.id"), index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=True, index=True)
    global_score = Column(Float)
    factors = Column(JSON, default=dict)                    # {factor: {score, peso, detalle}}
    critical_failures = Column(JSON, default=list)
    fortalezas = Column(JSON, default=list)
    debilidades = Column(JSON, default=list)
    docs_faltantes = Column(JSON, default=list)
    riesgos = Column(JSON, default=list)
    costo_estimado = Column(JSON, default=dict)
    recommendation = Column(String(20))                     # participar|revisar|descartar
    weights_json = Column(JSON, default=dict)
    disclaimer = Column(String(500), default="")
    created_at = Column(DateTime, default=utcnow)


class OfferProject(Base):
    """Proyecto de propuesta del Agente 4 (Preparador de Ofertas)."""
    __tablename__ = "offer_projects"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=True, index=True)
    opportunity_id = Column(Integer, ForeignKey("opportunities.id"), index=True)
    name = Column(String(300))
    checklist = Column(JSON, default=list)                  # [{item, tipo, estado, responsable, evidencia}]
    matriz_cumplimiento = Column(JSON, default=list)
    borradores = Column(JSON, default=list)                 # [{tipo, contenido, version}]
    cronograma = Column(JSON, default=list)
    comentarios = Column(JSON, default=list)                # [{autor, texto, fecha}]
    status = Column(String(30), default="activo")           # activo|en_revision|aprobado|presentado|archivado
    approved_by = Column(String(255), default="")           # aprobación humana obligatoria
    version = Column(Integer, default=1)
    history = Column(JSON, default=list)                    # versiones guardadas
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)


class Alert(Base):
    """Alerta in-app. El resumen por correo es opcional (SMTP configurable)."""
    __tablename__ = "alerts"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    opportunity_id = Column(Integer, ForeignKey("opportunities.id"), nullable=True)
    tipo = Column(String(40))        # alta_compatibilidad|nueva|cierre_proximo|resumen_diario|documento
    title = Column(String(300))
    body = Column(Text, default="")
    email_sent = Column(Boolean, default=False)
    read_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=utcnow, index=True)


class AlertPrefs(Base):
    """Preferencias de alertas por usuario (digest, umbral, recordatorios de cierre)."""
    __tablename__ = "alert_prefs"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    email_enabled = Column(Boolean, default=False)
    high_score_threshold = Column(Integer, default=70)
    close_days = Column(JSON, default=list)                 # [10, 5, 1]
    digest_hour = Column(Integer, default=7)                # hora local America/Bogota
    user = relationship("User", back_populates="alert_prefs")


class SyncRun(Base):
    """Registro de cada ingesta de datos (auditoría y deduplicación)."""
    __tablename__ = "sync_runs"
    id = Column(Integer, primary_key=True)
    dataset = Column(String(60))                            # p6dx-8zbt | jbjy-vk9h | e985-4d7e
    started_at = Column(DateTime, default=utcnow)
    finished_at = Column(DateTime, nullable=True)
    pages = Column(Integer, default=0)
    upserted = Column(Integer, default=0)
    duplicates = Column(Integer, default=0)
    errors = Column(Integer, default=0)
    watermark = Column(DateTime, nullable=True)             # última fecha_de_ultima_publicaci procesada
    detail = Column(JSON, default=dict)


class Company(Base):
    """Empresa cliente (Fase 5): aislamiento de información por tenant."""
    __tablename__ = "companies"
    id = Column(Integer, primary_key=True)
    nombre = Column(String(255), nullable=False)
    nit = Column(String(50), default="")
    sector = Column(String(120), default="")
    owner_user_id = Column(Integer, ForeignKey("users.id"), index=True)
    created_at = Column(DateTime, default=utcnow)


class Subscription(Base):
    """Suscripción por empresa o usuario individual (Fase 5). Estado pendiente_pago
    hasta integrar la pasarela (requiere credenciales externas)."""
    __tablename__ = "subscriptions"
    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    plan = Column(String(30), default="explorador")          # explorador | profesional | corporativo
    status = Column(String(30), default="activa")            # activa | pendiente_pago | cancelada
    provider = Column(String(30), default="manual")          # manual | stripe
    external_id = Column(String(120), nullable=True, index=True)
    checkout_url = Column(String(1000), nullable=True)
    current_period_end = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=utcnow)


class UsageCounter(Base):
    """Contador mensual de consumo de IA por usuario (Fase 5: límites por suscripción)."""
    __tablename__ = "usage_counters"
    __table_args__ = (UniqueConstraint("user_id", "month", name="uq_uso_mensual"),)
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    month = Column(String(7))                               # YYYY-MM
    analyses = Column(Integer, default=0)


class AuditLog(Base):
    """Registro de auditoría de acciones (Fase 5)."""
    __tablename__ = "audit_logs"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=True, index=True)
    action = Column(String(60))                             # crear_empresa | triaje | analizar_pliego | ...
    entity = Column(String(60))
    entity_id = Column(Integer, nullable=True)
    detail = Column(JSON, default=dict)
    created_at = Column(DateTime, default=utcnow, index=True)


class ContactMessage(Base):
    """Mensajes del formulario de contacto público (Fase 5)."""
    __tablename__ = "contact_messages"
    id = Column(Integer, primary_key=True)
    nombre = Column(String(120))
    email = Column(String(255))
    mensaje = Column(Text)
    atendido = Column(Boolean, default=False)
    created_at = Column(DateTime, default=utcnow)
