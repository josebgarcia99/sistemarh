"""Fase 6: psicometría, entrevistas, pruebas técnicas, estudios socioeconómicos y síntesis.

Datos sintéticos y proveedor de IA simulado.
"""

# ruff: noqa: F401, F811  (las fixtures se importan de otros módulos de pruebas)
from __future__ import annotations

import json
import uuid
from decimal import Decimal

import pytest

from app.infrastructure.ai_providers.http_clients import Generation
from app.modules.ai_settings.domain.models import ProviderCode, ProviderError
from app.modules.assessments.domain import assistant, rules
from app.modules.assessments.domain.models import FieldType, Kind
from app.tests.conftest import share
from app.tests.support.sample_files import docx_cv, pdf_cv
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

# --- Reglas sin API ----------------------------------------------------------------------


def test_la_prueba_tecnica_se_califica_con_los_puntos_de_la_rubrica():
    rubric = [
        {"criterion": "Fórmulas", "max_points": 10, "points": "7,5"},
        {"criterion": "Tablas dinámicas", "max_points": "5", "points": 5},
        {"criterion": "", "max_points": None, "points": None},
    ]
    clean, score = rules.technical(
        {"test_type": "Excel", "rubric": rubric, "pass_mark": 80}, "REALIZADA"
    )
    assert score == Decimal("83.33") and clean["passed"] is True and len(clean["rubric"]) == 2
    below, low = rules.technical(
        {"test_type": "Excel", "rubric": rubric, "pass_mark": "90"}, "REALIZADA"
    )
    assert low == Decimal("83.33") and below["passed"] is False
    # Sin todos los puntos no hay calificación; sin mínimo no hay aprobado ni reprobado.
    partial, none = rules.technical(
        {"test_type": "Excel", "rubric": [{"criterion": "A", "max_points": 10, "points": None}]},
        "PENDIENTE",
    )
    assert none is None and partial["passed"] is None
    for bad, fragment in (
        ({"test_type": ""}, "tipo de prueba"),
        (
            {"test_type": "X", "rubric": [{"criterion": "A", "max_points": 0, "points": 0}]},
            "mayores que cero",
        ),
        (
            {"test_type": "X", "rubric": [{"criterion": "A", "max_points": 5, "points": 6}]},
            "de 0 a 5",
        ),
        ({"test_type": "X", "rubric": [{"criterion": "", "max_points": 5}]}, "no tiene nombre"),
        ({"test_type": "X", "pass_mark": 120}, "0 a 100"),
        ({"test_type": "X", "rubric": [{"criterion": "A", "max_points": "diez"}]}, "número"),
    ):
        with pytest.raises(rules.RuleError, match=fragment):
            rules.technical(bad, "PENDIENTE")
    with pytest.raises(rules.RuleError, match="toda la rúbrica"):
        rules.technical(
            {"test_type": "X", "rubric": [{"criterion": "A", "max_points": 5}]}, "REALIZADA"
        )


