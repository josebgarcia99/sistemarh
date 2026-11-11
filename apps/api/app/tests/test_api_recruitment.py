"""Fase 5: postulaciones, etapas, bancos de preguntas y llamadas.

Todo con datos sintéticos y un proveedor de IA simulado.
"""

# ruff: noqa: F401, F811  (las fixtures se importan de otro módulo de pruebas)
from __future__ import annotations

import io
import json
import shutil
import uuid
from datetime import date
from decimal import Decimal

import pytest

from app.infrastructure.ai_providers.http_clients import Generation
from app.modules.ai_settings.domain.models import ProviderCode, ProviderError
from app.modules.cv_processing.domain.extraction import (
    InvalidExtractionError,
    contact_from_text,
    extraction_from_answer,
)
from app.modules.phone_calls.domain import assistant as call_assistant
from app.modules.recruitment.domain.tenure import summarize
from app.tests.conftest import VACANCY, share
from app.tests.support.sample_files import docx_cv, pdf_cv
from app.tests.test_api_cv_batches import (
    API,
    admin,
    answer,
    app,
    audit,
    model,
    other,
    prompt,
    providers,
    recruiter,
    start,
    upload,
    vacancy_id,
)
from app.tests.test_api_evaluation_setup import save_profile


def reply(body) -> Generation:
    return Generation(json.dumps(body, ensure_ascii=False), 600, 200, True)


# --- Reglas sin API ----------------------------------------------------------------------


def test_la_permanencia_se_calcula_con_los_periodos_del_cv():
    jobs = [
        {"puesto": "Analista", "empresa": "Uno", "inicio": "2020-01", "fin": "2021-12"},
        {"puesto": "Auxiliar", "empresa": "Dos", "inicio": "2021-07", "fin": "2022-06"},
        {"puesto": "Jefa", "empresa": "Tres", "inicio": "2024-05", "fin": "", "actual": True},
        {"puesto": "Becaria", "empresa": "Cuatro", "inicio": "2018", "fin": "2018"},
        {"puesto": "Sin fechas", "empresa": "Cinco", "inicio": "", "fin": "2019-03"},
        {"puesto": "Al revés", "empresa": "Seis", "inicio": "2023-05", "fin": "2023-01"},
    ]
    summary = summarize(jobs, date(2024, 10, 15))
    assert [job.months for job in summary.jobs] == [24, 12, 6, 12, None, None]
    assert summary.jobs[3].approximate is True and summary.jobs[0].approximate is False
    assert summary.average_months == 13.5 and summary.median_months == 12.0
    # 2018 (12) + 2020-01 a 2022-06 (30, sin contar dos veces el traslape) + 6 vigentes.
    assert summary.total_months == 48
    assert summary.overlaps == 1 and summary.incomplete == 2
    empty = summarize([], date(2024, 1, 1))
    assert empty.average_months is None and empty.total_months == 0


def test_el_contacto_se_toma_del_texto_y_la_extraccion_se_limpia():
    email, phone = contact_from_text("Ana PEREZ ana.perez@Correo.test Tel. +52 55 1234 5678")
    assert email == "ana.perez@correo.test" and phone == "+52 55 1234 5678"
    assert contact_from_text("Sin datos de contacto, 2019-2023") == (None, None)
    data = extraction_from_answer(
        json.dumps(
            {
                "nombre": "  Ana   Pérez ",
                "edad": 30,
                "experiencia": [
                    {"puesto": "Analista", "empresa": "Uno", "inicio": "2020-13", "fin": "marzo"},
                    {"puesto": "", "empresa": ""},
                    "basura",
                ],
                "habilidades": ["Excel", "Excel", 5],
                "estudios": [{"titulo": "Contaduría", "institucion": "UNAM", "periodo": "2015"}],
            }
        )
    )
    assert data["nombre"] == "Ana Pérez" and "edad" not in data
    # Las fechas que no cumplen el formato quedan vacías: no se adivinan.
    assert data["experiencia"] == [
        {
            "puesto": "Analista",
            "empresa": "Uno",
            "inicio": "",
            "fin": "",
            "actual": False,
            "funciones": [],
        }
    ]
    assert data["habilidades"] == ["Excel"]
    for text in ("no es json", "{}"):
        with pytest.raises(InvalidExtractionError):
            extraction_from_answer(text)


# --- Soporte -----------------------------------------------------------------------------

ANA = {
    "nombre": "Ana Pérez Ficticia",
    "experiencia": [
        {
            "puesto": "Analista de nómina",
            "empresa": "Uno SA",
            "inicio": "2020-01",
            "fin": "2022-06",
            "actual": False,
            "funciones": ["Cálculo de nómina"],
        },
        {"puesto": "Auxiliar", "empresa": "Dos SA", "inicio": "2018", "fin": "", "actual": False},
    ],
    "habilidades": ["Excel"],
    "estudios": [],
    "certificaciones": [],
    "proyectos": [],
}
BETO = {**ANA, "nombre": "Beto López Ficticio", "experiencia": []}


