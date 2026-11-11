from __future__ import annotations

from pathlib import Path

from app.core.config.settings import Environment, Settings
from app.modules.system.infrastructure.checks import build_default_checks


def test_live_responde_ok(client):
    response = client.get("/api/v1/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_ready_ok_cuando_todo_responde(make_client):
    client = make_client({"sql_server": lambda: True, "redis": lambda: True})
    response = client.get("/api/v1/health/ready")
    assert response.status_code == 200
    assert response.json()["ready"] is True


def test_ready_503_si_un_componente_falla(make_client):
    client = make_client({"sql_server": lambda: True, "redis": lambda: False})
    response = client.get("/api/v1/health/ready")
    assert response.status_code == 503
    body = response.json()
    assert body["ready"] is False
    assert {"name": "redis", "status": "fallo"} in body["components"]


def test_ready_503_si_un_componente_no_esta_configurado(make_client):
    client = make_client({"sql_server": lambda: None})
    response = client.get("/api/v1/health/ready")
    assert response.status_code == 503
    assert response.json()["components"] == [{"name": "sql_server", "status": "sin_configurar"}]


def test_ready_trata_una_excepcion_como_fallo_sin_filtrar_detalles(make_client):
    def roto() -> bool:
        raise RuntimeError("mssql+pyodbc://usuario:clave-secreta@servidor/base")

    client = make_client({"sql_server": roto})
    response = client.get("/api/v1/health/ready")
    assert response.status_code == 503
    assert "clave-secreta" not in response.text


def test_almacenamiento_comprueba_escritura_real(tmp_path: Path):
    settings = Settings(environment=Environment.TEST, storage_root=tmp_path)
    check = build_default_checks(settings)["almacenamiento"]
    assert check() is True
    # La comprobación no deja archivos de sonda.
    assert list((tmp_path / "processing" / "temporary").iterdir()) == []


def test_almacenamiento_falla_si_la_raiz_no_existe(tmp_path: Path):
    settings = Settings(environment=Environment.TEST, storage_root=tmp_path / "no-existe")
    assert build_default_checks(settings)["almacenamiento"]() is False


def test_componentes_sin_configurar_devuelven_none():
    checks = build_default_checks(Settings(environment=Environment.TEST))
    assert checks["sql_server"]() is None
    assert checks["redis"]() is None
    assert checks["almacenamiento"]() is None
