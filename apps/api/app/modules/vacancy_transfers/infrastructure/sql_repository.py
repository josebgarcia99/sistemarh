"""Repositorio de transferencias sobre SQL Server (SQLAlchemy)."""

from __future__ import annotations

import uuid
from dataclasses import fields

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.modules.vacancy_transfers.domain.models import (
    OwnershipChange,
    Transfer,
    TransferKind,
)
from app.modules.vacancy_transfers.infrastructure.orm import (
    VacancyOwnershipHistoryRow,
    VacancyTransferRow,
)

_TRANSFER_FIELDS = tuple(f.name for f in fields(Transfer) if f.name != "id")
_CHANGE_FIELDS = tuple(f.name for f in fields(OwnershipChange) if f.name != "id")


class SqlTransferRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add_transfer(self, transfer: Transfer) -> None:
        values = {name: getattr(transfer, name) for name in _TRANSFER_FIELDS}
        values["kind"] = transfer.kind.value
        self._session.add(VacancyTransferRow(id=transfer.id, **values))
        self._session.flush()

    def get_transfer(self, transfer_id: uuid.UUID) -> Transfer | None:
        row = self._session.get(VacancyTransferRow, transfer_id)
        if row is None:
            return None
        values = {name: getattr(row, name) for name in _TRANSFER_FIELDS}
        values["kind"] = TransferKind(row.kind)
        return Transfer(id=row.id, **values)

    def add_change(self, change: OwnershipChange) -> None:
        self._session.add(
            VacancyOwnershipHistoryRow(
                id=change.id, **{name: getattr(change, name) for name in _CHANGE_FIELDS}
            )
        )
        self._session.flush()

    def changes_for(self, vacancy_id: uuid.UUID) -> list[OwnershipChange]:
        rows = self._session.execute(
            sa.select(VacancyOwnershipHistoryRow)
            .where(VacancyOwnershipHistoryRow.vacancy_id == vacancy_id)
            .order_by(
                VacancyOwnershipHistoryRow.changed_at.desc(), VacancyOwnershipHistoryRow.id.desc()
            )
        ).scalars()
        return [
            OwnershipChange(id=row.id, **{name: getattr(row, name) for name in _CHANGE_FIELDS})
            for row in rows
        ]
