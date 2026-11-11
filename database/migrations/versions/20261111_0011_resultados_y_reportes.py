"""Resultados finales de las postulaciones y registro de reportes.

Revisión: 0011
Anterior: 0010
Fecha: 2026-11-11

- ``recruitment.application_outcomes``: resultado final de una postulación
  (contratado, no contratado, desistió, no localizado, vacante cancelada u otro
  cierre), con quién lo registró, cuándo, el motivo y la fecha de
  incorporación. Al reabrir la postulación el registro se anula, no se borra.
  Como mucho hay un resultado vigente por postulación.
- ``recruitment.applications.status`` admite tres estados más: CONTRATADA,
  NO_LOCALIZADA y OTRO_CIERRE.
- ``recruitment.application_movements.kind`` admite CONTRATACION,
  NO_LOCALIZADO y CIERRE.
- ``ops.report_exports``: cada Excel de reportes generado, con sus filtros, las
  vacantes que contiene, quién lo pidió, su tamaño y su huella SHA-256.

Las postulaciones que ya estaban cerradas (desistimiento, descarte o
cancelación de la fase anterior) reciben su resultado final a partir del
movimiento con el que se cerraron.

Reversión: ``downgrade`` elimina las dos tablas y vuelve a las listas
anteriores. Falla, a propósito, si existen postulaciones o movimientos con los
valores nuevos: antes hay que decidir qué hacer con esas contrataciones.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mssql

revision: str = "0011"
down_revision: str | None = "0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

GUID = mssql.UNIQUEIDENTIFIER()
UTC = mssql.DATETIME2(precision=3)
S = "recruitment"
MAX = sa.NVARCHAR(None)

_STATUS_BEFORE = "'ACTIVA', 'DESISTIO', 'DESCARTADA', 'CANCELADA'"
_STATUS_AFTER = _STATUS_BEFORE + ", 'CONTRATADA', 'NO_LOCALIZADA', 'OTRO_CIERRE'"
_KIND_BEFORE = (
    "'ALTA', 'AVANCE', 'RETROCESO', 'OMISION', 'DESISTIMIENTO', 'DESCARTE', "
    "'CANCELACION', 'REACTIVACION', 'REPROGRAMACION', 'INCIDENCIA'"
)
_KIND_AFTER = _KIND_BEFORE + ", 'CONTRATACION', 'NO_LOCALIZADO', 'CIERRE'"

_BACKFILL = """
INSERT INTO recruitment.application_outcomes
    (id, application_id, vacancy_id, outcome, reason, recorded_at, recorded_by)
SELECT NEWID(), a.id, a.vacancy_id,
       CASE a.status
            WHEN 'DESISTIO' THEN 'DESISTIO'
            WHEN 'DESCARTADA' THEN 'NO_CONTRATADO'
            ELSE 'VACANTE_CANCELADA'
       END,
       m.note, m.occurred_at, m.actor_user_id
FROM recruitment.applications AS a
JOIN recruitment.application_movements AS m ON m.application_id = a.id
WHERE a.status <> 'ACTIVA'
  AND m.actor_user_id IS NOT NULL
  AND m.sequence = (
        SELECT MAX(x.sequence)
        FROM recruitment.application_movements AS x
        WHERE x.application_id = a.id
          AND x.kind IN ('DESISTIMIENTO', 'DESCARTE', 'CANCELACION')
      )
