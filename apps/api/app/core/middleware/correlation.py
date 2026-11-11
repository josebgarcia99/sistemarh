"""Contexto por solicitud: identificador de correlación y errores inesperados.

Si el cliente envía ``X-Correlation-ID`` con un formato seguro se reutiliza; en
otro caso se genera uno. El valor viaja en los logs y en la respuesta, también
cuando la solicitud termina en un error no controlado.
"""

from __future__ import annotations

import json
import logging
import re
import uuid

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.exceptions.errors import PROBLEM_MEDIA_TYPE, internal_error_problem
from app.core.logging.setup import correlation_id_var

logger = logging.getLogger(__name__)

HEADER = "X-Correlation-ID"
_SAFE = re.compile(r"^[A-Za-z0-9\-_.]{8,64}$")


class RequestContextMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

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

        async def send_with_header(message: Message) -> None:
            nonlocal response_started
            if message["type"] == "http.response.start":
                response_started = True
                headers = list(message.get("headers", []))
                headers.append((HEADER.encode("latin-1"), correlation_id.encode("latin-1")))
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
            correlation_id_var.reset(token)