def test_los_formularios_se_validan_y_un_dato_solo_lo_verifica_una_persona():
    sections = rules.template_sections(
        [
            {
                "title": "Datos",
                "fields": [
                    {
                        "id": "visita",
                        "label": "Fecha de la visita",
                        "type": "FECHA",
                        "required": True,
                    },
                    {
                        "id": "refs",
                        "label": "Referencias",
                        "type": "NUMERO",
                        "minimum": 0,
                        "maximum": 5,
                    },
                    {
                        "id": "resultado",
                        "label": "Resultado",
                        "type": "OPCIONES",
                        "options": ["Sí", "No", "Sí"],
                    },
                    {
                        "id": "id oficial!",
                        "label": "Identificación",
                        "type": "CASILLA",
                        "required": True,
                    },
                    {"label": "Notas", "type": "OBSERVACION", "required": True},
                ],
            }
        ]
    )
    fields = sections[0].fields
    assert [f.id for f in fields[:3]] == ["visita", "refs", "resultado"]
    assert fields[3].id.startswith("c_") and fields[2].options == ("Sí", "No")
    assert fields[4].required is False  # una observación nunca es obligatoria

    class Version:
        fields = sections[0].fields

    answers = {
        "visita": {"value": "2026-11-10", "verified": True, "source": "MANUAL"},
        "refs": {"value": "3", "verified": "sí", "source": "IA"},
        "resultado": {"value": "Sí"},
        fields[3].id: {"value": True, "verified": True},
        "desconocido": {"value": "x"},
    }
    clean = rules.study({"answers": answers, "performed_by": " Ana  Ruiz "}, "COMPLETADO", Version)
    assert clean["performed_by"] == "Ana Ruiz" and "desconocido" not in clean["answers"]
    assert clean["answers"]["visita"] == {
        "value": "2026-11-10",
        "verified": True,
        "source": "MANUAL",
    }
    # Solo ``true`` cuenta como verificado, y el origen IA se conserva.
    assert clean["answers"]["refs"] == {"value": "3", "verified": False, "source": "IA"}
    for bad, fragment in (
        ({"visita": {"value": "10/11/2026"}}, "fecha"),
        ({"refs": {"value": 9}}, "rango"),
        ({"resultado": {"value": "Tal vez"}}, "opciones"),
    ):
        with pytest.raises(rules.RuleError, match=fragment):
            rules.study({"answers": bad}, "EN_PROCESO", Version)
    with pytest.raises(rules.RuleError, match="faltan: Fecha de la visita, Identificación"):
        rules.study({"answers": {}}, "COMPLETADO", Version)
    assert rules.study({"answers": {}}, "EN_PROCESO", Version)["answers"] == {}
    for bad, fragment in (
        ([], "al menos una sección"),
        ([{"title": "", "fields": []}], "no tiene título"),
        ([{"title": "A", "fields": []}], "no tiene campos"),
        ([{"title": "A", "fields": [{"label": "x", "type": "COLOR"}]}], "no es válido"),
        (
            [{"title": "A", "fields": [{"label": "x", "type": "OPCIONES", "options": ["a"]}]}],
            "dos opciones",
        ),
        (
            [
                {
                    "title": "A",
                    "fields": [{"label": "x", "type": "NUMERO", "minimum": 5, "maximum": 1}],
                }
            ],
            "mayor que el máximo",
        ),
    ):
        with pytest.raises(rules.RuleError, match=fragment):
            rules.template_sections(bad)


def test_la_sintesis_descarta_puntuaciones_y_recomendaciones():
    result = assistant.synthesis_from_answer(
        json.dumps(
            {
                "hechos_documentados": ["Analista en Uno SA (CV)", "Analista en Uno SA (CV)", 5],
                "declaraciones": ["Dijo tres años (llamada 1)"],
                "idoneidad": 87,
                "recomendacion": "Contratar",
            }
        )
    )
    assert set(result) == set(assistant.SYNTHESIS_LISTS)
    assert result["hechos_documentados"] == ["Analista en Uno SA (CV)"]
    with pytest.raises(assistant.InvalidAnswerError):
        assistant.synthesis_from_answer(json.dumps({"idoneidad": 87}))


# --- Soporte -----------------------------------------------------------------------------


@pytest.fixture
def ana(evaluated) -> str:
    return by_name(evaluated)["Ana Pérez Ficticia"]["id"]


def create(client, application_id, kind, **body):
    return client.post(
        f"{API}/applications/{application_id}/assessments", json={"kind": kind, **body}
    )


def update(client, item, **changes):
    body = {
        "status": item["status"],
        "data": item["data"],
        "event_date": item["event_date"],
        "file_id": item["file_id"],
        "version": item["version"],
        **changes,
    }
    return client.put(f"{API}/assessments/{item['id']}", json=body)


def listing(client, application_id) -> dict:
    return client.get(f"{API}/applications/{application_id}/assessments").json()


# --- Psicometría -------------------------------------------------------------------------


