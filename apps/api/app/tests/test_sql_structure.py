"""Comprobación ESTRUCTURAL de los repositorios SQLAlchemy y de la migración.

Todavía no hay una instancia de SQL Server autorizada. Estas pruebas ejecutan
los repositorios reales sobre un motor en memoria solo para detectar errores de
mapeo y de consultas, y generan el T-SQL de la migración sin conectarse.

NO validan el comportamiento en SQL Server (tipos, intercalación, bloqueos,
paginación OFFSET/FETCH). Eso queda pendiente y está anotado en
``docs/estado_proyecto.md``. La aplicación sigue rechazando cualquier motor
distinto de SQL Server.
"""

from __future__ import annotations

import io
import os
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.composition.sql_backend import SqlBackend
from app.infrastructure.database.base import SCHEMA_AUTH, SCHEMA_OPS, Base
from app.main import create_app
from app.modules.audit.infrastructure import orm as _audit_orm  # noqa: F401
from app.modules.authentication.api.dependencies import CSRF_HEADER
from app.modules.authentication.infrastructure import orm as _auth_orm  # noqa: F401
from app.modules.users.infrastructure import orm as _users_orm  # noqa: F401
from app.modules.users.infrastructure.orm import RoleRow
from app.tests.conftest import new_client

REPO_ROOT = Path(__file__).resolve().parents[4]


@pytest.fixture
def sql_backend() -> SqlBackend:
    engine = sa.create_engine(
        "sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False}
    ).execution_options(schema_translate_map={SCHEMA_AUTH: None, SCHEMA_OPS: None})
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as session:
        session.add_all(
            [
                RoleRow(code="ADMINISTRADOR", name="Administrador"),
                RoleRow(code="RECLUTADOR", name="Reclutador"),
            ]
        )
        session.commit()
    return SqlBackend(factory)


def test_el_flujo_de_usuarios_funciona_con_los_repositorios_sqlalchemy(
    settings, sql_backend, hasher, clock
):
    app = create_app(
        settings=settings,
        health_checks={"x": lambda: True},
        backend=sql_backend,
        hasher=hasher,
        clock=clock,
    )
    context = app.state.context
    with sql_backend.transaction() as repos:
        context.user_service(repos).create_master_user(
            email="admin@ejemplo.test", full_name="Administradora", password="Clave-Maestra-2026"
        )

    client = new_client(app)
    session = client.post(
        "/api/v1/auth/login", json={"email": "admin@ejemplo.test", "password": "Clave-Maestra-2026"}
    )
    assert session.status_code == 200
    client.headers[CSRF_HEADER] = session.json()["csrf_token"]

    created = client.post(
        "/api/v1/users",
        json={
            "email": "reclutador@ejemplo.test",
            "full_name": "Reclutador Uno",
            "password": "Clave-Inicial-2026",
            "role": "RECLUTADOR",
        },
    )
    assert created.status_code == 201
    user_id = created.json()["id"]

    recruiter = new_client(app)
    assert (
        recruiter.post(
            "/api/v1/auth/login",
            json={"email": "reclutador@ejemplo.test", "password": "Clave-Inicial-2026"},
        ).status_code
        == 200
    )

    assert client.get("/api/v1/users", params={"search": "RECLUTADOR UNO"}).json()["total"] == 1
    promoted = client.patch(f"/api/v1/users/{user_id}", json={"role": "ADMINISTRADOR"})
    assert promoted.json()["role"] == "ADMINISTRADOR"
    reset = client.post(
        f"/api/v1/users/{user_id}/reset-password", json={"new_password": "Clave-Nueva-2026!"}
    )
    assert reset.json() == {"sessions_closed": 1}
    assert recruiter.get("/api/v1/auth/me").status_code == 401
    assert client.post(f"/api/v1/users/{user_id}/deactivate").json()["is_active"] is False

    clock.advance(minutes=5)
    me = client.get("/api/v1/auth/me").json()
    assert me["user"]["last_activity_at"] is not None

    events = client.get("/api/v1/audit/events", params={"page_size": 100}).json()
    actions = [event["action"] for event in events["items"]]
    for expected in (
        "usuario.creado",
        "sesion.inicio",
        "usuario.actualizado",
        "usuario.contrasena_restablecida",
        "usuario.desactivado",
    ):
        assert expected in actions
    # Las fechas vuelven con zona UTC.
    assert events["items"][0]["occurred_at"].endswith(("Z", "+00:00"))


