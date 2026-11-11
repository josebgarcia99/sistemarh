"""Configuración de la aplicación.

Todo valor se lee de variables de entorno con el prefijo ``RECLU_``. Ningún
secreto tiene valor por omisión y ninguno se escribe en el repositorio.
"""

from __future__ import annotations

from enum import StrEnum
from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Environment(StrEnum):
    DEVELOPMENT = "development"
    TEST = "test"
    PRODUCTION = "production"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="RECLU_", extra="ignore")

    environment: Environment = Environment.DEVELOPMENT
    app_name: str = "Sistema Integral de Reclutamiento e IA"
    api_prefix: str = "/api/v1"
    log_level: str = "INFO"

    # SQL Server. Formato: mssql+pyodbc://usuario:clave@servidor/base?driver=ODBC+Driver+18+for+SQL+Server
    database_url: SecretStr | None = None
    # Redis solo como intermediario de tareas.
    redis_url: SecretStr | None = None
    # Raíz del almacenamiento documental privado, fuera del directorio público.
    storage_root: Path | None = None

    # Zona horaria de presentación. Las fechas se guardan siempre en UTC.
    display_timezone: str = "America/Mexico_City"

    # Restricción 8 del documento maestro: en desarrollo y pruebas no se envían
    # documentos reales a proveedores de IA salvo autorización expresa.
    ai_allow_real_documents: bool = False

    max_upload_bytes: int = Field(default=20 * 1024 * 1024, gt=0)

    @model_validator(mode="after")
    def _validate_production(self) -> Settings:
        if self.environment is Environment.PRODUCTION:
            missing = [
                name
                for name, value in (
                    ("RECLU_DATABASE_URL", self.database_url),
                    ("RECLU_REDIS_URL", self.redis_url),
                    ("RECLU_STORAGE_ROOT", self.storage_root),
                )
                if value is None
            ]
            if missing:
                raise ValueError(
                    "Faltan variables obligatorias en producción: " + ", ".join(missing)
                )
        if self.storage_root is not None and not self.storage_root.is_absolute():
            raise ValueError("RECLU_STORAGE_ROOT debe ser una ruta absoluta")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