def person_cv(name: str, email: str) -> bytes:
    return pdf_cv(
        f"Curriculum ficticio de {name}",
        "Analista de nomina con experiencia en calculo de IMSS e ISR",
        f"Correo: {email}  Telefono: 55 1234 5678",
    )


def assign(admin, *operations):
    found = next(
        m for m in admin.get(f"{API}/ai/models").json() if m["model_id"] == "modelo-grande-1"
    )
    for operation in operations:
        admin.put(f"{API}/ai/assignments/{operation}", json={"model_id": found["id"]})


def board(client, vacancy_id, **params) -> dict:
    response = client.get(f"{API}/vacancies/{vacancy_id}/applications", params=params)
    assert response.status_code == 200, response.text
    return response.json()


def by_name(data: dict) -> dict[str, dict]:
    return {item["full_name"]: item for item in data["applications"]}


def stage_id(data: dict, name: str) -> str:
    return next(stage["id"] for stage in data["pipeline"]["stages"] if stage["name"] == name)


def move(client, vacancy_id, ids, stage, note=None):
    return client.post(
        f"{API}/vacancies/{vacancy_id}/application-moves",
        json={"application_ids": ids, "to_stage_id": stage, "note": note},
    )


@pytest.fixture
def evaluated(recruiter, admin, vacancy_id, prompt, model, providers) -> dict:
    """Un lote con Ana (aceptada) y Beto (rechazado), con sus datos ordenados."""
    assign(admin, "EXTRACCION_CV")
    upload(recruiter, vacancy_id, "cv ana.pdf", person_cv("Ana", "ana@ejemplo.test"))
    upload(recruiter, vacancy_id, "CV_beto-lopez.pdf", person_cv("Beto", "beto@ejemplo.test"))
    fake = providers[ProviderCode.ANTHROPIC]
    fake.prompts = []
    fake.script = [answer(prompt, 4), reply(ANA), answer(prompt, 1), reply(BETO)]
    assert start(recruiter, vacancy_id).json()["batch"]["status"] == "COMPLETADO"
    return board(recruiter, vacancy_id)


# --- Postulaciones y etapas --------------------------------------------------------------


def test_cada_cv_evaluado_entra_como_postulacion_en_revision_de_rh(
    evaluated, recruiter, admin, vacancy_id, providers
):
    data = evaluated
    assert data["campaign"]["name"] == "Convocatoria 1" and data["campaign"]["status"] == "ABIERTA"
    assert [s["name"] for s in data["pipeline"]["stages"]][:3] == [
        "Evaluación de CV",
        "Revisión local RH",
        "Llamada telefónica",
    ]
    people = by_name(data)
    assert set(people) == {"Ana Pérez Ficticia", "Beto López Ficticio"}
    ana, beto = people["Ana Pérez Ficticia"], people["Beto López Ficticio"]
    review = stage_id(data, "Revisión local RH")
    assert ana["stage_id"] == beto["stage_id"] == review and ana["status"] == "ACTIVA"
    assert ana["ai_classification"] == "ACEPTADO_IA" and Decimal(ana["ai_score"]) == 100
    assert beto["ai_classification"] == "RECHAZADO_IA" and Decimal(beto["ai_score"]) == 25
    # El contacto sale del texto del CV, no de la IA; a la IA se le envió oculto.
    assert ana["email"] == "ana@ejemplo.test" and ana["phone"] == "55 1234 5678"
    extraction_prompts = [
        user for _, system, user in providers[ProviderCode.ANTHROPIC].prompts if "Ordena" in system
    ]
    assert len(extraction_prompts) == 2 and "ana@ejemplo.test" not in extraction_prompts[0]

    detail = recruiter.get(f"{API}/applications/{ana['id']}").json()
    assert [(m["kind"], m["actor_name"], m["to_stage"]) for m in detail["movements"]] == [
        ("ALTA", None, "Evaluación de CV"),
        ("AVANCE", None, "Revisión local RH"),
    ]
    assert "aceptado, 100.00 de 100" in detail["movements"][0]["note"]
    assert detail["evaluation"]["classification"] == "ACEPTADO_IA"
    assert detail["evaluation"]["extraction"]["habilidades"] == ["Excel"]
    assert len(detail["evaluation"]["result"]["criterios"]) == 3
    tenure = detail["tenure"]
    assert [job["months"] for job in tenure["jobs"]] == [30, None]
    assert tenure["total_months"] == 30 and tenure["incomplete"] == 1

    # Repetir la sincronización o volver a evaluar no duplica ni cambia la evaluación original.
    providers[ProviderCode.ANTHROPIC].script = [
        answer({"criteria": [{"code": c} for c in ("C1", "C2", "C3")]}, 0)
    ] * 2
    assert start(recruiter, vacancy_id, reevaluate=True).status_code == 201
    again = by_name(board(recruiter, vacancy_id))
    assert len(again) == 2 and Decimal(again["Ana Pérez Ficticia"]["ai_score"]) == 100
    created = audit(admin, "postulacion.creada")
    assert [e["details"]["postulaciones"] for e in created] == [2] and created[0][
        "actor_name"
    ] is None


