"""Repositorios SQLAlchemy y migraciones, sin una instancia de SQL Server.

- Los repositorios reales se ejecutan sobre un motor en memoria (ver
  ``app/tests/support/sql_memory.py``).
- Las migraciones se convierten a T-SQL sin conectarse y se comprueba que
  definen las mismas tablas y columnas que el modelo.

Nada de esto valida el comportamiento propio de SQL Server; lo pendiente está
anotado en ``docs/estado_proyecto.md``.
"""

from __future__ import annotations

import io
import os
import re
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config

from app.cli import SCHEMA_VERSION
from app.composition.sql_backend import SqlBackend
from app.infrastructure.database.base import Base
from app.main import create_app
from app.modules.audit.infrastructure import orm as _audit_orm  # noqa: F401
from app.modules.authentication.api.dependencies import CSRF_HEADER
from app.modules.authentication.infrastructure import orm as _auth_orm  # noqa: F401
from app.modules.users.infrastructure import orm as _users_orm  # noqa: F401
from app.tests.conftest import new_client
from app.tests.support.sql_memory import build_test_backend

REPO_ROOT = Path(__file__).resolve().parents[4]


@pytest.fixture
def sql_backend() -> SqlBackend:
    return build_test_backend()


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
        "CREATE SCHEMA [vacancy]",
        "CREATE TABLE vacancy.vacancies",
        "CREATE UNIQUE INDEX uq_vacancy_members_active",
        "WHERE revoked_at IS NULL",
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
    assert len(Base.metadata.tables) >= 10
    for table in Base.metadata.tables.values():
        qualified = f"{table.schema}.{table.name}"
        start = sql.index(f"CREATE TABLE {qualified} (")
        body = sql[start : sql.index("\n)", start)]
        migrated = {
            line.strip().split(" ")[0]
            for line in body.splitlines()[1:]
            if line.strip() and not line.strip().startswith(("CONSTRAINT", "PRIMARY", "FOREIGN"))
        }
        # Columnas añadidas por migraciones posteriores.
        migrated |= set(
            re.findall(rf"ALTER TABLE {re.escape(qualified)} ADD (?!CONSTRAINT)(\w+) ", sql)
        )
        expected = {column.name for column in table.columns} | only_in_database.get(
            qualified, set()
        )
        assert migrated == expected, f"{qualified}: {migrated ^ expected}"


def test_ninguna_columna_usa_tipos_obsoletos_de_sql_server():
    from sqlalchemy.dialects import mssql

    dialect = mssql.dialect()
    obsolete = {
        f"{table.name}.{column.name}"
        for table in Base.metadata.tables.values()
        for column in table.columns
        if column.type.compile(dialect=dialect).upper() in {"NTEXT", "TEXT", "IMAGE"}
    }
    assert obsolete == set()


# --- Revisión de SQL Server (Fase 8) -------------------------------------------------------


def _generated_sql(monkeypatch, *, downgrade: bool = False) -> str:
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
        if downgrade:
            command.downgrade(config, "head:base", sql=True)
        else:
            command.upgrade(config, "head", sql=True)
    finally:
        os.chdir(previous)
    return buffer.getvalue()


def test_el_modelo_y_la_migracion_definen_los_mismos_indices(monkeypatch):
    """Un índice declarado en el ORM que no esté en la migración existiría en
    las pruebas pero no en SQL Server."""
    sql = _generated_sql(monkeypatch)
    created = {
        name: (bool(unique), f"{table}", [c.strip() for c in columns.split(",")])
        for unique, name, table, columns in re.findall(
            r"CREATE (UNIQUE )?INDEX (\w+) ON ([\w.]+) \(([^)]+)\)", sql
        )
    }
    dropped = set(re.findall(r"DROP INDEX (\w+) ON", sql))
    declared = {
        index.name: (
            bool(index.unique),
            f"{table.schema}.{table.name}",
            [column.name for column in index.columns],
        )
        for table in Base.metadata.tables.values()
        for index in table.indexes
    }
    assert len(declared) >= 30
    missing = {name: spec for name, spec in declared.items() if created.get(name) != spec}
    assert not missing, f"Índices del ORM que la migración no crea igual: {missing}"
    # Y al revés: lo que la migración crea (y no elimina después) está en el ORM
    # o es una restricción única declarada en la columna.
    unique_columns = {
        (f"{table.schema}.{table.name}", column.name)
        for table in Base.metadata.tables.values()
        for column in table.columns
        if column.unique
    }
    extra = {
        name
        for name, (_, table, columns) in created.items()
        if name not in declared
        and name not in dropped
        and not (len(columns) == 1 and (table, columns[0]) in unique_columns)
    }
    assert not extra, f"Índices de la migración que el ORM no declara: {extra}"


