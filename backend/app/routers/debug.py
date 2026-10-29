"""Diagnóstico protegido y disponible únicamente fuera de producción."""
from fastapi import APIRouter, Header, HTTPException, Request

from app.core.config import get_settings
from app.core.runtime_errors import recent_errors

router = APIRouter(prefix="/api/debug", tags=["debug"])


@router.get("/errors")
def errors(request: Request, x_debug_token: str | None = Header(default=None)):
    settings = get_settings()
    if settings.environment == "production":
        raise HTTPException(status_code=404, detail="No encontrado")
    if not settings.debug_endpoint_token or x_debug_token != settings.debug_endpoint_token:
        raise HTTPException(status_code=403, detail="Token de diagnóstico inválido")
    return {"count": len(recent_errors()), "errors": recent_errors()}
