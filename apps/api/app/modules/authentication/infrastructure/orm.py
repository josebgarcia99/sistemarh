"""Tabla de sesiones (esquema ``auth``)."""

from __future__ import annotations

import uuid
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.base import GUID, SCHEMA_AUTH, Base, UTCDateTime


class SessionRow(Base):
    __tablename__ = "sessions"
    __table_args__ = (
        sa.Index("ix_sessions_user_id", "user_id"),
        {"schema": SCHEMA_AUTH},
    )

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(GUID, sa.ForeignKey(f"{SCHEMA_AUTH}.users.id"))
    # SHA-256 en hexadecimal del token; el token en claro nunca se guarda.
    token_hash: Mapped[str] = mapped_column(sa.String(64), unique=True)
    csrf_token: Mapped[str] = mapped_column(sa.String(64))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime)
    last_seen_at: Mapped[datetime] = mapped_column(UTCDateTime)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime)
    ip: Mapped[str | None] = mapped_column(sa.String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(sa.Unicode(300), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
