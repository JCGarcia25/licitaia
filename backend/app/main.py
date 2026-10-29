"""Aplicación FastAPI de LicitaIA (API REST documentada con OpenAPI en /docs)."""
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.routers import agents, alerts, auth, billing, companies, contact, documents, opportunities, profile, sync

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

settings = get_settings()
logger = logging.getLogger("licitaia.main")

app = FastAPI(
    title="LicitaIA API",
    version="1.0.0",
    description=(
        "API de LicitaIA — agentes inteligentes para contratación pública en Colombia. "
        "Fuentes oficiales: SECOP II (datos.gov.co, Socrata). "
        "LicitaIA NO es una plataforma oficial del Gobierno colombiano."
    ),
    docs_url="/docs",
    openapi_url="/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(profile.router)
app.include_router(opportunities.router)
app.include_router(agents.router)
app.include_router(sync.router)
app.include_router(documents.router)
app.include_router(alerts.router)
app.include_router(companies.router)
app.include_router(billing.router)
app.include_router(contact.router)


@app.get("/health", tags=["operación"])
def health():
    return {"status": "ok", "app": settings.app_name, "environment": settings.environment}


@app.on_event("startup")
def on_startup() -> None:
    from app.db.session import init_db
    from app.services.demo import seed_demo_if_empty

    init_db()
    if settings.environment == "production":
        if settings.secret_key == "change-me-in-production":
            logger.warning("SECRET_KEY por defecto en producción: configurar inmediatamente (variable SECRET_KEY)")
    elif settings.environment == "development" and settings.allow_demo_seed:
        seed_demo_if_empty()
