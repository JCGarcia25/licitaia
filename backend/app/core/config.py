"""Configuración central de LicitaIA (12-factor, vía variables de entorno)."""
from functools import lru_cache

from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Todas las opciones sensibles llegan por entorno; nunca se codifican aquí."""

    app_name: str = "LicitaIA API"
    environment: str = "development"  # development | testing | production
    secret_key: str = "change-me-in-production"
    access_token_expire_minutes: int = 60 * 24
    cors_origins: str = "http://localhost:3000"
    debug_endpoint_token: str = "development25"
    debug_endpoint_enabled: bool = False

    # --- Persistencia ---
    database_url: str = "sqlite:///./licitaia.db"  # Postgres en docker-compose
    redis_url: str = "redis://localhost:6379/0"
    storage_dir: str = "./storage"  # documentos privados (S3-compatible en producción)

    # --- SECOP / Socrata (ver docs/fuentes-secop.md) ---
    secop_app_token: str = ""  # registrarlo en profile.socrata.com; header X-App-Token
    secop_domain: str = "www.datos.gov.co"
    # Página conservadora para que la ingesta manual responda detrás de Nginx;
    # las siguientes ejecuciones continúan con paginación incremental.
    secop_page_size: int = 200
    secop_max_pages_per_run: int = 25
    secop_dataset_procesos: str = "p6dx-8zbt"   # SECOP II - Procesos de Contratación
    secop_dataset_contratos: str = "jbjy-vk9h"  # SECOP II - Contratos Electrónicos
    secop_dataset_secop1: str = "e985-4d7e"     # SECOP I - 202002
    secop_sync_every_minutes: int = 30

    # --- Inteligencia artificial (proveedor configurable) ---
    embedding_provider: str = "fake"  # fake | openai
    embedding_dim: int = 768
    match_batch_size: int = Field(default=200, ge=1, le=1000)
    match_global_concurrency: int = Field(default=2, ge=1, le=16)
    match_lease_seconds: int = Field(default=300, ge=10, le=3600)
    match_max_retries: int = Field(default=3, ge=1, le=10)
    match_algorithm_version: str = "heuristic-v1-phase12"
    compatibility_v2_shadow_enabled: bool = False
    compatibility_v2_sample_limit: int = Field(default=20, ge=1, le=100)
    compatibility_v2_batch_size: int = Field(default=5, ge=1, le=20)
    compatibility_v2_lease_seconds: int = Field(default=120, ge=10, le=600)
    compatibility_v2_affinity_weights: tuple[float,float,float] = (.5,.3,.2)
    compatibility_v2_hierarchy_weights: tuple[float,float,float,float] = (1.,.7,.4,.15)
    compatibility_v2_min_coverage: float = Field(default=.25,ge=0,le=1)
    compatibility_v2_lexical_gate: float = Field(default=.20,ge=0,le=1)
    compatibility_v2_semantic_gate: float = Field(default=.45,ge=0,le=1)
    compatibility_v2_weights: dict[str, float] = Field(default_factory=lambda: {
        'affinity':25., 'experience':20., 'financial':15., 'technical':15.,
        'geography':10., 'amount':10., 'preferences':5.})
    evaluation_enabled: bool = False
    tvec_events_enabled: bool = False
    tvec_events_refresh_enabled: bool = False
    tvec_enabled: bool = False
    tvec_ingest_enabled: bool = False
    tvec_dev_targets: list[dict[str, str]] = Field(default_factory=list)
    tvec_api_origin: str = "http://localhost:8000"
    tvec_page_size: int = Field(default=100, ge=1, le=200)
    tvec_max_pages: int = Field(default=2, ge=1, le=5)
    tvec_lease_seconds: int = Field(default=180, ge=60, le=600)
    evaluation_api_origin: str = "http://localhost:8000"
    evaluation_dev_targets: list[dict[str,str]] = Field(default_factory=list)
    evaluation_max_universe: int = Field(default=500,ge=1,le=1000)
    evaluation_max_sample: int = Field(default=100,ge=1,le=200)
    evaluation_retention_days: int = Field(default=30,ge=1,le=90)
    evaluation_semantic_enabled: bool = False
    evaluation_external_max_calls: int = Field(default=0,ge=0,le=200)
    evaluation_embedding_usd_per_million_tokens: float|None = Field(default=None,ge=0)
    evaluation_max_cost_usd: float = Field(default=.25,gt=0,le=10)
    llm_provider: str = "heuristic"  # heuristic | openai
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"

    # --- Alertas (por defecto: in-app + correo, resumen diario) ---
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    alerts_from_email: str = "alertas@licitaia.local"
    alert_high_score: int = 70
    alert_close_days: str = "10,5,1"  # recordatorios D-10, D-5, D-1
    digest_hour: int = 7  # 07:00 America/Bogota
    timezone: str = "America/Bogota"

    # --- Fase 5: control comercial ---
    allow_demo_seed: bool = True    # ALLOW_DEMO_SEED=false: cero datos simulados (producción)
    billing_provider: str = "manual"  # manual | mercadopago | stripe
    stripe_api_key: str = ""
    mercadopago_access_token: str = ""
    mercadopago_public_key: str = ""
    mercadopago_webhook_secret: str = ""
    mercadopago_test_payer_email: str = ""
    mercadopago_sandbox: bool = True
    mercadopago_back_url: str = "https://licitaia.centralspike.com/app/plan"
    quota_free_analyses: int = 20   # límite mensual de IA del plan explorador
    quota_pro_analyses: int = 500   # límite mensual de IA del plan profesional
    contact_email: str = "jorge@zorbagames.com"
    # Dominio del frontend usado en enlaces de correo. Sobrescribir por
    # ambiente (STAGING/PRODUCCIÓN) con FRONTEND_URL.
    frontend_url: str = "https://dev.mysecop.co"
    # Enlace usado por las bienvenidas enviadas desde el Centro de control.
    # Se mantiene en STG para que las invitaciones de prueba no apunten a producción.
    admin_welcome_frontend_url: str = "https://stg.mysecop.co"
    # Protección contra picos: evita que el pool de workers/CPU se agote y que
    # el proxy termine mostrando 502 por upstream saturado.
    max_concurrent_requests: int = 32
    overload_wait_seconds: float = 0.05

    model_config = {"env_file": ".env", "extra": "ignore"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
