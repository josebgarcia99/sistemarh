"""Backend de datos sobre SQL Server."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy.orm import Session, sessionmaker

from app.composition.backend import Repositories
from app.modules.audit.infrastructure.sql_repository import SqlAuditRepository
from app.modules.authentication.infrastructure.sql_repository import SqlSessionRepository
from app.modules.users.infrastructure.sql_repository import SqlUserRepository


class SqlBackend:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    @contextmanager
    def transaction(self) -> Iterator[Repositories]:
        session = self._session_factory()
        try:
            yield Repositories(
                users=SqlUserRepository(session),
                sessions=SqlSessionRepository(session),
                audit=SqlAuditRepository(session),
            )
            session.commit()
        except BaseException:
            session.rollback()
            raise
        finally:
            session.close()
