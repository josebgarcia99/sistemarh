"""Bancos de preguntas y llamadas telefónicas.

- Un banco se guarda por versiones: cada cambio en sus preguntas crea una
  versión nueva y las anteriores no cambian. Una llamada queda ligada a la
  versión con la que se hizo.
- Una llamada pertenece a una postulación. Mientras es borrador se puede
  seguir capturando; al cerrarla queda fija.
- Cada llamada tiene su propia lista de preguntas. Empieza con las generales
  de la empresa y las de los bancos elegidos; en esa llamada se pueden quitar,
  redactar distinto, sumar preguntas de otros bancos o escribir nuevas. Nada
  de eso cambia los bancos.
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
    # Preguntas generales de la empresa: se agregan solas a toda llamada, antes
    # de las de los bancos elegidos.
    GENERAL = "GENERAL"


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


class QuestionSource(StrEnum):
    """De dónde salió una pregunta de la llamada."""

    GENERAL = "GENERAL"  # banco general de la empresa
    BANCO = "BANCO"  # banco elegido para la llamada
    LLAMADA = "LLAMADA"  # escrita solo para esta llamada


# Tope de preguntas de una llamada, contando las quitadas.
MAX_CALL_QUESTIONS = 80


@dataclass(frozen=True)
class CallQuestion:
    """Una pregunta tal como quedó en una llamada."""

    id: uuid.UUID
    text: str
    competency: str = ""
    guidance: str = ""
    origin: str = "MANUAL"
    source: QuestionSource = QuestionSource.BANCO
    # Banco del que se tomó (nombre y versión de ese momento); vacío si se
    # escribió para la llamada.
    bank_id: uuid.UUID | None = None
    bank_name: str = ""
    bank_version: int | None = None
    # Redacción del banco, cuando se cambió para esta llamada.
    original_text: str | None = None
    # Quitada de esta llamada: no se pregunta, no se analiza y no cuenta.
    omitted: bool = False


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
    # Primer banco elegido al abrir la llamada, si se eligió alguno. Se conserva
    # como referencia; las preguntas de la llamada están en ``questions``.
    bank_version_id: uuid.UUID | None
    status: CallStatus
    called_at: datetime
    created_at: datetime
    created_by: uuid.UUID
    updated_at: datetime
    notes: str = ""
    answers: tuple[Answer, ...] = ()
    # Las preguntas de esta llamada, en orden, incluidas las quitadas.
    questions: tuple[CallQuestion, ...] = ()
    closed_at: datetime | None = None
    # Versiones de los bancos generales vigentes cuando se abrió la llamada.
    general_version_ids: tuple[uuid.UUID, ...] = ()
    # Último análisis de IA de la llamada, con su fecha y quién lo pidió.
    analysis: dict[str, Any] | None = None
    analysis_at: datetime | None = None
    analysis_by: uuid.UUID | None = None

    @property
    def active_questions(self) -> tuple[CallQuestion, ...]:
        """Las que sí forman parte de la llamada (sin las quitadas)."""
        return tuple(question for question in self.questions if not question.omitted)


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

    def add_call(self, call: CallSession) -> None:
        """Guarda la llamada y anota los bancos de los que tomó preguntas."""
        ...

    def save_call(self, call: CallSession) -> None: ...
