"""Aplicación FastAPI de LicitaIA (API REST documentada con OpenAPI en /docs)."""
import asyncio
import logging
from fastapi.responses import JSONResponse

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.requests import Request

from app.core.config import get_settings
from app.core.runtime_errors import record_error
from app.routers import agents, alerts, auth, billing, companies, contact, debug, documents, opportunities, profile, sync

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

# Backpressure a nivel de aplicación: cuando el API está ocupado, rechazamos
# de forma explícita y recuperable en lugar de acumular trabajo hasta provocar
# timeouts del proxy (502). El endpoint de salud siempre queda disponible.
_request_slots = asyncio.Semaphore(max(1, settings.max_concurrent_requests))


@app.middleware("http")
async def overload_guard(request: Request, call_next):
    if request.url.path == "/health":
        return await call_next(request)
    try:
        await asyncio.wait_for(_request_slots.acquire(), timeout=settings.overload_wait_seconds)
    except asyncio.TimeoutError:
        return JSONResponse(
            status_code=503,
            content={"detail": "Servicio temporalmente ocupado. Intenta de nuevo en unos segundos."},
            headers={"Retry-After": "2", "X-MySECOP-Overload": "1"},
        )
    try:
        return await call_next(request)
    finally:
        _request_slots.release()

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
app.include_router(debug.router)


@app.exception_handler(Exception)
async def runtime_error_handler(request, exc: Exception):
    record_error(request, exc)
    logger.exception("Unhandled runtime error: %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Error interno del servidor"})


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