def test_psicometria_estados_validacion_profesional_y_resumen_del_documento(
    ana, recruiter, admin, vacancy_id, providers
):
    assert create(recruiter, ana, "PSICOMETRIA", data={}).status_code == 422
    created = create(
        recruiter,
        ana,
        "PSICOMETRIA",
        data={"instrument": " Prueba  Ficticia X ", "provider": "Proveedor Demo"},
    )
    assert created.status_code == 201
    test = created.json()
    assert test["status"] == "PENDIENTE" and test["data"]["instrument"] == "Prueba Ficticia X"
    assert test["statuses"] == [
        "PENDIENTE",
        "PRESENTADA",
        "NO_PRESENTADA",
        "INCOMPLETA",
        "NO_APLICA",
        "ANULADA",
        "VALIDADA",
    ]
    assert (
        update(recruiter, test, status="REALIZADA").status_code == 422
    )  # no es un estado de psicometría

    # El documento debe ser de psicometría y de esta vacante; se guarda cifrado.
    cv = recruiter.get(f"{API}/vacancies/{vacancy_id}/files").json()[0]
    assert update(recruiter, test, file_id=cv["id"]).status_code == 422
    report = upload(
        recruiter,
        vacancy_id,
        "reporte.docx",
        docx_cv(
            "Reporte ficticio de la Prueba X.",
            "Escala de razonamiento: percentil 70.",
            "Escala verbal: percentil 55.",
        ),
        document_type="PSICOMETRIA",
    )
    assert report["encrypted"] is True
    presented = update(
        recruiter,
        test,
        status="PRESENTADA",
        file_id=report["id"],
        event_date="2026-11-09T16:00:00Z",
    )
    assert presented.status_code == 200 and presented.json()["version"] == 2
    # Dos personas a la vez: la segunda no pisa a la primera.
    assert update(recruiter, test, status="INCOMPLETA").status_code == 409
    test = presented.json()

    # Resumen de IA: lee el documento descifrado; no diagnostica ni declara aptitud.
    url = f"{API}/assessments/{test['id']}/summary"
    assert "modelo asignado" in recruiter.post(url).json()["detail"]
    assign(admin, "RESUMEN_PRUEBAS")
    fake = providers[ProviderCode.ANTHROPIC]
    fake.prompts = []
    fake.script = [
        reply(
            {
                "resumen": "El reporte documenta dos escalas.",
                "resultados_documentados": ["Razonamiento: percentil 70"],
                "diagnostico": "Ansiedad",
                "apto": True,
            }
        ),
        ProviderError("solicitud", "El modelo rechazó la solicitud."),
    ]
    summarized = recruiter.post(url)
    assert summarized.status_code == 200
    summary = summarized.json()["ai_summary"]
    assert summary["resumen"].startswith("El reporte") and set(summary) == {
        "resumen",
        "resultados_documentados",
        "datos_no_legibles",
        "advertencias",
    }
    _, system, user = fake.prompts[0]
    assert system == assistant.PSYCHOMETRIC_SYSTEM and "percentil 70" in user
    assert recruiter.post(url).status_code == 503
    test = recruiter.get(f"{API}/assessments/{test['id']}").json()
    assert test["ai_summary"]["resumen"].startswith("El reporte")  # el fallo no borra el anterior

    # Validada: exige al profesional que la interpretó y el resultado documentado.
    refused = update(recruiter, test, status="VALIDADA")
    assert refused.status_code == 422 and "profesional" in refused.json()["detail"]
    data = {
        **test["data"],
        "professional_name": "Psic. Laura Ficticia",
        "professional_license": "0000000",
        "result": "Razonamiento percentil 70; verbal percentil 55.",
        "validation_note": "Resultados dentro de lo esperado para el puesto.",
    }
    validated = update(recruiter, test, status="VALIDADA", data=data)
    assert validated.status_code == 200 and validated.json()["status"] == "VALIDADA"
    # Registrar una evaluación no mueve de etapa ni cambia el estado de la postulación.
    application = recruiter.get(f"{API}/applications/{ana}").json()
    assert application["application"]["status"] == "ACTIVA" and len(application["movements"]) == 2
    events = audit(admin, "evaluacion.actualizada")
    assert all(
        "result" not in e["details"] and "instrument" not in json.dumps(e["details"])
        for e in events
    )


