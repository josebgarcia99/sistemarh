"""Backend de datos sobre SQL Server."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy.orm import Session, sessionmaker

from app.composition.backend import Repositories
from app.modules.ai_settings.infrastructure.sql_repository import SqlAiRepository
from app.modules.audit.infrastructure.sql_repository import SqlAuditRepository
from app.modules.authentication.infrastructure.sql_repository import SqlSessionRepository
from app.modules.file_management.infrastructure.sql_repository import SqlFileRepository
from app.modules.users.infrastructure.sql_repository import SqlUserRepository
from app.modules.vacancies.infrastructure.sql_repository import SqlVacancyRepository
from app.modules.vacancy_transfers.infrastructure.sql_repository import SqlTransferRepository


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
                vacancies=SqlVacancyRepository(session),
                transfers=SqlTransferRepository(session),
                files=SqlFileRepository(session),
                ai=SqlAiRepository(session),
            )
            session.commit()
        except BaseException:
            session.rollback()
            raise
        finally:
            session.close()
