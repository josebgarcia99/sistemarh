"""Clientes HTTP de los proveedores de IA.

Por ahora solo consultan la lista de modelos (comprobación de conexión y
registro de modelos): no envían documentos. Los errores se traducen a mensajes
que nunca contienen la clave ni la respuesta completa del proveedor.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import httpx

TIMEOUT_SECONDS = 20.0
_MAX_PAGES = 20


@dataclass(frozen=True)
class DiscoveredModel:
    model_id: str
    display_name: str
    capabilities: dict[str, Any] | None = None


@dataclass(frozen=True)
class Generation:
    text: str
    input_tokens: int
    output_tokens: int
    # Falso si el proveedor cortó la respuesta por el límite de salida.
    complete: bool


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


def _post(client: httpx.Client, url: str, headers: dict[str, str], body: dict[str, Any]) -> Any:
    try:
        response = client.post(url, headers=headers, json=body)
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


class _BaseClient:
    def __init__(
        self, base_url: str, client_factory: Callable[[], httpx.Client] | None = None
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._client_factory = client_factory or (lambda: httpx.Client(timeout=TIMEOUT_SECONDS))


class AnthropicClient(_BaseClient):
    """API de Anthropic. La versión de la API es configurable, no fija."""

    def __init__(
        self,
        api_version: str,
        base_url: str = "https://api.anthropic.com",
        client_factory: Callable[[], httpx.Client] | None = None,
    ) -> None:
        super().__init__(base_url, client_factory)
        self._api_version = api_version

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
        self, api_key: str, model: str, *, system: str, user: str, max_output_tokens: int
    ) -> Generation:
        """API de mensajes. No se ha ejecutado contra el servicio real."""
        headers = {"Authorization": f"Bearer {api_key}", "anthropic-version": self._api_version}
        body = {
            "model": model,
            "max_tokens": max_output_tokens,
            "system": system,
            "messages": [{"role": "user", "content": user}],
        }
        with self._client_factory() as client:
            payload = _post(client, f"{self._base_url}/v1/messages", headers, body)
        try:
            text = "".join(
                block.get("text", "") for block in payload["content"] if block.get("type") == "text"
            )
            usage = payload["usage"]
            return Generation(
                text=text,
                input_tokens=int(usage["input_tokens"]),
                output_tokens=int(usage["output_tokens"]),
                complete=payload.get("stop_reason") != "max_tokens",
            )
        except (KeyError, TypeError, ValueError, AttributeError) as error:
            raise ProviderHttpError(
                "proveedor", "El proveedor devolvió una respuesta con un formato inesperado."
            ) from error


class OpenAIClient(_BaseClient):
    def __init__(
        self,
        base_url: str = "https://api.openai.com",
        client_factory: Callable[[], httpx.Client] | None = None,
    ) -> None:
        super().__init__(base_url, client_factory)

    def list_models(self, api_key: str) -> list[DiscoveredModel]:
        headers = {"Authorization": f"Bearer {api_key}"}
        with self._client_factory() as client:
            payload = _get(client, f"{self._base_url}/v1/models", headers, {})
        return [
            DiscoveredModel(model_id=str(item["id"]), display_name=str(item["id"]))
            for item in payload.get("data", [])
        ]

    def generate(
        self, api_key: str, model: str, *, system: str, user: str, max_output_tokens: int
    ) -> Generation:
        """API de respuestas. No se ha ejecutado contra el servicio real."""
        headers = {"Authorization": f"Bearer {api_key}"}
        body = {
            "model": model,
            "instructions": system,
            "input": user,
            "max_output_tokens": max_output_tokens,
            # Los documentos no se conservan en el proveedor.
            "store": False,
        }
        with self._client_factory() as client:
            payload = _post(client, f"{self._base_url}/v1/responses", headers, body)
        try:
            if payload.get("error"):
                raise ProviderHttpError("proveedor", "El proveedor no pudo generar la respuesta.")
            text = "".join(
                part.get("text", "")
                for item in payload["output"]
                if item.get("type") == "message"
                for part in item.get("content", [])
                if part.get("type") == "output_text"
            )
            usage = payload["usage"]
            return Generation(
                text=text,
                input_tokens=int(usage["input_tokens"]),
                output_tokens=int(usage["output_tokens"]),
                complete=payload.get("status") != "incomplete",
            )
        except (KeyError, TypeError, ValueError, AttributeError) as error:
            raise ProviderHttpError(
                "proveedor", "El proveedor devolvió una respuesta con un formato inesperado."
            ) from error


class GeminiClient(_BaseClient):
    """API de Gemini (Google AI): ``models.list`` y ``generateContent``.

    La clave viaja en la cabecera ``x-goog-api-key``, nunca en la dirección.
    No se ha ejecutado contra el servicio real.
    """

    _GENERATE = "generateContent"

    def __init__(
        self,
        base_url: str = "https://generativelanguage.googleapis.com",
        api_version: str = "v1beta",
        client_factory: Callable[[], httpx.Client] | None = None,
    ) -> None:
        super().__init__(base_url, client_factory)
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
        self, api_key: str, model: str, *, system: str, user: str, max_output_tokens: int
    ) -> Generation:
        headers = {"x-goog-api-key": api_key}
        body = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": user}]}],
            "generationConfig": {"maxOutputTokens": max_output_tokens},
        }
        url = f"{self._base_url}/{self._api_version}/models/{model}:{self._GENERATE}"
        with self._client_factory() as client:
            payload = _post(client, url, headers, body)
        try:
            candidates = payload.get("candidates") or []
            if not candidates:
                # Sin candidatos: el proveedor bloqueó la solicitud o no generó nada.
                raise ProviderHttpError("proveedor", "El proveedor no pudo generar la respuesta.")
            candidate = candidates[0]
            text = "".join(
                part.get("text", "")
                for part in (candidate.get("content") or {}).get("parts", [])
                # Las partes de razonamiento del modelo no son la respuesta.
                if not part.get("thought")
            )
            usage = payload["usageMetadata"]
            return Generation(
                text=text,
                input_tokens=int(usage["promptTokenCount"]),
                # El razonamiento interno se cobra como salida.
                output_tokens=int(usage.get("candidatesTokenCount", 0))
                + int(usage.get("thoughtsTokenCount", 0)),
                complete=candidate.get("finishReason") != "MAX_TOKENS",
            )
        except (KeyError, TypeError, ValueError, AttributeError) as error:
            raise ProviderHttpError(
                "proveedor", "El proveedor devolvió una respuesta con un formato inesperado."
            ) from error
