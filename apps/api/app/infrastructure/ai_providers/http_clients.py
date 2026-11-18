"""Clientes HTTP de los proveedores de IA.

Consultan la lista de modelos y piden respuestas de texto, con imágenes
adjuntas cuando la operación las lleva. Los errores se traducen a mensajes
que nunca contienen la clave ni la respuesta completa del proveedor.

Las respuestas se piden **por partes** (eventos enviados por el servidor): el
proveedor va mandando señales conforme trabaja, y así se sabe en qué punto está
cada solicitud:

1. Se conectó y el proveedor aceptó la solicitud (respondió 200).
2. El modelo empezó a contestar (llegó el primer pedazo de texto).
3. Terminó (llegó la señal de fin, con el consumo).

Con eso un fallo se informa por lo que fue: no se pudo conectar, el modelo no
empezó a responder, la respuesta se interrumpió a la mitad o tardó demasiado.
Mientras sigan llegando pedazos se sigue esperando; solo se abandona si pasa
un rato sin que llegue nada o si se rebasa el tope total.

Formatos (documentación de cada proveedor, noviembre de 2026):
- Anthropic, ``POST /v1/messages`` con ``"stream": true``: eventos
  ``message_start``, ``content_block_delta`` (``text_delta``), ``message_delta``,
  ``message_stop``, ``ping`` y ``error``.
- OpenAI, ``POST /v1/responses`` con ``"stream": true``: eventos
  ``response.output_text.delta``, ``response.completed``, ``response.incomplete``,
  ``response.failed`` y ``error``.
- Gemini, ``POST …:streamGenerateContent?alt=sse``: cada dato es una respuesta
  parcial con ``candidates``, ``finishReason`` y ``usageMetadata``.

Nada de esto se ha ejecutado todavía contra los servicios reales.
"""

from __future__ import annotations

import base64
import json
import re
import time
from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol

import httpx

# Para consultar la lista de modelos basta poco tiempo.
TIMEOUT_SECONDS = 20.0
# Al pedir una respuesta por partes:
# - tiempo para conectar con el proveedor;
CONNECT_SECONDS = 10.0
# - silencio máximo: cuánto se espera sin que llegue nada nuevo, sea antes del
#   primer pedazo (un modelo que razona puede tardar en empezar) o entre dos;
IDLE_SECONDS = 90.0
# - tope total de una respuesta, aunque sigan llegando pedazos. Con el silencio
#   máximo queda por debajo de lo que el proxy deja durar una llamada a la API
#   (360 s), para que el aviso lo dé la aplicación y no el proxy.
TOTAL_SECONDS = 240.0
STREAM_TIMEOUT = httpx.Timeout(IDLE_SECONDS, connect=CONNECT_SECONDS, pool=CONNECT_SECONDS)
_MAX_PAGES = 20


@dataclass(frozen=True)
class DiscoveredModel:
    model_id: str
    display_name: str
    capabilities: dict[str, Any] | None = None


class ImageInput(Protocol):
    """Imagen adjunta a una solicitud: tipo (image/jpeg, image/png) y contenido."""

    @property
    def media_type(self) -> str: ...

    @property
    def data(self) -> bytes: ...


@dataclass(frozen=True)
class Generation:
    text: str
    input_tokens: int
    output_tokens: int
    # Falso si el proveedor cortó la respuesta por el límite de salida.
    complete: bool
    # Cuánto tardó cada paso, en milisegundos desde que se envió la solicitud:
    # hasta que el proveedor la aceptó y hasta el primer pedazo de texto.
    accepted_ms: int | None = None
    first_text_ms: int | None = None


class ProviderHttpError(Exception):
    def __init__(self, kind: str, message: str) -> None:
        super().__init__(message)
        self.kind = kind
        self.message = message


def _get(client: httpx.Client, url: str, headers: dict[str, str], params: dict[str, str]) -> Any:
    try:
        response = client.get(url, headers=headers, params=params)
    except httpx.HTTPError as error:
        raise ProviderHttpError("red", "No se pudo conectar con el proveedor.") from error
    return _checked(response)


