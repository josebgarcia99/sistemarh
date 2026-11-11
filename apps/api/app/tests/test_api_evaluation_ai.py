"""Ayudas de IA para el perfil y la rúbrica, con un proveedor simulado."""

# ruff: noqa: F401, F811  (las fixtures se importan de otro módulo de pruebas)
from __future__ import annotations

import json

import pytest

from app.infrastructure.ai_providers.http_clients import Generation
from app.modules.ai_settings.domain.models import ProviderCode, ProviderError
from app.modules.evaluation_setup.domain import assistant
from app.tests.conftest import VACANCY, share
from app.tests.support.sample_files import docx_cv, pdf_cv
from app.tests.test_api_cv_batches import (
    API,
    admin,
    app,
    audit,
    other,
    providers,
    recruiter,
    upload,
    vacancy_id,
)
from app.tests.test_api_evaluation_setup import PROFILE, edit_body, save_profile, step

SOURCE_TEXT = (
    "Perfil: Analista de Nómina. Objetivo: calcular y pagar la nómina quincenal sin errores. "
    "Indispensable: dos años de experiencia en cálculo de nómina. Deseable: CONTPAQi Nóminas. "
    "Excel intermedio."
)
ANSWER = {
    "objetivo": "Calcular y pagar la nómina quincenal sin errores.",
    "experiencia": "Dos años en cálculo de nómina.",
    "formacion": "",
    "funciones": ["Calcular nómina", "  ", 7, "Calcular nómina"],
    "responsabilidades": [],
    "conocimientos": ["IMSS"],
    "habilidades": "no es una lista",
    "certificaciones": [],
    "requisitos_indispensables": ["Dos años de experiencia en cálculo de nómina"],
    "requisitos_deseables": ["CONTPAQi Nóminas"],
    "ambiguedades": ["«Excel intermedio» no indica qué funciones"],
    "edad_maxima": 35,
}


def reply(body) -> Generation:
    return Generation(json.dumps(body, ensure_ascii=False), 800, 300, True)


@pytest.fixture
def models(admin) -> dict:
    """Un modelo asignado al análisis de perfiles y a la generación de prompts."""
    found = next(
        m for m in admin.get(f"{API}/ai/models").json() if m["model_id"] == "modelo-grande-1"
    )
    for operation in ("ANALISIS_PERFILES", "GENERACION_PROMPTS"):
        admin.put(f"{API}/ai/assignments/{operation}", json={"model_id": found["id"]})
    return found


def extract(client, vacancy_id, **body):
    return client.post(f"{API}/vacancies/{vacancy_id}/profile-extractions", json=body)


def usage_rows(admin) -> list[dict]:
    return admin.get(f"{API}/ai/usage", params={"year": 2026, "month": 11}).json()["rows"]


def test_la_ia_propone_el_perfil_desde_un_texto_y_no_guarda_nada(
    recruiter, admin, vacancy_id, models, providers
):
    fake = providers[ProviderCode.ANTHROPIC]
    fake.script, fake.prompts = [reply(ANSWER)], []
    response = extract(recruiter, vacancy_id, text=SOURCE_TEXT)
    assert response.status_code == 200, response.text
    proposal = response.json()
    assert proposal["objective"] == ANSWER["objetivo"]
    # Solo cadenas, sin vacíos ni repetidos; lo que no es una lista se ignora.
    assert proposal["functions"] == ["Calcular nómina"] and proposal["skills"] == []
    assert proposal["must_have"] == ["Dos años de experiencia en cálculo de nómina"]
    assert proposal["ambiguities"] == ["«Excel intermedio» no indica qué funciones"]
    assert proposal["source_file_id"] is None and proposal["truncated"] is False
    assert "edad_maxima" not in proposal

    _, system, user = fake.prompts[0]
    assert system == assistant.PROFILE_SYSTEM and "<<<DOCUMENTO" in user and SOURCE_TEXT in user
    # Es una propuesta: no hay ninguna versión guardada.
    assert recruiter.get(f"{API}/vacancies/{vacancy_id}/profile-versions").json() == []
    assert [row["operation"] for row in usage_rows(admin)] == ["ANALISIS_PERFILES"]
    assert audit(admin, "perfil.extraido_con_ia")[0]["details"]["origen"] == "texto"

    # La persona la revisa y la guarda: queda marcada como originada con IA.
    fields = {k: proposal[k] for k in PROFILE}
    saved = recruiter.post(
        f"{API}/vacancies/{vacancy_id}/profile-versions",
        json={**fields, "expected_version": 0, "from_ai": True},
    )
    assert saved.status_code == 201 and saved.json()["origin"] == "IA"