def test_sin_extraccion_el_nombre_sale_del_archivo(recruiter, vacancy_id, prompt, model, providers):
    upload(recruiter, vacancy_id, "CV_maria-gomez.pdf", person_cv("Maria", "maria@ejemplo.test"))
    upload(recruiter, vacancy_id, "escaneado.pdf", pdf_cv())
    providers[ProviderCode.ANTHROPIC].script = [answer(prompt, 4)]
    start(recruiter, vacancy_id)
    people = by_name(board(recruiter, vacancy_id))
    assert set(people) == {"maria gomez", "escaneado"}
    assert people["maria gomez"]["email"] == "maria@ejemplo.test"
    # Un CV no evaluable también entra a revisión: no es un rechazo.
    assert people["escaneado"]["ai_classification"] == "NO_EVALUABLE"
    detail = recruiter.get(f"{API}/applications/{people['maria gomez']['id']}").json()
    assert (
        detail["tenure"] is None and detail["evaluation"]["extraction"]["estado"] == "SOLO_CONTACTO"
    )


def test_un_rechazado_por_la_ia_avanza_a_llamada_por_decision_humana_y_queda_registrado(
    evaluated, recruiter, admin, vacancy_id
):
    beto = by_name(evaluated)["Beto López Ficticio"]
    call_stage = stage_id(evaluated, "Llamada telefónica")
    refused = move(recruiter, vacancy_id, [beto["id"]], call_stage)
    assert refused.status_code == 422 and "motivo de tu decisión" in refused.json()["detail"]
    moved = move(
        recruiter,
        vacancy_id,
        [beto["id"]],
        call_stage,
        "Tiene experiencia en nómina que la IA no vio.",
    )
    assert moved.status_code == 200 and moved.json()[0]["stage_id"] == call_stage

    detail = recruiter.get(f"{API}/applications/{beto['id']}").json()
    last = detail["movements"][-1]
    assert (last["kind"], last["actor_name"], last["from_stage"], last["to_stage"]) == (
        "AVANCE",
        "Reclutadora de Prueba",
        "Revisión local RH",
        "Llamada telefónica",
    )
    assert "la IA no vio" in last["note"]
    # La clasificación inicial no se sobrescribe y las etapas anteriores siguen en el historial.
    assert detail["application"]["ai_classification"] == "RECHAZADO_IA"
    assert [m["kind"] for m in detail["movements"]] == ["ALTA", "AVANCE", "AVANCE"]
    event = audit(admin, "postulacion.movida")[0]["details"]
    assert event["no_aceptadas_por_ia"] == 1 and event["etapa"] == "Llamada telefónica"


def test_mover_omitir_retroceder_y_mover_en_grupo(evaluated, recruiter, vacancy_id):
    people = by_name(evaluated)
    ana, beto = people["Ana Pérez Ficticia"]["id"], people["Beto López Ficticio"]["id"]
    stage = lambda name: stage_id(evaluated, name)  # noqa: E731

    # Una aceptada avanza a la etapa siguiente sin motivo; saltar etapas obligatorias lo exige.
    assert move(recruiter, vacancy_id, [ana], stage("Llamada telefónica")).status_code == 200
    skip = move(recruiter, vacancy_id, [ana], stage("Entrevista con gerente"))
    assert skip.status_code == 422 and "omitir" in skip.json()["detail"]
    assert (
        move(
            recruiter,
            vacancy_id,
            [ana],
            stage("Entrevista con gerente"),
            "Ya tiene psicometría vigente",
        ).status_code
        == 200
    )
    # La prueba técnica es opcional: se omite sin motivo.
    assert move(recruiter, vacancy_id, [ana], stage("Estudio socioeconómico")).status_code == 200
    back = move(recruiter, vacancy_id, [ana], stage("Entrevista con gerente"))
    assert back.status_code == 422 and "regresar" in back.json()["detail"]
    assert (
        move(
            recruiter,
            vacancy_id,
            [ana],
            stage("Entrevista con gerente"),
            "El gerente pidió otra entrevista",
        ).status_code
        == 200
    )
    same = move(recruiter, vacancy_id, [ana], stage("Entrevista con gerente"), "x")
    assert same.status_code == 422

    kinds = [
        (m["kind"], m["from_stage"], m["to_stage"])
        for m in recruiter.get(f"{API}/applications/{ana}").json()["movements"][2:]
    ]
    assert kinds == [
        ("AVANCE", "Revisión local RH", "Llamada telefónica"),
        ("OMISION", "Pruebas psicométricas", None),
        ("AVANCE", "Llamada telefónica", "Entrevista con gerente"),
        ("OMISION", "Prueba técnica", None),
        ("AVANCE", "Entrevista con gerente", "Estudio socioeconómico"),
        ("RETROCESO", "Estudio socioeconómico", "Entrevista con gerente"),
    ]

    # Movimiento masivo: todo o nada.
    final = stage("Resultado final")
    assert move(recruiter, vacancy_id, [ana, beto], final).status_code == 422
    assert recruiter.get(f"{API}/applications/{beto}").json()["application"]["stage_id"] == stage(
        "Revisión local RH"
    )
    assert (
        move(recruiter, vacancy_id, [ana, beto, ana], final, "Cierre del proceso").status_code
        == 200
    )
    for person in (ana, beto):
        detail = recruiter.get(f"{API}/applications/{person}").json()
        assert (
            detail["application"]["stage_id"] == final and detail["movements"][-1]["mass"] is True
        )
    assert move(recruiter, vacancy_id, [ana], str(uuid.uuid4()), "x").status_code == 422
    assert move(recruiter, vacancy_id, [str(uuid.uuid4())], final, "x").status_code == 404