def _checked(response: httpx.Response) -> Any:
    if response.status_code in (401, 403):
        raise ProviderHttpError(
            "clave", "El proveedor rechazó la clave: no es válida o no tiene permisos."
        )
    if response.status_code == 429:
        raise ProviderHttpError(
            "limite", "El proveedor limitó las solicitudes. Inténtalo más tarde."
        )
    if response.status_code >= 400:
        raise ProviderHttpError(
            "proveedor", f"El proveedor respondió con un error ({response.status_code})."
        )
    try:
        return response.json()
    except ValueError as error:
        raise ProviderHttpError(
            "proveedor", "El proveedor devolvió una respuesta ilegible."
        ) from error


_NOT_STARTED = (
    "El proveedor recibió la solicitud, pero el modelo no empezó a responder. Vuelve a intentarlo."
)
_INTERRUPTED = (
    "El modelo empezó a responder y la respuesta se interrumpió antes de terminar. "
    "Vuelve a intentarlo."
)
_TOO_LONG = (
    f"El modelo llevaba más de {int(TOTAL_SECONDS // 60)} minutos respondiendo y se dejó de "
    "esperar. Vuelve a intentarlo."
)
_UNEXPECTED = "El proveedor devolvió una respuesta con un formato inesperado."


@dataclass
class _Reply:
    """Lo que se lleva recibido de una respuesta por partes."""

    parts: list[str] = field(default_factory=list)
    input_tokens: int = 0
    output_tokens: int = 0
    # Llegó la señal de fin del proveedor.
    finished: bool = False
    # Falso si el proveedor la cortó por el límite de salida.
    complete: bool = True
    accepted_ms: int | None = None
    first_text_ms: int | None = None

    def generation(self) -> Generation:
        return Generation(
            text="".join(self.parts),
            input_tokens=self.input_tokens,
            output_tokens=self.output_tokens,
            complete=self.complete,
            accepted_ms=self.accepted_ms,
            first_text_ms=self.first_text_ms,
        )


def _count(value: object) -> int:
    """Un número de tokens del proveedor; si no viene o no es un número, cero."""
    return value if isinstance(value, int) and not isinstance(value, bool) and value > 0 else 0


def _code(value: object) -> str:
    """El código de error del proveedor, reducido a letras, números y guiones."""
    return re.sub(r"[^a-z0-9_.-]", "", str(value or "").lower())[:40] or "sin_codigo"


def _stream_failure(reply: _Reply, code: object) -> ProviderHttpError:
    """El proveedor avisó de un error dentro de la propia respuesta."""
    if reply.parts:
        # Ya había texto: repetir la solicitud volvería a costar, así que no se
        # trata como un fallo pasajero.
        return ProviderHttpError("interrumpida", _INTERRUPTED)
    name = _code(code)
    if "rate_limit" in name or name in {"429", "resource_exhausted"}:
        return ProviderHttpError(
            "limite", "El proveedor limitó las solicitudes. Inténtalo más tarde."
        )
    if "authentication" in name or "permission" in name:
        return ProviderHttpError(
            "clave", "El proveedor rechazó la clave: no es válida o no tiene permisos."
        )
    return ProviderHttpError("proveedor", f"El proveedor no pudo generar la respuesta ({name}).")


def _b64(image: ImageInput) -> str:
    return base64.b64encode(image.data).decode("ascii")


