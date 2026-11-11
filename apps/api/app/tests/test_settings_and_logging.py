from __future__ import annotations

import json
import logging

import pytest
from pydantic import ValidationError

from app.core.config.settings import Environment, Settings
from app.core.logging.setup import REDACTED, JsonFormatter, RedactingFilter, redact
from app.infrastructure.database.engine import UnsupportedDatabaseError, validate_database_url


def test_produccion_exige_base_de_datos_redis_y_almacenamiento():
    with pytest.raises(ValidationError) as error:
        Settings(environment=Environment.PRODUCTION)
    message = str(error.value)
    assert "RECLU_DATABASE_URL" in message
    assert "RECLU_REDIS_URL" in message
    assert "RECLU_STORAGE_ROOT" in message


def test_el_almacenamiento_debe_ser_ruta_absoluta():
    with pytest.raises(ValidationError):
        Settings(environment=Environment.TEST, storage_root="relativa/storage")


def test_los_documentos_reales_estan_bloqueados_por_omision():
    assert Settings(environment=Environment.TEST).ai_allow_real_documents is False


def test_los_secretos_no_aparecen_al_imprimir_la_configuracion():
    settings = Settings(
        environment=Environment.TEST,
        database_url="mssql+pyodbc://usuario:clave-secreta@servidor/base",
    )
    assert "clave-secreta" not in repr(settings)
    assert "clave-secreta" not in str(settings.model_dump())


@pytest.mark.parametrize(
    "url",
    ["sqlite:///local.db", "postgresql://u:p@host/db", "mssql+pymssql://u:p@host/db"],
)
def test_solo_se_admite_sql_server_con_pyodbc(url):
    with pytest.raises(UnsupportedDatabaseError):
        validate_database_url(url)


def test_se_admite_sql_server_con_pyodbc():
    validate_database_url(
        "mssql+pyodbc://u:p@servidor/base?driver=ODBC+Driver+18+for+SQL+Server"
    )


@pytest.mark.parametrize(
    ("texto", "secreto"),
    [
        ("clave sk-ant-api03-CLAVE-FICTICIA-0000 usada", "sk-ant-api03-CLAVE-FICTICIA-0000"),
        ("clave sk-proj-CLAVE-FICTICIA-0000 usada", "sk-proj-CLAVE-FICTICIA-0000"),
        ("Authorization: Bearer abcdef1234567890.token", "abcdef1234567890.token"),
        ("password=MiClave!2026 enviada", "MiClave!2026"),
        ('{"api_key": "valor-muy-secreto"}', "valor-muy-secreto"),
        ("contraseña: Temporal123", "Temporal123"),
        ("mssql+pyodbc://usuario:clave-secreta@servidor/base", "clave-secreta"),
    ],
)
def test_redact_oculta_secretos(texto, secreto):
    resultado = redact(texto)
    assert secreto not in resultado
    assert REDACTED in resultado


def test_redact_no_altera_texto_normal():
    texto = "Lote L-0009 completado con 3 incidencias"
    assert redact(texto) == texto


def test_el_log_sale_en_json_y_sin_secretos():
    record = logging.LogRecord(
        name="prueba",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="Conectando con %s",
        args=("mssql+pyodbc://usuario:clave-secreta@servidor/base",),
        exc_info=None,
    )
    assert RedactingFilter().filter(record) is True
    payload = json.loads(JsonFormatter().format(record))
    assert payload["level"] == "INFO"
    assert "clave-secreta" not in payload["message"]
    assert "correlation_id" in payload