def test_la_psicometria_y_el_estudio_exigen_el_permiso_adicional(ana, recruiter, vacancy_id, other):
    other_client, other_id = other
    psychometric = create(recruiter, ana, "PSICOMETRIA", data={"instrument": "Prueba X"}).json()
    interview = create(
        recruiter, ana, "ENTREVISTA", data={"interviewer": "Gerente Ficticio"}
    ).json()
    templates = recruiter.get(f"{API}/form-templates").json()
    study = create(recruiter, ana, "ESTUDIO_SOCIOECONOMICO", template_id=templates[0]["id"]).json()

    # Sin acceso a la vacante, nada existe.
    assert other_client.get(f"{API}/applications/{ana}/assessments").status_code == 404
    assert other_client.get(f"{API}/assessments/{interview['id']}").status_code == 404

    # Con colaboración se trabaja la entrevista, pero no se ve lo sensible.
    share(recruiter, vacancy_id, other_id, "COLABORACION")
    seen = listing(other_client, ana)
    assert [item["kind"] for item in seen["items"]] == ["ENTREVISTA"]
    assert seen["restricted"] == ["ESTUDIO_SOCIOECONOMICO", "PSICOMETRIA"]
    assert seen["writable"] == ["ENTREVISTA", "PRUEBA_TECNICA"]
    for item in (psychometric, study):
        assert other_client.get(f"{API}/assessments/{item['id']}").status_code == 403
        assert update(other_client, item).status_code == 403
    assert create(other_client, ana, "PSICOMETRIA", data={"instrument": "Otra"}).status_code == 403
    assert (
        create(other_client, ana, "PRUEBA_TECNICA", data={"test_type": "Excel"}).status_code == 201
    )

    # El permiso adicional es por clase: psicometría sí, estudio no.
    grants = f"{API}/vacancies/{vacancy_id}/members/{other_id}/sensitive-grants"
    recruiter.put(grants, json={"document_classes": ["PSICOMETRIA"]})
    seen = listing(other_client, ana)
    assert {item["kind"] for item in seen["items"]} == {
        "ENTREVISTA",
        "PSICOMETRIA",
        "PRUEBA_TECNICA",
    }
    assert seen["restricted"] == ["ESTUDIO_SOCIOECONOMICO"]
    assert update(other_client, psychometric, status="PRESENTADA").status_code == 200
    # Con lectura y permiso se consulta, pero no se captura.
    share(recruiter, vacancy_id, other_id, "LECTURA")
    recruiter.put(grants, json={"document_classes": ["PSICOMETRIA"]})
    assert other_client.get(f"{API}/assessments/{psychometric['id']}").status_code == 200
    assert listing(other_client, ana)["writable"] == []
    assert create(other_client, ana, "ENTREVISTA", data={"interviewer": "X"}).status_code == 403


# --- Entrevista y prueba técnica ---------------------------------------------------------


def test_entrevista_con_gerente_conclusion_humana_y_resumen(ana, recruiter, admin, providers):
    interview = create(
        recruiter,
        ana,
        "ENTREVISTA",
        data={"interviewer": "Gerente Ficticio"},
        event_date="2026-11-12T16:00:00Z",
    ).json()
    assert interview["status"] == "PROGRAMADA"
    data = {
        "interviewer": "Gerente Ficticio",
        "questions": [
            {
                "question": "¿Cómo resuelves un error de nómina?",
                "answer": "Lo documento y recalculo.",
            },
            {"question": "", "answer": ""},
        ],
        "competencies": ["Análisis", "Análisis", "Comunicación"],
        "feedback": "Explica con claridad sus procesos.",
    }
    # Realizada exige la conclusión de quien entrevistó y una fecha que ya pasó.
    refused = update(recruiter, interview, status="REALIZADA", data=data)
    assert refused.status_code == 422 and "conclusión" in refused.json()["detail"]
    data["conclusion"] = "Recomiendo continuar con la prueba técnica."
    assert (
        update(recruiter, interview, status="REALIZADA", data=data).status_code == 422
    )  # fecha futura
    done = update(
        recruiter, interview, status="REALIZADA", data=data, event_date="2026-11-09T16:00:00Z"
    )
    assert done.status_code == 200
    interview = done.json()
    assert (
        interview["data"]["competencies"] == ["Análisis", "Comunicación"]
        and len(interview["data"]["questions"]) == 1
    )

    assign(admin, "ANALISIS_LLAMADAS")
    fake = providers[ProviderCode.ANTHROPIC]
    fake.prompts = []
    fake.script = [
        reply(
            {
                "resumen": "Describe cómo corrige errores.",
                "competencias_observadas": ["Análisis"],
                "conclusion": "No contratar",
            }
        )
    ]
    summarized = recruiter.post(f"{API}/assessments/{interview['id']}/summary").json()
    assert summarized["ai_summary"]["competencias_observadas"] == ["Análisis"]
    assert "conclusion" not in summarized["ai_summary"]
    # La conclusión humana no cambia con el resumen.
    assert summarized["data"]["conclusion"] == "Recomiendo continuar con la prueba técnica."
    _, system, user = fake.prompts[0]
    assert system == assistant.INTERVIEW_SYSTEM and "Lo documento y recalculo." in user


