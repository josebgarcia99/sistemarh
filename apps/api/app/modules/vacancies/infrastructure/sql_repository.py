"""Repositorio de vacantes sobre SQL Server (SQLAlchemy)."""

from __future__ import annotations

import uuid
from dataclasses import fields

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.core.exceptions.errors import ConflictError
from app.modules.vacancies.domain.models import (
    AccessType,
    Member,
    Scope,
    SensitiveClass,
    SensitiveGrant,
    Vacancy,
    VacancyStatus,
    WorkMode,
)
from app.modules.vacancies.infrastructure.orm import (
    VacancyMemberRow,
    VacancyRow,
    VacancySensitiveGrantRow,
)

_VACANCY_FIELDS = tuple(f.name for f in fields(Vacancy) if f.name != "id")
_MEMBER_FIELDS = tuple(f.name for f in fields(Member) if f.name != "id")
_GRANT_FIELDS = tuple(f.name for f in fields(SensitiveGrant) if f.name != "id")


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _vacancy(row: VacancyRow) -> Vacancy:
    values = {name: getattr(row, name) for name in _VACANCY_FIELDS}
    values["work_mode"] = WorkMode(row.work_mode)
    values["status"] = VacancyStatus(row.status)
    return Vacancy(id=row.id, **values)


def _member(row: VacancyMemberRow) -> Member:
    values = {name: getattr(row, name) for name in _MEMBER_FIELDS}
    values["access_type"] = AccessType(row.access_type)
    return Member(id=row.id, **values)


def _grant(row: VacancySensitiveGrantRow) -> SensitiveGrant:
    values = {name: getattr(row, name) for name in _GRANT_FIELDS}
    values["document_class"] = SensitiveClass(row.document_class)
    return SensitiveGrant(id=row.id, **values)


def _plain(value: object) -> object:
    # Los enumerados de texto se guardan por su valor.
    return getattr(value, "value", value)


class SqlVacancyRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    # --- Vacantes --------------------------------------------------------------

    def add(self, vacancy: Vacancy) -> None:
        self._session.add(
            VacancyRow(id=vacancy.id, **{n: _plain(getattr(vacancy, n)) for n in _VACANCY_FIELDS})
        )
        self._session.flush()

    def save(self, vacancy: Vacancy) -> None:
        values = {n: _plain(getattr(vacancy, n)) for n in _VACANCY_FIELDS}
        values["version"] = vacancy.version + 1
        # La condición sobre la versión hace que dos guardados simultáneos no se
        # pisen: el segundo no encuentra la fila y se rechaza.
        result = self._session.execute(
            sa.update(VacancyRow)
            .where(VacancyRow.id == vacancy.id, VacancyRow.version == vacancy.version)
            .values(**values)
            .execution_options(synchronize_session=False)
        )
        if result.rowcount != 1:
            raise ConflictError(
                "Otra persona modificó esta vacante. Vuelve a cargarla antes de guardar."
            )
        self._session.expire_all()
        vacancy.version += 1

    def get(self, vacancy_id: uuid.UUID) -> Vacancy | None:
        row = self._session.get(VacancyRow, vacancy_id)
        return _vacancy(row) if row else None

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
        membership = sa.and_(
            VacancyMemberRow.vacancy_id == VacancyRow.id,
            VacancyMemberRow.revoked_at.is_(None),
            # Sin espectador (administrador que lista todo) no se une ninguna fila.
            VacancyMemberRow.user_id == viewer_id if viewer_id is not None else sa.false(),
        )
        query = sa.select(VacancyRow, VacancyMemberRow.access_type).outerjoin(
            VacancyMemberRow, membership
        )
        conditions: list[sa.ColumnElement[bool]] = []
        if viewer_id is not None:
            owned = VacancyRow.owner_user_id == viewer_id
            shared = VacancyMemberRow.id.is_not(None)
            if scope is Scope.MINE:
                conditions.append(owned)
            elif scope is Scope.SHARED:
                conditions.append(shared)
            else:
                conditions.append(sa.or_(owned, shared))
        if status is not None:
            conditions.append(VacancyRow.status == status.value)
        if text:
            pattern = f"%{_escape_like(text.lower())}%"
            conditions.append(
                sa.or_(
                    sa.func.lower(VacancyRow.name).like(pattern, escape="\\"),
                    sa.func.lower(VacancyRow.department).like(pattern, escape="\\"),
                )
            )
        query = query.where(*conditions)
        total = self._session.execute(
            sa.select(sa.func.count()).select_from(query.subquery())
        ).scalar_one()
        rows = self._session.execute(
            query.order_by(VacancyRow.created_at.desc(), VacancyRow.id).offset(offset).limit(limit)
        ).all()
        return [
            (_vacancy(row), AccessType(access) if access else None) for row, access in rows
        ], total

    def owned_by(self, user_id: uuid.UUID) -> list[Vacancy]:
        rows = self._session.execute(
            sa.select(VacancyRow)
            .where(VacancyRow.owner_user_id == user_id)
            .order_by(VacancyRow.created_at, VacancyRow.id)
        ).scalars()
        return [_vacancy(row) for row in rows]

    # --- Acceso compartido -------------------------------------------------------

    def active_member(self, vacancy_id: uuid.UUID, user_id: uuid.UUID) -> Member | None:
        row = self._session.execute(
            sa.select(VacancyMemberRow).where(
                VacancyMemberRow.vacancy_id == vacancy_id,
                VacancyMemberRow.user_id == user_id,
                VacancyMemberRow.revoked_at.is_(None),
            )
        ).scalar_one_or_none()
        return _member(row) if row else None

    def active_members(self, vacancy_id: uuid.UUID) -> list[Member]:
        rows = self._session.execute(
            sa.select(VacancyMemberRow)
            .where(VacancyMemberRow.vacancy_id == vacancy_id, VacancyMemberRow.revoked_at.is_(None))
            .order_by(VacancyMemberRow.granted_at, VacancyMemberRow.id)
        ).scalars()
        return [_member(row) for row in rows]

    def memberships_of(self, user_id: uuid.UUID) -> list[Member]:
        rows = self._session.execute(
            sa.select(VacancyMemberRow).where(
                VacancyMemberRow.user_id == user_id, VacancyMemberRow.revoked_at.is_(None)
            )
        ).scalars()
        return [_member(row) for row in rows]

    def add_member(self, member: Member) -> None:
        self._session.add(
            VacancyMemberRow(
                id=member.id, **{n: _plain(getattr(member, n)) for n in _MEMBER_FIELDS}
            )
        )
        self._session.flush()

    def save_member(self, member: Member) -> None:
        row = self._session.get(VacancyMemberRow, member.id)
        if row is None:
            raise LookupError(f"Acceso inexistente: {member.id}")
        for name in _MEMBER_FIELDS:
            setattr(row, name, _plain(getattr(member, name)))
        self._session.flush()

    # --- Permisos de documentos sensibles ------------------------------------------

    def active_grants(
        self, *, vacancy_id: uuid.UUID | None = None, user_id: uuid.UUID | None = None
    ) -> list[SensitiveGrant]:
        query = sa.select(VacancySensitiveGrantRow).where(
            VacancySensitiveGrantRow.revoked_at.is_(None)
        )
        if vacancy_id is not None:
            query = query.where(VacancySensitiveGrantRow.vacancy_id == vacancy_id)
        if user_id is not None:
            query = query.where(VacancySensitiveGrantRow.user_id == user_id)
        return [_grant(row) for row in self._session.execute(query).scalars()]

    def add_grant(self, grant: SensitiveGrant) -> None:
        self._session.add(
            VacancySensitiveGrantRow(
                id=grant.id, **{n: _plain(getattr(grant, n)) for n in _GRANT_FIELDS}
            )
        )
        self._session.flush()

    def save_grant(self, grant: SensitiveGrant) -> None:
        row = self._session.get(VacancySensitiveGrantRow, grant.id)
        if row is None:
            raise LookupError(f"Permiso inexistente: {grant.id}")
        for name in _GRANT_FIELDS:
            setattr(row, name, _plain(getattr(grant, name)))
        self._session.flush()
