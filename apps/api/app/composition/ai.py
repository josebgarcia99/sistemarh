"""Conexión entre la configuración de IA y los clientes HTTP de los proveedores."""

from __future__ import annotations

from collections.abc import Sequence

from app.core.config.settings import Settings
from app.infrastructure.ai_providers.http_clients import (
    AnthropicClient,
    GeminiClient,
    OpenAIClient,
    ProviderHttpError,
)
from app.modules.ai_settings.domain.models import (
    DiscoveredModel,
    Generation,
    ImageInput,
    ProviderClient,
    ProviderCode,
    ProviderError,
)


class _Adapter:
    def __init__(self, inner: AnthropicClient | OpenAIClient | GeminiClient) -> None:
        self._inner = inner

    def list_models(self, api_key: str) -> list[DiscoveredModel]:
        try:
            found = self._inner.list_models(api_key)
        except ProviderHttpError as error:
            raise ProviderError(error.kind, error.message) from error
        return [DiscoveredModel(m.model_id, m.display_name, m.capabilities) for m in found]

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
        try:
            result = self._inner.generate(
                api_key,
                model,
                system=system,
                user=user,
                max_output_tokens=max_output_tokens,
                images=images,
            )
        except ProviderHttpError as error:
            raise ProviderError(error.kind, error.message) from error
        return Generation(result.text, result.input_tokens, result.output_tokens, result.complete)


def build_provider_clients(settings: Settings) -> dict[ProviderCode, ProviderClient]:
    return {
        ProviderCode.ANTHROPIC: _Adapter(AnthropicClient(settings.anthropic_api_version)),
        ProviderCode.OPENAI: _Adapter(OpenAIClient()),
        ProviderCode.GEMINI: _Adapter(GeminiClient(api_version=settings.gemini_api_version)),
    }


def env_api_keys(settings: Settings) -> dict[ProviderCode, str]:
    """Claves inyectadas por Sistemas como variables de entorno del servidor."""
    keys = {}
    if settings.anthropic_api_key is not None:
        keys[ProviderCode.ANTHROPIC] = settings.anthropic_api_key.get_secret_value()
    if settings.openai_api_key is not None:
        keys[ProviderCode.OPENAI] = settings.openai_api_key.get_secret_value()
    if settings.gemini_api_key is not None:
        keys[ProviderCode.GEMINI] = settings.gemini_api_key.get_secret_value()
    return keys