def test_desistimiento_descarte_reactivacion_incidencia_y_reprogramacion(
    evaluated, recruiter, vacancy_id, clock
):
    ana = by_name(evaluated)["Ana Pérez Ficticia"]["id"]
    url = f"{API}/applications/{ana}"
    assert (
        recruiter.post(f"{url}/status", json={"action": "DESISTIMIENTO", "note": ""}).status_code
        == 422
    )
    gone = recruiter.post(
        f"{url}/status", json={"action": "DESISTIMIENTO", "note": "Aceptó otra oferta"}
    )
    assert gone.status_code == 200 and gone.json()["application"]["status"] == "DESISTIO"
    # Sin estar activa no se mueve ni se vuelve a dar de baja.
    assert (
        move(recruiter, vacancy_id, [ana], stage_id(evaluated, "Llamada telefónica")).status_code
        == 409
    )
    assert (
        recruiter.post(
            f"{url}/status", json={"action": "DESCARTE", "note": "Duplicado"}
        ).status_code
        == 409
    )
    back = recruiter.post(
        f"{url}/status", json={"action": "REACTIVACION", "note": "Volvió a estar disponible"}
    )
    assert back.json()["application"]["status"] == "ACTIVA"
    assert (
        recruiter.post(
            f"{url}/status", json={"action": "REACTIVACION", "note": "Otra vez"}
        ).status_code
        == 409
    )

    assert (
        recruiter.post(f"{url}/notes", json={"note": "No contestó la llamada"}).status_code == 200
    )
    due = "2026-11-20T16:00:00Z"
    moved = recruiter.post(f"{url}/notes", json={"note": "Pidió cambiar la fecha", "due_at": due})
    assert moved.json()["application"]["due_at"].startswith("2026-11-20T16:00:00")
    kinds = [m["kind"] for m in moved.json()["movements"]]
    assert kinds == [
        "ALTA",
        "AVANCE",
        "DESISTIMIENTO",
        "REACTIVACION",
        "INCIDENCIA",
        "REPROGRAMACION",
    ]
    # Al cambiar de etapa, la fecha acordada de la anterior ya no aplica.
    after = move(recruiter, vacancy_id, [ana], stage_id(evaluated, "Llamada telefónica"))
    assert after.json()[0]["due_at"] is None


def test_alta_manual_y_correccion_de_datos(evaluated, recruiter, vacancy_id):
    url = f"{API}/vacancies/{vacancy_id}/applications"
    for body, fragment in (
        ({"full_name": "X"}, "nombre completo"),
        ({"full_name": "Carla Ruiz", "email": "no-es-correo"}, "correo"),
        ({"full_name": "Otra Ana", "email": "ANA@ejemplo.test"}, "ya tiene una postulación"),
        ({"full_name": "Carla Ruiz", "cv_file_id": str(uuid.uuid4())}, "no es un currículum"),
    ):
        response = recruiter.post(url, json=body)
        assert response.status_code in (409, 422) and fragment in response.json()["detail"], body
    created = recruiter.post(
        url,
        json={"full_name": " Carla  Ruiz ", "email": "Carla@Ejemplo.test", "phone": "55 0000 0000"},
    )
    assert created.status_code == 201
    carla = created.json()
    assert (
        carla["application"]["full_name"] == "Carla Ruiz"
        and carla["application"]["email"] == "carla@ejemplo.test"
    )
    assert carla["application"]["ai_classification"] is None and carla["evaluation"] is None
    assert [(m["kind"], m["to_stage"], m["actor_name"]) for m in carla["movements"]] == [
        ("ALTA", "Revisión local RH", "Reclutadora de Prueba")
    ]
    # Sin clasificación de IA, avanzar no exige motivo.
    assert (
        move(
            recruiter,
            vacancy_id,
            [carla["application"]["id"]],
            stage_id(evaluated, "Llamada telefónica"),
        ).status_code
        == 200
    )

    edit = f"{API}/applications/{carla['application']['id']}/candidate"
    clash = recruiter.put(edit, json={"full_name": "Carla Ruiz", "email": "ana@ejemplo.test"})
    assert clash.status_code == 409
    fixed = recruiter.put(edit, json={"full_name": "Carla Ruiz Mora", "email": None, "phone": None})
    assert (
        fixed.json()["application"]["full_name"] == "Carla Ruiz Mora"
        and fixed.json()["application"]["email"] is None
    )
    assert len(board(recruiter, vacancy_id)["applications"]) == 3


