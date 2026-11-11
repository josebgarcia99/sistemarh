"""Comprobaciones reales de SQL Server, Redis y el almacenamiento documental."""

from __future__ import annotations

import os
import uuid
from collections.abc import Mapping

from app.core.config.settings import Settings
from app.modules.system.application.health import HealthCheck


def _database_check(settings: Settings) -> HealthCheck:
    def check() -> bool | None:
        if settings.database_url is None:
            return None
        from sqlalchemy import text

        from app.infrastructure.database.engine import get_engine

        with get_engine(settings.database_url.get_secret_value()).connect() as connection:
            connection.execute(text("SELECT 1"))
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
        "redis": _redis_check(settings),
        "almacenamiento": _storage_check(settings),
    }
