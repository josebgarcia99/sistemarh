"""Índices para las consultas de reportes (revisión de SQL Server, Fase 8).

Revisión: 0012
Anterior: 0011
Fecha: 2026-11-12

SQL Server no crea índices para las claves foráneas. Al revisar las consultas
de los tableros y del histórico se añadieron los que esas consultas usan para
filtrar o unir tablas:

- ``recruitment.call_sessions (vacancy_id)`` y ``(bank_version_id)``: filtro del
  histórico por banco de preguntas y lista de bancos usados.
- ``ai.cv_batches (prompt_version_id)``: versión del prompt de cada postulación.
- ``recruitment.applications (evaluation_item_id)``: unión con la evaluación
  inicial del CV.
- ``ai.executions (vacancy_id, occurred_at)``: uso de IA de unas vacantes en un
  periodo.

No cambia datos ni columnas. Las columnas de autoría (quién creó o modificó)
quedan sin índice a propósito: los usuarios nunca se borran y esas columnas no
se usan para buscar. El detalle está en ``docs/database/revision_sql_server.md``.

Reversión: ``downgrade`` elimina los cinco índices.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0012"
down_revision: str | None = "0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

INDEXES = (
    ("ix_call_sessions_vacancy", "call_sessions", ["vacancy_id"], "recruitment"),
    ("ix_call_sessions_bank_version", "call_sessions", ["bank_version_id"], "recruitment"),
    ("ix_cv_batches_prompt_version", "cv_batches", ["prompt_version_id"], "ai"),
    ("ix_applications_evaluation_item", "applications", ["evaluation_item_id"], "recruitment"),
    ("ix_executions_vacancy", "executions", ["vacancy_id", "occurred_at"], "ai"),
)


def upgrade() -> None:
    for name, table, columns, schema in INDEXES:
        op.create_index(name, table, columns, schema=schema)


def downgrade() -> None:
    for name, table, _, schema in reversed(INDEXES):
        op.drop_index(name, table_name=table, schema=schema)