def test_prueba_tecnica_con_rubrica_calificacion_y_documento(
    ana, recruiter, admin, vacancy_id, providers
):
    rubric = [
        {"criterion": "Fórmulas", "max_points": 10, "points": 8},
        {"criterion": "Tablas", "max_points": 10, "points": None},
    ]
    created = create(
        recruiter,
        ana,
        "PRUEBA_TECNICA",
        data={
            "test_type": "Excel",
            "competency": "Hojas de cálculo",
            "rubric": rubric,
            "pass_mark": 70,
        },
    )
    assert created.status_code == 201
    test = created.json()
    assert (
        test["status"] == "PENDIENTE" and test["score"] is None and test["data"]["passed"] is None
    )
    rubric[1]["points"] = 7
    done = update(
        recruiter,
        test,
        status="REALIZADA",
        data={**test["data"], "rubric": rubric, "result": "Resolvió 3 de 4 ejercicios."},
    )
    assert done.status_code == 200
    test = done.json()
    assert Decimal(test["score"]) == Decimal("75") and test["data"]["passed"] is True

    document = upload(
        recruiter,
        vacancy_id,
        "prueba.docx",
        docx_cv("Prueba ficticia de Excel resuelta." * 3),
        document_type="PRUEBA_TECNICA",
    )
    attached = update(recruiter, test, file_id=document["id"]).json()
    assign(admin, "RESUMEN_PRUEBAS")
    fake = providers[ProviderCode.ANTHROPIC]
    fake.prompts = []
    fake.script = [reply({"resumen": "Prueba de Excel resuelta.", "resultados_documentados": []})]
    assert recruiter.post(f"{API}/assessments/{attached['id']}/summary").status_code == 200
    assert "Prueba ficticia de Excel" in fake.prompts[0][2]
    # Omitir el módulo: se registra como «no aplica».
    skipped = create(
        recruiter,
        ana,
        "PRUEBA_TECNICA",
        status="NO_APLICA",
        data={"test_type": "No se requiere para este puesto"},
    )
    assert skipped.status_code == 201 and skipped.json()["status"] == "NO_APLICA"


# --- Estudio socioeconómico --------------------------------------------------------------


def test_formularios_configurables_por_versiones(recruiter, admin):
    templates = recruiter.get(f"{API}/form-templates").json()
    assert [t["name"] for t in templates] == ["SGC.F3.RH. Estudio socioeconómico"]
    default = templates[0]
    assert default["version_number"] == 1 and len(default["sections"]) == 19
    body = {
        "name": "Estudio para puestos de confianza",
        "sections": [{"title": "Datos", "fields": [{"label": "Fecha", "type": "FECHA"}]}],
    }
    assert recruiter.post(f"{API}/form-templates", json=body).status_code == 403
    assert admin.post(f"{API}/form-templates", json={**body, "sections": []}).status_code == 422
    created = admin.post(f"{API}/form-templates", json=body)
    assert created.status_code == 201 and created.json()["version_number"] == 1
    template = created.json()
    url = f"{API}/form-templates/{template['id']}"
    kept = template["sections"][0]["fields"][0]
    changed = {
        **body,
        "expected_version": 1,
        "sections": [
            {"title": "Datos", "fields": [kept, {"label": "Observaciones", "type": "OBSERVACION"}]}
        ],
    }
    saved = admin.put(url, json=changed)
    assert saved.status_code == 200 and saved.json()["version_number"] == 2
    assert (
        saved.json()["sections"][0]["fields"][0]["id"] == kept["id"]
    )  # el campo conserva su identificador
    assert admin.put(url, json=changed).status_code == 409
    # Cambiar solo el nombre no crea versión.
    renamed = admin.put(
        url,
        json={
            **changed,
            "name": "Estudio de confianza",
            "sections": saved.json()["sections"],
            "expected_version": 2,
        },
    )
    assert (
        renamed.json()["version_number"] == 2 and renamed.json()["name"] == "Estudio de confianza"
    )
    assert admin.post(f"{url}/archive").json()["status"] == "ARCHIVADA"
    assert recruiter.post(f"{url}/restore").status_code == 403
    assert len(audit(admin, "formulario.version_creada")) == 2


