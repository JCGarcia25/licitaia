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
    JSON, Boolean, Column, Date, DateTime, Float, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.db.session import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class LandingVisit(Base):
    __tablename__ = "landing_visits"
    id = Column(String(36), primary_key=True)
    started_at = Column(DateTime, nullable=False, index=True)
    last_seen_at = Column(DateTime, nullable=False, index=True)
    duration_seconds = Column(Integer, nullable=False, default=0)
    visible = Column(Boolean, nullable=False, default=True)


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
    password_reset_token = Column(String(64), nullable=True, index=True)
    password_reset_expires_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=utcnow)
    last_seen_at = Column(DateTime, nullable=True, index=True)
    current_path = Column(String(255), nullable=True)
    last_user_agent = Column(String(255), nullable=True)
    last_opportunity_search = Column(JSON, nullable=True)
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
    match_version = Column(String(64), nullable=True)
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
    match_version = Column(String(64), nullable=True)
    embedding = relationship("OpportunityEmbedding", back_populates="opportunity", uselist=False)


class OpportunityEmbedding(Base):
    __tablename__ = "opportunity_embeddings"
    id = Column(Integer, primary_key=True)
    opportunity_id = Column(Integer, ForeignKey("opportunities.id"), unique=True, nullable=False)
    model = Column(String(80), default="fake-hash-768")
    vector = Column(JSON)                                   # lista de floats (pgvector en producción)
    content_version = Column(String(64), nullable=True)
    opportunity = relationship("Opportunity", back_populates="embedding")


class UserOpportunity(Base):
    """Relación usuario-oportunidad: score, razones y estados de triage."""
    __tablename__ = "user_opportunities"
    __table_args__ = (UniqueConstraint("user_id", "opportunity_id", name="uq_user_oportunidad"),)
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    opportunity_id = Column(Integer, ForeignKey("opportunities.id"), index=True, nullable=False)
    score = Column(Float, nullable=True)                   # NULL = aún no puntuado
    reasons = Column(JSON, default=list)                    # razones verificables [{factor, detalle, evidencia}]
    match_state = Column(String(16), nullable=True)
    profile_version = Column(String(64), nullable=True)
    opportunity_version = Column(String(64), nullable=True)
    algorithm_version = Column(String(64), nullable=True)
    embedding_version = Column(String(64), nullable=True)
    scored_at = Column(DateTime, nullable=True)
    match_error = Column(String(80), nullable=True)
    failed_input_versions = Column(JSON(none_as_null=True), nullable=True)
    triage = Column(String(20), default="detectada")        # detectada|guardada|descartada|proyecto
    feedback = Column(Boolean, nullable=True)               # retroalimentación: útil / no útil (Fase 3)
    feedback_note = Column(String(500), default="")
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)
    opportunity = relationship("Opportunity")


