"""Transferencias de responsable e historial de propiedad."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Protocol


class TransferKind(StrEnum):
    INDIVIDUAL = "INDIVIDUAL"
    MASIVA = "MASIVA"


@dataclass(frozen=True)
class OwnershipChange:
    """Un cambio de responsable. ``previous_owner_id`` es ``None`` al crear la vacante."""

    id: uuid.UUID
    vacancy_id: uuid.UUID
    previous_owner_id: uuid.UUID | None
    new_owner_id: uuid.UUID
    changed_at: datetime
    reason: str
    authorized_by: uuid.UUID
    transfer_id: uuid.UUID | None = None


@dataclass(frozen=True)
class Transfer:
    """Una operación de transferencia. Su ``id`` la hace idempotente."""

    id: uuid.UUID
    kind: TransferKind
    from_user_id: uuid.UUID
    to_user_id: uuid.UUID
    reason: str
    requested_by: uuid.UUID
    completed_at: datetime
    vacancies_transferred: int
    memberships_revoked: int
    grants_revoked: int
    user_deactivated: bool


class TransferRepository(Protocol):
    def add_transfer(self, transfer: Transfer) -> None: ...

    def get_transfer(self, transfer_id: uuid.UUID) -> Transfer | None: ...

    def add_change(self, change: OwnershipChange) -> None: ...

    def changes_for(self, vacancy_id: uuid.UUID) -> list[OwnershipChange]: ...