def test_una_excepcion_revierte_la_transaccion(sql_backend, settings, hasher, clock):
    app = create_app(settings=settings, backend=sql_backend, hasher=hasher, clock=clock)
    context = app.state.context
    with pytest.raises(RuntimeError), sql_backend.transaction() as repos:
        context.user_service(repos).create_master_user(
            email="admin@ejemplo.test", full_name="Administradora", password="Clave-Maestra-2026"
        )
        raise RuntimeError("fallo simulado")
    with sql_backend.transaction() as repos:
        assert repos.users.get_by_email("admin@ejemplo.test") is None


def test_la_migracion_genera_t_sql_para_sql_server(monkeypatch):
    monkeypatch.setenv(
        "RECLU_DATABASE_URL",
        "mssql+pyodbc://usuario:clave@servidor/base?driver=ODBC+Driver+18+for+SQL+Server",
    )
    buffer = io.StringIO()
    config = Config(str(REPO_ROOT / "database" / "alembic.ini"), output_buffer=buffer)
    config.set_main_option("script_location", str(REPO_ROOT / "database" / "migrations"))
    previous = os.getcwd()
    try:
        os.chdir(REPO_ROOT / "database")
        command.upgrade(config, "head", sql=True)
    finally:
        os.chdir(previous)
    sql = buffer.getvalue()
    for fragment in (
        "CREATE SCHEMA [auth]",
        "CREATE TABLE auth.users",
        "CREATE TABLE auth.sessions",
        "CREATE TABLE ops.audit_events",
        "UNIQUEIDENTIFIER",
        "DATETIME2(3)",
        "ROWVERSION",
        "ISJSON(details) = 1",
        "INSERT INTO auth.roles",
        "CONSTRAINT pk_users PRIMARY KEY (id)",
    ):
        assert fragment in sql, f"Falta en el T-SQL generado: {fragment}"
    # Ninguna tabla tiene columna de identidad: este comando fallaría en SQL Server.
    assert "IDENTITY_INSERT" not in sql


def test_el_modelo_y_la_migracion_definen_las_mismas_columnas(monkeypatch):
    """Evita que el ORM y la migración escrita a mano se separen."""
    monkeypatch.setenv(
        "RECLU_DATABASE_URL",
        "mssql+pyodbc://usuario:clave@servidor/base?driver=ODBC+Driver+18+for+SQL+Server",
    )
    buffer = io.StringIO()
    config = Config(str(REPO_ROOT / "database" / "alembic.ini"), output_buffer=buffer)
    config.set_main_option("script_location", str(REPO_ROOT / "database" / "migrations"))
    previous = os.getcwd()
    try:
        os.chdir(REPO_ROOT / "database")
        command.upgrade(config, "head", sql=True)
    finally:
        os.chdir(previous)
    sql = buffer.getvalue()

    # Columnas que solo existen en SQL Server y el ORM no necesita leer.
    only_in_database = {"auth.users": {"row_version"}}
    for table in Base.metadata.tables.values():
        qualified = f"{table.schema}.{table.name}"
        start = sql.index(f"CREATE TABLE {qualified} (")
        body = sql[start : sql.index("\n)", start)]
        migrated = {
            line.strip().split(" ")[0]
            for line in body.splitlines()[1:]
            if line.strip() and not line.strip().startswith(("CONSTRAINT", "PRIMARY", "FOREIGN"))
        }
        expected = {column.name for column in table.columns} | only_in_database.get(
            qualified, set()
        )
        assert migrated == expected, f"{qualified}: {migrated ^ expected}"
