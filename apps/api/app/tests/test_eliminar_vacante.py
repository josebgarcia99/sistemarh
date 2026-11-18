"""Eliminar una vacante: solo administradores, confirmando el nombre, y se lleva
todo lo que contiene sin tocar nada de las demás."""

# ruff: noqa: F401, F811  (las fixtures se importan de otro módulo de pruebas)
from __future__ import annotations

import uuid

import pytest
import sqlalchemy as sa
from sqlalchemy.exc import ProgrammingError

from app.composition import vacancy_deletion
from app.infrastructure.database.base import Base
from app.sample_data import content
from app.sample_data.loader import load
from app.tests.test_analista_estudios import analyst
from app.tests.test_api_assessments import ana
from app.tests.test_api_cv_batches import (
    ADMIN_EMAIL,
    API,
    RECRUITER_EMAIL,
    admin,
    app,
    audit,
    model,
    other,
    prompt,
    providers,
    recruiter,
    upload,
    vacancy_id,
)
from app.tests.test_api_recruitment import by_name, evaluated, new_bank


def _rows(app, vacancy: str) -> dict[str, int]:
    """Cuántas filas quedan de esa vacante en cada tabla que la menciona."""
    found: dict[str, int] = {}
    with app.state.context.require_backend().transaction() as repos:
        session = repos.vacancy_purge._session
        for table in Base.metadata.tables.values():
            column = table.c.get("vacancy_id")
            if column is None:
                continue
            count = session.execute(
                sa.select(sa.func.count()).select_from(table).where(column == uuid.UUID(vacancy))
            ).scalar_one()
            if count:
                found[table.fullname] = count
    return found


def _total(app, table: str) -> int:
    with app.state.context.require_backend().transaction() as repos:
        return repos.vacancy_purge._session.execute(
            sa.select(sa.func.count()).select_from(Base.metadata.tables[table])
        ).scalar_one()


