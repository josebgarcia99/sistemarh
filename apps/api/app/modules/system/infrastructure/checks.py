"""Comprobaciones reales de SQL Server, Redis y el almacenamiento documental."""

from __future__ import annotations

import logging
import os
import uuid
from collections.abc import Mapping

from sqlalchemy import Connection, text

from app.core.config.settings import Settings
from app.core.schema_version import SCHEMA_VERSION
from app.modules.system.application.health import HealthCheck

logger = logging.getLogger(__name__)


def _database_check(settings: Settings) -> HealthCheck:
    def check() -> bool | None:
        if settings.database_url is None:
            return None
        from app.infrastructure.database.engine import get_engine

        with get_engine(settings.database_url.get_secret_value()).connect() as connection:
            connection.execute(text("SELECT 1"))
        return True

    return check


def installed_schema_version(connection: Connection) -> str | None:
    """Versión del esquema instalada, o ``None`` si la base aún no tiene tablas."""
    try:
        return connection.execute(text("SELECT version_num FROM alembic_version")).scalar()
    except Exception:  # noqa: BLE001  (la tabla no existe: base sin instalar)
        return None


def _schema_check(settings: Settings) -> HealthCheck:
    """La base debe tener exactamente la versión de esquema que espera el código.

    Evita dar servicio tras actualizar la aplicación sin ejecutar los scripts de
    la base (o al revés).
    """

    def check() -> bool | None:
        if settings.database_url is None:
            return None
        from app.infrastructure.database.engine import get_engine

        with get_engine(settings.database_url.get_secret_value()).connect() as connection:
            installed = installed_schema_version(connection)
        if installed != SCHEMA_VERSION:
            logger.error(
                "La base de datos tiene el esquema %s y la aplicación espera el %s.",
                installed or "sin instalar",
                SCHEMA_VERSION,
            )
            return False
        return True

    return check


def _redis_check(settings: Settings) -> HealthCheck:
    def check() -> bool | None:
        if settings.redis_url is None:
            return None
        import redis

        client = redis.Redis.from_url(
            settings.redis_url.get_secret_value(), socket_connect_timeout=2, socket_timeout=2
        )
        try:
            return bool(client.ping())
        finally:
            client.close()

    return check


def _storage_check(settings: Settings) -> HealthCheck:
    def check() -> bool | None:
        root = settings.storage_root
        if root is None:
            return None
        if not root.is_dir():
            return False
        # Se comprueba escritura real: un disco montado en solo lectura no sirve.
        probe = root / "processing" / "temporary" / f".salud-{uuid.uuid4().hex}"
        probe.parent.mkdir(parents=True, exist_ok=True)
        with open(probe, "wb") as handle:
            handle.write(b"ok")
            handle.flush()
            os.fsync(handle.fileno())
        probe.unlink()
        return True

    return check


def build_default_checks(settings: Settings) -> Mapping[str, HealthCheck]:
    return {
        "sql_server": _database_check(settings),
        "esquema": _schema_check(settings),
        "redis": _redis_check(settings),
        "almacenamiento": _storage_check(settings),
    }
