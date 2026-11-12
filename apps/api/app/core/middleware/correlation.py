"""Contexto por solicitud: correlación, cabeceras de seguridad, registro y métricas.

Si el cliente envía ``X-Correlation-ID`` con un formato seguro se reutiliza; en
otro caso se genera uno. El valor viaja en los logs y en la respuesta, también
cuando la solicitud termina en un error no controlado.

Cada respuesta sale con cabeceras de seguridad (salvo las que la propia ruta
haya fijado) y deja una línea de registro con método, ruta, estado y duración.
En esa línea no va la cadena de consulta: puede llevar nombres de personas.
"""

from __future__ import annotations

import json
import logging
import re
import time
import uuid

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.exceptions.errors import PROBLEM_MEDIA_TYPE, internal_error_problem
from app.core.logging.setup import correlation_id_var
from app.core.middleware.metrics import UNROUTED, RequestMetrics

logger = logging.getLogger(__name__)
access_logger = logging.getLogger("app.access")

HEADER = "X-Correlation-ID"
_SAFE = re.compile(r"^[A-Za-z0-9\-_.]{8,64}$")

# La API solo entrega datos (JSON y descargas): nada de lo que responde debe
# ejecutarse, enmarcarse ni quedar guardado en cachés intermedias.
SECURITY_HEADERS: tuple[tuple[str, str], ...] = (
    ("x-content-type-options", "nosniff"),
    ("x-frame-options", "DENY"),
    ("referrer-policy", "no-referrer"),
    ("cross-origin-resource-policy", "same-origin"),
    ("cache-control", "no-store"),
)
CONTENT_SECURITY_POLICY = ("content-security-policy", "default-src 'none'; frame-ancestors 'none'")
STRICT_TRANSPORT_SECURITY = ("strict-transport-security", "max-age=31536000; includeSubDomains")


def route_template(scope: Scope) -> str:
    """La ruta declarada (``/vacancies/{vacancy_id}``), sin los identificadores reales."""
    if "route" not in scope:
        return UNROUTED
    path = str(scope.get("path", ""))
    for name, value in (scope.get("path_params") or {}).items():
        path = path.replace(f"/{value}", f"/{{{name}}}", 1)
    return path


class RequestContextMiddleware:
    def __init__(
        self,
        app: ASGIApp,
        *,
        metrics: RequestMetrics | None = None,
        https_only: bool = False,
        csp_exempt_paths: tuple[str, ...] = (),
        slow_request_ms: int = 2000,
    ) -> None:
        self.app = app
        self._metrics = metrics
        self._headers = list(SECURITY_HEADERS)
        if https_only:
            self._headers.append(STRICT_TRANSPORT_SECURITY)
        # La documentación interactiva (fuera de producción) necesita sus scripts.
        self._csp_exempt = csp_exempt_paths
        self._slow_ms = slow_request_ms

    def _with_security(self, headers: list[tuple[bytes, bytes]], path: str) -> None:
        present = {name.lower() for name, _ in headers}
        wanted = list(self._headers)
        if path not in self._csp_exempt:
            wanted.append(CONTENT_SECURITY_POLICY)
        for name, value in wanted:
            if name.encode("latin-1") not in present:
                headers.append((name.encode("latin-1"), value.encode("latin-1")))

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        incoming = None
        for name, value in scope.get("headers", []):
            if name.decode("latin-1").lower() == HEADER.lower():
                incoming = value.decode("latin-1")
                break
        correlation_id = incoming if incoming and _SAFE.match(incoming) else str(uuid.uuid4())
        token = correlation_id_var.set(correlation_id)
        response_started = False
        status = 500
        started = time.perf_counter()
        path = scope.get("path", "")

        async def send_with_header(message: Message) -> None:
            nonlocal response_started, status
            if message["type"] == "http.response.start":
                response_started = True
                status = message["status"]
                headers = list(message.get("headers", []))
                headers.append((HEADER.encode("latin-1"), correlation_id.encode("latin-1")))
                self._with_security(headers, path)
                message["headers"] = headers
            await send(message)

        try:
            await self.app(scope, receive, send_with_header)
        except Exception as exc:
            # El detalle va al log (ya filtrado); la respuesta no revela nada interno.
            logger.exception("Error no controlado: %s", type(exc).__name__)
            if response_started:
                raise
            body = json.dumps(internal_error_problem(), ensure_ascii=False).encode("utf-8")
            await send_with_header(
                {
                    "type": "http.response.start",
                    "status": 500,
                    "headers": [
                        (b"content-type", PROBLEM_MEDIA_TYPE.encode("latin-1")),
                        (b"content-length", str(len(body)).encode("latin-1")),
                    ],
                }
            )
            await send({"type": "http.response.body", "body": body})
        finally:
            duration_ms = (time.perf_counter() - started) * 1000
            route = route_template(scope)
            method = scope.get("method", "")
            if self._metrics is not None:
                self._metrics.record(method, route, status, duration_ms)
            access_logger.log(
                logging.WARNING if duration_ms >= self._slow_ms else logging.INFO,
                "%s %s %s %.0f ms",
                method,
                path,
                status,
                duration_ms,
                extra={
                    "fields": {
                        "method": method,
                        "route": route,
                        "status": status,
                        "duration_ms": round(duration_ms, 1),
                    }
                },
            )
            correlation_id_var.reset(token)
