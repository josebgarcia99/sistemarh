"""Registro de los reportes generados (esquema ``ops``)."""

from __future__ import annotations

import uuid
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.base import (
    GUID,
    SCHEMA_AUTH,
    SCHEMA_OPS,
    Base,
    UTCDateTime,
    long_text,
)


class ReportExportRow(Base):
    __tablename__ = "report_exports"
    __table_args__ = (
        sa.Index("ix_report_exports_user", "created_by", "created_at"),
        {"schema": SCHEMA_OPS},
    )

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True)
    kind: Mapped[str] = mapped_column(sa.String(20))
    name: Mapped[str] = mapped_column(sa.Unicode(200))
    # JSON: filtros pedidos y vacantes cuyos datos contiene el archivo.
    filters: Mapped[str] = mapped_column(long_text())
    vacancy_ids: Mapped[str] = mapped_column(long_text())
    row_count: Mapped[int] = mapped_column(sa.Integer)
    storage_key: Mapped[str] = mapped_column(sa.String(200), unique=True)
    size_bytes: Mapped[int] = mapped_column(sa.BigInteger)
    sha256: Mapped[str] = mapped_column(sa.String(64))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime)
    created_by: Mapped[uuid.UUID] = mapped_column(GUID, sa.ForeignKey(f"{SCHEMA_AUTH}.users.id"))
