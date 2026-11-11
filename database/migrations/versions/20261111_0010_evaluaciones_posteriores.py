"""Evaluaciones posteriores, formularios del estudio socioeconómico y síntesis.

Revisión: 0010
Anterior: 0009
Fecha: 2026-11-11

Añade al esquema ``recruitment``:

- ``form_templates`` y ``form_template_versions``: formularios configurables del
  estudio socioeconómico, por versiones.
- ``assessments``: una evaluación de una postulación (psicometría, entrevista
  con gerente, prueba técnica o estudio socioeconómico), con lo capturado en JSON.
- ``application_syntheses``: síntesis del expediente generadas por la IA.

El formulario inicial no se inserta aquí: la aplicación lo crea la primera vez
que se usa.

Reversión: ``downgrade`` elimina las cuatro tablas. Se pierden las
evaluaciones, los formularios y las síntesis.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mssql

revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

GUID = mssql.UNIQUEIDENTIFIER()
UTC = mssql.DATETIME2(precision=3)
S = "recruitment"
MAX = sa.NVARCHAR(None)
_STATUSES = (
    "'PENDIENTE', 'PRESENTADA', 'NO_PRESENTADA', 'INCOMPLETA', 'NO_APLICA', 'ANULADA', "
    "'VALIDADA', 'PROGRAMADA', 'REALIZADA', 'NO_REALIZADA', 'CANCELADA', 'EN_PROCESO', "
    "'COMPLETADO', 'ANULADO'"
)


def _fk(column: str, target: str, name: str) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint([column], [target], name=name)


def upgrade() -> None:
    op.create_table(
        "form_templates",
        sa.Column("id", GUID, nullable=False),
        sa.Column("name", sa.NVARCHAR(150), nullable=False),
        sa.Column("description", sa.NVARCHAR(500), nullable=True),
        sa.Column("status", sa.VARCHAR(20), nullable=False),
        sa.Column("created_at", UTC, nullable=False),
        sa.Column("updated_at", UTC, nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_form_templates"),
        sa.CheckConstraint("status IN ('ACTIVA', 'ARCHIVADA')", name="ck_form_templates_status"),
        schema=S,
    )
    op.create_table(
        "form_template_versions",
        sa.Column("id", GUID, nullable=False),
        sa.Column("template_id", GUID, nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("sections", MAX, nullable=False),
        sa.Column("created_at", UTC, nullable=False),
        sa.Column("created_by", GUID, nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_form_template_versions"),
        sa.UniqueConstraint(
            "template_id", "version_number", name="uq_form_template_versions_number"
        ),
        _fk("template_id", f"{S}.form_templates.id", "fk_form_template_versions_template"),
        _fk("created_by", "auth.users.id", "fk_form_template_versions_creator"),
        sa.CheckConstraint("ISJSON(sections) = 1", name="ck_form_template_versions_json"),
        schema=S,
    )
    op.create_table(
        "assessments",
        sa.Column("id", GUID, nullable=False),
        sa.Column("application_id", GUID, nullable=False),
        sa.Column("vacancy_id", GUID, nullable=False),
        sa.Column("kind", sa.VARCHAR(30), nullable=False),
        sa.Column("status", sa.VARCHAR(20), nullable=False),
        sa.Column("event_date", UTC, nullable=True),
        sa.Column("file_id", GUID, nullable=True),
        sa.Column("template_version_id", GUID, nullable=True),
        sa.Column("data", MAX, nullable=False),
        sa.Column("score", sa.Numeric(5, 2), nullable=True),
        sa.Column("ai_summary", MAX, nullable=True),
        sa.Column("ai_summary_at", UTC, nullable=True),
        sa.Column("ai_summary_by", GUID, nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", UTC, nullable=False),
        sa.Column("created_by", GUID, nullable=False),
        sa.Column("updated_at", UTC, nullable=False),
        sa.Column("updated_by", GUID, nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_assessments"),
        _fk("application_id", f"{S}.applications.id", "fk_assessments_application"),
        _fk("vacancy_id", "vacancy.vacancies.id", "fk_assessments_vacancy"),
        _fk("file_id", "files.file_assets.id", "fk_assessments_file"),
        _fk("template_version_id", f"{S}.form_template_versions.id", "fk_assessments_template"),
        _fk("ai_summary_by", "auth.users.id", "fk_assessments_summary_author"),
        _fk("created_by", "auth.users.id", "fk_assessments_creator"),
        _fk("updated_by", "auth.users.id", "fk_assessments_editor"),
        sa.CheckConstraint(
            "kind IN ('PSICOMETRIA', 'ENTREVISTA', 'PRUEBA_TECNICA', 'ESTUDIO_SOCIOECONOMICO')",
            name="ck_assessments_kind",
        ),
        sa.CheckConstraint(f"status IN ({_STATUSES})", name="ck_assessments_status"),
        sa.CheckConstraint("ISJSON(data) = 1", name="ck_assessments_data_json"),
        sa.CheckConstraint(
            "score IS NULL OR (score >= 0 AND score <= 100)", name="ck_assessments_score"
        ),
        # Un estudio socioeconómico siempre tiene formulario; los demás tipos, nunca.
        sa.CheckConstraint(
            "(kind = 'ESTUDIO_SOCIOECONOMICO' AND template_version_id IS NOT NULL) OR "
            "(kind <> 'ESTUDIO_SOCIOECONOMICO' AND template_version_id IS NULL)",
            name="ck_assessments_template",
        ),
        schema=S,
    )
    op.create_index(
        "ix_assessments_application", "assessments", ["application_id", "kind"], schema=S
    )
    op.create_table(
        "application_syntheses",
        sa.Column("id", GUID, nullable=False),
        sa.Column("application_id", GUID, nullable=False),
        sa.Column("vacancy_id", GUID, nullable=False),
        sa.Column("result", MAX, nullable=False),
        sa.Column("sources", MAX, nullable=False),
        sa.Column("includes_psychometrics", sa.Boolean(), nullable=False),
        sa.Column("created_at", UTC, nullable=False),
        sa.Column("created_by", GUID, nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_application_syntheses"),
        _fk("application_id", f"{S}.applications.id", "fk_application_syntheses_application"),
        _fk("vacancy_id", "vacancy.vacancies.id", "fk_application_syntheses_vacancy"),
        _fk("created_by", "auth.users.id", "fk_application_syntheses_creator"),
        sa.CheckConstraint("ISJSON(result) = 1", name="ck_application_syntheses_json"),
        schema=S,
    )
    op.create_index(
        "ix_application_syntheses_application",
        "application_syntheses",
        ["application_id", "created_at"],
        schema=S,
    )


def downgrade() -> None:
    op.drop_table("application_syntheses", schema=S)
    op.drop_table("assessments", schema=S)
    op.drop_table("form_template_versions", schema=S)
    op.drop_table("form_templates", schema=S)
