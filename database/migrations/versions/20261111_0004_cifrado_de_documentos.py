"""Cifrado de documentos sensibles.

Revisión: 0004
Anterior: 0003
Fecha: 2026-11-11

Añade a ``files.file_assets`` el tamaño y el SHA-256 de lo que hay realmente en
el disco (``stored_size_bytes``, ``stored_sha256``) y el identificador de la
clave maestra con que se cifró el archivo (``encryption_key_id``). En archivos
sin cifrar, los valores guardados coinciden con los del contenido.

Reversión: ``downgrade`` elimina las tres columnas. Los archivos cifrados
seguirían cifrados en el disco, pero la aplicación ya no sabría que lo están:
no ejecutar en producción si existen documentos cifrados.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "file_assets",
        sa.Column("stored_size_bytes", sa.BigInteger(), nullable=True),
        schema="files",
    )
    op.add_column(
        "file_assets", sa.Column("stored_sha256", sa.VARCHAR(64), nullable=True), schema="files"
    )
    op.add_column(
        "file_assets", sa.Column("encryption_key_id", sa.VARCHAR(32), nullable=True), schema="files"
    )
    # Los documentos guardados antes de esta versión no están cifrados.
    op.execute(
        "UPDATE files.file_assets SET stored_size_bytes = size_bytes, stored_sha256 = sha256 "
        "WHERE status IN ('CONFIRMADO', 'ELIMINADO')"
    )
    op.create_check_constraint(
        "ck_file_assets_stored_complete",
        "file_assets",
        "status NOT IN ('CONFIRMADO', 'ELIMINADO') OR (stored_size_bytes IS NOT NULL "
        "AND stored_sha256 IS NOT NULL)",
        schema="files",
    )


def downgrade() -> None:
    op.drop_constraint("ck_file_assets_stored_complete", "file_assets", schema="files")
    op.drop_column("file_assets", "encryption_key_id", schema="files")
    op.drop_column("file_assets", "stored_sha256", schema="files")
    op.drop_column("file_assets", "stored_size_bytes", schema="files")
