"""Cada llamada tiene su propia lista de preguntas.

Revisión: 0018
Anterior: 0017
Fecha: 2026-11-17

Hasta la versión 0017 una llamada usaba, tal cual, las preguntas de un banco (y
las generales de la empresa). Ahora la llamada guarda su propia lista: empieza
con las generales y las de los bancos elegidos, y en esa llamada se pueden
quitar preguntas, cambiar su redacción, sumar las de otros bancos o escribir
preguntas nuevas, sin tocar los bancos.

- ``recruitment.call_sessions.questions`` (nueva, admite vacío): la lista de
  preguntas de la llamada, en JSON. Las llamadas que ya existían quedan con el
  valor vacío y sus preguntas se siguen leyendo de los bancos, como antes.
- ``recruitment.call_sessions.bank_version_id`` pasa a admitir vacío: una
  llamada puede abrirse solo con las preguntas generales o con preguntas
  escritas. Para que el cambio no dependa de cómo trate SQL Server una columna
  con índice y clave foránea, se quitan el índice y la clave, se cambia la
  columna y se vuelven a crear con los mismos nombres.
- ``recruitment.call_session_banks`` (nueva): de qué bancos tomó preguntas cada
  llamada. La usa el filtro «banco de preguntas» de los indicadores, que antes
  salía de ``bank_version_id``. Se llena con las llamadas que ya existían. La
  aplicación solo agrega filas: no borra.

No se borra ni se modifica ningún dato existente.

Reversión: ``downgrade`` elimina la tabla y la columna nuevas y vuelve a exigir
``bank_version_id``. Si ya existe alguna llamada sin banco, SQL Server rechaza
ese último paso y la reversión se detiene: esas llamadas no se pueden
representar en la versión 0017. En ese caso hay que restaurar el respaldo.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mssql

revision: str = "0018"
down_revision: str | None = "0017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA = "recruitment"
GUID = mssql.UNIQUEIDENTIFIER()
INDEX = "ix_call_sessions_bank_version"
FOREIGN_KEY = "fk_call_sessions_bank_version"
JSON_CHECK = "ck_call_sessions_questions_json"

_BACKFILL = """
INSERT INTO recruitment.call_session_banks (call_id, bank_id)
SELECT c.id, v.bank_id
FROM recruitment.call_sessions AS c
JOIN recruitment.question_bank_versions AS v ON v.id = c.bank_version_id
"""


def _bank_version(nullable: bool) -> None:
    op.drop_index(INDEX, table_name="call_sessions", schema=SCHEMA)
    op.drop_constraint(FOREIGN_KEY, "call_sessions", schema=SCHEMA, type_="foreignkey")
    op.alter_column(
        "call_sessions",
        "bank_version_id",
        existing_type=GUID,
        nullable=nullable,
        schema=SCHEMA,
    )
    op.create_foreign_key(
        FOREIGN_KEY,
        "call_sessions",
        "question_bank_versions",
        ["bank_version_id"],
        ["id"],
        source_schema=SCHEMA,
        referent_schema=SCHEMA,
    )
    op.create_index(INDEX, "call_sessions", ["bank_version_id"], schema=SCHEMA)


def upgrade() -> None:
    op.add_column(
        "call_sessions", sa.Column("questions", sa.NVARCHAR(None), nullable=True), schema=SCHEMA
    )
    op.create_check_constraint(
        JSON_CHECK, "call_sessions", "questions IS NULL OR ISJSON(questions) = 1", schema=SCHEMA
    )
    _bank_version(nullable=True)
    op.create_table(
        "call_session_banks",
        sa.Column("call_id", GUID, nullable=False),
        sa.Column("bank_id", GUID, nullable=False),
        sa.PrimaryKeyConstraint("call_id", "bank_id", name="pk_call_session_banks"),
        sa.ForeignKeyConstraint(
            ["call_id"], [f"{SCHEMA}.call_sessions.id"], name="fk_call_session_banks_call"
        ),
        sa.ForeignKeyConstraint(
            ["bank_id"], [f"{SCHEMA}.question_banks.id"], name="fk_call_session_banks_bank"
        ),
        schema=SCHEMA,
    )
    op.create_index("ix_call_session_banks_bank", "call_session_banks", ["bank_id"], schema=SCHEMA)
    op.execute(_BACKFILL)


def downgrade() -> None:
    op.drop_index("ix_call_session_banks_bank", table_name="call_session_banks", schema=SCHEMA)
    op.drop_table("call_session_banks", schema=SCHEMA)
    _bank_version(nullable=False)
    op.drop_constraint(JSON_CHECK, "call_sessions", schema=SCHEMA, type_="check")
    op.drop_column("call_sessions", "questions", schema=SCHEMA)
