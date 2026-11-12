"""Puesto de analista de estudios socioeconómicos: trabaja los estudios de
cualquier vacante y nada más. Datos inventados."""

# ruff: noqa: F401, F811  (las fixtures se importan de otro módulo de pruebas)
from __future__ import annotations

import uuid

import pytest

from app.modules.ai_settings.domain.models import ProviderCode
from app.modules.authentication.api.dependencies import STUDY_ANALYST_ROUTES
from app.tests.conftest import OTHER_PASSWORD, login
from app.tests.support.sample_files import pdf_cv, photo
from app.tests.test_api_assessments import ana, create, update
from app.tests.test_api_cv_batches import (
    API,
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
from app.tests.test_api_recruitment import assign, by_name, evaluated, new_bank, reply

DENIED = "Tu puesto solo da acceso a los estudios socioeconómicos."


@pytest.fixture
def analyst(app, admin):
    """Una analista de estudios, sin ninguna vacante compartida."""
    created = admin.post(
        f"{API}/users",
        json={
            "email": "analista@ejemplo.test",
            "full_name": "Analista de Estudios Ficticia",
            "password": OTHER_PASSWORD,
            "role": "ANALISTA_ESTUDIOS",
        },
    )
    assert created.status_code == 201, created.text
    return login(app, "analista@ejemplo.test", OTHER_PASSWORD)


def test_la_analista_hace_todo_el_estudio_de_cualquier_vacante(
    ana, analyst, recruiter, admin, vacancy_id, providers
):
    assert analyst.get(f"{API}/auth/me").json()["user"]["role"] == "ANALISTA_ESTUDIOS"
    # Su lista de trabajo: las postulaciones en proceso, sin datos del expediente.
    queue = analyst.get(f"{API}/study-queue")
    assert queue.status_code == 200, queue.text
    row = next(item for item in queue.json() if item["application_id"] == ana)
    assert row == {
        "application_id": ana,
        "vacancy_id": vacancy_id,
        "candidate_name": "Ana Pérez Ficticia",
        "vacancy_name": row["vacancy_name"],
        "active": True,
        "study_status": None,
        "study_updated_at": None,
    }
    assert [i["candidate_name"] for i in analyst.get(f"{API}/study-queue?search=ana p").json()] == [
        "Ana Pérez Ficticia"
    ]
    assert analyst.get(f"{API}/study-queue", params={"search": "100%_"}).json() == []

    # Registra el estudio, carga la fotografía y el formato, y usa las ayudas de IA.
    listing = analyst.get(f"{API}/applications/{ana}/assessments").json()
    assert listing["items"] == [] and listing["writable"] == ["ESTUDIO_SOCIOECONOMICO"]
    [template] = analyst.get(f"{API}/form-templates").json()
    ids = {f["label"]: f["id"] for section in template["sections"] for f in section["fields"]}
    study = create(analyst, ana, "ESTUDIO_SOCIOECONOMICO", template_id=template["id"])
    assert study.status_code == 201, study.text
    picture = upload(
        analyst, vacancy_id, "fachada.jpg", photo(), document_type="ESTUDIO_SOCIOECONOMICO"
    )
    scanned = upload(
        analyst,
        vacancy_id,
        "estudio.pdf",
        pdf_cv("Estudio ficticio", "Nombre completo: Persona Ficticia", "Ocupacion: Comerciante"),
        document_type="ESTUDIO_SOCIOECONOMICO",
    )
    assert analyst.get(f"{API}/files/{picture['id']}/download").status_code == 200
    for operation in ("LECTURA_DOCUMENTOS", "DESCRIPCION_FOTOGRAFIAS"):
        assign(admin, operation)
    fake = providers[ProviderCode.ANTHROPIC]
    fake.script = [
        reply({"valores": {ids["Nombre completo"]: "Persona Ficticia"}}),
        reply({"descripcion": "Fachada de dos niveles."}),
    ]
    base = f"{API}/assessments/{study.json()['id']}"
    read = analyst.post(f"{base}/digitization", json={"file_id": scanned["id"]})
    assert read.status_code == 200, read.text
    described = analyst.post(f"{base}/photo-descriptions", json={"file_id": picture["id"]})
    assert described.status_code == 200, described.text
    saved = update(
        analyst,
        study.json(),
        status="COMPLETADO",
        data={
            "answers": {
                ids["Fecha de aplicación"]: {"value": "2026-11-12"},
                ids["Nombre completo"]: {"value": "Persona Ficticia", "source": "IA"},
                ids["Fotografía: fachada de la vivienda"]: {
                    "value": picture["id"],
                    "description": described.json()["description"],
                    "description_source": "IA",
                },
                ids["Dictamen (observaciones)"]: {"value": "Dictamen de la analista."},
            }
        },
    )
    assert saved.status_code == 200, saved.text
    assert analyst.get(base).json()["status"] == "COMPLETADO"
    row = next(i for i in analyst.get(f"{API}/study-queue").json() if i["application_id"] == ana)
    assert row["study_status"] == "COMPLETADO" and row["study_updated_at"]

    # La reclutadora responsable y el administrador siguen viendo y editando ese estudio.
    for client in (recruiter, admin):
        seen = client.get(f"{API}/applications/{ana}/assessments").json()
        assert [item["kind"] for item in seen["items"]] == ["ESTUDIO_SOCIOECONOMICO"]
        assert "ESTUDIO_SOCIOECONOMICO" in seen["writable"]
        assert client.get(f"{API}/files/{picture['id']}/download").status_code == 200
    edited = update(recruiter, analyst.get(base).json(), status="EN_PROCESO")
    assert edited.status_code == 200, edited.text
    # La lista de trabajo es del analista y del administrador, no de los reclutadores.
    assert admin.get(f"{API}/study-queue").status_code == 200
    assert recruiter.get(f"{API}/study-queue").status_code == 403


def test_la_analista_no_ve_nada_que_no_sea_el_estudio(
    ana, analyst, recruiter, admin, vacancy_id, providers
):
    # Otras evaluaciones de la misma persona: ni las ve ni las puede registrar.
    technical = create(recruiter, ana, "PRUEBA_TECNICA", data={"test_type": "Excel"}).json()
    listing = analyst.get(f"{API}/applications/{ana}/assessments").json()
    assert listing["items"] == [] and listing["writable"] == ["ESTUDIO_SOCIOECONOMICO"]
    assert analyst.get(f"{API}/assessments/{technical['id']}").status_code == 403
    assert create(analyst, ana, "PRUEBA_TECNICA", data={"test_type": "Excel"}).status_code == 403
    assert create(analyst, ana, "PSICOMETRIA", data={"instrument": "X"}).status_code == 403

    # Documentos: solo los del estudio. Los CV no aparecen ni se descargan ni se cargan.
    files = recruiter.get(f"{API}/vacancies/{vacancy_id}/files").json()
    cv = next(item for item in files if item["document_type"] == "CV")
    psychometric = upload(
        recruiter, vacancy_id, "reporte.pdf", pdf_cv("Reporte ficticio " * 5), "PSICOMETRIA"
    )
    study_doc = upload(
        recruiter, vacancy_id, "estudio.pdf", pdf_cv("Estudio " * 9), "ESTUDIO_SOCIOECONOMICO"
    )
    visible = analyst.get(f"{API}/vacancies/{vacancy_id}/files")
    assert visible.status_code == 200
    assert [item["id"] for item in visible.json()] == [study_doc["id"]]
    for hidden in (cv, psychometric):
        assert analyst.get(f"{API}/files/{hidden['id']}/download").status_code == 403
        assert analyst.get(f"{API}/files/{hidden['id']}").status_code == 403
    refused = analyst.post(
        f"{API}/vacancies/{vacancy_id}/files",
        params={"document_type": "CV", "filename": "cv.pdf"},
        content=pdf_cv("Curriculum " * 9),
    )
    assert refused.status_code == 403 and refused.json()["detail"] == DENIED
    # Una vacante que no existe no revela nada.
    assert analyst.get(f"{API}/vacancies/{uuid.uuid4()}/files").status_code == 404


def test_todo_lo_demas_esta_cerrado_para_la_analista(analyst, app):
    """Barrido de todas las rutas: lo que no está en su lista responde 403."""
    schema = app.openapi()
    public = {("POST", "/auth/login")}
    checked = 0
    for path, operations in schema["paths"].items():
        template = path.removeprefix("/api/v1")
        if not path.startswith("/api/v1") or template.startswith("/health"):
            continue
        for method in operations:
            route = (method.upper(), template)
            if route in STUDY_ANALYST_ROUTES or route in public:
                continue
            url = path
            for name in ("{" + part.split("}")[0] + "}" for part in path.split("{")[1:]):
                url = url.replace(name, str(uuid.uuid4()))
            response = analyst.request(method.upper(), url, json={})
            assert response.status_code == 403, f"{route}: {response.status_code}"
            assert response.json()["detail"] == DENIED, route
            checked += 1
    # Vacantes, candidatos, lotes de CV, prompts, bancos, reportes, IA, usuarios, auditoría…
    assert checked > 80
    # Las rutas de su lista existen todas (una errata la dejaría sin acceso sin que se note).
    declared = {
        (method.upper(), path.removeprefix("/api/v1"))
        for path, operations in schema["paths"].items()
        for method in operations
    }
    assert STUDY_ANALYST_ROUTES <= declared


def test_el_rechazo_a_la_analista_queda_auditado(analyst, admin):
    assert analyst.get(f"{API}/vacancies").status_code == 403
    [event] = audit(admin, "acceso.denegado")
    assert event["result"] == "DENEGADO" and "/vacancies" in str(event["details"])
