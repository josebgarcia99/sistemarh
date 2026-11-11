"""Tablas de configuración de IA (esquema ``ai``)."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.base import (
    GUID,
    SCHEMA_AI,
    SCHEMA_AUTH,
    Base,
    UTCDateTime,
    long_text,
)

_USER_FK = f"{SCHEMA_AUTH}.users.id"
_PROVIDER_FK = f"{SCHEMA_AI}.providers.code"


class AiProviderRow(Base):
    __tablename__ = "providers"
    __table_args__ = {"schema": SCHEMA_AI}

    code: Mapped[str] = mapped_column(sa.String(20), primary_key=True)
    enabled: Mapped[bool] = mapped_column(sa.Boolean)
    monthly_limit_usd: Mapped[Decimal | None] = mapped_column(sa.Numeric(12, 2), nullable=True)
    last_test_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    last_test_ok: Mapped[bool | None] = mapped_column(sa.Boolean, nullable=True)
    last_test_error: Mapped[str | None] = mapped_column(sa.Unicode(300), nullable=True)
    updated_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    updated_by: Mapped[uuid.UUID | None] = mapped_column(
        GUID, sa.ForeignKey(_USER_FK), nullable=True
    )


class AiProviderCredentialRow(Base):
    __tablename__ = "provider_credentials"
    __table_args__ = (
        # Una sola clave vigente por proveedor.
        sa.Index(
            "uq_provider_credentials_active",
            "provider_code",
            unique=True,
            mssql_where=sa.text("revoked_at IS NULL"),
            sqlite_where=sa.text("revoked_at IS NULL"),
        ),
        {"schema": SCHEMA_AI},
    )

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True)
    provider_code: Mapped[str] = mapped_column(sa.String(20), sa.ForeignKey(_PROVIDER_FK))
    # Texto cifrado con la clave maestra. Se borra al revocar o sustituir.
    ciphertext: Mapped[str | None] = mapped_column(long_text(), nullable=True)
    last4: Mapped[str] = mapped_column(sa.String(4))
    master_key_id: Mapped[str] = mapped_column(sa.String(32))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime)
    created_by: Mapped[uuid.UUID] = mapped_column(GUID, sa.ForeignKey(_USER_FK))
    revoked_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    revoked_by: Mapped[uuid.UUID | None] = mapped_column(
        GUID, sa.ForeignKey(_USER_FK), nullable=True
    )


class AiModelRow(Base):
    __tablename__ = "models"
    __table_args__ = (
        sa.UniqueConstraint("provider_code", "model_id", name="uq_models_provider_model"),
        {"schema": SCHEMA_AI},
    )

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True)
    provider_code: Mapped[str] = mapped_column(sa.String(20), sa.ForeignKey(_PROVIDER_FK))
    model_id: Mapped[str] = mapped_column(sa.Unicode(200))
    display_name: Mapped[str] = mapped_column(sa.Unicode(200))
    capabilities: Mapped[str | None] = mapped_column(long_text(), nullable=True)
    is_available: Mapped[bool] = mapped_column(sa.Boolean)
    first_seen_at: Mapped[datetime] = mapped_column(UTCDateTime)
    last_seen_at: Mapped[datetime] = mapped_column(UTCDateTime)


class AiOperationAssignmentRow(Base):
    __tablename__ = "operation_assignments"
    __table_args__ = {"schema": SCHEMA_AI}

    operation: Mapped[str] = mapped_column(sa.String(40), primary_key=True)
    model_ref: Mapped[uuid.UUID | None] = mapped_column(
        GUID, sa.ForeignKey(f"{SCHEMA_AI}.models.id"), nullable=True
    )
    updated_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    updated_by: Mapped[uuid.UUID | None] = mapped_column(
        GUID, sa.ForeignKey(_USER_FK), nullable=True
    )
