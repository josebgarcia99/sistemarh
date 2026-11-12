"""Registro estructurado en JSON con identificador de correlación.

Los mensajes pasan por un filtro que oculta secretos antes de escribirse:
ninguna clave de API, contraseña ni cadena de conexión debe llegar a un log.
"""

from __future__ import annotations

import json
import logging
import re
import sys
from contextvars import ContextVar
from datetime import UTC, datetime

correlation_id_var: ContextVar[str | None] = ContextVar("correlation_id", default=None)

REDACTED = "[OCULTO]"

_SECRET_PATTERNS: tuple[re.Pattern[str], ...] = (
    # Claves de proveedores de IA (Anthropic, OpenAI y formatos similares).
    re.compile(r"sk-[A-Za-z0-9_\-]{8,}"),
    # Claves de Google (Gemini).
    re.compile(r"AIza[A-Za-z0-9_\-]{20,}"),
    # Cabeceras de autorización.
    re.compile(r"(?i)(bearer\s+)[A-Za-z0-9_\-\.=]{8,}"),
    # Pares clave=valor o "clave": "valor" con nombres sensibles.
    re.compile(
        r"(?i)((?:password|passwd|pwd|contrase(?:n|ñ)a|api[_-]?key|secret|token)"
        r"[\"']?\s*[:=]\s*[\"']?)([^\s\"',;&]+)"
    ),
    # Credenciales dentro de una URL: esquema://usuario:clave@servidor
    re.compile(r"(://[^:/\s]+:)([^@\s]+)(@)"),
)


def redact(text: str) -> str:
    """Devuelve ``text`` con los secretos reconocibles sustituidos."""
    provider_key, google_key, bearer, pair, url_credentials = _SECRET_PATTERNS
    text = provider_key.sub(REDACTED, text)
    text = google_key.sub(REDACTED, text)
    text = bearer.sub(lambda m: m.group(1) + REDACTED, text)
    text = pair.sub(lambda m: m.group(1) + REDACTED, text)
    text = url_credentials.sub(lambda m: m.group(1) + REDACTED + m.group(3), text)
    return text


class RedactingFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = redact(record.getMessage())
        record.args = None
        return True


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "timestamp": datetime.now(UTC).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "correlation_id": correlation_id_var.get(),
        }
        # Campos estructurados (por ejemplo, los de la línea de acceso).
        fields = getattr(record, "fields", None)
        if isinstance(fields, dict):
            payload.update(fields)
        if record.exc_info:
            payload["exception"] = redact(self.formatException(record.exc_info))
        return json.dumps(payload, ensure_ascii=False)


def configure_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    handler.addFilter(RedactingFilter())
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level.upper())
