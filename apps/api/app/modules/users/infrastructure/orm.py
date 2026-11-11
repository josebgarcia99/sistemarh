"""Tablas del dominio de identidad (esquema ``auth``)."""

from __future__ import annotations

import uuid
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.base import GUID, SCHEMA_AUTH, Base, UTCDateTime


class RoleRow(Base):
    __tablename__ = "roles"
    __table_args__ = {"schema": SCHEMA_AUTH}

    code: Mapped[str] = mapped_column(sa.Unicode(30), primary_key=True)
    name: Mapped[str] = mapped_column(sa.Unicode(100))


class UserRow(Base):
    __tablename__ = "users"
    __table_args__ = {"schema": SCHEMA_AUTH}

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True)
    email: Mapped[str] = mapped_column(sa.Unicode(254), unique=True)
    full_name: Mapped[str] = mapped_column(sa.Unicode(200))
    password_hash: Mapped[str] = mapped_column(sa.Unicode(255))
    is_active: Mapped[bool] = mapped_column(sa.Boolean)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        GUID, sa.ForeignKey(f"{SCHEMA_AUTH}.users.id"), nullable=True
    )
    last_activity_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    deactivated_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    password_changed_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    failed_login_count: Mapped[int] = mapped_column(sa.Integer, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)


class UserRoleRow(Base):
    __tablename__ = "user_roles"
    __table_args__ = {"schema": SCHEMA_AUTH}

    user_id: Mapped[uuid.UUID] = mapped_column(
        GUID, sa.ForeignKey(f"{SCHEMA_AUTH}.users.id"), primary_key=True
    )
    role_code: Mapped[str] = mapped_column(
        sa.Unicode(30), sa.ForeignKey(f"{SCHEMA_AUTH}.roles.code"), primary_key=True
    )