# Claves foráneas sin índice propio, a propósito. Las tablas son pequeñas o la
# columna no se usa para buscar. Revisado en docs/database/revision_sql_server.md.
UNINDEXED_ON_PURPOSE = {
    "auth.user_roles.role_code",
    "ai.operation_assignments.model_ref",
    "ai.prompt_versions.profile_version_id",
    "ai.prompt_versions.duplicated_from",
    "ai.cv_batches.report_file_id",
    "ai.cv_batches.accepted_zip_file_id",
    "ai.cv_batches.rejected_zip_file_id",
    "ai.cv_batches.unevaluable_zip_file_id",
    "ai.cv_batch_items.duplicate_of",
    "vacancy.job_profile_versions.source_file_id",
    "vacancy.vacancy_ownership_history.transfer_id",
    "recruitment.campaigns.pipeline_version_id",
    "recruitment.question_banks.duplicated_from",
    "recruitment.applications.stage_id",
    "recruitment.application_movements.from_stage_id",
    "recruitment.application_movements.to_stage_id",
    "recruitment.application_syntheses.vacancy_id",
    "recruitment.assessments.vacancy_id",
    "recruitment.assessments.file_id",
    "recruitment.assessments.template_version_id",
}


def test_las_claves_foraneas_sin_indice_son_una_decision_revisada():
    """SQL Server no indexa las claves foráneas. Las de autoría (hacia usuarios)
    no lo necesitan; cualquier otra sin índice debe estar en la lista revisada."""
    unindexed = set()
    for table in Base.metadata.tables.values():
        leading = {next(iter(index.columns)).name for index in table.indexes if index.columns}
        leading |= {column.name for column in table.columns if column.unique}
        for constraint in table.constraints:
            columns = list(getattr(constraint, "columns", []))
            if (
                type(constraint).__name__ in ("PrimaryKeyConstraint", "UniqueConstraint")
                and columns
            ):
                leading.add(columns[0].name)
        for key in table.foreign_key_constraints:
            column = key.column_keys[0]
            if column not in leading and key.referred_table.fullname != "auth.users":
                unindexed.add(f"{table.schema}.{table.name}.{column}")
    assert unindexed == UNINDEXED_ON_PURPOSE, unindexed ^ UNINDEXED_ON_PURPOSE


def test_las_migraciones_forman_una_cadena_y_todas_se_pueden_revertir(monkeypatch):
    """Pruebas de migración sin servidor: una sola línea de revisiones, cada una
    con su reversión documentada, y una reversión completa que elimina todo."""
    from alembic.script import ScriptDirectory

    config = Config(str(REPO_ROOT / "database" / "alembic.ini"))
    config.set_main_option("script_location", str(REPO_ROOT / "database" / "migrations"))
    scripts = ScriptDirectory.from_config(config)
    assert len(scripts.get_heads()) == 1
    revisions = list(scripts.walk_revisions())
    numbers = sorted(script.revision for script in revisions)
    assert numbers == [f"{n:04d}" for n in range(1, len(numbers) + 1)]
    assert numbers[-1] == SCHEMA_VERSION
    for script in revisions:
        assert script.down_revision == (
            f"{int(script.revision) - 1:04d}" if script.revision != "0001" else None
        )
        assert "Reversión" in (script.doc or "") or "Reversión" in (script.module.__doc__ or "")

    down = _generated_sql(monkeypatch, downgrade=True)
    for table in Base.metadata.tables.values():
        assert f"DROP TABLE {table.schema}.{table.name}" in down, table.name


def test_las_validaciones_de_integridad_solo_leen_y_usan_columnas_que_existen():
    """El script que ejecuta Sistemas no puede probarse aquí contra SQL Server,
    pero sí se comprueba que es una sola consulta de lectura y que cada tabla y
    columna que nombra existe en el modelo."""
    sqlglot = pytest.importorskip("sqlglot")
    from sqlglot import exp
    from sqlglot.optimizer.qualify import qualify

    text = (REPO_ROOT / "database" / "sqlserver" / "validaciones_integridad.sql").read_text()
    statements = [s for s in sqlglot.parse(text, read="tsql") if s is not None]
    selects = [s for s in statements if isinstance(s, exp.Select)]
    assert len(selects) == 1 and len(statements) == 2  # SET NOCOUNT ON y la consulta
    for forbidden in (exp.Insert, exp.Update, exp.Delete, exp.Drop, exp.Alter, exp.Create):
        assert not any(statement.find(forbidden) for statement in statements), forbidden

    schema: dict[str, dict[str, dict[str, str]]] = {
        "dbo": {"alembic_version": {"version_num": "varchar"}}
    }
    for table in Base.metadata.tables.values():
        schema.setdefault(table.schema, {})[table.name] = {
            column.name: "varchar" for column in table.columns
        }
    # Falla si se nombra una tabla o una columna que no existe.
    qualify(selects[0], schema=schema, dialect="tsql", validate_qualify_columns=True)
    referenced = {f"{t.db}.{t.name}" for t in selects[0].find_all(exp.Table) if t.db}
    assert len(referenced) >= 10 and len(re.findall(r"SELECT '\d\d\. ", text)) == 18
    assert f"'{SCHEMA_VERSION}'" in text
