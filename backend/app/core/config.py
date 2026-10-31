"""Configuración central de LicitaIA (12-factor, vía variables de entorno)."""
from functools import lru_cache

from pydantic_settings import BaseSettings


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
    mercadopago_back_url: str = "https://licitaia.centralspike.com/app/plan"
    quota_free_analyses: int = 20   # límite mensual de IA del plan explorador
    quota_pro_analyses: int = 500   # límite mensual de IA del plan profesional
    contact_email: str = "contacto@licitaia.local"
    # Protección contra picos: evita que el pool de workers/CPU se agote y que
    # el proxy termine mostrando 502 por upstream saturado.
    max_concurrent_requests: int = 32
    overload_wait_seconds: float = 0.05

    model_config = {"env_file": ".env", "extra": "ignore"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
