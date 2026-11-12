"""Síntesis del expediente que incluyen fotografías del estudio socioeconómico.

Revisión: 0015
Anterior: 0014
Fecha: 2026-11-12

Añade la columna ``includes_study`` a ``recruitment.application_syntheses``.
Indica que la síntesis usó las descripciones guardadas junto a las fotografías
del estudio socioeconómico. Con ese dato, la aplicación solo muestra esa
síntesis a quien tiene el permiso adicional del estudio, igual que ya hace con
las síntesis que incluyen psicometría.

Las síntesis que ya existían quedan con el valor 0 (falso): ninguna incluía
fotografías. No se cambia ni se borra ningún otro dato.

Reversión: ``downgrade`` elimina la columna (y su valor por omisión). Las
síntesis que incluían fotografías dejarían de estar restringidas: antes de
revertir conviene eliminarlas o aceptar ese efecto.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0015"
down_revision: str | None = "0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLE = "application_syntheses"
SCHEMA = "recruitment"


def upgrade() -> None:
    op.add_column(
        TABLE,
        sa.Column("includes_study", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        schema=SCHEMA,
    )


def downgrade() -> None:
    # SQL Server exige quitar primero el valor por omisión ligado a la columna.
    op.drop_column(TABLE, "includes_study", schema=SCHEMA, mssql_drop_default=True)
