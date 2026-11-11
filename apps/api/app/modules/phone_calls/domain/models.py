"""Bancos de preguntas y llamadas telefónicas.

- Un banco se guarda por versiones: cada cambio en sus preguntas crea una
  versión nueva y las anteriores no cambian. Una llamada queda ligada a la
  versión con la que se hizo.
- Una llamada pertenece a una postulación. Mientras es borrador se puede
  seguir capturando; al cerrarla queda fija.
- El análisis de IA resume lo dicho en la llamada. No decide nada.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any, Protocol


class BankScope(StrEnum):
    PRIVADO = "PRIVADO"
    COMPARTIDO = "COMPARTIDO"


class BankStatus(StrEnum):
    ACTIVO = "ACTIVO"
    ARCHIVADO = "ARCHIVADO"


@dataclass
class Bank:
    id: uuid.UUID
    name: str
    owner_user_id: uuid.UUID
    scope: BankScope
    status: BankStatus
    created_at: datetime
    updated_at: datetime
    description: str | None = None
    duplicated_from: uuid.UUID | None = None


@dataclass(frozen=True)
class Question:
    id: uuid.UUID
    text: str
    # Competencia que explora la pregunta (opcional).
    competency: str = ""
    # Qué escuchar en la respuesta: la rúbrica opcional de la pregunta.
    guidance: str = ""
    origin: str = "MANUAL"  # MANUAL o IA (propuesta por la IA y aceptada por una persona)


@dataclass(frozen=True)
class BankVersion:
    id: uuid.UUID
    bank_id: uuid.UUID
    version_number: int
    questions: tuple[Question, ...]
    created_at: datetime
    created_by: uuid.UUID
    change_note: str | None = None


class CallStatus(StrEnum):
    BORRADOR = "BORRADOR"
    CERRADA = "CERRADA"


@dataclass(frozen=True)
class Answer:
    question_id: uuid.UUID
    answer: str = ""
    notes: str = ""
    not_asked: bool = False


@dataclass
class CallSession:
    id: uuid.UUID
    application_id: uuid.UUID
    vacancy_id: uuid.UUID
    bank_version_id: uuid.UUID
    status: CallStatus
    called_at: datetime
    created_at: datetime
    created_by: uuid.UUID
    updated_at: datetime
    notes: str = ""
    answers: tuple[Answer, ...] = ()
    closed_at: datetime | None = None
    # Último análisis de IA de la llamada, con su fecha y quién lo pidió.
    analysis: dict[str, Any] | None = None
    analysis_at: datetime | None = None
    analysis_by: uuid.UUID | None = None


@dataclass(frozen=True)
class ApplicationRef:
    """Lo que una llamada necesita saber de la postulación."""

    id: uuid.UUID
    vacancy_id: uuid.UUID
    active: bool
    candidate_name: str
    # Datos ordenados del CV, si existen, para contrastar con la llamada.
    cv: dict[str, Any] = field(default_factory=dict)
    # Requisitos del perfil del puesto.
    requirements: tuple[str, ...] = ()


class Applications(Protocol):
    def get(self, application_id: uuid.UUID) -> ApplicationRef | None: ...


class JobProfiles(Protocol):
    def summary(self, vacancy_id: uuid.UUID) -> str | None:
        """Texto del perfil vigente de la vacante, o ``None`` si no tiene."""
        ...


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
    ) -> AssistantAnswer: ...


class PhoneCallRepository(Protocol):
    def banks(self) -> list[Bank]: ...

    def bank(self, bank_id: uuid.UUID) -> Bank | None: ...

    def add_bank(self, bank: Bank) -> None: ...

    def save_bank(self, bank: Bank) -> None: ...

    def versions(self, bank_id: uuid.UUID) -> list[BankVersion]:
        """De la más reciente a la más antigua."""
        ...

    def version(self, version_id: uuid.UUID) -> BankVersion | None: ...

    def add_version(self, version: BankVersion) -> None: ...

    def latest_versions(self, bank_ids: list[uuid.UUID]) -> dict[uuid.UUID, BankVersion]: ...

    def call(self, call_id: uuid.UUID) -> CallSession | None: ...

    def calls(self, application_id: uuid.UUID) -> list[CallSession]:
        """De la más reciente a la más antigua."""
        ...

    def add_call(self, call: CallSession) -> None: ...

    def save_call(self, call: CallSession) -> None: ...
