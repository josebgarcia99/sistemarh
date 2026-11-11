"""Lo que el procesamiento de CV necesita de otras partes del sistema."""

from __future__ import annotations

import uuid
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from decimal import Decimal
from typing import BinaryIO, Protocol


@dataclass(frozen=True)
class CvFile:
    id: uuid.UUID
    name: str
    extension: str
    sha256: str
    size_bytes: int


class UnreadableCvError(Exception):
    """No se obtuvo texto del CV. ``code``: sin_texto, formato_sin_texto, protegido,
    ilegible, ocr_fallido o archivo_no_disponible."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class CvText:
    text: str
    truncated: bool
    # Salió de un documento escaneado (OCR).
    ocr: bool


class CvFiles(Protocol):
    def confirmed_cvs(self, vacancy_id: uuid.UUID) -> list[CvFile]: ...

    def get(self, file_id: uuid.UUID) -> CvFile | None:
        """``None`` si el CV se eliminó o ya no está disponible."""
        ...

    def read_text(self, file_id: uuid.UUID) -> CvText:
        """Texto del CV. Lanza ``UnreadableCvError``."""
        ...

    def read_chunks(self, file_id: uuid.UUID) -> Iterator[bytes]: ...

    def store_export(
        self,
        *,
        vacancy_id: uuid.UUID,
        kind: str,
        name: str,
        write: Callable[[BinaryIO], None],
        created_by: uuid.UUID,
    ) -> uuid.UUID:
        """Guarda un Excel (``kind="reporte"``) o un ZIP (``kind="paquete"``)."""
        ...


@dataclass(frozen=True)
class RubricCriterion:
    code: str
    name: str
    weight: Decimal


@dataclass(frozen=True)
class Rubric:
    """El prompt aprobado con el que se evalúa."""

    prompt_version_id: uuid.UUID
    version_number: int
    system_prompt: str
    criteria: tuple[RubricCriterion, ...]
    threshold: Decimal


class Rubrics(Protocol):
    def approved(self, vacancy_id: uuid.UUID) -> Rubric | None: ...

    def get(self, prompt_version_id: uuid.UUID) -> Rubric | None: ...


@dataclass(frozen=True)
class AiAnswer:
    ok: bool
    text: str
    complete: bool
    error: str | None
    execution_id: uuid.UUID


class Extractor(Protocol):
    def extract(
        self, *, system: str, user: str, vacancy_id: uuid.UUID, actor_user_id: uuid.UUID
    ) -> AiAnswer | None:
        """Ordena los datos del CV. ``None`` si esa operación no tiene un modelo
        utilizable en este momento: la extracción es opcional."""
        ...


class Evaluator(Protocol):
    def ensure_ready(self) -> None:
        """Lanza un error de negocio si no se puede evaluar ahora (sin modelo,
        sin clave, documentos no autorizados o límite de gasto alcanzado)."""
        ...

    def evaluate(
        self, *, system: str, user: str, vacancy_id: uuid.UUID, actor_user_id: uuid.UUID
    ) -> AiAnswer:
        """Un fallo del proveedor se devuelve; las comprobaciones previas lanzan."""
        ...
