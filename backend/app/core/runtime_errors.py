"""Registro acotado de errores para diagnóstico durante desarrollo."""
from collections import deque
from datetime import datetime, timezone
import traceback
from typing import Any

_errors: deque[dict[str, Any]] = deque(maxlen=100)


def record_error(request: Any, exc: Exception, status_code: int = 500) -> None:
    _errors.appendleft({
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "method": request.method,
        "path": request.url.path,
        "status_code": status_code,
        "error": type(exc).__name__,
        "message": str(exc),
        "traceback": "".join(traceback.format_exception(type(exc), exc, exc.__traceback__)),
    })


def recent_errors(limit: int = 50) -> list[dict[str, Any]]:
    return list(_errors)[: max(1, min(limit, 100))]
