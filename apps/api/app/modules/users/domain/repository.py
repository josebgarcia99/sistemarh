from __future__ import annotations

import uuid
from collections.abc import Iterable
from datetime import datetime
from typing import Protocol

from app.modules.users.domain.models import User


class UserRepository(Protocol):
    def add(self, user: User) -> None: ...

    def save(self, user: User) -> None: ...

    def get(self, user_id: uuid.UUID) -> User | None: ...

    def get_by_email(self, email: str) -> User | None: ...

    def list(self, *, search: str | None, offset: int, limit: int) -> tuple[list[User], int]: ...

    def count_active_admins(self) -> int: ...

    def get_many(self, user_ids: Iterable[uuid.UUID]) -> dict[uuid.UUID, User]: ...

    def search_active(self, *, search: str, limit: int) -> list[User]: ...


class SessionRevoker(Protocol):
    """Lo único que este módulo necesita de las sesiones: poder cerrarlas."""

    def revoke_all_for_user(self, user_id: uuid.UUID, at: datetime) -> int: ...
