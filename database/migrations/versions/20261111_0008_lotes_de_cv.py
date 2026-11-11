"""Evaluación de CV por lotes.

Revisión: 0008
Anterior: 0007
Fecha: 2026-11-11

Crea ``ai.cv_batches`` (un lote: qué vacante, con qué versión aprobada del
prompt, su estado y sus archivos generados) y ``ai.cv_batch_items`` (un CV del
lote: paso alcanzado, clasificación inicial, puntuación y resultado). Amplía
los tipos de documento de ``files.file_assets`` con los que genera el sistema:
el Excel de evaluación y los ZIP de CV.

Reversión: ``downgrade`` elimina las dos tablas y restaura la lista anterior
de tipos de documento. Se pierden los resultados de evaluación. Falla, a
propósito, si quedan documentos generados registrados: hay que eliminarlos
antes de forma controlada.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mssql

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

GUID = mssql.UNIQUEIDENTIFIER()
UTC = mssql.DATETIME2(precision=3)

_OLD_TYPES = (
    "'CV', 'PERFIL_PUESTO', 'PSICOMETRIA', 'PRUEBA_TECNICA', 'ESTUDIO_SOCIOECONOMICO', 'ADJUNTO'"
)
_NEW_TYPES = _OLD_TYPES + ", 'REPORTE_EVALUACION', 'PAQUETE_CV'"
_BATCH_STATES = (
    "'PENDIENTE', 'EN_COLA', 'PROCESANDO', 'COMPLETADO', 'COMPLETADO_CON_INCIDENCIAS', "
    "'FALLIDO', 'CANCELADO'"
)


def _document_types(allowed: str) -> None:
    op.drop_constraint("ck_file_assets_document_type", "file_assets", schema="files")
    op.create_check_constraint(
        "ck_file_assets_document_type",
        "file_assets",
        f"document_type IN ({allowed})",
        schema="files",
    )


def upgrade() -> None:
    _document_types(_NEW_TYPES)
    op.create_table(
        "cv_batches",
        sa.Column("id", GUID, nullable=False),
        sa.Column("vacancy_id", GUID, nullable=False),
        sa.Column("prompt_version_id", GUID, nullable=False),
        sa.Column("status", sa.VARCHAR(30), nullable=False),
        sa.Column("total", sa.Integer(), nullable=False),
        sa.Column("error", sa.NVARCHAR(500), nullable=True),
        sa.Column("created_at", UTC, nullable=False),
        sa.Column("created_by", GUID, nullable=False),
        sa.Column("started_at", UTC, nullable=True),
        sa.Column("finished_at", UTC, nullable=True),
        sa.Column("report_file_id", GUID, nullable=True),
        sa.Column("accepted_zip_file_id", GUID, nullable=True),
        sa.Column("rejected_zip_file_id", GUID, nullable=True),
        sa.Column("unevaluable_zip_file_id", GUID, nullable=True),
        sa.Column("runner_token", sa.VARCHAR(40), nullable=True),
        sa.Column("lease_until", UTC, nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_cv_batches"),
        sa.ForeignKeyConstraint(
            ["vacancy_id"], ["vacancy.vacancies.id"], name="fk_cv_batches_vacancy"
        ),
        sa.ForeignKeyConstraint(
            ["prompt_version_id"], ["ai.prompt_versions.id"], name="fk_cv_batches_prompt"
        ),
        sa.ForeignKeyConstraint(["created_by"], ["auth.users.id"], name="fk_cv_batches_creator"),
        sa.ForeignKeyConstraint(
            ["report_file_id"], ["files.file_assets.id"], name="fk_cv_batches_report"
        ),
        sa.ForeignKeyConstraint(
            ["accepted_zip_file_id"], ["files.file_assets.id"], name="fk_cv_batches_accepted"
        ),
        sa.ForeignKeyConstraint(
            ["rejected_zip_file_id"], ["files.file_assets.id"], name="fk_cv_batches_rejected"
        ),
        sa.ForeignKeyConstraint(
            ["unevaluable_zip_file_id"],
            ["files.file_assets.id"],
            name="fk_cv_batches_unevaluable",
        ),
        sa.CheckConstraint(f"status IN ({_BATCH_STATES})", name="ck_cv_batches_status"),
        sa.CheckConstraint("total >= 1", name="ck_cv_batches_total"),
        schema="ai",
    )
    op.create_index(
        "ix_cv_batches_vacancy", "cv_batches", ["vacancy_id", "created_at"], schema="ai"
    )
    op.create_index("ix_cv_batches_status", "cv_batches", ["status"], schema="ai")

    op.create_table(
        "cv_batch_items",
        sa.Column("id", GUID, nullable=False),
        sa.Column("batch_id", GUID, nullable=False),
        sa.Column("file_id", GUID, nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("status", sa.VARCHAR(20), nullable=False),
        sa.Column("step", sa.VARCHAR(20), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("classification", sa.VARCHAR(20), nullable=True),
        sa.Column("score", sa.Numeric(5, 2), nullable=True),
        sa.Column("result", sa.NVARCHAR(None), nullable=True),
        sa.Column("error_code", sa.VARCHAR(40), nullable=True),
        sa.Column("error_message", sa.NVARCHAR(500), nullable=True),
        sa.Column("duplicate_of", GUID, nullable=True),
        # Sin clave foránea a propósito: el consumo tiene su propia conservación.
        sa.Column("execution_id", GUID, nullable=True),
        sa.Column("updated_at", UTC, nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_cv_batch_items"),
        sa.ForeignKeyConstraint(["batch_id"], ["ai.cv_batches.id"], name="fk_cv_batch_items_batch"),
        sa.ForeignKeyConstraint(
            ["file_id"], ["files.file_assets.id"], name="fk_cv_batch_items_file"
        ),
        sa.ForeignKeyConstraint(
            ["duplicate_of"], ["ai.cv_batch_items.id"], name="fk_cv_batch_items_duplicate"
        ),
        sa.UniqueConstraint("batch_id", "position", name="uq_cv_batch_items_position"),
        sa.UniqueConstraint("batch_id", "file_id", name="uq_cv_batch_items_file"),
        sa.CheckConstraint(
            "status IN ('PENDIENTE', 'EVALUADO', 'FALLIDO')", name="ck_cv_batch_items_status"
        ),
        sa.CheckConstraint(
            "step IN ('RECIBIDO', 'TEXTO_EXTRAIDO', 'ANALIZADO', 'CALIFICADO')",
            name="ck_cv_batch_items_step",
        ),
        sa.CheckConstraint(
            "classification IS NULL OR classification IN "
            "('ACEPTADO_IA', 'RECHAZADO_IA', 'NO_EVALUABLE')",
            name="ck_cv_batch_items_classification",
        ),
        sa.CheckConstraint(
            "score IS NULL OR (score >= 0 AND score <= 100)", name="ck_cv_batch_items_score"
        ),
        schema="ai",
    )
    op.create_index(
        "ix_cv_batch_items_status", "cv_batch_items", ["batch_id", "status"], schema="ai"
    )
    op.create_index("ix_cv_batch_items_file", "cv_batch_items", ["file_id"], schema="ai")


def downgrade() -> None:
    op.drop_table("cv_batch_items", schema="ai")
    op.drop_table("cv_batches", schema="ai")
    _document_types(_OLD_TYPES)