"""


def _fk(column: str, target: str, name: str) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint([column], [target], name=name)


def _replace_check(table: str, name: str, condition: str) -> None:
    op.drop_constraint(name, table, schema=S, type_="check")
    op.create_check_constraint(name, table, condition, schema=S)


def upgrade() -> None:
    _replace_check("applications", "ck_applications_status", f"status IN ({_STATUS_AFTER})")
    _replace_check(
        "application_movements", "ck_application_movements_kind", f"kind IN ({_KIND_AFTER})"
    )
    op.create_table(
        "application_outcomes",
        sa.Column("id", GUID, nullable=False),
        sa.Column("application_id", GUID, nullable=False),
        sa.Column("vacancy_id", GUID, nullable=False),
        sa.Column("outcome", sa.VARCHAR(20), nullable=False),
        sa.Column("reason", sa.NVARCHAR(500), nullable=True),
        sa.Column("notes", MAX, nullable=True),
        sa.Column("start_date", sa.DATE(), nullable=True),
        sa.Column("recorded_at", UTC, nullable=False),
        sa.Column("recorded_by", GUID, nullable=False),
        sa.Column("voided_at", UTC, nullable=True),
        sa.Column("voided_by", GUID, nullable=True),
        sa.Column("void_reason", sa.NVARCHAR(500), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_application_outcomes"),
        _fk("application_id", "recruitment.applications.id", "fk_application_outcomes_application"),
        _fk("vacancy_id", "vacancy.vacancies.id", "fk_application_outcomes_vacancy"),
        _fk("recorded_by", "auth.users.id", "fk_application_outcomes_recorded_by"),
        _fk("voided_by", "auth.users.id", "fk_application_outcomes_voided_by"),
        sa.CheckConstraint(
            "outcome IN ('CONTRATADO', 'NO_CONTRATADO', 'DESISTIO', 'NO_LOCALIZADO', "
            "'VACANTE_CANCELADA', 'OTRO_CIERRE')",
            name="ck_application_outcomes_outcome",
        ),
        # La fecha de incorporación solo acompaña a una contratación.
        sa.CheckConstraint(
            "start_date IS NULL OR outcome = 'CONTRATADO'",
            name="ck_application_outcomes_start_date",
        ),
        schema=S,
    )
    op.create_index(
        "uq_application_outcomes_current",
        "application_outcomes",
        ["application_id"],
        unique=True,
        schema=S,
        mssql_where=sa.text("voided_at IS NULL"),
    )
    op.create_index(
        "ix_application_outcomes_vacancy",
        "application_outcomes",
        ["vacancy_id", "outcome", "recorded_at"],
        schema=S,
    )
    op.execute(_BACKFILL)

    op.create_table(
        "report_exports",
        sa.Column("id", GUID, nullable=False),
        sa.Column("kind", sa.VARCHAR(20), nullable=False),
        sa.Column("name", sa.NVARCHAR(200), nullable=False),
        sa.Column("filters", MAX, nullable=False),
        sa.Column("vacancy_ids", MAX, nullable=False),
        sa.Column("row_count", sa.INTEGER(), nullable=False),
        sa.Column("storage_key", sa.VARCHAR(200), nullable=False),
        sa.Column("size_bytes", sa.BIGINT(), nullable=False),
        sa.Column("sha256", sa.VARCHAR(64), nullable=False),
        sa.Column("created_at", UTC, nullable=False),
        sa.Column("created_by", GUID, nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_report_exports"),
        sa.UniqueConstraint("storage_key", name="uq_report_exports_storage_key"),
        _fk("created_by", "auth.users.id", "fk_report_exports_created_by"),
        sa.CheckConstraint(
            "kind IN ('INDICADORES', 'POSTULACIONES')", name="ck_report_exports_kind"
        ),
        sa.CheckConstraint("ISJSON(filters) = 1", name="ck_report_exports_filters_json"),
        sa.CheckConstraint("ISJSON(vacancy_ids) = 1", name="ck_report_exports_vacancies_json"),
        schema="ops",
    )
    op.create_index(
        "ix_report_exports_user", "report_exports", ["created_by", "created_at"], schema="ops"
    )


def downgrade() -> None:
    op.drop_table("report_exports", schema="ops")
    op.drop_table("application_outcomes", schema=S)
    _replace_check(
        "application_movements", "ck_application_movements_kind", f"kind IN ({_KIND_BEFORE})"
    )
    _replace_check("applications", "ck_applications_status", f"status IN ({_STATUS_BEFORE})")
