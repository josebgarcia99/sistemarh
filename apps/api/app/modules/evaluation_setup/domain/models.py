"""Perfil de puesto y prompt de evaluación de una vacante.

- El perfil se guarda por versiones: cada corrección crea una versión nueva y
  las anteriores no cambian.
- El prompt se compone de diez capas y una rúbrica. Solo una versión APROBADA
  puede usarse para evaluar CV, y una versión aprobada es inmutable.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Protocol

PROFILE_TEXT_FIELDS = ("objective", "experience", "education")
PROFILE_LIST_FIELDS = (
    "functions",
    "responsibilities",
    "knowledge",
    "skills",
    "certifications",
    "must_have",
    "nice_to_have",
    "ambiguities",
)


@dataclass(frozen=True)
class ProfileContent:
    objective: str = ""
    experience: str = ""
    education: str = ""
    functions: tuple[str, ...] = ()
    responsibilities: tuple[str, ...] = ()
    knowledge: tuple[str, ...] = ()
    skills: tuple[str, ...] = ()
    certifications: tuple[str, ...] = ()
    # Requisitos indispensables y deseables: de aquí sale la rúbrica.
    must_have: tuple[str, ...] = ()
    nice_to_have: tuple[str, ...] = ()
    # Requisitos del perfil que no están claros y conviene precisar.
    ambiguities: tuple[str, ...] = ()


class ProfileOrigin(StrEnum):
    MANUAL = "MANUAL"
    IA = "IA"


@dataclass(frozen=True)
class ProfileVersion:
    id: uuid.UUID
    vacancy_id: uuid.UUID
    version_number: int
    origin: ProfileOrigin
    content: ProfileContent
    change_note: str | None
    source_file_id: uuid.UUID | None
    created_at: datetime
    created_by: uuid.UUID


class PromptStatus(StrEnum):
    BORRADOR = "BORRADOR"
    EN_REVISION = "EN_REVISION"
    APROBADO = "APROBADO"
    ARCHIVADO = "ARCHIVADO"


class LayerKey(StrEnum):
    """Las diez capas, en el orden en que forman el prompt."""

    INSTRUCCIONES = "INSTRUCCIONES"
    PERFIL = "PERFIL"
    REQUISITOS = "REQUISITOS"
    RUBRICA = "RUBRICA"
    EVIDENCIAS = "EVIDENCIAS"
    AMBIGUEDADES = "AMBIGUEDADES"
    DATOS_FALTANTES = "DATOS_FALTANTES"
    RESTRICCIONES = "RESTRICCIONES"
    FORMATO_JSON = "FORMATO_JSON"
    REGLAS_VALIDACION = "REGLAS_VALIDACION"


# Capas que escribe el sistema: la rúbrica sale de los criterios, y el formato y
# las reglas deben coincidir con lo que el sistema valida al recibir la respuesta.
LOCKED_LAYERS = frozenset({LayerKey.RUBRICA, LayerKey.FORMATO_JSON, LayerKey.REGLAS_VALIDACION})


class CriterionKind(StrEnum):
    INDISPENSABLE = "INDISPENSABLE"
    DESEABLE = "DESEABLE"


class CriterionOrigin(StrEnum):
    PERFIL = "PERFIL"  # derivado de un requisito del perfil
    MANUAL = "MANUAL"  # añadido por una persona


@dataclass
class Criterion:
    id: uuid.UUID
    position: int
    name: str
    description: str
    kind: CriterionKind
    weight: Decimal
    # Descripción de los niveles 0 a 4.
    levels: tuple[str, str, str, str, str]
    origin: CriterionOrigin

    @property
    def code(self) -> str:
        return f"C{self.position}"


@dataclass
class PromptVersion:
    id: uuid.UUID
    vacancy_id: uuid.UUID
    version_number: int
    status: PromptStatus
    profile_version_id: uuid.UUID
    # Puntuación mínima (0 a 100) para clasificar un CV como aceptado.
    pass_threshold: Decimal
    layers: dict[LayerKey, str]
    criteria: list[Criterion]
    created_at: datetime
    created_by: uuid.UUID
    updated_at: datetime
    updated_by: uuid.UUID
    # Aumenta con cada edición del borrador: evita que dos personas se pisen.
    revision: int = 1
    duplicated_from: uuid.UUID | None = None
    submitted_at: datetime | None = None
    submitted_by: uuid.UUID | None = None
    approved_at: datetime | None = None
    approved_by: uuid.UUID | None = None
    archived_at: datetime | None = None
    archived_by: uuid.UUID | None = None
    issues: list[str] = field(default_factory=list)


class EvaluationSetupRepository(Protocol):
    def profile_versions(self, vacancy_id: uuid.UUID) -> list[ProfileVersion]:
        """De la más reciente a la más antigua."""
        ...

    def profile_version(self, version_id: uuid.UUID) -> ProfileVersion | None: ...

    def add_profile_version(self, version: ProfileVersion) -> None: ...

    def prompt_versions(self, vacancy_id: uuid.UUID) -> list[PromptVersion]:
        """De la más reciente a la más antigua."""
        ...

    def prompt_version(self, version_id: uuid.UUID) -> PromptVersion | None: ...

    def add_prompt_version(self, version: PromptVersion) -> None: ...

    def save_prompt_version(self, version: PromptVersion, *, expected_revision: int) -> bool:
        """Guarda si la revisión coincide. Devuelve falso si otra persona la cambió."""
        ...
