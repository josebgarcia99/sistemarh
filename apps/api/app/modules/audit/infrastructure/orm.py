"""Tabla de auditoría (esquema ``ops``). Solo admite inserciones."""

from __future__ import annotations

import uuid
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.base import GUID, SCHEMA_OPS, Base, UTCDateTime


class AuditEventRow(Base):
    __tablename__ = "audit_events"
    __table_args__ = (
        sa.Index("ix_audit_events_occurred_at", "occurred_at"),
        sa.Index("ix_audit_events_actor", "actor_user_id", "occurred_at"),
        sa.Index("ix_audit_events_action", "action", "occurred_at"),
        {"schema": SCHEMA_OPS},
    )

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True)
    occurred_at: Mapped[datetime] = mapped_column(UTCDateTime)
    # Sin clave foránea a propósito: la auditoría no debe impedir ni depender de
    # cambios en otras tablas.
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(GUID, nullable=True)
    action: Mapped[str] = mapped_column(sa.String(80))
    result: Mapped[str] = mapped_column(sa.String(20))
    resource_type: Mapped[str | None] = mapped_column(sa.String(60), nullable=True)
    resource_id: Mapped[str | None] = mapped_column(sa.String(64), nullable=True)
    ip: Mapped[str | None] = mapped_column(sa.String(45), nullable=True)
    correlation_id: Mapped[str | None] = mapped_column(sa.String(64), nullable=True)
    details: Mapped[str] = mapped_column(sa.UnicodeText)