def test_convocatorias_y_etapas_por_versiones(evaluated, recruiter, admin, vacancy_id, other):
    other_client, other_id = other
    first = evaluated["campaign"]
    ana = by_name(evaluated)["Ana Pérez Ficticia"]["id"]
    share(recruiter, vacancy_id, other_id, "COLABORACION")
    assert other_client.post(f"{API}/campaigns/{first['id']}/close").status_code == 403
    assert recruiter.post(f"{API}/vacancies/{vacancy_id}/campaigns", json={}).status_code == 409

    # El administrador cambia las etapas: se guarda una versión nueva.
    pipeline = admin.get(f"{API}/pipeline").json()
    stages = [{k: s[k] for k in ("name", "kind", "is_optional")} for s in pipeline["stages"]]
    assert (
        recruiter.put(f"{API}/pipeline", json={"stages": stages, "expected_version": 1}).status_code
        == 403
    )
    for bad, fragment in (
        (stages, "no tienen cambios"),
        (stages[:1], "entre 2 y 20"),
        ([*stages, stages[0]], "mismo nombre"),
        ([{**stages[0], "name": " "}, *stages[1:]], "nombre"),
    ):
        response = admin.put(f"{API}/pipeline", json={"stages": bad, "expected_version": 1})
        assert response.status_code == 422 and fragment in response.json()["detail"]
    changed = [
        *stages[:3],
        {"name": "Entrevista con RH", "kind": "OTRA", "is_optional": True},
        *stages[3:],
    ]
    saved = admin.put(f"{API}/pipeline", json={"stages": changed, "expected_version": 1})
    assert saved.status_code == 200 and saved.json()["version_number"] == 2
    assert (
        admin.put(f"{API}/pipeline", json={"stages": stages, "expected_version": 1}).status_code
        == 409
    )

    # La convocatoria abierta conserva sus etapas.
    assert len(board(recruiter, vacancy_id)["pipeline"]["stages"]) == 8
    closed = recruiter.post(f"{API}/campaigns/{first['id']}/close")
    assert closed.status_code == 200 and closed.json()["status"] == "CERRADA"
    assert recruiter.post(f"{API}/campaigns/{first['id']}/close").status_code == 409
    assert (
        move(recruiter, vacancy_id, [ana], stage_id(evaluated, "Llamada telefónica")).status_code
        == 409
    )

    second = recruiter.post(f"{API}/vacancies/{vacancy_id}/campaigns", json={"name": "Enero 2027"})
    assert second.status_code == 201 and second.json()["number"] == 2
    current = board(recruiter, vacancy_id)
    assert current["campaign"]["name"] == "Enero 2027" and current["applications"] == []
    assert len(current["pipeline"]["stages"]) == 9
    assert [c["number"] for c in current["campaigns"]] == [2, 1]
    # La anterior sigue consultable, con sus personas y su historial.
    past = board(recruiter, vacancy_id, campaign_id=first["id"])
    assert len(past["applications"]) == 2 and past["campaign"]["status"] == "CERRADA"
    assert board_status(recruiter, vacancy_id, str(uuid.uuid4())) == 404
    # La misma persona puede participar otra vez: es una postulación distinta.
    again = recruiter.post(
        f"{API}/vacancies/{vacancy_id}/applications",
        json={"full_name": "Ana Pérez Ficticia", "email": "ana@ejemplo.test"},
    )
    assert again.status_code == 201
    assert (
        again.json()["application"]["candidate_id"]
        == by_name(past)["Ana Pérez Ficticia"]["candidate_id"]
    )
    assert again.json()["application"]["id"] != ana
    assert {
        e["action"]
        for e in audit(admin, "convocatoria.abierta") + audit(admin, "etapas.version_creada")
    } == {
        "convocatoria.abierta",
        "etapas.version_creada",
    }


def board_status(client, vacancy_id, campaign_id) -> int:
    return client.get(
        f"{API}/vacancies/{vacancy_id}/applications", params={"campaign_id": campaign_id}
    ).status_code


def test_permisos_sobre_postulaciones(evaluated, recruiter, vacancy_id, other):
    other_client, other_id = other
    ana = by_name(evaluated)["Ana Pérez Ficticia"]["id"]
    call_stage = stage_id(evaluated, "Llamada telefónica")
    note = {"note": "Una nota suficiente"}
    requests = (
        ("get", f"{API}/vacancies/{vacancy_id}/applications", None),
        ("get", f"{API}/applications/{ana}", None),
        ("post", f"{API}/vacancies/{vacancy_id}/applications", {"full_name": "Persona Nueva"}),
        (
            "post",
            f"{API}/vacancies/{vacancy_id}/application-moves",
            {"application_ids": [ana], "to_stage_id": call_stage},
        ),
        ("post", f"{API}/applications/{ana}/status", {"action": "DESCARTE", **note}),
        ("post", f"{API}/applications/{ana}/notes", note),
        ("put", f"{API}/applications/{ana}/candidate", {"full_name": "Otro Nombre"}),
        ("post", f"{API}/vacancies/{vacancy_id}/campaigns", {}),
    )

    def run(method, url, body):
        return getattr(other_client, method)(url, **({"json": body} if body is not None else {}))

    # Sin acceso a la vacante, nada existe.
    assert [run(*request).status_code for request in requests] == [404] * len(requests)
    share(recruiter, vacancy_id, other_id, "LECTURA")
    assert [run(*request).status_code for request in requests] == [
        200,
        200,
        403,
        403,
        403,
        403,
        403,
        403,
    ]
    share(recruiter, vacancy_id, other_id, "COLABORACION")
    assert [run(*request).status_code for request in requests[2:7]] == [201, 200, 200, 200, 200]


