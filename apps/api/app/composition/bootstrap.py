"""Construcción de las dependencias reales a partir de la configuración.

Lo usan la API, la línea de comandos y el worker, para que los tres trabajen
con la misma base de datos, el mismo almacenamiento y la misma clave maestra.
"""

from __future__ import annotations

from app.composition.ai import build_provider_clients
from app.composition.backend import Backend
from app.composition.context import AppContext
from app.core.clock import utc_now
from app.core.config.settings import AntivirusMode, Settings
from app.core.security.master_key import MasterKey
from app.core.security.passwords import Argon2Hasher
from app.infrastructure.antivirus.scanner import ClamdScanner, DisabledScanner, MalwareScanner
from app.infrastructure.storage.local import LocalFileStorage
from app.modules.authentication.domain.models import AuthPolicy


def build_sql_backend(settings: Settings) -> Backend | None:
    """Backend sobre SQL Server, o ``None`` si aún no hay base configurada."""
    if settings.database_url is None:
        return None
    from app.composition.sql_backend import SqlBackend
    from app.infrastructure.database.engine import get_session_factory

    try:
        factory = get_session_factory(settings.database_url.get_secret_value())
    except ImportError as error:
        raise RuntimeError(
            "No se pudo cargar el controlador de SQL Server. Instala "
            "Microsoft ODBC Driver 18 for SQL Server en este equipo."
        ) from error
    return SqlBackend(factory)


def build_storage(settings: Settings) -> LocalFileStorage | None:
    """Almacenamiento documental, o ``None`` si aún no hay carpeta configurada.

    Si la carpeta configurada no existe, el arranque falla: es preferible a
    guardar documentos en un lugar que no persiste.
    """
    if settings.storage_root is None:
        return None
    storage = LocalFileStorage(settings.storage_root)
    storage.prepare()
    return storage


def build_master_key(settings: Settings) -> MasterKey | None:
    """Clave maestra, o ``None`` si no está configurada. Si el archivo indicado
    falta o no es válido, el arranque falla."""
    if settings.master_key_file is None:
        return None
    return MasterKey.load(settings.master_key_file)


def build_scanner(settings: Settings) -> MalwareScanner:
    if settings.antivirus_mode is AntivirusMode.CLAMD:
        return ClamdScanner(settings.clamd_host, settings.clamd_port)
    return DisabledScanner()


def default_job_mode(settings: Settings) -> str:
    """Con Redis configurado los trabajos van al worker; sin él, a un hilo de la API."""
    return "celery" if settings.redis_url is not None else "thread"


def build_context(settings: Settings, *, job_mode: str | None = None) -> AppContext:
    return AppContext(
        settings=settings,
        backend=build_sql_backend(settings),
        hasher=Argon2Hasher(),
        clock=utc_now,
        auth_policy=AuthPolicy(),
        storage=build_storage(settings),
        scanner=build_scanner(settings),
        master_key=build_master_key(settings),
        ai_clients=build_provider_clients(settings),
        job_mode=job_mode or default_job_mode(settings),
    )
