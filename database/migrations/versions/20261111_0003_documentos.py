"""Documentos almacenados.

Revisión: 0003
Anterior: 0002
Fecha: 2026-11-11

Crea el esquema ``files`` y la tabla ``file_assets``: los metadatos de cada
documento guardado en el disco privado del servidor (qué es, de qué vacante,
dónde está, cuánto mide, su SHA-256 y su estado).

Reversión: ``downgrade`` elimina la tabla y el esquema. Los archivos físicos
quedarían en el disco sin registro: no ejecutar en producción sin respaldo.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mssql

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

GUID = mssql.UNIQUEIDENTIFIER()
UTC = mssql.DATETIME2(precision=3)


def upgrade() -> None:
    # Sentencia literal: el nombre del esquema es fijo, no un dato de entrada.
    op.execute(
        "IF NOT EXISTS (SELECT 1 FROM sys.schemas WHERE name = N'files') "
        "EXEC(N'CREATE SCHEMA [files]')"
    )

    op.create_table(
        "file_assets",
        sa.Column("id", GUID, nullable=False),
        sa.Column("vacancy_id", GUID, nullable=False),
        sa.Column("document_type", sa.VARCHAR(40), nullable=False),
        # Clase que exige permiso adicional; vacío en documentos ordinarios.
        sa.Column("sensitive_class", sa.VARCHAR(40), nullable=True),
        sa.Column("original_name", sa.NVARCHAR(200), nullable=False),
        sa.Column("extension", sa.VARCHAR(10), nullable=False),
        sa.Column("content_type", sa.VARCHAR(100), nullable=True),
        sa.Column("size_bytes", sa.BigInteger(), nullable=True),
        sa.Column("sha256", sa.VARCHAR(64), nullable=True),
        sa.Column("storage_backend", sa.VARCHAR(20), nullable=False),
        # Referencia lógica relativa. Nunca una ruta absoluta.
        sa.Column("storage_key", sa.VARCHAR(200), nullable=False),
        sa.Column("status", sa.VARCHAR(20), nullable=False),
        sa.Column("malware_scan", sa.VARCHAR(20), nullable=True),
        sa.Column("failure_code", sa.VARCHAR(40), nullable=True),
        sa.Column("uploaded_by", GUID, nullable=False),
        sa.Column("created_at", UTC, nullable=False),
        sa.Column("confirmed_at", UTC, nullable=True),
        sa.Column("retention_until", UTC, nullable=True),
        sa.Column("deleted_at", UTC, nullable=True),
        sa.Column("deleted_by", GUID, nullable=True),
        sa.Column("deletion_reason", sa.NVARCHAR(500), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_file_assets"),
        sa.UniqueConstraint("storage_key", name="uq_file_assets_storage_key"),
        sa.ForeignKeyConstraint(
            ["vacancy_id"], ["vacancy.vacancies.id"], name="fk_file_assets_vacancy"
        ),
        sa.ForeignKeyConstraint(
            ["uploaded_by"], ["auth.users.id"], name="fk_file_assets_uploaded_by"
        ),
        sa.ForeignKeyConstraint(
            ["deleted_by"], ["auth.users.id"], name="fk_file_assets_deleted_by"
        ),
        sa.CheckConstraint(
            "status IN ('RECIBIENDO', 'CONFIRMADO', 'RECHAZADO', 'FALLIDO', 'ELIMINADO')",
            name="ck_file_assets_status",
        ),
        sa.CheckConstraint(
            "document_type IN ('CV', 'PERFIL_PUESTO', 'PSICOMETRIA', 'PRUEBA_TECNICA', "
            "'ESTUDIO_SOCIOECONOMICO', 'ADJUNTO')",
            name="ck_file_assets_document_type",
        ),
        sa.CheckConstraint(
            "sensitive_class IS NULL OR sensitive_class IN "
            "('PSICOMETRIA', 'ESTUDIO_SOCIOECONOMICO')",
            name="ck_file_assets_sensitive_class",
        ),
        sa.CheckConstraint(
            "malware_scan IS NULL OR malware_scan IN ('LIMPIO', 'NO_ANALIZADO')",
            name="ck_file_assets_malware_scan",
        ),
        # Un documento no se declara guardado sin tamaño, hash y fecha de confirmación.
        sa.CheckConstraint(
            "status NOT IN ('CONFIRMADO', 'ELIMINADO') OR (size_bytes IS NOT NULL "
            "AND sha256 IS NOT NULL AND confirmed_at IS NOT NULL)",
            name="ck_file_assets_confirmed_complete",
        ),
        sa.CheckConstraint(
            "status <> 'ELIMINADO' OR (deleted_at IS NOT NULL AND deleted_by IS NOT NULL "
            "AND deletion_reason IS NOT NULL)",
            name="ck_file_assets_deleted_complete",
        ),
        sa.CheckConstraint("size_bytes IS NULL OR size_bytes >= 0", name="ck_file_assets_size"),
        schema="files",
    )
    op.create_index(
        "ix_file_assets_vacancy", "file_assets", ["vacancy_id", "status"], schema="files"
    )
    op.create_index("ix_file_assets_hash", "file_assets", ["vacancy_id", "sha256"], schema="files")
    op.create_index(
        "ix_file_assets_status", "file_assets", ["status", "created_at"], schema="files"
    )


def downgrade() -> None:
    op.drop_table("file_assets", schema="files")
    op.execute("DROP SCHEMA [files]")