# --- Bancos de preguntas -----------------------------------------------------------------

QUESTIONS = [
    {
        "text": "¿Qué nóminas has calculado?",
        "competency": "Nómina",
        "guidance": "Tamaño y periodicidad",
    },
    {"text": "¿Cómo validas el cálculo del IMSS?"},
]


def new_bank(client, **changes) -> dict:
    body = {
        "name": "Banco de nómina",
        "description": "Filtro inicial",
        "shared": False,
        "questions": QUESTIONS,
    }
    response = client.post(f"{API}/question-banks", json={**body, **changes})
    assert response.status_code == 201, response.text
    return response.json()


def test_bancos_privados_compartidos_versiones_duplicado_y_archivo(recruiter, admin, other):
    other_client, _ = other
    for body, fragment in (
        ({"name": "x"}, "nombre"),
        ({"questions": []}, "al menos una"),
        ({"questions": [{"text": " "}]}, "sin texto"),
    ):
        response = recruiter.post(
            f"{API}/question-banks", json={"name": "Banco", "questions": QUESTIONS, **body}
        )
        assert response.status_code == 422 and fragment in response.json()["detail"]
    bank = new_bank(recruiter)
    url = f"{API}/question-banks/{bank['id']}"
    assert bank["version_number"] == 1 and bank["mine"] and bank["can_edit"] and not bank["shared"]
    assert [q["competency"] for q in bank["questions"]] == ["Nómina", ""]

    # Privado: nadie más lo ve; el administrador sí.
    assert other_client.get(f"{API}/question-banks").json() == []
    assert other_client.get(url).status_code == 404
    assert [b["id"] for b in admin.get(f"{API}/question-banks").json()] == [bank["id"]]

    # Cambiar las preguntas crea la versión 2 y conserva el identificador de las que siguen.
    kept, dropped = bank["questions"]
    update = {
        "name": "Banco de nómina",
        "description": "Filtro inicial",
        "shared": True,
        "questions": [
            {**kept, "text": "¿Qué nóminas has calculado y de qué tamaño?"},
            {"text": "¿Usas CONTPAQi?", "origin": "IA"},
        ],
        "change_note": "Se precisó la primera",
        "expected_version": 1,
    }
    saved = recruiter.put(url, json=update)
    assert (
        saved.status_code == 200 and saved.json()["version_number"] == 2 and saved.json()["shared"]
    )
    assert saved.json()["questions"][0]["id"] == kept["id"]
    assert (
        saved.json()["questions"][1]["id"] != dropped["id"]
        and saved.json()["questions"][1]["origin"] == "IA"
    )
    assert recruiter.put(url, json=update).status_code == 409  # versión esperada antigua
    # Cambiar solo el nombre no crea versión.
    renamed = recruiter.put(
        url,
        json={
            **update,
            "name": "Banco nómina 2027",
            "questions": saved.json()["questions"],
            "expected_version": 2,
        },
    )
    assert renamed.json()["version_number"] == 2 and renamed.json()["name"] == "Banco nómina 2027"
    detail = recruiter.get(url).json()
    assert [
        (v["version_number"], v["questions"], v["change_note"]) for v in detail["versions"]
    ] == [
        (2, 2, "Se precisó la primera"),
        (1, 2, None),
    ]

    # Compartido: los demás lo ven y lo duplican, pero no lo modifican.
    seen = other_client.get(url).json()["bank"]
    assert (
        seen["mine"] is False
        and seen["can_edit"] is False
        and seen["owner_name"] == "Reclutadora de Prueba"
    )
    assert other_client.put(url, json={**update, "expected_version": 2}).status_code == 403
    assert other_client.post(f"{url}/archive").status_code == 403
    copy = other_client.post(f"{url}/duplicate")
    assert copy.status_code == 201
    assert (
        copy.json()["mine"]
        and not copy.json()["shared"]
        and copy.json()["name"] == "Banco nómina 2027 (copia)"
    )
    assert [q["text"] for q in copy.json()["questions"]] == [
        q["text"] for q in saved.json()["questions"]
    ]

    archived = recruiter.post(f"{url}/archive").json()
    assert archived["status"] == "ARCHIVADO"
    assert recruiter.put(url, json={**update, "expected_version": 2}).status_code == 409
    assert recruiter.post(f"{url}/restore").json()["status"] == "ACTIVO"
    assert len(audit(admin, "banco_preguntas.creado")) == 2


