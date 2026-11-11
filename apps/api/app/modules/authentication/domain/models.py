"""Sesión de usuario guardada en el servidor."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Protocol


@dataclass(frozen=True)
class AuthPolicy:
    idle_timeout: timedelta = timedelta(minutes=30)
    absolute_timeout: timedelta = timedelta(hours=12)
    max_failed_attempts: int = 5
    lock_duration: timedelta = timedelta(minutes=15)
    # La última actividad se actualiza como mucho una vez por intervalo.
    touch_interval: timedelta = timedelta(minutes=1)


@dataclass
class AuthSession:
    id: uuid.UUID
    user_id: uuid.UUID
    token_hash: str
    csrf_token: str
    created_at: datetime
    last_seen_at: datetime
    expires_at: datetime
    ip: str | None = None
    user_agent: str | None = None
    revoked_at: datetime | None = None

    def is_valid(self, now: datetime, idle_timeout: timedelta) -> bool:
        return (
            self.revoked_at is None
            and now < self.expires_at
            and now - self.last_seen_at < idle_timeout
        )


class SessionRepository(Protocol):
    def add(self, session: AuthSession) -> None: ...

    def save(self, session: AuthSession) -> None: ...

    def get_by_token_hash(self, token_hash: str) -> AuthSession | None: ...

    def revoke_all_for_user(self, user_id: uuid.UUID, at: datetime) -> int: ...
