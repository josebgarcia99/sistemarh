"""Datos de prueba: una vacante ficticia con personas en cada etapa, sin IA."""

# ruff: noqa: F401, F811  (las fixtures se importan de otro módulo de pruebas)
from __future__ import annotations

from dataclasses import replace

import pytest

from app.core.config.settings import Environment
from app.core.exceptions.errors import ConflictError, ValidationFailedError
from app.sample_data import content
from app.sample_data.loader import load
from app.tests.test_analista_estudios import analyst
from app.tests.test_api_cv_batches import (
    ADMIN_EMAIL,
    API,
    RECRUITER_EMAIL,
    admin,
    app,
    providers,
    recruiter,
)


@pytest.fixture
def context(app, recruiter):
    return app.state.context


def test_carga_una_vacante_con_personas_en_cada_etapa(context, recruiter, admin):
    ai_before = [admin.get(f"{API}/ai/{part}").json() for part in ("providers", "assignments")]
    summary = load(context, RECRUITER_EMAIL)
    assert summary.warnings == []
    assert summary.people == {
        "Mariana Ficticia Ortega": "Estudio socioeconómico",
        "Luis Ficticio Herrera": "Prueba técnica",
        "Sofía Ficticia Rangel": "Entrevista con gerente",
        "Diego Ficticio Morales": "Pruebas psicométricas",
        "Valeria Ficticia Núñez": "Llamada telefónica",
        "Jorge Ficticio Salas": "Llamada telefónica",
        "Paola Ficticia Rivas": "Revisión local RH",
        "Andrés Ficticio Cano": "Revisión local RH",
        "Fernanda Ficticia Lugo": "Llamada telefónica · Desistio",
        "Elena Ficticia Duarte": "Resultado final · Contratado",
    }
    vacancy = f"{API}/vacancies/{summary.vacancy_id}"
    assert recruiter.get(vacancy).json()["name"] == content.VACANCY_NAME

    # Las pantallas lo ven por las mismas rutas de siempre.
    board = recruiter.get(f"{vacancy}/applications").json()
    people = {item["full_name"]: item for item in board["applications"]}
    assert len(people) == 11  # diez personas y el CV escaneado
    stages = {stage["id"]: stage["name"] for stage in board["pipeline"]["stages"]}
    assert stages[people["Sofía Ficticia Rangel"]["stage_id"]] == "Entrevista con gerente"
    assert people["Mariana Ficticia Ortega"]["ai_classification"] == "ACEPTADO_IA"
    assert people["Mariana Ficticia Ortega"]["email"] == "mariana@ejemplo.test"
    # La IA rechazó a Jorge y aun así RH lo avanzó, con su motivo.
    assert people["Jorge Ficticio Salas"]["ai_classification"] == "RECHAZADO_IA"
    assert people["Andrés Ficticio Cano"]["ai_classification"] == "RECHAZADO_IA"
    assert sum(1 for item in people.values() if item["ai_classification"] == "NO_EVALUABLE") == 1
    assert people["Elena Ficticia Duarte"]["status"] != "ACTIVA"
    assert board["hires"] == 1

    mariana = people["Mariana Ficticia Ortega"]["id"]
    kinds = {
        item["kind"]: item
        for item in recruiter.get(f"{API}/applications/{mariana}/assessments").json()["items"]
    }
    assert set(kinds) == {
        "PSICOMETRIA",
        "ENTREVISTA",
        "PRUEBA_TECNICA",
        "REFERENCIAS",
        "ESTUDIO_SOCIOECONOMICO",
    }
    assert kinds["ESTUDIO_SOCIOECONOMICO"]["status"] == "EN_PROCESO"
    assert kinds["REFERENCIAS"]["ai_summary"]["sin_confirmar"]
    assert kinds["PRUEBA_TECNICA"]["score"] == "88.00"
    synthesis = recruiter.get(f"{API}/applications/{mariana}/syntheses").json()
    assert synthesis["latest"]["result"]["preguntas_sugeridas"]
    call = recruiter.get(f"{API}/applications/{mariana}/calls").json()[0]
    assert call["status"] == "CERRADA" and call["analysis"]["medicion"]["score"] is not None
    # Quien se queda en llamada la tiene abierta, a medias.
    valeria = recruiter.get(f"{API}/applications/{people['Valeria Ficticia Núñez']['id']}/calls")
    assert valeria.json()[0]["status"] == "BORRADOR"

    # No configuró ni usó la IA: ni claves, ni asignaciones, ni consumo.
    today = context.clock()
    usage = admin.get(f"{API}/ai/usage", params={"year": today.year, "month": today.month})
    assert usage.status_code == 200 and usage.json()["rows"] == []
    ai_after = [admin.get(f"{API}/ai/{part}").json() for part in ("providers", "assignments")]
    assert ai_after == ai_before

    # Queda en la auditoría a nombre de quien figura como responsable.
    events = admin.get(f"{API}/audit/events", params={"action": "vacante.creada"}).json()
    assert events["total"] >= 1


def test_no_se_repite_ni_se_carga_donde_no_debe(context, recruiter, analyst, admin):
    load(context, RECRUITER_EMAIL)
    with pytest.raises(ConflictError, match="ya tiene la vacante"):
        load(context, RECRUITER_EMAIL)
    with pytest.raises(ValidationFailedError, match="No hay un usuario activo"):
        load(context, "nadie@ejemplo.test")
    with pytest.raises(ValidationFailedError, match="administrador o reclutador"):
        load(context, "analista@ejemplo.test")
    # En producción se niega, salvo autorización expresa.
    production = replace(
        context,
        settings=context.settings.model_copy(update={"environment": Environment.PRODUCTION}),
    )
    with pytest.raises(ConflictError, match="producción"):
        load(production, ADMIN_EMAIL)
    assert load(production, ADMIN_EMAIL, allow_production=True).warnings == []


def test_si_algo_falla_no_queda_nada_a_medias(context, recruiter, monkeypatch):
    from app.sample_data import loader

    def broken(self, vacancy_id):
        raise ConflictError("Fallo provocado por la prueba.")

    monkeypatch.setattr(loader._Loader, "_advance", broken)
    with pytest.raises(ConflictError, match="Fallo provocado"):
        load(context, RECRUITER_EMAIL)
    listed = recruiter.get(f"{API}/vacancies", params={"search": "DATOS DE PRUEBA"}).json()
    assert listed["total"] == 0
    # Corregido el fallo, se carga completa.
    monkeypatch.undo()
    assert len(load(context, RECRUITER_EMAIL).people) == 10


def test_el_comando_dice_donde_quedo_cada_persona(context, recruiter, capsys):
    from app.cli import load_sample_data

    assert load_sample_data(context, RECRUITER_EMAIL, allow_production=False) == 0
    printed = capsys.readouterr().out
    assert "Analista de Nómina · DATOS DE PRUEBA" in printed
    assert "Elena Ficticia Duarte: Resultado final · Contratado" in printed
    assert "no se usó ningún proveedor" in printed