def test_la_ia_propone_preguntas_desde_el_perfil(recruiter, admin, vacancy_id, providers, other):
    other_client, _ = other
    url = f"{API}/question-banks/question-proposals"
    body = {"vacancy_id": vacancy_id, "count": 3}
    assert other_client.post(url, json=body).status_code == 404  # sin acceso a la vacante
    assert "perfil" in recruiter.post(url, json=body).json()["detail"]
    save_profile(recruiter, vacancy_id)
    assert "modelo asignado" in recruiter.post(url, json=body).json()["detail"]
    assign(admin, "ANALISIS_PERFILES")
    fake = providers[ProviderCode.ANTHROPIC]
    fake.prompts = []
    fake.script = [
        reply(
            {
                "preguntas": [
                    {
                        "texto": "¿Qué nóminas has calculado?",
                        "competencia": "Nómina",
                        "guia": "Tamaño",
                    },
                    {"texto": "¿Qué nóminas has calculado?"},
                    {"texto": ""},
                    "basura",
                ]
            }
        ),
        ProviderError("solicitud", "El modelo rechazó la solicitud."),
        reply({"preguntas": []}),
    ]
    proposed = recruiter.post(url, json=body)
    assert proposed.status_code == 200
    assert proposed.json() == [
        {"text": "¿Qué nóminas has calculado?", "competency": "Nómina", "guidance": "Tamaño"}
    ]
    _, system, user = fake.prompts[0]
    assert system == call_assistant.QUESTIONS_SYSTEM and "Propón 3 preguntas" in user
    assert "Experiencia en cálculo de nómina" in user
    assert recruiter.post(url, json=body).status_code == 503
    assert recruiter.post(url, json=body).status_code == 503
    # Proponer no guarda nada.
    assert recruiter.get(f"{API}/question-banks").json() == []


# --- Llamadas ----------------------------------------------------------------------------

ANALYSIS = {
    "resumen": "Describe tres años calculando nómina quincenal.",
    "evidencias": ["Nómina de 200 personas"],
    "competencias_exploradas": ["Nómina"],
    "informacion_faltante": ["No se preguntó por IMSS"],
    "coincidencias_con_cv": ["Analista de nómina en Uno SA"],
    "discrepancias_verificables": ["El CV indica 2020 a 2022; en la llamada dijo tres años"],
    "preguntas_de_seguimiento": ["¿En qué fechas trabajó en Uno SA?"],
    "recomendacion": "Contratar",
}