class MatchJob(Base):
    __tablename__ = "match_jobs"
    id = Column(String(36), primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    # NULL libera la exclusión, conservando trabajos anteriores.
    active_key = Column(Integer, unique=True, nullable=True)
    state = Column(String(24), nullable=False, default="PENDING")
    profile_version = Column(String(64), nullable=True)
    algorithm_version = Column(String(64), nullable=False)
    embedding_version = Column(String(64), nullable=False)
    cursor_id = Column(Integer, nullable=False, default=0)
    max_id = Column(Integer, nullable=False, default=0)
    candidate_total = Column(Integer, nullable=False, default=0)
    excluded_total = Column(Integer, nullable=False, default=0)
    examined = Column(Integer, nullable=False, default=0)
    scored = Column(Integer, nullable=False, default=0)
    skipped = Column(Integer, nullable=False, default=0)
    failed = Column(Integer, nullable=False, default=0)
    batches = Column(Integer, nullable=False, default=0)
    retries = Column(Integer, nullable=False, default=0)
    lease_token = Column(String(36), nullable=True)
    lease_until = Column(DateTime, nullable=True)
    error = Column(String(80), nullable=True)
    created_at = Column(DateTime, nullable=False, default=utcnow)
    updated_at = Column(DateTime, nullable=False, default=utcnow)
    finished_at = Column(DateTime, nullable=True)
    last_batch_seconds = Column(Float, nullable=True)
    profile_vector = Column(JSON, nullable=True)
    processing_seconds = Column(Float, nullable=False, default=0)
    last_batch_queries = Column(Integer, nullable=True)
    peak_rss_bytes = Column(Float, nullable=True)


class MatchSlot(Base):
    __tablename__ = "match_slots"
    id = Column(Integer, primary_key=True)
    token = Column(String(36), nullable=True)
    lease_until = Column(DateTime, nullable=True)


class MatchScoreHistory(Base):
    __tablename__ = "match_score_history"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    opportunity_id = Column(Integer, ForeignKey("opportunities.id"), nullable=False)
    score = Column(Float, nullable=True)
    reasons = Column(JSON, nullable=True)
    versions = Column(JSON, nullable=True)
    recorded_at = Column(DateTime, nullable=False, default=utcnow)


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
    email_to = Column(String(255), nullable=True)
    high_score_threshold = Column(Integer, default=70)
    close_days = Column(JSON, default=list)                 # [10, 5, 1]
    digest_hour = Column(Integer, default=7)                # hora local America/Bogota
    user = relationship("User", back_populates="alert_prefs")


class SyncCursor(Base):
    """Progreso compartido por dataset; los resultados de corridas siguen por usuario."""
    __tablename__ = "sync_cursors"
    source = Column(String(60), primary_key=True)
    dataset_id = Column(String(40), nullable=False)
    cursor_time = Column(DateTime, nullable=True)
    cursor_id = Column(String(255), nullable=True)
    high_watermark = Column(DateTime, nullable=True)
    mode = Column(String(24), nullable=False, default="incremental")
    status = Column(String(24), nullable=False, default="idle")
    last_success_at = Column(DateTime, nullable=True)
    processed = Column(Integer, nullable=False, default=0)
    errors = Column(Integer, nullable=False, default=0)
    lease_token = Column(String(36), nullable=True)
    lease_until = Column(DateTime, nullable=True)


class SyncRun(Base):
    """Registro de cada ingesta de datos (auditoría y deduplicación)."""
    __tablename__ = "sync_runs"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    dataset = Column(String(60))                            # p6dx-8zbt | jbjy-vk9h | e985-4d7e
    started_at = Column(DateTime, default=utcnow)
    finished_at = Column(DateTime, nullable=True)
    pages = Column(Integer, default=0)
    upserted = Column(Integer, default=0)
    duplicates = Column(Integer, default=0)
    errors = Column(Integer, default=0)
    watermark = Column(DateTime, nullable=True)             # última fecha_de_ultima_publicaci procesada
    detail = Column(JSON, default=dict)

class SyncUsage(Base):
    __tablename__ = "sync_usage"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    month = Column(String(7), nullable=False, index=True)
    successful_runs = Column(Integer, default=0, nullable=False)
    __table_args__ = (UniqueConstraint("user_id", "month", name="uq_sync_usage_user_month"),)


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

# Registra la invalidación para todos los flujos ORM (API, ingesta y workers).
from app.services.match_versions import install_version_events
install_version_events()


class CompatibilityEvidenceProfile(Base):
    """Private, append-only progressive evidence snapshots. No organizational sharing."""
    __tablename__ = 'compatibility_evidence_profiles'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False, index=True)
    payload = Column(JSON, nullable=False)
    version = Column(String(64), nullable=False)
    created_at = Column(DateTime, default=utcnow, nullable=False)


class CompatibilityShadowRun(Base):
    __tablename__ = 'compatibility_shadow_runs'
    id = Column(String(36), primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False, index=True)
    state = Column(String(24), nullable=False, default='PENDING')
    snapshot = Column(JSON, nullable=False)
    model_version = Column(String(64), nullable=False)
    cursor = Column(Integer, nullable=False, default=0)
    lease_token = Column(String(36), nullable=True)
    lease_until = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    finished_at = Column(DateTime, nullable=True)
    error = Column(String(120), nullable=True)


