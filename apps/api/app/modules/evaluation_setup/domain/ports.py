"""Lo que el perfil y el prompt necesitan de la IA y de los documentos."""

from __future__ import annotations

import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol

# Operaciones a las que el administrador asigna un modelo.
PROFILE_ANALYSIS = "ANALISIS_PERFILES"
PROMPT_GENERATION = "GENERACION_PROMPTS"


@dataclass(frozen=True)
class AssistantAnswer:
    ok: bool
    text: str
    complete: bool
    error: str | None


class Assistant(Protocol):
    def ask(
        self,
        operation: str,
        *,
        system: str,
        user: str,
        vacancy_id: uuid.UUID,
        actor_user_id: uuid.UUID,
        carries_document: bool,
    ) -> AssistantAnswer:
        """Un fallo del proveedor se devuelve. Lanza un error de negocio si la
        operación no se puede ejecutar (sin modelo, sin clave, límite de gasto)."""
        ...


class ProfileSourceError(Exception):
    """El documento no se puede usar como origen del perfil. Mensaje apto para mostrarse."""


class ProfileSources(Protocol):
    def is_profile_document(self, vacancy_id: uuid.UUID, file_id: uuid.UUID) -> bool: ...

    def read_text(self, vacancy_id: uuid.UUID, file_id: uuid.UUID) -> tuple[str, bool]:
        """Texto del documento de perfil y si se recortó. Lanza ``ProfileSourceError``."""
        ...

    def read_sheets(
        self, vacancy_id: uuid.UUID, file_id: uuid.UUID
    ) -> list[Mapping[tuple[int, int], object]] | None:
        """Celdas de cada hoja si el documento es una hoja de cálculo; ``None`` si
        no lo es. Lanza ``ProfileSourceError``."""
        ...