def test_llamada_completa_con_banco_respuestas_cierre_y_analisis(
    evaluated, recruiter, admin, vacancy_id, providers, other, clock
):
    other_client, other_id = other
    ana = by_name(evaluated)["Ana Pérez Ficticia"]["id"]
    bank = new_bank(recruiter)
    calls_url = f"{API}/applications/{ana}/calls"
    assert recruiter.get(calls_url).json() == []

    opened = recruiter.post(calls_url, json={"bank_id": bank["id"]})
    assert opened.status_code == 201
    call = opened.json()
    url = f"{API}/calls/{call['id']}"
    assert (
        call["status"] == "BORRADOR"
        and call["bank_name"] == "Banco de nómina"
        and call["bank_version"] == 1
    )
    assert [q["text"] for q in call["questions"]] == [q["text"] for q in QUESTIONS]
    assert call["created_by_name"] == "Reclutadora de Prueba"
    q1, q2 = (q["id"] for q in call["questions"])

    # Guardar parcialmente, y validar lo que no corresponde.
    partial = {
        "answers": [
            {
                "question_id": q1,
                "answer": "Tres años,\n  nómina quincenal de 200 personas.",
                "notes": "Respondió con detalle",
            }
        ],
        "notes": "Llamada de 15 minutos",
    }
    saved = recruiter.put(url, json=partial)
    assert (
        saved.status_code == 200
        and saved.json()["questions"][0]["answer"]
        == "Tres años,\nnómina quincenal de 200 personas."
    )
    assert (
        recruiter.put(
            url, json={"answers": [{"question_id": str(uuid.uuid4()), "answer": "x"}]}
        ).status_code
        == 422
    )
    future = clock.now.replace(year=2027).isoformat()
    assert recruiter.put(url, json={**partial, "called_at": future}).status_code == 422
    unfinished = recruiter.put(url, json={**partial, "close": True})
    assert unfinished.status_code == 422 and "Faltan: 2" in unfinished.json()["detail"]

    # El banco cambia después: la llamada conserva la versión con la que se abrió.
    recruiter.put(
        f"{API}/question-banks/{bank['id']}",
        json={
            "name": bank["name"],
            "shared": False,
            "questions": [{"text": "Pregunta nueva"}],
            "expected_version": 1,
        },
    )
    assert [q["text"] for q in recruiter.get(url).json()["questions"]] == [
        q["text"] for q in QUESTIONS
    ]

    # Análisis de IA: no decide, y a la IA no le llega el contacto de la persona.
    assert "modelo asignado" in recruiter.post(f"{url}/analysis").json()["detail"]
    assign(admin, "ANALISIS_LLAMADAS")
    fake = providers[ProviderCode.ANTHROPIC]
    fake.prompts = []
    fake.script = [reply(ANALYSIS), ProviderError("solicitud", "El modelo rechazó la solicitud.")]
    analyzed = recruiter.post(f"{url}/analysis")
    assert analyzed.status_code == 200
    analysis = analyzed.json()["analysis"]
    assert analysis["resumen"].startswith("Describe") and "recomendacion" not in analysis
    assert analysis["discrepancias_verificables"] == ANALYSIS["discrepancias_verificables"]
    _, system, user = fake.prompts[0]
    assert system == call_assistant.ANALYSIS_SYSTEM
    assert "nómina quincenal de 200 personas" in user and "No se realizó." in user
    assert "Analista de nómina en Uno SA (2020-01 a 2022-06)" in user
    assert "Experiencia en cálculo de nómina" in user
    assert "ana@ejemplo.test" not in user and "Ana Pérez" not in user
    # Si un análisis posterior falla, se conserva el anterior.
    assert recruiter.post(f"{url}/analysis").status_code == 503
    assert recruiter.get(url).json()["analysis"]["resumen"] == analysis["resumen"]

    # Cerrar: cada pregunta respondida o marcada como no realizada. Después no se modifica.
    final = {
        **partial,
        "answers": [*partial["answers"], {"question_id": q2, "not_asked": True}],
        "close": True,
    }
    closed = recruiter.put(url, json=final)
    assert (
        closed.status_code == 200
        and closed.json()["status"] == "CERRADA"
        and closed.json()["closed_at"]
    )
    assert closed.json()["questions"][1]["not_asked"] is True
    assert recruiter.put(url, json=partial).status_code == 409

    # Varias llamadas por postulación; permisos por vacante.
    second = recruiter.post(calls_url, json={"bank_id": bank["id"]}).json()
    assert second["bank_version"] == 2 and len(recruiter.get(calls_url).json()) == 2
    assert (
        "al menos una respuesta"
        in recruiter.post(f"{API}/calls/{second['id']}/analysis").json()["detail"]
    )
    assert (
        other_client.get(url).status_code == 404 and other_client.get(calls_url).status_code == 404
    )
    share(recruiter, vacancy_id, other_id, "LECTURA")
    assert other_client.get(url).status_code == 200 and len(other_client.get(calls_url).json()) == 2
    assert other_client.put(f"{API}/calls/{second['id']}", json=partial).status_code == 403
    assert other_client.post(f"{url}/analysis").status_code == 403
    # Con colaboración sí, pero no con un banco privado ajeno.
    share(recruiter, vacancy_id, other_id, "COLABORACION")
    assert other_client.post(calls_url, json={"bank_id": bank["id"]}).status_code == 404

    # Banco archivado o postulación inactiva: no se abre una llamada.
    recruiter.post(f"{API}/question-banks/{bank['id']}/archive")
    assert recruiter.post(calls_url, json={"bank_id": bank["id"]}).status_code == 409
    recruiter.post(f"{API}/question-banks/{bank['id']}/restore")
    recruiter.post(
        f"{API}/applications/{ana}/status",
        json={"action": "DESISTIMIENTO", "note": "Ya no le interesa"},
    )
    assert recruiter.post(calls_url, json={"bank_id": bank["id"]}).status_code == 409
    actions = {
        e["action"]
        for name in ("llamada.abierta", "llamada.guardada", "llamada.cerrada", "llamada.analizada")
        for e in audit(admin, name)
    }
    assert len(actions) == 4
    assert {e["result"] for e in audit(admin, "llamada.analizada")} == {"PERMITIDO", "FALLIDO"}


# --- OCR ---------------------------------------------------------------------------------


@pytest.mark.skipif(shutil.which("tesseract") is None, reason="Tesseract no está instalado")
def test_un_cv_escaneado_se_lee_con_ocr_y_se_evalua(
    recruiter, vacancy_id, prompt, model, providers
):
    from PIL import Image, ImageDraw, ImageFont

    image = Image.new("L", (1500, 520), 255)
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default(size=40)
    for row, line in enumerate(
        (
            "Curriculum ficticio escaneado",
            "Analista de nomina con cinco anios de experiencia",
            "Calculo de IMSS e ISR en Excel",
        )
    ):
        draw.text((40, 60 + row * 120), line, fill=0, font=font)
    scanned = io.BytesIO()
    image.save(scanned, format="PDF")
    picture = io.BytesIO()
    image.save(picture, format="PNG")
    upload(recruiter, vacancy_id, "escaneado.pdf", scanned.getvalue())
    upload(recruiter, vacancy_id, "foto.png", picture.getvalue() + b" ")
    fake = providers[ProviderCode.ANTHROPIC]
    fake.prompts = []
    fake.script = [answer(prompt, 4), answer(prompt, 3)]
    detail = start(recruiter, vacancy_id).json()
    assert detail["batch"]["status"] == "COMPLETADO" and detail["batch"]["accepted"] == 2
    assert {item["step"] for item in detail["items"]} == {"CALIFICADO"}
    _, _, user = fake.prompts[0]
    assert "Analista de nomina" in user and "documento escaneado" in user