def test_la_ia_lee_el_perfil_de_un_documento_de_la_vacante(
    recruiter, vacancy_id, models, providers
):
    document = upload(
        recruiter, vacancy_id, "perfil.docx", docx_cv(SOURCE_TEXT), document_type="PERFIL_PUESTO"
    )
    fake = providers[ProviderCode.ANTHROPIC]
    fake.script, fake.prompts = [reply(ANSWER)], []
    response = extract(recruiter, vacancy_id, file_id=document["id"])
    assert response.status_code == 200, response.text
    assert response.json()["source_file_id"] == document["id"]
    assert "calcular y pagar la nómina" in fake.prompts[0][2]

    fields = {k: response.json()[k] for k in PROFILE}
    saved = recruiter.post(
        f"{API}/vacancies/{vacancy_id}/profile-versions",
        json={**fields, "expected_version": 0, "source_file_id": document["id"]},
    )
    assert saved.status_code == 201 and saved.json()["origin"] == "IA"


def test_solo_sirve_un_documento_de_perfil_legible_de_la_misma_vacante(
    recruiter, vacancy_id, models, providers
):
    cv = upload(recruiter, vacancy_id, "cv.pdf", pdf_cv("Curriculum ficticio " * 5))
    scanned = upload(
        recruiter, vacancy_id, "escaneado.pdf", pdf_cv(), document_type="PERFIL_PUESTO"
    )
    other_vacancy = recruiter.post(
        f"{API}/vacancies", json={**VACANCY, "name": "Otra vacante"}
    ).json()["id"]
    foreign = upload(
        recruiter, other_vacancy, "perfil.docx", docx_cv(SOURCE_TEXT), document_type="PERFIL_PUESTO"
    )
    fake = providers[ProviderCode.ANTHROPIC]
    fake.prompts = []
    for file_id, fragment in (
        (cv["id"], "Perfil de puesto"),
        (foreign["id"], "Perfil de puesto"),
        (scanned["id"], "parece escaneado"),
    ):
        response = extract(recruiter, vacancy_id, file_id=file_id)
        assert response.status_code == 422 and fragment in response.json()["detail"]
    assert fake.prompts == []  # nada salió hacia el proveedor
    # Tampoco se puede declarar como origen un documento que no es un perfil de la vacante.
    saved = recruiter.post(
        f"{API}/vacancies/{vacancy_id}/profile-versions",
        json={**PROFILE, "expected_version": 0, "source_file_id": cv["id"]},
    )
    assert saved.status_code == 422


def test_entradas_no_validas_y_operacion_sin_modelo(recruiter, admin, vacancy_id, providers):
    for body in ({}, {"text": SOURCE_TEXT, "file_id": vacancy_id}):
        assert extract(recruiter, vacancy_id, **body).status_code == 422
    short = extract(recruiter, vacancy_id, text="Muy corto")
    assert short.status_code == 422 and "muy corto" in short.json()["detail"]
    missing = extract(recruiter, vacancy_id, text=SOURCE_TEXT)
    assert missing.status_code == 422 and "modelo asignado" in missing.json()["detail"]


def test_si_la_ia_falla_se_informa_y_el_consumo_queda_registrado(
    recruiter, admin, vacancy_id, models, providers
):
    fake = providers[ProviderCode.ANTHROPIC]
    fake.script = [
        ProviderError("solicitud", "El modelo rechazó la solicitud."),
        Generation("Aquí tienes el perfil solicitado", 500, 20, True),
        Generation(json.dumps(ANSWER), 500, 20, False),
        reply({"objetivo": "", "funciones": []}),
    ]
    first = extract(recruiter, vacancy_id, text=SOURCE_TEXT)
    assert first.status_code == 503 and "rechazó" in first.json()["detail"]
    for _ in range(3):
        bad = extract(recruiter, vacancy_id, text=SOURCE_TEXT)
        assert bad.status_code == 503 and "propuesta utilizable" in bad.json()["detail"]
    row = usage_rows(admin)[0]
    assert (row["calls"], row["failures"]) == (4, 1)
    events = audit(admin, "perfil.extraido_con_ia")
    assert len(events) == 4 and {event["result"] for event in events} == {"FALLIDO"}
    assert recruiter.get(f"{API}/vacancies/{vacancy_id}/profile-versions").json() == []


