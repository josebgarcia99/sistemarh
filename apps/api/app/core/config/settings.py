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


class AntivirusMode(StrEnum):
    CLAMD = "clamd"
    DISABLED = "disabled"


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
    # Las cargas se rechazan si el disco de documentos tiene menos espacio libre.
    storage_min_free_bytes: int = Field(default=1024 * 1024 * 1024, ge=0)

    # Antivirus local: "clamd" (ClamAV en la infraestructura propia) o "disabled".
    # En producción debe elegirse de forma expresa.
    antivirus_mode: AntivirusMode | None = None
    clamd_host: str = "clamav"
    clamd_port: int = Field(default=3310, gt=0, lt=65536)

    # Archivo con la clave maestra (AES-256), fuera de SQL Server y del
    # repositorio. Cifra las API keys de IA y los documentos de clase sensible.
    master_key_file: Path | None = None

    # API keys inyectadas por Sistemas como variables de entorno del servidor.
    # Alternativa a registrarlas en la pantalla; nunca van en el repositorio.
    anthropic_api_key: SecretStr | None = None
    openai_api_key: SecretStr | None = None
    # Versión de la API de Anthropic que se envía en cada solicitud.
    anthropic_api_version: str = "2026-10-21"

    # Sin clave maestra, los documentos de clase sensible no se aceptan. Esta
    # opción los admite sin cifrar; solo para desarrollo con datos sintéticos.
    allow_unencrypted_sensitive_files: bool = False

    @model_validator(mode="after")
    def _validate_production(self) -> Settings:
        if self.environment is Environment.PRODUCTION:
            missing = [
                name
                for name, value in (
                    ("RECLU_DATABASE_URL", self.database_url),
                    ("RECLU_REDIS_URL", self.redis_url),
                    ("RECLU_STORAGE_ROOT", self.storage_root),
                    ("RECLU_ANTIVIRUS_MODE", self.antivirus_mode),
                    ("RECLU_MASTER_KEY_FILE", self.master_key_file),
                )
                if value is None
            ]
            if missing:
                raise ValueError(
                    "Faltan variables obligatorias en producción: " + ", ".join(missing)
                )
            if self.allow_unencrypted_sensitive_files:
                raise ValueError(
                    "RECLU_ALLOW_UNENCRYPTED_SENSITIVE_FILES no puede activarse en producción"
                )
        if self.storage_root is not None and not self.storage_root.is_absolute():
            raise ValueError("RECLU_STORAGE_ROOT debe ser una ruta absoluta")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
