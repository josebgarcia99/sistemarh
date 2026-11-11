"""Configuración de inteligencia artificial.

Revisión: 0005
Anterior: 0004
Fecha: 2026-11-11

Crea el esquema ``ai`` con los proveedores, sus API keys cifradas, el registro
de modelos que cada proveedor informa y el modelo asignado a cada operación.

Las API keys se guardan cifradas con la clave maestra, que no está en la base
de datos. Al revocar o sustituir una clave, su texto cifrado se borra.

Reversión: ``downgrade`` elimina las cuatro tablas y el esquema. Se pierden las
API keys registradas y las asignaciones de modelos.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mssql

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

GUID = mssql.UNIQUEIDENTIFIER()
UTC = mssql.DATETIME2(precision=3)


def _user_fk(column: str, name: str) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint([column], ["auth.users.id"], name=name)


def upgrade() -> None:
    # Sentencia literal: el nombre del esquema es fijo, no un dato de entrada.
    op.execute(
        "IF NOT EXISTS (SELECT 1 FROM sys.schemas WHERE name = N'ai') EXEC(N'CREATE SCHEMA [ai]')"
    )

    op.create_table(
        "providers",
        sa.Column("code", sa.VARCHAR(20), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("monthly_limit_usd", sa.Numeric(12, 2), nullable=True),
        sa.Column("last_test_at", UTC, nullable=True),
        sa.Column("last_test_ok", sa.Boolean(), nullable=True),
        sa.Column("last_test_error", sa.NVARCHAR(300), nullable=True),
        sa.Column("updated_at", UTC, nullable=True),
        sa.Column("updated_by", GUID, nullable=True),
        sa.PrimaryKeyConstraint("code", name="pk_providers"),
        _user_fk("updated_by", "fk_providers_updated_by"),
        sa.CheckConstraint("code IN ('ANTHROPIC', 'OPENAI')", name="ck_providers_code"),
        sa.CheckConstraint(
            "monthly_limit_usd IS NULL OR monthly_limit_usd >= 0", name="ck_providers_limit"
        ),
        schema="ai",
    )

    op.create_table(
        "provider_credentials",
        sa.Column("id", GUID, nullable=False),
        sa.Column("provider_code", sa.VARCHAR(20), nullable=False),
        # Texto cifrado con la clave maestra. Vacío cuando la clave se revocó.
        sa.Column("ciphertext", sa.NVARCHAR(None), nullable=True),
        sa.Column("last4", sa.VARCHAR(4), nullable=False),
        sa.Column("master_key_id", sa.VARCHAR(32), nullable=False),
        sa.Column("created_at", UTC, nullable=False),
        sa.Column("created_by", GUID, nullable=False),
        sa.Column("revoked_at", UTC, nullable=True),
        sa.Column("revoked_by", GUID, nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_provider_credentials"),
        sa.ForeignKeyConstraint(
            ["provider_code"], ["ai.providers.code"], name="fk_provider_credentials_provider"
        ),
        _user_fk("created_by", "fk_provider_credentials_created_by"),
        _user_fk("revoked_by", "fk_provider_credentials_revoked_by"),
        # Una clave vigente conserva su texto cifrado; una revocada, no.
        sa.CheckConstraint(
            "(revoked_at IS NULL AND ciphertext IS NOT NULL) "
            "OR (revoked_at IS NOT NULL AND ciphertext IS NULL)",
            name="ck_provider_credentials_secret",
        ),
        schema="ai",
    )
    op.create_index(
        "uq_provider_credentials_active",
        "provider_credentials",
        ["provider_code"],
        unique=True,
        schema="ai",
        mssql_where=sa.text("revoked_at IS NULL"),
    )

    op.create_table(
        "models",
        sa.Column("id", GUID, nullable=False),
        sa.Column("provider_code", sa.VARCHAR(20), nullable=False),
        sa.Column("model_id", sa.NVARCHAR(200), nullable=False),
        sa.Column("display_name", sa.NVARCHAR(200), nullable=False),
        sa.Column("capabilities", sa.NVARCHAR(None), nullable=True),
        sa.Column("is_available", sa.Boolean(), nullable=False),
        sa.Column("first_seen_at", UTC, nullable=False),
        sa.Column("last_seen_at", UTC, nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_models"),
        sa.UniqueConstraint("provider_code", "model_id", name="uq_models_provider_model"),
        sa.ForeignKeyConstraint(
            ["provider_code"], ["ai.providers.code"], name="fk_models_provider"
        ),
        sa.CheckConstraint(
            "capabilities IS NULL OR ISJSON(capabilities) = 1", name="ck_models_capabilities_json"
        ),
        schema="ai",
    )

    op.create_table(
        "operation_assignments",
        sa.Column("operation", sa.VARCHAR(40), nullable=False),
        sa.Column("model_ref", GUID, nullable=True),
        sa.Column("updated_at", UTC, nullable=True),
        sa.Column("updated_by", GUID, nullable=True),
        sa.PrimaryKeyConstraint("operation", name="pk_operation_assignments"),
        sa.ForeignKeyConstraint(
            ["model_ref"], ["ai.models.id"], name="fk_operation_assignments_model"
        ),
        _user_fk("updated_by", "fk_operation_assignments_updated_by"),
        sa.CheckConstraint(
            "operation IN ('ANALISIS_PERFILES', 'GENERACION_PROMPTS', 'EXTRACCION_CV', "
            "'EVALUACION_DOCUMENTAL', 'ANALISIS_LLAMADAS', 'LECTURA_DOCUMENTOS', "
            "'RESUMEN_PRUEBAS', 'SINTESIS_EXPEDIENTES')",
            name="ck_operation_assignments_operation",
        ),
        schema="ai",
    )


def downgrade() -> None:
    op.drop_table("operation_assignments", schema="ai")
    op.drop_table("models", schema="ai")
    op.drop_table("provider_credentials", schema="ai")
    op.drop_table("providers", schema="ai")
    op.execute("DROP SCHEMA [ai]")