class CompatibilityShadowResult(Base):
    __tablename__ = 'compatibility_shadow_results'
    __table_args__ = (UniqueConstraint('run_id','opportunity_id',name='uq_compatibility_shadow_result'),)
    id = Column(Integer, primary_key=True)
    run_id = Column(String(36), ForeignKey('compatibility_shadow_runs.id'), nullable=False, index=True)
    opportunity_id = Column(Integer, ForeignKey('opportunities.id'), nullable=False)
    legacy_score = Column(Float, nullable=True)
    legacy_versions = Column(JSON, nullable=False)
    result = Column(JSON, nullable=False)
    duration_ms = Column(Float, nullable=False)
    created_at = Column(DateTime, default=utcnow, nullable=False)


class EvaluationEnvironmentIdentity(Base):
    __tablename__ = 'evaluation_environment_identities'
    id = Column(String(36), primary_key=True)
    fingerprint = Column(String(64), nullable=False, unique=True)
    purpose = Column(String(32), nullable=False)
    created_at = Column(DateTime, default=utcnow, nullable=False)


class EvaluationCampaign(Base):
    __tablename__ = 'evaluation_campaigns'
    id = Column(String(36), primary_key=True)
    owner_user_id = Column(Integer, ForeignKey('users.id'), nullable=False, index=True)
    name = Column(String(160), nullable=False)
    state = Column(String(24), nullable=False, default='PREPARING')
    data_scope = Column(String(24), nullable=False)
    config = Column(JSON, nullable=False)
    universe = Column(JSON, nullable=False)
    selection = Column(JSON, nullable=True)
    cursor = Column(Integer, nullable=False, default=0)
    lease_token = Column(String(36), nullable=True)
    lease_until = Column(DateTime, nullable=True)
    semantic_disabled_at = Column(DateTime, nullable=True)
    external_calls = Column(Integer, nullable=False, default=0)
    reserved_cost = Column(Float, nullable=False, default=0.)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    closed_at = Column(DateTime, nullable=True)


class EvaluationSample(Base):
    __tablename__ = 'evaluation_samples'
    __table_args__ = (UniqueConstraint('campaign_id','pair_key',name='uq_evaluation_sample_pair'),)
    id = Column(String(36), primary_key=True)
    campaign_id = Column(String(36), ForeignKey('evaluation_campaigns.id'), nullable=False, index=True)
    pair_key = Column(String(64), nullable=False)
    process_key = Column(String(255), nullable=False)
    snapshot = Column(JSON, nullable=False)
    stratum = Column(JSON, nullable=False)
    inclusion_probability = Column(Float, nullable=False)
    split = Column(String(20), nullable=False)


class EvaluationAssignment(Base):
    __tablename__ = 'evaluation_assignments'
    __table_args__ = (UniqueConstraint('sample_id','evaluator_user_id',name='uq_evaluation_assignment'),)
    id = Column(String(36), primary_key=True)
    sample_id = Column(String(36), ForeignKey('evaluation_samples.id'), nullable=False, index=True)
    evaluator_user_id = Column(Integer, ForeignKey('users.id'), nullable=False, index=True)
    kind = Column(String(20), nullable=False)
    created_at = Column(DateTime, default=utcnow, nullable=False)


class EvaluationJudgment(Base):
    __tablename__ = 'evaluation_judgments'
    id = Column(String(36), primary_key=True)
    assignment_id = Column(String(36), ForeignKey('evaluation_assignments.id'), nullable=False, unique=True)
    payload = Column(JSON, nullable=False)
    criteria_version = Column(String(64), nullable=False)
    created_at = Column(DateTime, default=utcnow, nullable=False)


