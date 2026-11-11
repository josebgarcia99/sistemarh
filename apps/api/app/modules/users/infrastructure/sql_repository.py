"""Repositorio de usuarios sobre SQL Server (SQLAlchemy)."""

from __future__ import annotations

import uuid

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.modules.users.domain.models import Role, User
from app.modules.users.infrastructure.orm import UserRoleRow, UserRow

_FIELDS = (
    "email",
    "full_name",
    "password_hash",
    "is_active",
    "created_at",
    "created_by",
    "last_activity_at",
    "deactivated_at",
    "password_changed_at",
    "failed_login_count",
    "locked_until",
)


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


class SqlUserRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def _to_domain(self, row: UserRow, role_code: str) -> User:
        return User(id=row.id, role=Role(role_code), **{f: getattr(row, f) for f in _FIELDS})

    def _query(self) -> sa.Select[tuple[UserRow, str]]:
        return sa.select(UserRow, UserRoleRow.role_code).join(
            UserRoleRow, UserRoleRow.user_id == UserRow.id
        )

    def add(self, user: User) -> None:
        self._session.add(UserRow(id=user.id, **{f: getattr(user, f) for f in _FIELDS}))
        self._session.flush()
        self._session.add(UserRoleRow(user_id=user.id, role_code=user.role.value))
        self._session.flush()

    def save(self, user: User) -> None:
        row = self._session.get(UserRow, user.id)
        if row is None:
            raise LookupError(f"Usuario inexistente: {user.id}")
        for field in _FIELDS:
            setattr(row, field, getattr(user, field))
        role_row = self._session.execute(
            sa.select(UserRoleRow).where(UserRoleRow.user_id == user.id)
        ).scalar_one()
        if role_row.role_code != user.role.value:
            self._session.delete(role_row)
            self._session.flush()
            self._session.add(UserRoleRow(user_id=user.id, role_code=user.role.value))
        self._session.flush()

    def get(self, user_id: uuid.UUID) -> User | None:
        result = self._session.execute(self._query().where(UserRow.id == user_id)).first()
        return self._to_domain(*result) if result else None

    def get_by_email(self, email: str) -> User | None:
        result = self._session.execute(self._query().where(UserRow.email == email)).first()
        return self._to_domain(*result) if result else None

    def list(self, *, search: str | None, offset: int, limit: int) -> tuple[list[User], int]:
        query = self._query()
        count = sa.select(sa.func.count()).select_from(UserRow)
        if search:
            pattern = f"%{_escape_like(search.lower())}%"
            condition = sa.or_(
                sa.func.lower(UserRow.email).like(pattern, escape="\\"),
                sa.func.lower(UserRow.full_name).like(pattern, escape="\\"),
            )
            query = query.where(condition)
            count = count.where(condition)
        total = self._session.execute(count).scalar_one()
        # SQL Server exige ORDER BY para paginar con OFFSET/FETCH.
        rows = self._session.execute(
            query.order_by(UserRow.full_name, UserRow.id).offset(offset).limit(limit)
        ).all()
        return [self._to_domain(*row) for row in rows], total

    def count_active_admins(self) -> int:
        return self._session.execute(
            sa.select(sa.func.count())
            .select_from(UserRow)
            .join(UserRoleRow, UserRoleRow.user_id == UserRow.id)
            .where(UserRow.is_active.is_(True), UserRoleRow.role_code == Role.ADMINISTRADOR.value)
        ).scalar_one()