def test_un_administrador_elimina_una_vacante_con_todo_su_contenido(
    app, admin, recruiter, analyst, ana, vacancy_id
):
    context = app.state.context
    storage = context.storage
    # Una vacante que no se debe tocar, con sus archivos.
    kept_files = set(storage.iter_keys())
    assert kept_files
    # La vacante de prueba completa: personas en cada etapa, llamadas, evaluaciones,
    # estudio con documentos, síntesis y un resultado final.
    sample = str(load(context, RECRUITER_EMAIL).vacancy_id)
    url = f"{API}/vacancies/{sample}/deletion"
    kept_before = _rows(app, vacancy_id)
    assert len(set(storage.iter_keys())) > len(kept_files)
    # Una persona de la vacante de prueba también se postula en la otra: se conserva.
    board = recruiter.get(f"{API}/vacancies/{sample}/applications").json()["applications"]
    shared = next(item for item in board if item["full_name"] == "Mariana Ficticia Ortega")
    with context.require_backend().transaction() as repos:
        session = repos.vacancy_purge._session
        applications = Base.metadata.tables["recruitment.applications"]
        other_application = session.execute(
            sa.select(applications.c.id).where(applications.c.vacancy_id == uuid.UUID(vacancy_id))
        ).scalar()
        candidate = session.execute(
            sa.select(applications.c.candidate_id).where(
                applications.c.id == uuid.UUID(shared["id"])
            )
        ).scalar_one()
        session.execute(
            sa.update(applications)
            .where(applications.c.id == other_application)
            .values(candidate_id=candidate)
        )
    candidates_before = _total(app, "recruitment.candidates")
    costs_before = _total(app, "ai.executions")
    sample_rows = _rows(app, sample)
    assert {
        "recruitment.applications",
        "recruitment.call_sessions",
        "recruitment.assessments",
        "recruitment.application_syntheses",
        "recruitment.application_outcomes",
        "recruitment.campaigns",
        "ai.cv_batches",
        "ai.prompt_versions",
        "vacancy.job_profile_versions",
        "files.file_assets",
    } <= set(sample_rows)

    # Solo un administrador: ni quien es responsable de la vacante ni la analista.
    for client in (recruiter, analyst):
        assert client.get(url).status_code == 403
        assert client.post(url, json={"confirm_name": content.VACANCY_NAME}).status_code == 403
    assert admin.get(f"{API}/vacancies/{uuid.uuid4()}/deletion").status_code == 404

    # Antes de borrar se ve qué contiene.
    preview = admin.get(url)
    assert preview.status_code == 200, preview.text
    shown = preview.json()
    assert shown["name"] == content.VACANCY_NAME and shown["active_batches"] == 0
    assert shown["applications"] == 11 and shown["cv_files"] == 11
    # Diez de once: Mariana tiene postulación en otra vacante y no se borra.
    assert shown["candidates"] == 10
    assert shown["calls"] >= 5 and shown["assessments"] >= 5 and shown["documents"] >= 11
    assert _rows(app, sample) == sample_rows  # ver no cambia nada

    # Hay que escribir el nombre de la vacante: con otro texto no se borra nada.
    wrong = admin.post(url, json={"confirm_name": "otra vacante"})
    assert wrong.status_code == 422 and "No se eliminó nada" in wrong.json()["detail"]
    assert _rows(app, sample) == sample_rows

    # Con CV en proceso tampoco.
    batches = Base.metadata.tables["ai.cv_batches"]
    with context.require_backend().transaction() as repos:
        session = repos.vacancy_purge._session
        batch_id, status = session.execute(
            sa.select(batches.c.id, batches.c.status).where(
                batches.c.vacancy_id == uuid.UUID(sample)
            )
        ).first()
        session.execute(
            sa.update(batches).where(batches.c.id == batch_id).values(status="PROCESANDO")
        )
    busy = admin.post(url, json={"confirm_name": content.VACANCY_NAME})
    assert busy.status_code == 409 and "CV en proceso" in busy.json()["detail"]
    with context.require_backend().transaction() as repos:
        repos.vacancy_purge._session.execute(
            sa.update(batches).where(batches.c.id == batch_id).values(status=status)
        )
    assert _rows(app, sample) == sample_rows

    # Se elimina, sin importar mayúsculas ni espacios de más en el nombre.
    done = admin.post(url, json={"confirm_name": f"  {content.VACANCY_NAME.upper()}  "})
    assert done.status_code == 200, done.text
    result = done.json()
    assert result["applications"] == 11 and result["candidates"] == 10
    assert result["files_removed"] == shown["documents"] and result["files_pending"] == 0

    # No queda nada de ella: ni en las tablas ni en el servidor ni en las pantallas.
    # (solo el costo de IA, que es historial contable y no guarda contenido).
    assert set(_rows(app, sample)) <= {"ai.executions"}
    assert set(storage.iter_keys()) == kept_files
    assert admin.get(f"{API}/vacancies/{sample}").status_code == 404
    assert admin.get(url).status_code == 404
    names = [item["name"] for item in admin.get(f"{API}/vacancies").json()["items"]]
    assert content.VACANCY_NAME not in names
    assert admin.get(f"{API}/applications/{shared['id']}/calls").status_code == 404

    # Lo demás sigue igual: la otra vacante, sus archivos y la persona compartida.
    assert _rows(app, vacancy_id) == kept_before
    assert _total(app, "recruitment.candidates") == candidates_before - 10
    assert recruiter.get(f"{API}/applications/{ana}/calls").status_code == 200
    # El costo de IA es historial contable y la conciliación no encuentra huecos.
    assert _total(app, "ai.executions") == costs_before
    reconciled = admin.post(f"{API}/storage/reconciliation", json={}).json()
    assert reconciled["orphans_quarantined"] == 0 and reconciled["missing_files"] == []

    # Queda registrado quién eliminó qué.
    [event] = audit(admin, "vacante.eliminada")
    assert event["resource_id"] == sample
    assert event["details"]["nombre"] == content.VACANCY_NAME
    assert event["details"]["postulaciones"] == 11 and event["details"]["candidatos"] == 10
    # Una segunda vez ya no existe.
    assert admin.post(url, json={"confirm_name": content.VACANCY_NAME}).status_code == 404


def test_si_la_base_no_permite_borrar_se_explica_y_no_se_elimina_nada(
    app, admin, recruiter, vacancy_id, monkeypatch
):
    """En SQL Server el usuario de la aplicación no puede borrar hasta que Sistemas
    le dé el permiso: el aviso lo dice y la vacante queda intacta."""
    before = _rows(app, vacancy_id)
    name = admin.get(f"{API}/vacancies/{vacancy_id}").json()["name"]

    def denied(self, vacancy):  # noqa: ANN001
        raise ProgrammingError("DELETE", {}, Exception("The DELETE permission was denied"))

    monkeypatch.setattr(vacancy_deletion.SqlVacancyPurge, "purge", denied)
    refused = admin.post(f"{API}/vacancies/{vacancy_id}/deletion", json={"confirm_name": name})
    assert refused.status_code == 409
    assert "permisos_eliminar_vacantes.sql" in refused.json()["detail"]
    assert _rows(app, vacancy_id) == before
    assert admin.get(f"{API}/vacancies/{vacancy_id}").status_code == 200
    assert audit(admin, "vacante.eliminada") == []
