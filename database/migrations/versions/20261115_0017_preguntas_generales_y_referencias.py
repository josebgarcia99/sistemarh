"""Preguntas generales de la empresa en las llamadas y referencias de la persona.

Revisión: 0017
Anterior: 0016
Fecha: 2026-11-15

- ``recruitment.question_banks.scope`` admite ``GENERAL``: un banco con las
  preguntas que se hacen a todas las personas candidatas. Se agregan solas a
  cada llamada, antes de las del banco elegido.
- ``recruitment.call_sessions.general_version_ids``: lista JSON con las
  versiones de los bancos generales que se incluyeron al abrir la llamada, para
  que una llamada conserve sus preguntas aunque después cambien las generales.
  Las llamadas que ya existían quedan con la lista vacía.

- ``recruitment.assessments.kind`` admite ``REFERENCIAS``: las referencias
  laborales y personales de la persona candidata, con lo que cada una dijo al
  contactarla. Usa los estados que ya existían, así que la regla de estados no
  cambia.

La medición de la llamada (qué tanto cubre cada respuesta lo que se esperaba)
no necesita cambios de esquema: va dentro del análisis, que ya era un JSON.

Reversión: ``downgrade`` elimina la columna y vuelve a las reglas anteriores. Si
existe algún banco ``GENERAL`` o alguna evaluación ``REFERENCIAS``, SQL Server
rechaza la regla anterior y la reversión se detiene en ese punto: primero hay
que cambiar el alcance de esos bancos y eliminar o respaldar esas referencias.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0017"
down_revision: str | None = "0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA = "recruitment"
CHECK = "ck_question_banks_scope"


KIND_CHECK = "ck_assessments_kind"
KINDS = ("PSICOMETRIA", "ENTREVISTA", "PRUEBA_TECNICA", "ESTUDIO_SOCIOECONOMICO")


def _allow(check: str, table: str, column: str, values: tuple[str, ...]) -> None:
    allowed = ", ".join(f"'{value}'" for value in values)
    op.drop_constraint(check, table, schema=SCHEMA, type_="check")
    op.create_check_constraint(check, table, f"{column} IN ({allowed})", schema=SCHEMA)


def _scope(values: tuple[str, ...]) -> None:
    _allow(CHECK, "question_banks", "scope", values)


def upgrade() -> None:
    _allow(KIND_CHECK, "assessments", "kind", (*KINDS, "REFERENCIAS"))
    _scope(("PRIVADO", "COMPARTIDO", "GENERAL"))
    op.add_column(
        "call_sessions",
        sa.Column(
            "general_version_ids", sa.String(800), nullable=False, server_default=sa.text("'[]'")
        ),
        schema=SCHEMA,
    )


def downgrade() -> None:
    # SQL Server exige quitar primero el valor por omisión ligado a la columna.
    op.drop_column("call_sessions", "general_version_ids", schema=SCHEMA, mssql_drop_default=True)
    _scope(("PRIVADO", "COMPARTIDO"))
    _allow(KIND_CHECK, "assessments", "kind", KINDS)
