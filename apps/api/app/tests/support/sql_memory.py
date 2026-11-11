"""Backend de pruebas: los repositorios reales sobre un motor SQL en memoria.

Todavía no hay una instancia de SQL Server autorizada. Las pruebas ejecutan el
mismo código de repositorios que usará producción, pero sobre un motor en
memoria, únicamente dentro de las pruebas. Esto detecta errores de reglas,
mapeo y consultas; NO valida el comportamiento propio de SQL Server (tipos,
intercalación, bloqueos, paginación). Lo pendiente está en
``docs/estado_proyecto.md``.

La aplicación en ejecución sigue rechazando cualquier motor distinto de SQL
Server (``validate_database_url``).
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy import event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.composition.sql_backend import SqlBackend
from app.infrastructure.database.base import (
    SCHEMA_AUTH,
    SCHEMA_FILES,
    SCHEMA_OPS,
    SCHEMA_VACANCY,
    Base,
)
from app.modules.users.infrastructure.orm import RoleRow


def build_test_backend() -> SqlBackend:
    engine = sa.create_engine(
        "sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False}
    )

    @event.listens_for(engine, "connect")
    def _enforce_foreign_keys(connection, _record):  # noqa: ANN001
        connection.execute("PRAGMA foreign_keys=ON")

    scoped = engine.execution_options(
        schema_translate_map={
            SCHEMA_AUTH: None,
            SCHEMA_OPS: None,
            SCHEMA_VACANCY: None,
            SCHEMA_FILES: None,
        }
    )
    Base.metadata.create_all(scoped)
    factory = sessionmaker(bind=scoped, expire_on_commit=False)
    with factory() as session:
        session.add_all(
            [
                RoleRow(code="ADMINISTRADOR", name="Administrador"),
                RoleRow(code="RECLUTADOR", name="Reclutador"),
            ]
        )
        session.commit()
    return SqlBackend(factory)
