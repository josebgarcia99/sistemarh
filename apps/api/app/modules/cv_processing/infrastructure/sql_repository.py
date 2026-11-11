"""Repositorio de lotes de CV sobre SQL Server (SQLAlchemy)."""

from __future__ import annotations

import json
import uuid
from dataclasses import fields
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.modules.cv_processing.domain.models import (
    ACTIVE,
    Batch,
    BatchItem,
    BatchStatus,
    ItemStatus,
    ItemStep,
)
from app.modules.cv_processing.domain.scoring import Classification
from app.modules.cv_processing.infrastructure.orm import CvBatchItemRow, CvBatchRow

_BATCH_FIELDS = tuple(f.name for f in fields(Batch) if f.name != "id")
_ITEM_FIELDS = tuple(f.name for f in fields(BatchItem) if f.name != "id")


def _batch_values(batch: Batch) -> dict[str, object]:
    values = {name: getattr(batch, name) for name in _BATCH_FIELDS}
    values["status"] = batch.status.value
    return values


def _to_batch(row: CvBatchRow) -> Batch:
    values = {name: getattr(row, name) for name in _BATCH_FIELDS}
    values["status"] = BatchStatus(row.status)
    return Batch(id=row.id, **values)


def _item_values(item: BatchItem) -> dict[str, object]:
    values = {name: getattr(item, name) for name in _ITEM_FIELDS}
    values["status"] = item.status.value
    values["step"] = item.step.value
    values["classification"] = item.classification.value if item.classification else None
    for name in ("result", "extraction"):
        value = getattr(item, name)
        values[name] = json.dumps(value, ensure_ascii=False) if value is not None else None
    return values


def _to_item(row: CvBatchItemRow) -> BatchItem:
    values = {name: getattr(row, name) for name in _ITEM_FIELDS}
    values["status"] = ItemStatus(row.status)
    values["step"] = ItemStep(row.step)
    values["classification"] = Classification(row.classification) if row.classification else None
    values["result"] = json.loads(row.result) if row.result else None
    values["extraction"] = json.loads(row.extraction) if row.extraction else None
    return BatchItem(id=row.id, **values)


class SqlCvBatchRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    # --- Lotes ---------------------------------------------------------------------------

    def add_batch(self, batch: Batch) -> None:
        self._session.add(CvBatchRow(id=batch.id, **_batch_values(batch)))
        self._session.flush()

    def save_batch(self, batch: Batch) -> None:
        row = self._session.get(CvBatchRow, batch.id)
        if row is None:
            raise LookupError("El lote no existe.")
        for name, value in _batch_values(batch).items():
            setattr(row, name, value)
        self._session.flush()

    def get_batch(self, batch_id: uuid.UUID) -> Batch | None:
        row = self._session.get(CvBatchRow, batch_id)
        if row is None:
            return None
        # Otro proceso pudo cambiar el estado (cancelación): se lee el valor actual.
        self._session.refresh(row)
        return _to_batch(row)

    def batches_for_vacancy(self, vacancy_id: uuid.UUID) -> list[Batch]:
        rows = self._session.execute(
            sa.select(CvBatchRow)
            .where(CvBatchRow.vacancy_id == vacancy_id)
            .order_by(CvBatchRow.created_at.desc(), CvBatchRow.id.desc())
        ).scalars()
        return [_to_batch(row) for row in rows]

    def active_batch_ids(self) -> list[uuid.UUID]:
        return list(
            self._session.execute(
                sa.select(CvBatchRow.id)
                .where(CvBatchRow.status.in_([status.value for status in ACTIVE]))
                .order_by(CvBatchRow.created_at)
            ).scalars()
        )

    def take_lease(
        self, batch_id: uuid.UUID, token: str, *, now: datetime, until: datetime
    ) -> bool:
        # Una sola sentencia: si dos procesos compiten, solo uno actualiza la fila.
        result = self._session.execute(
            sa.update(CvBatchRow)
            .where(
                CvBatchRow.id == batch_id,
                sa.or_(
                    CvBatchRow.runner_token == token,
                    CvBatchRow.lease_until.is_(None),
                    CvBatchRow.lease_until < now,
                ),
            )
            .values(runner_token=token, lease_until=until)
            .execution_options(synchronize_session=False)
        )
        return result.rowcount == 1

    # --- CV del lote ---------------------------------------------------------------------

    def add_items(self, items: list[BatchItem]) -> None:
        self._session.add_all(CvBatchItemRow(id=item.id, **_item_values(item)) for item in items)
        self._session.flush()

    def save_item(self, item: BatchItem) -> None:
        row = self._session.get(CvBatchItemRow, item.id)
        if row is None:
            raise LookupError("El CV no pertenece a ningún lote.")
        for name, value in _item_values(item).items():
            setattr(row, name, value)
        self._session.flush()

    def get_item(self, item_id: uuid.UUID) -> BatchItem | None:
        row = self._session.get(CvBatchItemRow, item_id)
        return _to_item(row) if row is not None else None

    def next_pending(self, batch_id: uuid.UUID) -> BatchItem | None:
        row = self._session.execute(
            sa.select(CvBatchItemRow)
            .where(
                CvBatchItemRow.batch_id == batch_id,
                CvBatchItemRow.status == ItemStatus.PENDIENTE.value,
            )
            .order_by(CvBatchItemRow.position)
            .limit(1)
        ).scalar_one_or_none()
        return _to_item(row) if row is not None else None

    def items(self, batch_id: uuid.UUID) -> list[BatchItem]:
        rows = self._session.execute(
            sa.select(CvBatchItemRow)
            .where(CvBatchItemRow.batch_id == batch_id)
            .order_by(CvBatchItemRow.position)
        ).scalars()
        return [_to_item(row) for row in rows]

    def counts(self, batch_ids: list[uuid.UUID]) -> dict[uuid.UUID, dict[str, int]]:
        if not batch_ids:
            return {}
        rows = self._session.execute(
            sa.select(
                CvBatchItemRow.batch_id,
                CvBatchItemRow.status,
                CvBatchItemRow.classification,
                sa.func.count(),
            )
            .where(CvBatchItemRow.batch_id.in_(batch_ids))
            .group_by(CvBatchItemRow.batch_id, CvBatchItemRow.status, CvBatchItemRow.classification)
        ).all()
        counts: dict[uuid.UUID, dict[str, int]] = {}
        for batch_id, status, classification, amount in rows:
            current = counts.setdefault(batch_id, {})
            current[status] = current.get(status, 0) + amount
            if classification:
                current[classification] = current.get(classification, 0) + amount
        return counts

    def reopen_failed(self, batch_id: uuid.UUID, now: datetime) -> int:
        result = self._session.execute(
            sa.update(CvBatchItemRow)
            .where(
                CvBatchItemRow.batch_id == batch_id,
                CvBatchItemRow.status == ItemStatus.FALLIDO.value,
            )
            .values(status=ItemStatus.PENDIENTE.value, updated_at=now)
            .execution_options(synchronize_session=False)
        )
        self._session.expire_all()
        return result.rowcount

    def evaluated_items(self, vacancy_id: uuid.UUID) -> list[BatchItem]:
        rows = self._session.execute(
            sa.select(CvBatchItemRow)
            .join(CvBatchRow, CvBatchRow.id == CvBatchItemRow.batch_id)
            .where(
                CvBatchRow.vacancy_id == vacancy_id,
                CvBatchItemRow.status == ItemStatus.EVALUADO.value,
            )
            .order_by(CvBatchRow.created_at, CvBatchRow.id, CvBatchItemRow.position)
        ).scalars()
        return [_to_item(row) for row in rows]

    def evaluated_file_ids(
        self, vacancy_id: uuid.UUID, prompt_version_id: uuid.UUID
    ) -> set[uuid.UUID]:
        return set(
            self._session.execute(
                sa.select(CvBatchItemRow.file_id)
                .join(CvBatchRow, CvBatchRow.id == CvBatchItemRow.batch_id)
                .where(
                    CvBatchRow.vacancy_id == vacancy_id,
                    CvBatchRow.prompt_version_id == prompt_version_id,
                    CvBatchItemRow.status == ItemStatus.EVALUADO.value,
                )
            ).scalars()
        )
