"""Genera los scripts T-SQL de SQL Server a partir de las migraciones.

No se conecta a ninguna base de datos: usa el modo "offline" de Alembic.

    python scripts/generate_sql.py

Escribe en ``database/sqlserver/``:

- ``instalacion_completa.sql``      base vacía  -> última versión
- ``actualizacion_<a>_a_<b>.sql``   un script por cada paso entre versiones
- ``reversion_completa.sql``        última versión -> base vacía (DESTRUCTIVO)
"""

from __future__ import annotations

import io
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DATABASE_DIR = REPO_ROOT / "database"
OUTPUT_DIR = DATABASE_DIR / "sqlserver"
sys.path.insert(0, str(REPO_ROOT / "apps" / "api"))

from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from alembic.script import ScriptDirectory  # noqa: E402

# Solo sirve para elegir el dialecto; nunca se abre una conexión.
DUMMY_URL = (
    "mssql+pyodbc://generador:sin-conexion@localhost/base?driver=ODBC+Driver+18+for+SQL+Server"
)

HEADER = """\
/* ============================================================================
   Sistema Integral de Reclutamiento e IA - {title}
   Versión del esquema: {versions}
   Generado: {generated} (UTC) con scripts/generate_sql.py

   {purpose}

   ANTES DE EJECUTAR
   1. Ejecutar primero en una base de PRUEBAS. Este script se generó sin
      conexión y todavía no se ha ejecutado contra un SQL Server real.
   2. La base de datos debe existir. Este script no la crea ni usa "USE":
      selecciónela en la conexión.
   3. Requiere permisos para crear esquemas y tablas (por ejemplo, db_owner).
   4. Ejecute con "sqlcmd -b" (se detiene al primer error) o en SSMS con el
      modo SQLCMD activado. Todo corre en una sola transacción y, si se detiene
      al primer error, no queda nada a medias. Sin esa opción, SSMS seguiría
      ejecutando los lotes posteriores al error fuera de la transacción.
   5. La tabla dbo.alembic_version registra la versión instalada. No la edite
      a mano: la aplicación y los scripts de actualización dependen de ella.
   ============================================================================ */

SET XACT_ABORT ON;
GO

"""


# Scripts escritos a mano: el generador no los toca.
HAND_WRITTEN = frozenset({"permisos_usuario_aplicacion.sql", "validaciones_integridad.sql"})


def _config(buffer: io.StringIO) -> Config:
    config = Config(str(DATABASE_DIR / "alembic.ini"), output_buffer=buffer)
    config.set_main_option("script_location", str(DATABASE_DIR / "migrations"))
    return config


def _render(revision_range: str, *, downgrade: bool = False) -> str:
    buffer = io.StringIO()
    previous_cwd, previous_url = os.getcwd(), os.environ.get("RECLU_DATABASE_URL")
    os.environ["RECLU_DATABASE_URL"] = DUMMY_URL
    try:
        os.chdir(DATABASE_DIR)
        action = command.downgrade if downgrade else command.upgrade
        action(_config(buffer), revision_range, sql=True)
    finally:
        os.chdir(previous_cwd)
        if previous_url is None:
            os.environ.pop("RECLU_DATABASE_URL", None)
        else:
            os.environ["RECLU_DATABASE_URL"] = previous_url
    return buffer.getvalue()


GUARD = """\
-- Protección: si la base no está en la versión esperada, no se ejecuta nada.
IF {condition}
BEGIN
    RAISERROR(N'{message}', 16, 1);
    SET NOEXEC ON;
END
GO

"""

FOOTER = """
GO
SET NOEXEC OFF;
GO
"""

FRESH_GUARD = GUARD.format(
    condition="OBJECT_ID(N'dbo.alembic_version') IS NOT NULL",
    message="Esta base ya tiene el sistema instalado. Use un script de actualizacion.",
)


VERSION_CONDITION = (
    "OBJECT_ID(N'dbo.alembic_version') IS NULL OR NOT EXISTS "
    "(SELECT 1 FROM dbo.alembic_version WHERE version_num = N'__VERSION__')"
)


def _version_guard(expected: str) -> str:
    # ``expected`` es un identificador de migración de este repositorio (0001, 0002...).
    if not expected.isalnum():
        raise ValueError(f"Identificador de versión inesperado: {expected!r}")
    return GUARD.format(
        condition=VERSION_CONDITION.replace("__VERSION__", expected),
        message=f"La base no esta en la version {expected}. No se aplico ningun cambio.",
    )


def _write(
    name: str, *, title: str, versions: str, purpose: str, guard: str, body: str, stamp: str
) -> Path:
    path = OUTPUT_DIR / name
    header = HEADER.format(title=title, versions=versions, generated=stamp, purpose=purpose)
    path.write_text(header + guard + body + FOOTER, encoding="utf-8", newline="\n")
    return path


def main() -> int:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y-%m-%d %H:%M")
    scripts = ScriptDirectory.from_config(_config(io.StringIO()))
    revisions = [rev.revision for rev in reversed(list(scripts.walk_revisions()))]
    head = revisions[-1]

    for stale in OUTPUT_DIR.glob("*.sql"):
        if stale.name not in HAND_WRITTEN:
            stale.unlink()

    written = [
        _write(
            "instalacion_completa.sql",
            title="Instalación completa",
            versions=f"(vacía) -> {head}",
            purpose="Crea todos los esquemas y tablas en una base de datos VACÍA.",
            guard=FRESH_GUARD,
            body=_render("head"),
            stamp=stamp,
        )
    ]
    for previous, current in zip(revisions, revisions[1:], strict=False):
        written.append(
            _write(
                f"actualizacion_{previous}_a_{current}.sql",
                title=f"Actualización {previous} -> {current}",
                versions=f"{previous} -> {current}",
                purpose=(
                    f"Aplica solo los cambios de la versión {current} sobre una base que ya\n"
                    f"   está en la versión {previous}. Si está en otra versión, no hace nada."
                ),
                guard=_version_guard(previous),
                body=_render(f"{previous}:{current}"),
                stamp=stamp,
            )
        )
    written.append(
        _write(
            "reversion_completa.sql",
            title="Reversión completa (DESTRUCTIVO)",
            versions=f"{head} -> (vacía)",
            purpose=(
                "ELIMINA todas las tablas y esquemas del sistema, con todos sus datos.\n"
                "   Solo para entornos de prueba. Nunca ejecutar en producción sin respaldo."
            ),
            guard=_version_guard(head),
            body=_render(f"{head}:base", downgrade=True),
            stamp=stamp,
        )
    )
    for path in written:
        print(f"{path.relative_to(REPO_ROOT)}  ({path.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