def test_estudio_socioeconomico_captura_digitalizacion_y_verificacion_humana(
    ana, recruiter, admin, vacancy_id, providers
):
    template = recruiter.get(f"{API}/form-templates").json()[0]
    fields = {f["label"]: f for section in template["sections"] for f in section["fields"]}
    assert (
        create(recruiter, ana, "ESTUDIO_SOCIOECONOMICO").status_code == 422
    )  # falta el formulario
    study = create(recruiter, ana, "ESTUDIO_SOCIOECONOMICO", template_id=template["id"]).json()
    assert study["status"] == "PENDIENTE" and study["score"] is None and len(study["form"]) == 19

    # Digitalización: la IA propone valores a partir del formulario escaneado; no guarda nada.
    scanned = upload(
        recruiter,
        vacancy_id,
        "estudio.docx",
        docx_cv(
            "Estudio socioeconómico ficticio.",
            "Fecha de aplicación: 10 de noviembre de 2026.",
            "Domicilio: Calle Inventada 123.",
        ),
        document_type="ESTUDIO_SOCIOECONOMICO",
    )
    url = f"{API}/assessments/{study['id']}/digitization"
    cv = next(
        f
        for f in recruiter.get(f"{API}/vacancies/{vacancy_id}/files").json()
        if f["document_type"] == "CV"
    )
    assert recruiter.post(url, json={"file_id": cv["id"]}).status_code == 422
    assign(admin, "LECTURA_DOCUMENTOS")
    visit, address, refs, identity = (
        fields[k]["id"]
        for k in (
            "Fecha de aplicación",
            "Domicilio",
            "Automóviles: cuántos",
            "INE",
        )
    )
    fake = providers[ProviderCode.ANTHROPIC]
    fake.prompts = []
    fake.script = [
        reply(
            {
                "valores": {
                    visit: "2026-11-10",
                    address: "Calle Inventada 123",
                    identity: True,
                    refs: None,
                    "campo_inventado": "x",
                    "nivel_socioeconomico": "medio",
                },
                "ilegibles": ["Ocupación"],
                "faltantes": ["Automóviles: cuántos"],
            }
        )
    ]
    proposal = recruiter.post(url, json={"file_id": scanned["id"]})
    assert proposal.status_code == 200
    assert proposal.json() == {
        "values": {visit: "2026-11-10", address: "Calle Inventada 123", identity: True},
        "illegible": ["Ocupación"],
        "missing": ["Automóviles: cuántos"],
    }
    _, system, user = fake.prompts[0]
    assert (
        system == assistant.DIGITIZATION_SYSTEM and "Calle Inventada 123" in user and visit in user
    )
    assert recruiter.get(f"{API}/assessments/{study['id']}").json()["data"]["answers"] == {}

    # La persona acepta la propuesta: entra como leída por IA y SIN verificar.
    answers = {
        key: {"value": value, "source": "IA"} for key, value in proposal.json()["values"].items()
    }
    saved = update(
        recruiter,
        study,
        status="EN_PROCESO",
        data={"answers": answers, "performed_by": "Trabajadora Social Ficticia"},
    )
    assert saved.status_code == 200
    study = saved.json()
    assert all(
        a["source"] == "IA" and a["verified"] is False for a in study["data"]["answers"].values()
    )
    # Verificar es un acto humano, campo por campo.
    answers[visit]["verified"] = True
    answers[fields["Formato firmado (escaneado)"]["id"]] = {"value": scanned["id"]}
    answers[fields["Nombre completo"]["id"]] = {"value": "Persona Ficticia"}
    done = update(recruiter, study, status="COMPLETADO", data={**study["data"], "answers": answers})
    assert done.status_code == 200 and done.json()["data"]["answers"][visit]["verified"] is True
    assert done.json()["data"]["answers"][address]["verified"] is False
    assert done.json()["score"] is None  # el estudio nunca se puntúa
    # Un documento que no es un estudio de la vacante no se acepta en el formulario.
    answers[fields["Formato firmado (escaneado)"]["id"]] = {"value": cv["id"]}
    assert (
        update(recruiter, done.json(), data={**study["data"], "answers": answers}).status_code
        == 422
    )
    # Completar exige los campos obligatorios.
    empty = create(recruiter, ana, "ESTUDIO_SOCIOECONOMICO", template_id=template["id"]).json()
    refused = update(recruiter, empty, status="COMPLETADO", data={"answers": {}})
    assert refused.status_code == 422 and "Fecha de aplicación" in refused.json()["detail"]
    assert recruiter.post(f"{API}/assessments/{study['id']}/summary").status_code == 422
    assert audit(admin, "estudio.digitalizado")[0]["result"] == "PERMITIDO"