def test_permisos_de_las_ayudas_de_ia(recruiter, vacancy_id, models, providers, other):
    other_client, other_id = other
    assert extract(other_client, vacancy_id, text=SOURCE_TEXT).status_code == 404
    share(recruiter, vacancy_id, other_id, "LECTURA")
    assert extract(other_client, vacancy_id, text=SOURCE_TEXT).status_code == 403
    save_profile(recruiter, vacancy_id)
    draft = recruiter.post(f"{API}/vacancies/{vacancy_id}/prompts").json()
    url = f"{API}/prompts/{draft['id']}/criteria-proposals"
    assert other_client.post(url).status_code == 403
    assert providers[ProviderCode.ANTHROPIC].prompts is None


def test_la_ia_mejora_la_redaccion_de_los_criterios_sin_anadir_ninguno(
    recruiter, admin, vacancy_id, models, providers
):
    save_profile(recruiter, vacancy_id)
    draft = recruiter.post(f"{API}/vacancies/{vacancy_id}/prompts").json()
    codes = [criterion["code"] for criterion in draft["criteria"]]
    assert len(codes) == 3
    levels = [
        "Sin evidencia",
        "Menos de un año",
        "Uno a dos años",
        "Dos a cuatro años",
        "Más de cuatro",
    ]
    fake = providers[ProviderCode.ANTHROPIC]
    fake.prompts = []
    fake.script = [
        reply(
            {
                "criterios": [
                    {
                        "id": "C1",
                        "descripcion": "Busca  puestos de nómina con fechas.",
                        "niveles": levels,
                    },
                    {"id": "C1", "descripcion": "Repetido", "niveles": levels},
                    {"id": "C2", "descripcion": "Incompleto", "niveles": levels[:4]},
                    {"id": "C3", "descripcion": "Niveles iguales", "niveles": ["x"] * 5},
                    {
                        "id": "C9",
                        "descripcion": "Requisito inventado: inglés avanzado",
                        "niveles": levels,
                    },
                    "basura",
                ],
                "observaciones": ["«Excel intermedio» es ambiguo", "", 3],
            }
        )
    ]
    url = f"{API}/prompts/{draft['id']}/criteria-proposals"
    response = recruiter.post(url)
    assert response.status_code == 200, response.text
    body = response.json()
    # Solo sobrevive la mejora válida de un criterio que ya existe.
    assert [item["code"] for item in body["suggestions"]] == ["C1"]
    suggestion = body["suggestions"][0]
    assert suggestion["id"] == draft["criteria"][0]["id"]
    assert suggestion["name"] == draft["criteria"][0]["name"]
    assert suggestion["description"] == "Busca puestos de nómina con fechas."
    assert suggestion["levels"] == levels
    assert body["observations"] == ["«Excel intermedio» es ambiguo"]

    _, system, user = fake.prompts[0]
    assert system == assistant.CRITERIA_SYSTEM
    assert "Experiencia en cálculo de nómina" in user and "C3." in user
    # Nada cambió en el borrador: aplicar la propuesta es una edición normal.
    unchanged = recruiter.get(f"{API}/prompts/{draft['id']}").json()
    assert unchanged["revision"] == draft["revision"] and unchanged["criteria"] == draft["criteria"]
    edited = edit_body(draft)
    edited["criteria"][0].update(description=suggestion["description"], levels=suggestion["levels"])
    applied = recruiter.put(f"{API}/prompts/{draft['id']}", json=edited)
    assert applied.status_code == 200 and applied.json()["criteria"][0]["levels"] == levels
    assert len(applied.json()["criteria"]) == 3
    assert audit(admin, "prompt.criterios_propuestos")[0]["details"]["criterios"] == 1

    # Sin nada utilizable se informa; sobre una versión que no es borrador no se propone.
    fake.script = [reply({"criterios": [{"id": "C9", "niveles": levels}]})]
    assert recruiter.post(url).status_code == 503
    in_review = step(recruiter, applied.json(), "submit").json()
    assert recruiter.post(url).status_code == 409
    assert step(recruiter, in_review, "approve").status_code == 200
    assert recruiter.post(url).status_code == 409
