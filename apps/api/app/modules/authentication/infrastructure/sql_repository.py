"""Repositorio de sesiones sobre SQL Server (SQLAlchemy)."""

from __future__ import annotations

import uuid
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.modules.authentication.domain.models import AuthSession
from app.modules.authentication.infrastructure.orm import SessionRow

_FIELDS = (
    "user_id",
    "token_hash",
    "csrf_token",
    "created_at",
    "last_seen_at",
    "expires_at",
    "ip",
    "user_agent",
    "revoked_at",
)


class SqlSessionRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, session: AuthSession) -> None:
        self._session.add(SessionRow(id=session.id, **{f: getattr(session, f) for f in _FIELDS}))
        self._session.flush()

    def save(self, session: AuthSession) -> None:
        row = self._session.get(SessionRow, session.id)
        if row is None:
            raise LookupError(f"Sesión inexistente: {session.id}")
        for field in _FIELDS:
            setattr(row, field, getattr(session, field))
        self._session.flush()

    def get_by_token_hash(self, token_hash: str) -> AuthSession | None:
        row = self._session.execute(
            sa.select(SessionRow).where(SessionRow.token_hash == token_hash)
        ).scalar_one_or_none()
        if row is None:
            return None
        return AuthSession(id=row.id, **{f: getattr(row, f) for f in _FIELDS})

    def revoke_all_for_user(self, user_id: uuid.UUID, at: datetime) -> int:
        result = self._session.execute(
            sa.update(SessionRow)
            .where(SessionRow.user_id == user_id, SessionRow.revoked_at.is_(None))
            .values(revoked_at=at)
            .execution_options(synchronize_session="fetch")
        )
        return result.rowcount or 0
