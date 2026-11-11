"""Repositorios de prueba en memoria.

Sirven para probar reglas de negocio y rutas mientras no exista una instancia
de SQL Server autorizada. No sustituyen la validación contra SQL Server: lo que
falta validar está en ``docs/estado_proyecto.md``.
"""

from __future__ import annotations

import copy
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime

from app.composition.backend import Repositories
from app.modules.audit.domain.models import AuditEvent
from app.modules.authentication.domain.models import AuthSession
from app.modules.users.domain.models import Role, User


class _Store:
    def __init__(self) -> None:
        self.users: dict[uuid.UUID, User] = {}
        self.sessions: dict[uuid.UUID, AuthSession] = {}
        self.audit: list[AuditEvent] = []


class MemoryUserRepository:
    def __init__(self, store: _Store) -> None:
        self._store = store

    def add(self, user: User) -> None:
        if any(u.email == user.email for u in self._store.users.values()):
            raise ValueError("Correo duplicado")
        self._store.users[user.id] = copy.deepcopy(user)

    def save(self, user: User) -> None:
        if user.id not in self._store.users:
            raise LookupError(f"Usuario inexistente: {user.id}")
        self._store.users[user.id] = copy.deepcopy(user)

    def get(self, user_id: uuid.UUID) -> User | None:
        return copy.deepcopy(self._store.users.get(user_id))

    def get_by_email(self, email: str) -> User | None:
        for user in self._store.users.values():
            if user.email == email:
                return copy.deepcopy(user)
        return None

    def list(self, *, search: str | None, offset: int, limit: int) -> tuple[list[User], int]:
        users = list(self._store.users.values())
        if search:
            needle = search.lower()
            users = [u for u in users if needle in u.email.lower() or needle in u.full_name.lower()]
        users.sort(key=lambda u: (u.full_name, str(u.id)))
        return copy.deepcopy(users[offset : offset + limit]), len(users)

    def count_active_admins(self) -> int:
        return sum(
            1 for u in self._store.users.values() if u.is_active and u.role is Role.ADMINISTRADOR
        )


class MemorySessionRepository:
    def __init__(self, store: _Store) -> None:
        self._store = store

    def add(self, session: AuthSession) -> None:
        self._store.sessions[session.id] = copy.deepcopy(session)

    def save(self, session: AuthSession) -> None:
        if session.id not in self._store.sessions:
            raise LookupError(f"Sesión inexistente: {session.id}")
        self._store.sessions[session.id] = copy.deepcopy(session)

    def get_by_token_hash(self, token_hash: str) -> AuthSession | None:
        for session in self._store.sessions.values():
            if session.token_hash == token_hash:
                return copy.deepcopy(session)
        return None

    def revoke_all_for_user(self, user_id: uuid.UUID, at: datetime) -> int:
        count = 0
        for session in self._store.sessions.values():
            if session.user_id == user_id and session.revoked_at is None:
                session.revoked_at = at
                count += 1
        return count


class MemoryAuditRepository:
    def __init__(self, store: _Store) -> None:
        self._store = store

    def add(self, event: AuditEvent) -> None:
        self._store.audit.append(event)

    def list(self, *, action: str | None, offset: int, limit: int) -> tuple[list[AuditEvent], int]:
        events = [e for e in self._store.audit if action is None or e.action == action]
        events.sort(key=lambda e: (e.occurred_at, str(e.id)), reverse=True)
        return events[offset : offset + limit], len(events)


class MemoryBackend:
    """Backend en memoria con confirmación y reversión reales."""

    def __init__(self) -> None:
        self._store = _Store()

    @contextmanager
    def transaction(self) -> Iterator[Repositories]:
        snapshot = copy.deepcopy(self._store)
        try:
            yield Repositories(
                users=MemoryUserRepository(self._store),
                sessions=MemorySessionRepository(self._store),
                audit=MemoryAuditRepository(self._store),
            )
        except BaseException:
            # Reversión: se descarta todo lo escrito durante la transacción.
            self._store.__dict__.update(snapshot.__dict__)
            raise
