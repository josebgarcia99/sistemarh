"""Configuración de inteligencia artificial: proveedores, claves, modelos y asignaciones.

Las API keys solo existen en claro dentro del backend y durante una llamada al
proveedor. En la base se guarda su texto cifrado con la clave maestra y sus
últimos cuatro caracteres, para mostrar un identificador enmascarado.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any, Protocol


class ProviderCode(StrEnum):
    ANTHROPIC = "ANTHROPIC"
    OPENAI = "OPENAI"


PROVIDER_NAMES: dict[ProviderCode, str] = {
    ProviderCode.ANTHROPIC: "Anthropic",
    ProviderCode.OPENAI: "OpenAI",
}


class Operation(StrEnum):
    """Operaciones a las que el administrador asigna un modelo."""

    ANALISIS_PERFILES = "ANALISIS_PERFILES"
    GENERACION_PROMPTS = "GENERACION_PROMPTS"
    EXTRACCION_CV = "EXTRACCION_CV"
    EVALUACION_DOCUMENTAL = "EVALUACION_DOCUMENTAL"
    ANALISIS_LLAMADAS = "ANALISIS_LLAMADAS"
    LECTURA_DOCUMENTOS = "LECTURA_DOCUMENTOS"
    RESUMEN_PRUEBAS = "RESUMEN_PRUEBAS"
    SINTESIS_EXPEDIENTES = "SINTESIS_EXPEDIENTES"


class KeySource(StrEnum):
    PANTALLA = "PANTALLA"  # registrada por el administrador y cifrada en la base
    ENTORNO = "ENTORNO"  # inyectada por Sistemas como variable de entorno del servidor


@dataclass
class Provider:
    code: ProviderCode
    enabled: bool = False
    monthly_limit_usd: Decimal | None = None
    last_test_at: datetime | None = None
    last_test_ok: bool | None = None
    last_test_error: str | None = None
    updated_at: datetime | None = None
    updated_by: uuid.UUID | None = None


@dataclass
class Credential:
    id: uuid.UUID
    provider_code: ProviderCode
    # Vacío cuando la clave se revocó o se sustituyó: el secreto se borra.
    ciphertext: str | None
    last4: str
    master_key_id: str
    created_at: datetime
    created_by: uuid.UUID
    revoked_at: datetime | None = None
    revoked_by: uuid.UUID | None = None


@dataclass
class Model:
    id: uuid.UUID
    provider_code: ProviderCode
    model_id: str
    display_name: str
    # Lo que el proveedor declara; vacío si no informa capacidades.
    capabilities: dict[str, Any] | None
    # Falso si el proveedor dejó de listarlo en la última comprobación.
    is_available: bool
    first_seen_at: datetime
    last_seen_at: datetime


@dataclass
class Assignment:
    operation: Operation
    model_ref: uuid.UUID | None = None
    updated_at: datetime | None = None
    updated_by: uuid.UUID | None = None


@dataclass(frozen=True)
class DiscoveredModel:
    model_id: str
    display_name: str
    capabilities: dict[str, Any] | None = None


class ProviderError(Exception):
    """Fallo al hablar con un proveedor. ``message`` es apto para mostrarse:
    nunca contiene la clave ni la respuesta completa del proveedor."""

    def __init__(self, kind: str, message: str) -> None:
        super().__init__(message)
        self.kind = kind
        self.message = message


class ProviderClient(Protocol):
    def list_models(self, api_key: str) -> list[DiscoveredModel]: ...


class TextCipher(Protocol):
    key_id: str

    def encrypt_text(self, plaintext: str, *, context: str) -> str: ...

    def decrypt_text(self, token: str, *, context: str) -> str: ...


class AiRepository(Protocol):
    def get_provider(self, code: ProviderCode) -> Provider: ...

    def save_provider(self, provider: Provider) -> None: ...

    def active_credential(self, code: ProviderCode) -> Credential | None: ...

    def add_credential(self, credential: Credential) -> None: ...

    def save_credential(self, credential: Credential) -> None: ...

    def list_models(self, code: ProviderCode | None = None) -> list[Model]: ...

    def get_model(self, model_ref: uuid.UUID) -> Model | None: ...

    def add_model(self, model: Model) -> None: ...

    def save_model(self, model: Model) -> None: ...

    def get_assignment(self, operation: Operation) -> Assignment: ...

    def save_assignment(self, assignment: Assignment) -> None: ...
