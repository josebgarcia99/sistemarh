from __future__ import annotations

import uuid

from fastapi import APIRouter
from fastapi.testclient import TestClient

from app.core.config.settings import Environment, Settings
from app.core.exceptions.errors import ConflictError, NotFoundError
from app.core.security.master_key import generate_key_text
from app.main import create_app
from app.tests.support.sql_memory import build_test_backend

HEADER = "X-Correlation-ID"


def _client_with_failing_routes() -> TestClient:
    app = create_app(
        settings=Settings(environment=Environment.TEST), health_checks={"x": lambda: True}
    )
    router = APIRouter()

    @router.get("/_prueba/no-encontrado")
    def _no_encontrado():
        raise NotFoundError()

    @router.get("/_prueba/conflicto")
    def _conflicto():
        raise ConflictError("La vacante cambió desde tu última lectura.")

    @router.get("/_prueba/explota")
    def _explota():
        raise RuntimeError("password=supersecreta ruta=/srv/reclutamiento/storage/private")

    @router.get("/_prueba/entero/{valor}")
    def _entero(valor: int):
        return {"valor": valor}

    app.include_router(router)
    return TestClient(app)


def test_se_genera_un_identificador_de_correlacion(client):
    response = client.get("/api/v1/health/live")
    uuid.UUID(response.headers[HEADER])


def test_se_reutiliza_un_identificador_valido(client):
    response = client.get("/api/v1/health/live", headers={HEADER: "peticion-12345678"})
    assert response.headers[HEADER] == "peticion-12345678"


def test_se_descarta_un_identificador_inseguro(client):
    response = client.get("/api/v1/health/live", headers={HEADER: "<script>alert(1)</script>"})
    assert response.headers[HEADER] != "<script>alert(1)</script>"
    uuid.UUID(response.headers[HEADER])


def test_error_de_negocio_usa_el_formato_uniforme():
    response = _client_with_failing_routes().get("/_prueba/conflicto")
    assert response.status_code == 409
    assert response.headers["content-type"].startswith("application/problem+json")
    body = response.json()
    assert body["code"] == "conflicto"
    assert body["detail"] == "La vacante cambió desde tu última lectura."
    assert body["correlation_id"] == response.headers[HEADER]


def test_no_encontrado_usa_el_formato_uniforme():
    response = _client_with_failing_routes().get("/_prueba/no-encontrado")
    assert response.status_code == 404
    assert response.json()["code"] == "no_encontrado"


def test_ruta_inexistente_usa_el_formato_uniforme(client):
    response = client.get("/api/v1/no-existe")
    assert response.status_code == 404
    assert response.json()["code"] == "http_404"


def test_error_de_validacion_lista_los_campos():
    response = _client_with_failing_routes().get("/_prueba/entero/abc")
    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "validacion"
    assert body["errors"][0]["campo"] == "path.valor"


def test_error_inesperado_no_revela_detalles_y_conserva_la_correlacion():
    response = _client_with_failing_routes().get("/_prueba/explota")
    assert response.status_code == 500
    assert "supersecreta" not in response.text
    assert "/srv/reclutamiento" not in response.text
    body = response.json()
    assert body["code"] == "error_interno"
    assert body["correlation_id"] == response.headers[HEADER]


def test_la_documentacion_no_se_publica_en_produccion(tmp_path):
    settings = Settings(
        environment=Environment.PRODUCTION,
        database_url="mssql+pyodbc://u:p@servidor/base?driver=ODBC+Driver+18+for+SQL+Server",
        redis_url="redis://redis:6379/0",
        storage_root=tmp_path,
        antivirus_mode="disabled",
        master_key_file=tmp_path / "clave",
    )
    (tmp_path / "clave").write_text(generate_key_text())
    app = create_app(
        settings=settings, health_checks={"x": lambda: True}, backend=build_test_backend()
    )
    client = TestClient(app)
    assert client.get("/api/v1/docs").status_code == 404
    assert client.get("/api/v1/openapi.json").status_code == 404
