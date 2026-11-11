"""Perfiles de puesto y prompts de evaluación.

Revisión: 0006
Anterior: 0005
Fecha: 2026-11-11

Crea ``vacancy.job_profile_versions`` (versiones del perfil de cada vacante),
``ai.prompt_versions`` (versiones del prompt, con sus diez capas) y
``ai.rubric_criteria`` (criterios de la rúbrica de cada versión).

Reversión: ``downgrade`` elimina las tres tablas. Se pierden los perfiles, los
prompts y sus aprobaciones.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mssql

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

GUID = mssql.UNIQUEIDENTIFIER()
UTC = mssql.DATETIME2(precision=3)


def _user_fk(table: str, column: str) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint([column], ["auth.users.id"], name=f"fk_{table}_{column}")


def upgrade() -> None:
    op.create_table(
        "job_profile_versions",
        sa.Column("id", GUID, nullable=False),
        sa.Column("vacancy_id", GUID, nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("origin", sa.VARCHAR(20), nullable=False),
        # Contenido estructurado del perfil, en JSON.
        sa.Column("content", sa.NVARCHAR(None), nullable=False),
        sa.Column("change_note", sa.NVARCHAR(300), nullable=True),
        sa.Column("source_file_id", GUID, nullable=True),
        sa.Column("created_at", UTC, nullable=False),
        sa.Column("created_by", GUID, nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_job_profile_versions"),
        sa.UniqueConstraint("vacancy_id", "version_number", name="uq_job_profile_versions_number"),
        sa.ForeignKeyConstraint(
            ["vacancy_id"], ["vacancy.vacancies.id"], name="fk_job_profile_versions_vacancy"
        ),
        sa.ForeignKeyConstraint(
            ["source_file_id"], ["files.file_assets.id"], name="fk_job_profile_versions_file"
        ),
        _user_fk("job_profile_versions", "created_by"),
        sa.CheckConstraint("origin IN ('MANUAL', 'IA')", name="ck_job_profile_versions_origin"),
        sa.CheckConstraint("version_number >= 1", name="ck_job_profile_versions_number"),
        sa.CheckConstraint("ISJSON(content) = 1", name="ck_job_profile_versions_json"),
        schema="vacancy",
    )

    op.create_table(
        "prompt_versions",
        sa.Column("id", GUID, nullable=False),
        sa.Column("vacancy_id", GUID, nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("status", sa.VARCHAR(20), nullable=False),
        sa.Column("profile_version_id", GUID, nullable=False),
        sa.Column("pass_threshold", sa.Numeric(5, 2), nullable=False),
        # Las diez capas del prompt, en JSON.
        sa.Column("layers", sa.NVARCHAR(None), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("duplicated_from", GUID, nullable=True),
        sa.Column("created_at", UTC, nullable=False),
        sa.Column("created_by", GUID, nullable=False),
        sa.Column("updated_at", UTC, nullable=False),
        sa.Column("updated_by", GUID, nullable=False),
        sa.Column("submitted_at", UTC, nullable=True),
        sa.Column("submitted_by", GUID, nullable=True),
        sa.Column("approved_at", UTC, nullable=True),
        sa.Column("approved_by", GUID, nullable=True),
        sa.Column("archived_at", UTC, nullable=True),
        sa.Column("archived_by", GUID, nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_prompt_versions"),
        sa.UniqueConstraint("vacancy_id", "version_number", name="uq_prompt_versions_number"),
        sa.ForeignKeyConstraint(
            ["vacancy_id"], ["vacancy.vacancies.id"], name="fk_prompt_versions_vacancy"
        ),
        sa.ForeignKeyConstraint(
            ["profile_version_id"],
            ["vacancy.job_profile_versions.id"],
            name="fk_prompt_versions_profile",
        ),
        sa.ForeignKeyConstraint(
            ["duplicated_from"], ["ai.prompt_versions.id"], name="fk_prompt_versions_duplicated"
        ),
        _user_fk("prompt_versions", "created_by"),
        _user_fk("prompt_versions", "updated_by"),
        _user_fk("prompt_versions", "submitted_by"),
        _user_fk("prompt_versions", "approved_by"),
        _user_fk("prompt_versions", "archived_by"),
        sa.CheckConstraint(
            "status IN ('BORRADOR', 'EN_REVISION', 'APROBADO', 'ARCHIVADO')",
            name="ck_prompt_versions_status",
        ),
        sa.CheckConstraint(
            "pass_threshold > 0 AND pass_threshold <= 100", name="ck_prompt_versions_threshold"
        ),
        # Una versión aprobada siempre registra quién la aprobó y cuándo.
        sa.CheckConstraint(
            "status <> 'APROBADO' OR (approved_at IS NOT NULL AND approved_by IS NOT NULL)",
            name="ck_prompt_versions_approved",
        ),
        sa.CheckConstraint("ISJSON(layers) = 1", name="ck_prompt_versions_layers_json"),
        schema="ai",
    )
    op.create_index(
        "ix_prompt_versions_vacancy_status",
        "prompt_versions",
        ["vacancy_id", "status"],
        schema="ai",
    )

    op.create_table(
        "rubric_criteria",
        sa.Column("id", GUID, nullable=False),
        sa.Column("prompt_version_id", GUID, nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("name", sa.NVARCHAR(200), nullable=False),
        sa.Column("description", sa.NVARCHAR(1000), nullable=False),
        sa.Column("kind", sa.VARCHAR(20), nullable=False),
        sa.Column("weight", sa.Numeric(6, 2), nullable=False),
        # Descripción de los niveles 0 a 4, en JSON.
        sa.Column("levels", sa.NVARCHAR(None), nullable=False),
        sa.Column("origin", sa.VARCHAR(20), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_rubric_criteria"),
        sa.UniqueConstraint("prompt_version_id", "position", name="uq_rubric_criteria_position"),
        sa.ForeignKeyConstraint(
            ["prompt_version_id"], ["ai.prompt_versions.id"], name="fk_rubric_criteria_prompt"
        ),
        sa.CheckConstraint("kind IN ('INDISPENSABLE', 'DESEABLE')", name="ck_rubric_criteria_kind"),
        sa.CheckConstraint("origin IN ('PERFIL', 'MANUAL')", name="ck_rubric_criteria_origin"),
        sa.CheckConstraint("weight >= 0 AND weight <= 100", name="ck_rubric_criteria_weight"),
        sa.CheckConstraint("ISJSON(levels) = 1", name="ck_rubric_criteria_levels_json"),
        schema="ai",
    )


def downgrade() -> None:
    op.drop_table("rubric_criteria", schema="ai")
    op.drop_table("prompt_versions", schema="ai")
    op.drop_table("job_profile_versions", schema="vacancy")
