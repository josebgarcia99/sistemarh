"""Vacantes, acceso compartido y permisos de documentos sensibles."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from enum import IntEnum, StrEnum
from typing import Protocol


class VacancyStatus(StrEnum):
    BORRADOR = "BORRADOR"
    ABIERTA = "ABIERTA"
    PAUSADA = "PAUSADA"
    CERRADA = "CERRADA"
    CANCELADA = "CANCELADA"
    ARCHIVADA = "ARCHIVADA"


# Cambios de estado permitidos. Una vacante cerrada puede reabrirse para
# reutilizarla en otro periodo; una archivada ya no cambia.
ALLOWED_TRANSITIONS: dict[VacancyStatus, frozenset[VacancyStatus]] = {
    VacancyStatus.BORRADOR: frozenset({VacancyStatus.ABIERTA, VacancyStatus.CANCELADA}),
    VacancyStatus.ABIERTA: frozenset(
        {VacancyStatus.PAUSADA, VacancyStatus.CERRADA, VacancyStatus.CANCELADA}
    ),
    VacancyStatus.PAUSADA: frozenset(
        {VacancyStatus.ABIERTA, VacancyStatus.CERRADA, VacancyStatus.CANCELADA}
    ),
    VacancyStatus.CERRADA: frozenset({VacancyStatus.ABIERTA, VacancyStatus.ARCHIVADA}),
    VacancyStatus.CANCELADA: frozenset({VacancyStatus.ARCHIVADA}),
    VacancyStatus.ARCHIVADA: frozenset(),
}


class WorkMode(StrEnum):
    PRESENCIAL = "PRESENCIAL"
    HIBRIDA = "HIBRIDA"
    REMOTA = "REMOTA"


class AccessType(StrEnum):
    """Tipo de acceso que se concede al compartir una vacante."""

    LECTURA = "LECTURA"
    COLABORACION = "COLABORACION"


class AccessLevel(IntEnum):
    """Acceso efectivo de un usuario sobre una vacante, de menor a mayor."""

    LECTURA = 1
    COLABORACION = 2
    RESPONSABLE = 3
    ADMINISTRADOR = 4


class SensitiveClass(StrEnum):
    """Clases de documento que exigen un permiso adicional por persona."""

    PSICOMETRIA = "PSICOMETRIA"
    ESTUDIO_SOCIOECONOMICO = "ESTUDIO_SOCIOECONOMICO"


@dataclass
class Vacancy:
    id: uuid.UUID
    name: str
    department: str
    location: str
    work_mode: WorkMode
    contract_type: str
    description: str
    positions: int
    status: VacancyStatus
    owner_user_id: uuid.UUID
    created_at: datetime
    created_by: uuid.UUID
    updated_at: datetime
    updated_by: uuid.UUID
    notes: str | None = None
    opened_at: datetime | None = None
    closed_at: datetime | None = None
    # Control de concurrencia optimista: cambia en cada guardado.
    version: int = 1


@dataclass
class Member:
    id: uuid.UUID
    vacancy_id: uuid.UUID
    user_id: uuid.UUID
    access_type: AccessType
    granted_by: uuid.UUID
    granted_at: datetime
    revoked_at: datetime | None = None
    revoked_by: uuid.UUID | None = None


@dataclass
class SensitiveGrant:
    id: uuid.UUID
    vacancy_id: uuid.UUID
    user_id: uuid.UUID
    document_class: SensitiveClass
    granted_by: uuid.UUID
    granted_at: datetime
    revoked_at: datetime | None = None
    revoked_by: uuid.UUID | None = None


class Scope(StrEnum):
    MINE = "mine"
    SHARED = "shared"
    ALL = "all"


class VacancyRepository(Protocol):
    def add(self, vacancy: Vacancy) -> None: ...

    def save(self, vacancy: Vacancy) -> None:
        """Guarda y aumenta la versión. Lanza ``ConflictError`` si alguien la cambió antes."""

    def get(self, vacancy_id: uuid.UUID) -> Vacancy | None: ...

    def search(
        self,
        *,
        viewer_id: uuid.UUID | None,
        scope: Scope,
        status: VacancyStatus | None,
        text: str | None,
        offset: int,
        limit: int,
    ) -> tuple[list[tuple[Vacancy, AccessType | None]], int]:
        """``viewer_id`` ``None`` significa sin filtro de acceso (solo administradores)."""

    def owned_by(self, user_id: uuid.UUID) -> list[Vacancy]: ...

    def active_member(self, vacancy_id: uuid.UUID, user_id: uuid.UUID) -> Member | None: ...

    def active_members(self, vacancy_id: uuid.UUID) -> list[Member]: ...

    def memberships_of(self, user_id: uuid.UUID) -> list[Member]: ...

    def add_member(self, member: Member) -> None: ...

    def save_member(self, member: Member) -> None: ...

    def active_grants(
        self, *, vacancy_id: uuid.UUID | None = None, user_id: uuid.UUID | None = None
    ) -> list[SensitiveGrant]: ...

    def add_grant(self, grant: SensitiveGrant) -> None: ...

    def save_grant(self, grant: SensitiveGrant) -> None: ...


class UserInfo(Protocol):
    """Lo que este módulo necesita saber de un usuario."""

    id: uuid.UUID
    full_name: str
    email: str
    is_active: bool

    @property
    def is_admin(self) -> bool: ...


class UserLookup(Protocol):
    def get(self, user_id: uuid.UUID) -> UserInfo | None: ...

    def get_many(self, user_ids: list[uuid.UUID]) -> dict[uuid.UUID, UserInfo]: ...
