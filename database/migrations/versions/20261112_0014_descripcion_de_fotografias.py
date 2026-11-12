"""Operación de IA para describir fotografías del estudio socioeconómico.

Revisión: 0014
Anterior: 0013
Fecha: 2026-11-12

La regla de validación (CHECK) de ``ai.operation_assignments.operation`` admite
un valor más: ``DESCRIPCION_FOTOGRAFIAS``. Es la operación a la que el
administrador asigna el modelo (por ejemplo, uno de Gemini) que describe lo que
se observa en una fotografía del estudio. No cambian tablas, columnas ni datos.

La descripción de cada fotografía se guarda dentro de lo capturado en el
estudio (columna ``data`` de ``recruitment.assessments``, que ya existía).

Reversión: ``downgrade`` vuelve a la regla anterior. Si la operación ya tiene un
modelo asignado, SQL Server rechaza la regla anterior y la reversión se detiene
sin cambiar nada: primero hay que quitar esa asignación.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0014"
down_revision: str | None = "0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

NAME = "ck_operation_assignments_operation"
TABLE = "operation_assignments"
SCHEMA = "ai"
OLD = (
    "ANALISIS_PERFILES",
    "GENERACION_PROMPTS",
    "EXTRACCION_CV",
    "EVALUACION_DOCUMENTAL",
    "ANALISIS_LLAMADAS",
    "LECTURA_DOCUMENTOS",
    "RESUMEN_PRUEBAS",
    "SINTESIS_EXPEDIENTES",
)
NEW = (*OLD, "DESCRIPCION_FOTOGRAFIAS")


def _replace(values: tuple[str, ...]) -> None:
    allowed = ", ".join(f"'{value}'" for value in values)
    op.drop_constraint(NAME, TABLE, schema=SCHEMA, type_="check")
    op.create_check_constraint(NAME, TABLE, f"operation IN ({allowed})", schema=SCHEMA)


def upgrade() -> None:
    _replace(NEW)


def downgrade() -> None:
    _replace(OLD)
