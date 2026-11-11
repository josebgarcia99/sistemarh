"""Base declarativa y tipos comunes para SQL Server."""

from __future__ import annotations

from datetime import UTC, datetime

import sqlalchemy as sa
from sqlalchemy.dialects import mssql
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.types import TypeDecorator

SCHEMA_AUTH = "auth"
SCHEMA_OPS = "ops"
SCHEMA_VACANCY = "vacancy"

# En SQL Server se materializa como UNIQUEIDENTIFIER.
GUID = sa.Uuid(as_uuid=True)


class UTCDateTime(TypeDecorator[datetime]):
    """Fecha y hora en UTC. En SQL Server es ``DATETIME2(3)``.

    La base guarda el valor sin zona; la aplicación siempre trabaja con fechas
    con zona UTC y rechaza las que no la traen.
    """

    impl = sa.DateTime
    cache_ok = True

    def load_dialect_impl(self, dialect: sa.Dialect) -> sa.types.TypeEngine[datetime]:
        if dialect.name == "mssql":
            return dialect.type_descriptor(mssql.DATETIME2(precision=3))
        return dialect.type_descriptor(sa.DateTime())

    def process_bind_param(self, value: datetime | None, dialect: sa.Dialect) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError("Las fechas deben incluir zona horaria (UTC).")
        return value.astimezone(UTC).replace(tzinfo=None)

    def process_result_value(self, value: datetime | None, dialect: sa.Dialect) -> datetime | None:
        return None if value is None else value.replace(tzinfo=UTC)


class Base(DeclarativeBase):
    pass
