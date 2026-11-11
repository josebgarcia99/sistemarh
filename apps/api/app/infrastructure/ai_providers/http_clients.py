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
