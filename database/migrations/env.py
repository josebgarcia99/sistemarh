"""Entorno de Alembic para SQL Server.

- La URL se toma de ``RECLU_DATABASE_URL``; no hay valor por omisión.
- Solo se admite ``mssql+pyodbc``: no hay sustituto silencioso de SQL Server.
- Ninguna migración destructiva se ejecuta de forma automática: cada cambio
  es un archivo revisable en ``versions/`` con su reversión documentada.
"""

from __future__ import annotations

import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, pool

from app.infrastructure.database.engine import validate_database_url

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Los modelos se registran aquí a partir de la Fase 2.
target_metadata = None


def _database_url() -> str:
    url = os.environ.get("RECLU_DATABASE_URL")
    if not url:
        raise RuntimeError(
            "Define RECLU_DATABASE_URL antes de ejecutar migraciones. "
            "Nunca apuntes a producción sin autorización."
        )
    validate_database_url(url)
    return url


def run_migrations_offline() -> None:
    """Genera el T-SQL sin conectarse, para que Sistemas pueda revisarlo."""
    context.configure(
        url=_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = create_engine(_database_url(), poolclass=pool.NullPool)
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
