"""Consumo de inteligencia artificial.

Revisión: 0007
Anterior: 0006
Fecha: 2026-11-11

Crea ``ai.executions`` (una fila por llamada a un proveedor: tokens, costo
estimado, duración, reintentos y resultado; nunca el contenido enviado ni la
respuesta) y añade a ``ai.models`` el precio por millón de tokens que captura
el administrador.

Reversión: ``downgrade`` elimina la tabla y las dos columnas. Se pierde el
historial de consumo.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mssql

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

GUID = mssql.UNIQUEIDENTIFIER()
UTC = mssql.DATETIME2(precision=3)


def upgrade() -> None:
    op.add_column("models", sa.Column("input_price", sa.Numeric(12, 4), nullable=True), schema="ai")
    op.add_column(
        "models", sa.Column("output_price", sa.Numeric(12, 4), nullable=True), schema="ai"
    )
    op.create_table(
        "executions",
        sa.Column("id", GUID, nullable=False),
        sa.Column("occurred_at", UTC, nullable=False),
        sa.Column("operation", sa.VARCHAR(40), nullable=False),
        sa.Column("provider_code", sa.VARCHAR(20), nullable=False),
        sa.Column("model_id", sa.NVARCHAR(200), nullable=False),
        sa.Column("status", sa.VARCHAR(20), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("estimated_cost_usd", sa.Numeric(12, 6), nullable=True),
        sa.Column("confirmed_cost_usd", sa.Numeric(12, 6), nullable=True),
        sa.Column("error_kind", sa.VARCHAR(20), nullable=True),
        # Sin clave foránea a propósito: el registro de consumo se conserva
        # aunque cambie el usuario o la vacante.
        sa.Column("actor_user_id", GUID, nullable=True),
        sa.Column("vacancy_id", GUID, nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_executions"),
        sa.CheckConstraint("status IN ('CORRECTA', 'FALLIDA')", name="ck_executions_status"),
        sa.CheckConstraint("attempts >= 1", name="ck_executions_attempts"),
        schema="ai",
    )
    op.create_index(
        "ix_executions_provider_date", "executions", ["provider_code", "occurred_at"], schema="ai"
    )
    op.create_index("ix_executions_date", "executions", ["occurred_at"], schema="ai")


def downgrade() -> None:
    op.drop_table("executions", schema="ai")
    op.drop_column("models", "output_price", schema="ai")
    op.drop_column("models", "input_price", schema="ai")
