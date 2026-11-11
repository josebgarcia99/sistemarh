"""Lotes de evaluación de CV. Cada paso tiene un estado explícito."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any, Protocol

from app.modules.cv_processing.domain.scoring import Classification


class BatchStatus(StrEnum):
    PENDIENTE = "PENDIENTE"
    EN_COLA = "EN_COLA"
    PROCESANDO = "PROCESANDO"
    COMPLETADO = "COMPLETADO"
    COMPLETADO_CON_INCIDENCIAS = "COMPLETADO_CON_INCIDENCIAS"
    FALLIDO = "FALLIDO"
    CANCELADO = "CANCELADO"


ACTIVE = frozenset({BatchStatus.PENDIENTE, BatchStatus.EN_COLA, BatchStatus.PROCESANDO})


class ItemStatus(StrEnum):
    PENDIENTE = "PENDIENTE"
    EVALUADO = "EVALUADO"
    FALLIDO = "FALLIDO"


class ItemStep(StrEnum):
    """Último paso completado del CV."""

    RECIBIDO = "RECIBIDO"
    TEXTO_EXTRAIDO = "TEXTO_EXTRAIDO"
    ANALIZADO = "ANALIZADO"
    CALIFICADO = "CALIFICADO"


@dataclass
class Batch:
    id: uuid.UUID
    vacancy_id: uuid.UUID
    prompt_version_id: uuid.UUID
    status: BatchStatus
    total: int
    created_at: datetime
    created_by: uuid.UUID
    started_at: datetime | None = None
    finished_at: datetime | None = None
    # Motivo si el lote se detuvo (por ejemplo, se alcanzó el límite de gasto).
    error: str | None = None
    report_file_id: uuid.UUID | None = None
    accepted_zip_file_id: uuid.UUID | None = None
    rejected_zip_file_id: uuid.UUID | None = None
    unevaluable_zip_file_id: uuid.UUID | None = None
    # Quién lo está procesando y hasta cuándo: evita dos procesos sobre un lote.
    runner_token: str | None = None
    lease_until: datetime | None = None


@dataclass
class BatchItem:
    id: uuid.UUID
    batch_id: uuid.UUID
    file_id: uuid.UUID
    position: int
    status: ItemStatus
    step: ItemStep
    updated_at: datetime
    attempts: int = 0
    classification: Classification | None = None
    score: Decimal | None = None
    # Niveles, evidencias y justificaciones. No se sobrescribe con decisiones posteriores.
    result: dict[str, Any] | None = None
    error_code: str | None = None
    error_message: str | None = None
    # Otro CV del mismo lote con el mismo contenido; no se evalúa dos veces.
    duplicate_of: uuid.UUID | None = None
    execution_id: uuid.UUID | None = None


class CvBatchRepository(Protocol):
    def add_batch(self, batch: Batch) -> None: ...

    def save_batch(self, batch: Batch) -> None: ...

    def get_batch(self, batch_id: uuid.UUID) -> Batch | None: ...

    def batches_for_vacancy(self, vacancy_id: uuid.UUID) -> list[Batch]: ...

    def active_batch_ids(self) -> list[uuid.UUID]: ...

    def take_lease(
        self, batch_id: uuid.UUID, token: str, *, now: datetime, until: datetime
    ) -> bool:
        """Toma o renueva el lote para un proceso. Falso si otro lo tiene vigente."""
        ...

    def add_items(self, items: list[BatchItem]) -> None: ...

    def save_item(self, item: BatchItem) -> None: ...

    def get_item(self, item_id: uuid.UUID) -> BatchItem | None: ...

    def next_pending(self, batch_id: uuid.UUID) -> BatchItem | None: ...

    def items(self, batch_id: uuid.UUID) -> list[BatchItem]:
        """En el orden del lote."""
        ...

    def counts(self, batch_ids: list[uuid.UUID]) -> dict[uuid.UUID, dict[str, int]]:
        """Por lote: cuántos CV hay en cada estado y en cada clasificación."""
        ...

    def reopen_failed(self, batch_id: uuid.UUID, now: datetime) -> int:
        """Devuelve a PENDIENTE los CV fallidos. Devuelve cuántos eran."""
        ...

    def evaluated_file_ids(
        self, vacancy_id: uuid.UUID, prompt_version_id: uuid.UUID
    ) -> set[uuid.UUID]:
        """CV de la vacante que ya se evaluaron con esa versión del prompt."""
        ...
