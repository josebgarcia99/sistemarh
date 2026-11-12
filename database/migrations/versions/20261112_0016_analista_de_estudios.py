"""Puesto de analista de estudios socioeconómicos.

Revisión: 0016
Anterior: 0015
Fecha: 2026-11-12

Añade el rol ``ANALISTA_ESTUDIOS`` al catálogo ``auth.roles``. Quien tiene ese
rol trabaja los estudios socioeconómicos de cualquier vacante (capturar el
estudio, cargar sus documentos y fotografías y usar las ayudas de IA del
estudio) y no tiene acceso a nada más. Los administradores y reclutadores
conservan el acceso que ya tenían.

No cambia tablas ni columnas, y no modifica a ningún usuario existente.

Reversión: ``downgrade`` elimina el rol del catálogo. Si algún usuario lo tiene
asignado, SQL Server rechaza el borrado (clave foránea de ``auth.user_roles``)
y la reversión se detiene sin cambiar nada: primero hay que cambiarles el rol.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0016"
down_revision: str | None = "0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "INSERT INTO auth.roles (code, name) VALUES "
        "(N'ANALISTA_ESTUDIOS', N'Analista de estudios socioeconómicos')"
    )


def downgrade() -> None:
    op.execute("DELETE FROM auth.roles WHERE code = N'ANALISTA_ESTUDIOS'")