class _BaseClient:
    def __init__(
        self,
        base_url: str,
        client_factory: Callable[[], httpx.Client] | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._client_factory = client_factory or (lambda: httpx.Client(timeout=TIMEOUT_SECONDS))
        self._clock = clock

    def _stream(
        self,
        url: str,
        headers: dict[str, str],
        body: dict[str, Any],
        reply: _Reply,
        params: dict[str, str] | None = None,
    ) -> Iterator[dict[str, Any]]:
        """Pide una respuesta por partes y entrega cada dato que manda el proveedor.

        Va anotando en ``reply`` cuándo se aceptó la solicitud. Traduce cada fallo
        según el punto en que ocurrió: sin conexión, sin respuesta del modelo,
        respuesta interrumpida o tiempo total rebasado."""
        started = self._clock()
        accepted = False
        try:
            with (
                self._client_factory() as client,
                client.stream(
                    "POST", url, headers=headers, json=body, params=params, timeout=STREAM_TIMEOUT
                ) as response,
            ):
                if response.status_code >= 400:
                    _checked(response)
                accepted = True
                reply.accepted_ms = int((self._clock() - started) * 1000)
                for line in response.iter_lines():
                    if self._clock() - started > TOTAL_SECONDS:
                        raise ProviderHttpError("tiempo", _TOO_LONG)
                    if not line.startswith("data:"):
                        continue  # nombre del evento, comentario o línea en blanco
                    data = line[5:].strip()
                    if not data or data == "[DONE]":
                        continue
                    try:
                        payload = json.loads(data)
                    except ValueError as error:
                        raise ProviderHttpError("proveedor", _UNEXPECTED) from error
                    if isinstance(payload, dict):
                        had_text = bool(reply.parts)
                        yield payload
                        if reply.parts and not had_text:
                            reply.first_text_ms = int((self._clock() - started) * 1000)
        except ProviderHttpError:
            raise
        except (httpx.ConnectError, httpx.ConnectTimeout, httpx.PoolTimeout) as error:
            # No se llegó al proveedor: sí es un fallo de red.
            raise ProviderHttpError("red", "No se pudo conectar con el proveedor.") from error
        except httpx.HTTPError as error:
            if reply.parts:
                raise ProviderHttpError("interrumpida", _INTERRUPTED) from error
            if accepted or isinstance(error, httpx.TimeoutException):
                # Se conectó, pero el modelo se quedó en silencio.
                raise ProviderHttpError("sin_respuesta", _NOT_STARTED) from error
            raise ProviderHttpError("red", "No se pudo conectar con el proveedor.") from error
        if not reply.finished:
            # El proveedor cerró sin mandar la señal de fin.
            if reply.parts:
                raise ProviderHttpError("interrumpida", _INTERRUPTED)
            raise ProviderHttpError("sin_respuesta", _NOT_STARTED)


class AnthropicClient(_BaseClient):
    """API de Anthropic. La versión de la API es configurable, no fija."""

    def __init__(
        self,
        api_version: str,
        base_url: str = "https://api.anthropic.com",
        client_factory: Callable[[], httpx.Client] | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        super().__init__(base_url, client_factory, clock)
        self._api_version = api_version

    @staticmethod
    def _content(user: str, images: Sequence[ImageInput]) -> object:
        """Sin imágenes, el texto tal cual; con ellas, bloques de imagen y de texto."""
        if not images:
            return user
        blocks: list[dict[str, object]] = [
            {
                "type": "image",
                "source": {"type": "base64", "media_type": image.media_type, "data": _b64(image)},
            }
            for image in images
        ]
        return [*blocks, {"type": "text", "text": user}]

    def list_models(self, api_key: str) -> list[DiscoveredModel]:
        headers = {"Authorization": f"Bearer {api_key}", "anthropic-version": self._api_version}
        models: list[DiscoveredModel] = []
        params = {"limit": "100"}
        with self._client_factory() as client:
            for _ in range(_MAX_PAGES):
                payload = _get(client, f"{self._base_url}/v1/models", headers, params)
                for item in payload.get("data", []):
                    capabilities = item.get("capabilities")
                    models.append(
                        DiscoveredModel(
                            model_id=str(item["id"]),
                            display_name=str(item.get("display_name") or item["id"]),
                            capabilities=capabilities if isinstance(capabilities, dict) else None,
                        )
                    )
                if not payload.get("has_more") or not payload.get("last_id"):
                    break
                params = {"limit": "100", "after_id": str(payload["last_id"])}
        return models

    def generate(
        self,
        api_key: str,
        model: str,
        *,
        system: str,
        user: str,
        max_output_tokens: int,
        images: Sequence[ImageInput] = (),
    ) -> Generation:
        """API de mensajes, por partes. No se ha ejecutado contra el servicio real."""
        headers = {"Authorization": f"Bearer {api_key}", "anthropic-version": self._api_version}
        body = {
            "model": model,
            "max_tokens": max_output_tokens,
            "system": system,
            "messages": [{"role": "user", "content": self._content(user, images)}],
            "stream": True,
        }
        reply = _Reply()
        try:
            for event in self._stream(f"{self._base_url}/v1/messages", headers, body, reply):
                kind = event.get("type")
                if kind == "message_start":
                    usage = (event.get("message") or {}).get("usage") or {}
                    reply.input_tokens = _count(usage.get("input_tokens"))
                    reply.output_tokens = _count(usage.get("output_tokens"))
                elif kind == "content_block_delta":
                    delta = event.get("delta") or {}
                    # El razonamiento del modelo y otros bloques no son la respuesta.
                    if delta.get("type") == "text_delta" and delta.get("text"):
                        reply.parts.append(str(delta["text"]))
                elif kind == "message_delta":
                    usage = event.get("usage") or {}
                    # El consumo de este evento es el acumulado.
                    reply.output_tokens = _count(usage.get("output_tokens")) or reply.output_tokens
                    reply.input_tokens = _count(usage.get("input_tokens")) or reply.input_tokens
                    if (event.get("delta") or {}).get("stop_reason") == "max_tokens":
                        reply.complete = False
                elif kind == "message_stop":
                    reply.finished = True
                elif kind == "error":
                    raise _stream_failure(reply, (event.get("error") or {}).get("type"))
                # «ping» y los tipos de evento que no se conocen se ignoran.
        except (TypeError, ValueError, AttributeError) as error:
            raise ProviderHttpError("proveedor", _UNEXPECTED) from error
        return reply.generation()


class OpenAIClient(_BaseClient):
    @staticmethod
    def _input(user: str, images: Sequence[ImageInput]) -> object:
        """Sin imágenes, el texto tal cual; con ellas, un mensaje con sus partes."""
        if not images:
            return user
        parts: list[dict[str, object]] = [{"type": "input_text", "text": user}]
        parts += [
            {"type": "input_image", "image_url": f"data:{image.media_type};base64,{_b64(image)}"}
            for image in images
        ]
        return [{"role": "user", "content": parts}]

    def __init__(
        self,
        base_url: str = "https://api.openai.com",
        client_factory: Callable[[], httpx.Client] | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        super().__init__(base_url, client_factory, clock)

    def list_models(self, api_key: str) -> list[DiscoveredModel]:
        headers = {"Authorization": f"Bearer {api_key}"}
        with self._client_factory() as client:
            payload = _get(client, f"{self._base_url}/v1/models", headers, {})
        return [
            DiscoveredModel(model_id=str(item["id"]), display_name=str(item["id"]))
            for item in payload.get("data", [])
        ]

    def generate(
        self,
        api_key: str,
        model: str,
        *,
        system: str,
        user: str,
        max_output_tokens: int,
        images: Sequence[ImageInput] = (),
    ) -> Generation:
        """API de respuestas, por partes. No se ha ejecutado contra el servicio real."""
        headers = {"Authorization": f"Bearer {api_key}"}
        body = {
            "model": model,
            "instructions": system,
            "input": self._input(user, images),
            "max_output_tokens": max_output_tokens,
            # Los documentos no se conservan en el proveedor.
            "store": False,
            "stream": True,
        }
        reply = _Reply()
        try:
            for event in self._stream(f"{self._base_url}/v1/responses", headers, body, reply):
                kind = event.get("type")
                if kind == "response.output_text.delta":
                    if event.get("delta"):
                        reply.parts.append(str(event["delta"]))
                elif kind in ("response.completed", "response.incomplete"):
                    usage = (event.get("response") or {}).get("usage") or {}
                    reply.input_tokens = _count(usage.get("input_tokens"))
                    reply.output_tokens = _count(usage.get("output_tokens"))
                    # «incomplete»: el proveedor la cortó (por ejemplo, por el límite de salida).
                    reply.complete = kind == "response.completed"
                    reply.finished = True
                elif kind == "response.failed":
                    failure = (event.get("response") or {}).get("error") or {}
                    raise _stream_failure(reply, failure.get("code"))
                elif kind == "error":
                    raise _stream_failure(reply, event.get("code"))
                # Los demás eventos (creación, razonamiento, negativas, etc.) se ignoran.
        except (TypeError, ValueError, AttributeError) as error:
            raise ProviderHttpError("proveedor", _UNEXPECTED) from error
        return reply.generation()


class GeminiClient(_BaseClient):
    """API de Gemini (Google AI): ``models.list`` y ``streamGenerateContent``.

    La clave viaja en la cabecera ``x-goog-api-key``, nunca en la dirección.
    Los modelos que sirven son los que admiten ``generateContent``; la respuesta
    se pide con su variante por partes, que recibe la misma solicitud.
    No se ha ejecutado contra el servicio real.
    """

    _GENERATE = "generateContent"
    _STREAM = "streamGenerateContent"

    def __init__(
        self,
        base_url: str = "https://generativelanguage.googleapis.com",
        api_version: str = "v1beta",
        client_factory: Callable[[], httpx.Client] | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        super().__init__(base_url, client_factory, clock)
        self._api_version = api_version

    def list_models(self, api_key: str) -> list[DiscoveredModel]:
        headers = {"x-goog-api-key": api_key}
        models: list[DiscoveredModel] = []
        params = {"pageSize": "200"}
        with self._client_factory() as client:
            for _ in range(_MAX_PAGES):
                payload = _get(
                    client, f"{self._base_url}/{self._api_version}/models", headers, params
                )
                for item in payload.get("models", []):
                    methods = item.get("supportedGenerationMethods") or []
                    # Solo sirven los modelos que generan texto (no los de vectores o imagen).
                    if self._GENERATE not in methods:
                        continue
                    # El nombre llega como «models/<id>»; se guarda solo el identificador.
                    model_id = str(item["name"]).removeprefix("models/")
                    models.append(
                        DiscoveredModel(
                            model_id=model_id,
                            display_name=str(item.get("displayName") or model_id),
                            capabilities={
                                key: item[key]
                                for key in ("inputTokenLimit", "outputTokenLimit")
                                if key in item
                            }
                            or None,
                        )
                    )
                token = payload.get("nextPageToken")
                if not token:
                    break
                params = {"pageSize": "200", "pageToken": str(token)}
        return models

    def generate(
        self,
        api_key: str,
        model: str,
        *,
        system: str,
        user: str,
        max_output_tokens: int,
        images: Sequence[ImageInput] = (),
    ) -> Generation:
        headers = {"x-goog-api-key": api_key}
        body = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [
                {
                    "role": "user",
                    "parts": [
                        *(
                            {"inline_data": {"mime_type": image.media_type, "data": _b64(image)}}
                            for image in images
                        ),
                        {"text": user},
                    ],
                }
            ],
            "generationConfig": {"maxOutputTokens": max_output_tokens},
        }
        url = f"{self._base_url}/{self._api_version}/models/{model}:{self._STREAM}"
        reply = _Reply()
        try:
            for chunk in self._stream(url, headers, body, reply, params={"alt": "sse"}):
                if chunk.get("error"):
                    raise _stream_failure(reply, (chunk.get("error") or {}).get("status"))
                if (chunk.get("promptFeedback") or {}).get("blockReason"):
                    # El proveedor bloqueó la solicitud: no habrá respuesta.
                    raise ProviderHttpError(
                        "proveedor", "El proveedor no pudo generar la respuesta."
                    )
                usage = chunk.get("usageMetadata") or {}
                if usage:
                    reply.input_tokens = _count(usage.get("promptTokenCount")) or reply.input_tokens
                    # El razonamiento interno se cobra como salida.
                    reply.output_tokens = _count(usage.get("candidatesTokenCount")) + _count(
                        usage.get("thoughtsTokenCount")
                    )
                for candidate in (chunk.get("candidates") or [])[:1]:
                    for part in (candidate.get("content") or {}).get("parts") or []:
                        # Las partes de razonamiento del modelo no son la respuesta.
                        if part.get("text") and not part.get("thought"):
                            reply.parts.append(str(part["text"]))
                    reason = candidate.get("finishReason")
                    if reason:
                        # No hay evento de fin: la última parte trae el motivo.
                        reply.finished = True
                        reply.complete = reason != "MAX_TOKENS"
        except (TypeError, ValueError, AttributeError) as error:
            raise ProviderHttpError("proveedor", _UNEXPECTED) from error
        return reply.generation()
