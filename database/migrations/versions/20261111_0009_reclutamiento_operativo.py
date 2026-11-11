"""Reclutamiento operativo: candidatos, postulaciones, etapas, bancos y llamadas.

Revisión: 0009
Anterior: 0008
Fecha: 2026-11-11

Crea el esquema ``recruitment`` con nueve tablas:

- ``pipeline_versions`` y ``pipeline_stages``: las etapas del proceso, por versiones.
- ``campaigns``: convocatorias de una vacante; cada una fija su versión de etapas.
- ``candidates``: personas, con identificador global.
- ``applications``: postulación de una persona en una convocatoria.
- ``application_movements``: historial completo de movimientos; solo recibe altas.
- ``question_banks`` y ``question_bank_versions``: bancos de preguntas por versiones.
- ``call_sessions``: llamadas telefónicas, sus respuestas y su análisis.

Añade a ``ai.cv_batch_items`` la columna ``extraction`` con los datos ordenados
del CV (contacto, experiencia, estudios).

Las etapas iniciales no se insertan aquí: la aplicación las crea la primera
vez que se usan.

Reversión: ``downgrade`` elimina las nueve tablas, el esquema y la columna. Se
pierden candidatos, postulaciones, historial, bancos y llamadas.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mssql

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

GUID = mssql.UNIQUEIDENTIFIER()
UTC = mssql.DATETIME2(precision=3)
S = "recruitment"
MAX = sa.NVARCHAR(None)


def _fk(column: str, target: str, name: str) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint([column], [target], name=name)


def upgrade() -> None:
    op.execute(
        "IF NOT EXISTS (SELECT 1 FROM sys.schemas WHERE name = N'recruitment') "
        "EXEC(N'CREATE SCHEMA [recruitment]')"
    )
    op.add_column("cv_batch_items", sa.Column("extraction", MAX, nullable=True), schema="ai")

    op.create_table(
        "pipeline_versions",
        sa.Column("id", GUID, nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("created_at", UTC, nullable=False),
        sa.Column("created_by", GUID, nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_pipeline_versions"),
        sa.UniqueConstraint("version_number", name="uq_pipeline_versions_number"),
        _fk("created_by", "auth.users.id", "fk_pipeline_versions_creator"),
        schema=S,
    )
    op.create_table(
        "pipeline_stages",
        sa.Column("id", GUID, nullable=False),
        sa.Column("pipeline_version_id", GUID, nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("name", sa.NVARCHAR(100), nullable=False),
        sa.Column("kind", sa.VARCHAR(30), nullable=False),
        sa.Column("is_optional", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_pipeline_stages"),
        sa.UniqueConstraint("pipeline_version_id", "position", name="uq_pipeline_stages_position"),
        _fk("pipeline_version_id", f"{S}.pipeline_versions.id", "fk_pipeline_stages_version"),
        sa.CheckConstraint(
            "kind IN ('EVALUACION_CV', 'REVISION_RH', 'LLAMADA', 'PSICOMETRIA', 'ENTREVISTA', "
            "'PRUEBA_TECNICA', 'ESTUDIO_SOCIOECONOMICO', 'RESULTADO', 'OTRA')",
            name="ck_pipeline_stages_kind",
        ),
        schema=S,
    )
    op.create_table(
        "campaigns",
        sa.Column("id", GUID, nullable=False),
        sa.Column("vacancy_id", GUID, nullable=False),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("name", sa.NVARCHAR(100), nullable=False),
        sa.Column("status", sa.VARCHAR(20), nullable=False),
        sa.Column("pipeline_version_id", GUID, nullable=False),
        sa.Column("opened_at", UTC, nullable=False),
        sa.Column("opened_by", GUID, nullable=True),
        sa.Column("closed_at", UTC, nullable=True),
        sa.Column("closed_by", GUID, nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_campaigns"),
        sa.UniqueConstraint("vacancy_id", "number", name="uq_campaigns_number"),
        _fk("vacancy_id", "vacancy.vacancies.id", "fk_campaigns_vacancy"),
        _fk("pipeline_version_id", f"{S}.pipeline_versions.id", "fk_campaigns_pipeline"),
        _fk("opened_by", "auth.users.id", "fk_campaigns_opener"),
        _fk("closed_by", "auth.users.id", "fk_campaigns_closer"),
        sa.CheckConstraint("status IN ('ABIERTA', 'CERRADA')", name="ck_campaigns_status"),
        schema=S,
    )
    op.create_table(
        "candidates",
        sa.Column("id", GUID, nullable=False),
        sa.Column("full_name", sa.NVARCHAR(200), nullable=False),
        sa.Column("email", sa.NVARCHAR(254), nullable=True),
        sa.Column("phone", sa.NVARCHAR(40), nullable=True),
        sa.Column("created_at", UTC, nullable=False),
        sa.Column("created_by", GUID, nullable=True),
        sa.Column("updated_at", UTC, nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_candidates"),
        _fk("created_by", "auth.users.id", "fk_candidates_creator"),
        schema=S,
    )
    op.create_index(
        "uq_candidates_email",
        "candidates",
        ["email"],
        unique=True,
        schema=S,
        mssql_where=sa.text("email IS NOT NULL"),
    )
    op.create_table(
        "applications",
        sa.Column("id", GUID, nullable=False),
        sa.Column("candidate_id", GUID, nullable=False),
        sa.Column("campaign_id", GUID, nullable=False),
        sa.Column("vacancy_id", GUID, nullable=False),
        sa.Column("stage_id", GUID, nullable=False),
        sa.Column("status", sa.VARCHAR(20), nullable=False),
        sa.Column("cv_file_id", GUID, nullable=True),
        sa.Column("evaluation_item_id", GUID, nullable=True),
        sa.Column("ai_classification", sa.VARCHAR(20), nullable=True),
        sa.Column("ai_score", sa.Numeric(5, 2), nullable=True),
        sa.Column("due_at", UTC, nullable=True),
        sa.Column("created_at", UTC, nullable=False),
        sa.Column("created_by", GUID, nullable=True),
        sa.Column("updated_at", UTC, nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_applications"),
        sa.UniqueConstraint("candidate_id", "campaign_id", name="uq_applications_candidate"),
        _fk("candidate_id", f"{S}.candidates.id", "fk_applications_candidate"),
        _fk("campaign_id", f"{S}.campaigns.id", "fk_applications_campaign"),
        _fk("vacancy_id", "vacancy.vacancies.id", "fk_applications_vacancy"),
        _fk("stage_id", f"{S}.pipeline_stages.id", "fk_applications_stage"),
        _fk("cv_file_id", "files.file_assets.id", "fk_applications_cv"),
        _fk("evaluation_item_id", "ai.cv_batch_items.id", "fk_applications_evaluation"),
        _fk("created_by", "auth.users.id", "fk_applications_creator"),
        sa.CheckConstraint(
            "status IN ('ACTIVA', 'DESISTIO', 'DESCARTADA', 'CANCELADA')",
            name="ck_applications_status",
        ),
        schema=S,
    )
    op.create_index(
        "ix_applications_campaign", "applications", ["campaign_id", "stage_id", "status"], schema=S
    )
    op.create_index("ix_applications_vacancy", "applications", ["vacancy_id"], schema=S)
    op.create_index("ix_applications_file", "applications", ["cv_file_id"], schema=S)
    op.create_table(
        "application_movements",
        sa.Column("id", GUID, nullable=False),
        sa.Column("application_id", GUID, nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("kind", sa.VARCHAR(20), nullable=False),
        sa.Column("from_stage_id", GUID, nullable=True),
        sa.Column("to_stage_id", GUID, nullable=True),
        sa.Column("note", sa.NVARCHAR(500), nullable=True),
        sa.Column("due_at", UTC, nullable=True),
        sa.Column("group_id", GUID, nullable=True),
        sa.Column("occurred_at", UTC, nullable=False),
        sa.Column("actor_user_id", GUID, nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_application_movements"),
        sa.UniqueConstraint("application_id", "sequence", name="uq_application_movements_sequence"),
        _fk("application_id", f"{S}.applications.id", "fk_application_movements_application"),
        _fk("from_stage_id", f"{S}.pipeline_stages.id", "fk_application_movements_from"),
        _fk("to_stage_id", f"{S}.pipeline_stages.id", "fk_application_movements_to"),
        _fk("actor_user_id", "auth.users.id", "fk_application_movements_actor"),
        sa.CheckConstraint(
            "kind IN ('ALTA', 'AVANCE', 'RETROCESO', 'OMISION', 'DESISTIMIENTO', 'DESCARTE', "
            "'CANCELACION', 'REACTIVACION', 'REPROGRAMACION', 'INCIDENCIA')",
            name="ck_application_movements_kind",
        ),
        schema=S,
    )
    op.create_table(
        "question_banks",
        sa.Column("id", GUID, nullable=False),
        sa.Column("name", sa.NVARCHAR(150), nullable=False),
        sa.Column("description", sa.NVARCHAR(500), nullable=True),
        sa.Column("owner_user_id", GUID, nullable=False),
        sa.Column("scope", sa.VARCHAR(20), nullable=False),
        sa.Column("status", sa.VARCHAR(20), nullable=False),
        sa.Column("duplicated_from", GUID, nullable=True),
        sa.Column("created_at", UTC, nullable=False),
        sa.Column("updated_at", UTC, nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_question_banks"),
        _fk("owner_user_id", "auth.users.id", "fk_question_banks_owner"),
        _fk("duplicated_from", f"{S}.question_banks.id", "fk_question_banks_source"),
        sa.CheckConstraint("scope IN ('PRIVADO', 'COMPARTIDO')", name="ck_question_banks_scope"),
        sa.CheckConstraint("status IN ('ACTIVO', 'ARCHIVADO')", name="ck_question_banks_status"),
        schema=S,
    )
    op.create_index(
        "ix_question_banks_owner", "question_banks", ["owner_user_id", "status"], schema=S
    )
    op.create_table(
        "question_bank_versions",
        sa.Column("id", GUID, nullable=False),
        sa.Column("bank_id", GUID, nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("questions", MAX, nullable=False),
        sa.Column("change_note", sa.NVARCHAR(300), nullable=True),
        sa.Column("created_at", UTC, nullable=False),
        sa.Column("created_by", GUID, nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_question_bank_versions"),
        sa.UniqueConstraint("bank_id", "version_number", name="uq_question_bank_versions_number"),
        _fk("bank_id", f"{S}.question_banks.id", "fk_question_bank_versions_bank"),
        _fk("created_by", "auth.users.id", "fk_question_bank_versions_creator"),
        sa.CheckConstraint("ISJSON(questions) = 1", name="ck_question_bank_versions_json"),
        schema=S,
    )
    op.create_table(
        "call_sessions",
        sa.Column("id", GUID, nullable=False),
        sa.Column("application_id", GUID, nullable=False),
        sa.Column("vacancy_id", GUID, nullable=False),
        sa.Column("bank_version_id", GUID, nullable=False),
        sa.Column("status", sa.VARCHAR(20), nullable=False),
        sa.Column("called_at", UTC, nullable=False),
        sa.Column("notes", MAX, nullable=False),
        sa.Column("answers", MAX, nullable=False),
        sa.Column("analysis", MAX, nullable=True),
        sa.Column("analysis_at", UTC, nullable=True),
        sa.Column("analysis_by", GUID, nullable=True),
        sa.Column("created_at", UTC, nullable=False),
        sa.Column("created_by", GUID, nullable=False),
        sa.Column("updated_at", UTC, nullable=False),
        sa.Column("closed_at", UTC, nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_call_sessions"),
        _fk("application_id", f"{S}.applications.id", "fk_call_sessions_application"),
        _fk("vacancy_id", "vacancy.vacancies.id", "fk_call_sessions_vacancy"),
        _fk("bank_version_id", f"{S}.question_bank_versions.id", "fk_call_sessions_bank_version"),
        _fk("analysis_by", "auth.users.id", "fk_call_sessions_analyst"),
        _fk("created_by", "auth.users.id", "fk_call_sessions_creator"),
        sa.CheckConstraint("status IN ('BORRADOR', 'CERRADA')", name="ck_call_sessions_status"),
        sa.CheckConstraint("ISJSON(answers) = 1", name="ck_call_sessions_answers_json"),
        schema=S,
    )
    op.create_index(
        "ix_call_sessions_application", "call_sessions", ["application_id", "called_at"], schema=S
    )


def downgrade() -> None:
    for table in (
        "call_sessions",
        "question_bank_versions",
        "question_banks",
        "application_movements",
        "applications",
        "candidates",
        "campaigns",
        "pipeline_stages",
        "pipeline_versions",
    ):
        op.drop_table(table, schema=S)
    op.drop_column("cv_batch_items", "extraction", schema="ai")
    op.execute("DROP SCHEMA [recruitment]")