# --- Síntesis del expediente -------------------------------------------------------------

SYNTHESIS = {
    "hechos_documentados": ["Analista de nómina en Uno SA de 2020-01 a 2022-06 (CV)"],
    "declaraciones": ["Dijo haber calculado nómina tres años (llamada 1)"],
    "observaciones_humanas": ["El gerente recomienda continuar (entrevista)"],
    "resultados_tecnicos": ["Excel: 75 de 100 (prueba técnica)"],
    "informacion_pendiente": ["Estudio socioeconómico pendiente"],
    "discrepancias_verificables": ["CV: 2 años 6 meses; llamada: tres años"],
    "indice_de_idoneidad": 82,
}


def test_sintesis_del_expediente_por_tipo_de_fuente_sin_puntuar(
    ana, recruiter, admin, vacancy_id, providers, other
):
    other_client, other_id = other
    url = f"{API}/applications/{ana}/syntheses"
    assert recruiter.get(url).json() == {"latest": None, "total": 0, "hidden": False}
    assert "modelo asignado" in recruiter.post(url).json()["detail"]
    assign(admin, "SINTESIS_EXPEDIENTES")

    # Un expediente con llamada, entrevista, prueba técnica, psicometría y estudio.
    bank = new_bank(recruiter)
    call = recruiter.post(f"{API}/applications/{ana}/calls", json={"bank_id": bank["id"]}).json()
    q1 = call["questions"][0]["id"]
    recruiter.put(
        f"{API}/calls/{call['id']}",
        json={
            "answers": [
                {
                    "question_id": q1,
                    "answer": "Calculé nómina tres años.",
                    "notes": "Segura al responder",
                }
            ],
            "notes": "",
        },
    )
    create(
        recruiter,
        ana,
        "ENTREVISTA",
        status="REALIZADA",
        event_date="2026-11-09T16:00:00Z",
        data={
            "interviewer": "Gerente Ficticio",
            "feedback": "Buen dominio.",
            "conclusion": "Recomiendo continuar.",
        },
    )
    create(
        recruiter,
        ana,
        "PRUEBA_TECNICA",
        status="REALIZADA",
        data={"test_type": "Excel", "rubric": [{"criterion": "A", "max_points": 4, "points": 3}]},
    )
    pending = create(
        recruiter,
        ana,
        "PSICOMETRIA",
        status="PRESENTADA",
        data={"instrument": "Prueba X", "result": "Percentil 70 SECRETO-SIN-VALIDAR"},
    ).json()
    template = recruiter.get(f"{API}/form-templates").json()[0]
    address_field = next(
        f["id"] for s in template["sections"] for f in s["fields"] if f["label"] == "Domicilio"
    )
    study = create(recruiter, ana, "ESTUDIO_SOCIOECONOMICO", template_id=template["id"]).json()
    update(
        recruiter,
        study,
        status="EN_PROCESO",
        data={"answers": {address_field: {"value": "Calle Privada 99 DOMICILIO-SECRETO"}}},
    )

    fake = providers[ProviderCode.ANTHROPIC]
    fake.prompts = []
    fake.script = [reply(SYNTHESIS)]
    created = recruiter.post(url)
    assert created.status_code == 201, created.text
    synthesis = created.json()
    assert set(synthesis["result"]) == set(assistant.SYNTHESIS_LISTS)  # sin índice de idoneidad
    assert synthesis["sources"] == ["CV", "1 llamadas", "1 pruebas técnicas", "1 entrevistas"]
    assert synthesis["includes_psychometrics"] is False
    _, system, user = fake.prompts[0]
    assert system == assistant.SYNTHESIS_SYSTEM
    assert "Calculé nómina tres años." in user and "Recomiendo continuar." in user
    assert "Calificación calculada: 75.00 de 100" in user and "Uno SA (2020-01 a 2022-06)" in user
    # La psicometría sin validar y el contenido del estudio socioeconómico NUNCA entran.
    assert "SECRETO-SIN-VALIDAR" not in user and "DOMICILIO-SECRETO" not in user
    assert "Prueba psicométrica sin validar por un profesional" in user
    assert "Estudio socioeconómico en estado EN_PROCESO" in user
    # Tampoco el nombre ni el contacto de la persona.
    assert "Ana Pérez" not in user and "ana@ejemplo.test" not in user

    # Con la psicometría validada por un profesional, entra su interpretación.
    update(
        recruiter,
        pending,
        status="VALIDADA",
        data={
            **pending["data"],
            "result": "Percentil 70 en razonamiento.",
            "professional_name": "Psic. Laura Ficticia",
            "validation_note": "Adecuado para el puesto.",
        },
    )
    recruiter.app.state.context.clock.advance(minutes=1)
    fake.prompts = []
    fake.script = [reply(SYNTHESIS), reply({"indice": 90})]
    second = recruiter.post(url).json()
    assert (
        second["includes_psychometrics"] is True
        and "1 pruebas psicométricas validadas" in second["sources"]
    )
    assert "Interpretación de Psic. Laura Ficticia: Adecuado para el puesto." in fake.prompts[0][2]
    assert recruiter.post(url).status_code == 503  # una respuesta sin las listas no sirve
    view = recruiter.get(url).json()
    assert view["total"] == 2 and view["latest"]["id"] == second["id"] and view["hidden"] is False

    # Quien no tiene el permiso de psicometría no ve la síntesis que la incluye, ni la provoca.
    assert other_client.get(url).status_code == 404
    share(recruiter, vacancy_id, other_id, "LECTURA")
    limited = other_client.get(url).json()
    assert (
        limited["latest"]["id"] == synthesis["id"]
        and limited["total"] == 1
        and limited["hidden"] is True
    )
    assert other_client.post(url).status_code == 403
    share(recruiter, vacancy_id, other_id, "COLABORACION")
    fake.prompts = []
    fake.script = [reply(SYNTHESIS)]
    mine = other_client.post(url).json()
    assert mine["includes_psychometrics"] is False and "Psic. Laura" not in fake.prompts[0][2]
    events = audit(admin, "expediente.sintetizado")
    assert {e["result"] for e in events} == {"PERMITIDO", "FALLIDO"}


def test_sin_informacion_no_hay_sintesis_y_una_postulacion_inactiva_no_admite_evaluaciones(
    recruiter, admin, vacancy_id, providers
):
    assign(admin, "SINTESIS_EXPEDIENTES")
    manual = recruiter.post(
        f"{API}/vacancies/{vacancy_id}/applications", json={"full_name": "Carla Ruiz"}
    ).json()
    application_id = manual["application"]["id"]
    empty = recruiter.post(f"{API}/applications/{application_id}/syntheses")
    assert empty.status_code == 422 and "no tiene información" in empty.json()["detail"]
    assert providers[ProviderCode.ANTHROPIC].prompts is None
    recruiter.post(
        f"{API}/applications/{application_id}/status",
        json={"action": "DESCARTE", "note": "Duplicada"},
    )
    assert (
        create(recruiter, application_id, "ENTREVISTA", data={"interviewer": "X"}).status_code
        == 409
    )
    assert recruiter.get(f"{API}/applications/{uuid.uuid4()}/assessments").status_code == 404
