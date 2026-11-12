"""Proveedor Gemini y perfiles leídos del formato de la empresa.

Revisión: 0013
Anterior: 0012
Fecha: 2026-11-12

Dos reglas de validación (CHECK) admiten un valor más. No cambian tablas,
columnas ni datos:

- ``ai.providers.code`` acepta ``GEMINI`` (Google Gemini) además de
  ``ANTHROPIC`` y ``OPENAI``.
- ``vacancy.job_profile_versions.origin`` acepta ``FORMATO``: el perfil se leyó
  directamente del formato de la empresa «SGC.F15.RH. Perfil de puesto» en
  Excel, sin IA.

Los campos nuevos del perfil de puesto, las tablas del estudio socioeconómico y
la plantilla «SGC.F3.RH. Estudio socioeconómico» no necesitan cambios de
esquema: viven dentro de columnas de texto que ya existían (``content``,
``sections`` y ``data``).

Reversión: ``downgrade`` vuelve a las reglas anteriores. Si ya hay un proveedor
``GEMINI`` configurado o un perfil con origen ``FORMATO``, SQL Server rechaza la
regla anterior y la reversión se detiene sin cambiar nada: primero hay que
decidir qué hacer con esas filas.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0013"
down_revision: str | None = "0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# (nombre, tabla, esquema, columna, valores anteriores, valores nuevos)
CHECKS = (
    (
        "ck_providers_code",
        "providers",
        "ai",
        "code",
        ("ANTHROPIC", "OPENAI"),
        ("ANTHROPIC", "OPENAI", "GEMINI"),
    ),
    (
        "ck_job_profile_versions_origin",
        "job_profile_versions",
        "vacancy",
        "origin",
        ("MANUAL", "IA"),
        ("MANUAL", "IA", "FORMATO"),
    ),
)


def _replace(name: str, table: str, schema: str, column: str, values: tuple[str, ...]) -> None:
    allowed = ", ".join(f"'{value}'" for value in values)
    op.drop_constraint(name, table, schema=schema, type_="check")
    op.create_check_constraint(name, table, f"{column} IN ({allowed})", schema=schema)


def upgrade() -> None:
    for name, table, schema, column, _, new in CHECKS:
        _replace(name, table, schema, column, new)


def downgrade() -> None:
    for name, table, schema, column, old, _ in reversed(CHECKS):
        _replace(name, table, schema, column, old)