class EvaluationAdjudication(Base):
    __tablename__ = 'evaluation_adjudications'
    id = Column(String(36), primary_key=True)
    sample_id = Column(String(36), ForeignKey('evaluation_samples.id'), nullable=False, unique=True)
    assignment_id = Column(String(36), ForeignKey('evaluation_assignments.id'), nullable=False, unique=True)
    payload = Column(JSON, nullable=False)
    created_at = Column(DateTime, default=utcnow, nullable=False)


class EvaluationReport(Base):
    __tablename__ = 'evaluation_reports'
    id = Column(String(36), primary_key=True)
    campaign_id = Column(String(36), ForeignKey('evaluation_campaigns.id'), nullable=False, unique=True)
    payload = Column(JSON, nullable=False)
    version = Column(String(64), nullable=False)
    created_at = Column(DateTime, default=utcnow, nullable=False)


class EvaluationEmbedding(Base):
    __tablename__ = 'evaluation_embeddings'
    __table_args__ = (UniqueConstraint('owner_user_id','cache_key',name='uq_evaluation_embedding_private'),)
    id = Column(String(36), primary_key=True)
    owner_user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    campaign_id = Column(String(36), ForeignKey('evaluation_campaigns.id'), nullable=False, index=True)
    cache_key = Column(String(64), nullable=False)
    text_hash = Column(String(64), nullable=False)
    model = Column(String(80), nullable=False)
    dimensions = Column(Integer, nullable=False)
    version = Column(String(64), nullable=False)
    state = Column(String(24), nullable=False)
    vector = Column(JSON, nullable=True)
    usage_tokens = Column(Integer, nullable=True)
    estimated_cost = Column(Float, nullable=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    expires_at = Column(DateTime, nullable=False)


class EvaluationExposure(Base):
    __tablename__ = 'evaluation_exposures'
    __table_args__ = (UniqueConstraint('user_id','pair_key',name='uq_evaluation_exposure'),)
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    pair_key = Column(String(64), nullable=False)
    created_at = Column(DateTime, default=utcnow, nullable=False)


class EvaluationDataGrant(Base):
    __tablename__ = 'evaluation_data_grants'
    id = Column(String(36), primary_key=True)
    owner_user_id = Column(Integer, ForeignKey('users.id'), nullable=False, index=True)
    administrator_user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    run_id = Column(String(36), ForeignKey('compatibility_shadow_runs.id'), nullable=False)
    state = Column(String(16), nullable=False)
    payload = Column(JSON, nullable=False)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    expires_at = Column(DateTime, nullable=False)


# Evaluation evidence/report history is append-only through the ORM as well as API.
from sqlalchemy import event, inspect as sa_inspect
from sqlalchemy.orm import Session as OrmSession

@event.listens_for(OrmSession,'before_flush')
def _evaluation_history_immutable(session,context,instances):
    for obj in session.dirty:
        if isinstance(obj,(EvaluationJudgment,EvaluationAdjudication,EvaluationReport,EvaluationExposure)) and session.is_modified(obj):
            raise ValueError('Sealed evaluation history cannot be modified')
        if isinstance(obj,EvaluationDataGrant) and any(sa_inspect(obj).attrs[k].history.has_changes() for k in ('owner_user_id','administrator_user_id','run_id','payload','expires_at')):
            raise ValueError('Authorization provenance immutable; revoke and create a new grant')


class TvecPurchaseOrder(Base):
    """Public purchase history. Intentionally no relationship to Opportunity."""
    __tablename__ = 'tvec_purchase_orders'
    id = Column(Integer, primary_key=True)
    official_id = Column(String(255), nullable=False, unique=True)
    source_row_id = Column(String(255), nullable=False)
    buyer = Column(Text)
    buyer_nit = Column(String(100))
    supplier = Column(Text)
    supplier_nit = Column(String(100))
    description = Column(Text)
    instrument = Column(Text, index=True)
    category = Column(Text)
    department = Column(String(255), index=True)
    city = Column(String(255))
    amount = Column(Numeric(30, 6))
    currency = Column(String(3))
    issued_at = Column(DateTime, index=True)
    expires_at = Column(DateTime)
    initial_request_at = Column(DateTime)
    status = Column(String(255), index=True)
    official_url = Column(Text)
    raw_json = Column(JSON, nullable=False)
    version = Column(String(64), nullable=False)
    seen_cycle = Column(String(36), nullable=False, index=True)
    synced_at = Column(DateTime, nullable=False)


class TvecOrderRevision(Base):
    __tablename__ = 'tvec_order_revisions'
    id = Column(Integer, primary_key=True)
    order_id = Column(Integer, ForeignKey('tvec_purchase_orders.id'), nullable=False, index=True)
    version = Column(String(64), nullable=False)
    payload = Column(JSON, nullable=False)
    recorded_at = Column(DateTime, nullable=False)


class TvecSourceMetadata(Base):
    __tablename__ = 'tvec_source_metadata'
    dataset_id = Column(String(20), primary_key=True)
    schema_hash = Column(String(64), nullable=False)
    columns = Column(JSON, nullable=False)
    source_updated_at = Column(DateTime)
    checked_at = Column(DateTime, nullable=False)
    declared_frequency = Column(String(80))
    source_count = Column(Integer)


class TvecSyncState(Base):
    __tablename__ = 'tvec_sync_states'
    dataset_id = Column(String(20), primary_key=True)
    cursor_id = Column(String(255))
    cycle_id = Column(String(36), nullable=False)
    cycle_rows = Column(Integer, nullable=False, default=0)
    completed_cycles = Column(Integer, nullable=False, default=0)
    source_generation = Column(String(64))
    lease_token = Column(String(36))
    lease_until = Column(DateTime)
    status = Column(String(24), nullable=False, default='IDLE')
    last_complete_at = Column(DateTime)
    error_count = Column(Integer, nullable=False, default=0)


class TvecSyncRun(Base):
    __tablename__ = 'tvec_sync_runs'
    id = Column(String(36), primary_key=True)
    state = Column(String(24), nullable=False)
    max_pages = Column(Integer, nullable=False)
    pages = Column(Integer, nullable=False, default=0)
    processed = Column(Integer, nullable=False, default=0)
    inserted = Column(Integer, nullable=False, default=0)
    updated = Column(Integer, nullable=False, default=0)
    unchanged = Column(Integer, nullable=False, default=0)
    error_type = Column(String(80))
    created_at = Column(DateTime, nullable=False)
    finished_at = Column(DateTime)


class TvecQuotationEvent(Base):
    __tablename__ = 'tvec_quotation_events'
    official_id = Column(String(32), primary_key=True)
    title = Column(Text, nullable=False)
    buyer = Column(Text, nullable=False)
    instrument = Column(Text, nullable=False)
    status = Column(String(80), nullable=False)
    kind = Column(String(12), nullable=False)
    kind_evidence = Column(String(64), nullable=False)
    opens_at = Column(DateTime, nullable=False)
    closes_at = Column(DateTime, nullable=False, index=True)
    official_url = Column(Text, nullable=False)
    detail_verified = Column(Boolean, nullable=False, default=False)
    checked_at = Column(DateTime, nullable=False)
    snapshot_id = Column(String(36), nullable=False, index=True)


class TvecQuotationSnapshot(Base):
    __tablename__ = 'tvec_quotation_snapshots'
    source = Column(String(32), primary_key=True)
    scan_progress = Column(JSON, nullable=True)
    published_snapshot = Column(String(36))
    checked_at = Column(DateTime)
    status = Column(String(16), nullable=False, default='IDLE')
    lease_token = Column(String(36))
    lease_until = Column(DateTime)
    scanned_pages = Column(Integer, nullable=False, default=0)
    scanned_rows = Column(Integer, nullable=False, default=0)
    excluded_rfi = Column(Integer, nullable=False, default=0)
    excluded_unknown = Column(Integer, nullable=False, default=0)
    error_type = Column(String(80))
