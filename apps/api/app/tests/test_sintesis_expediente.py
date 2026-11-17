"""Síntesis del expediente: preguntas sugeridas e historial. Datos inventados."""

# ruff: noqa: F401, F811  (las fixtures se importan de otro módulo de pruebas)
from __future__ import annotations

from app.modules.ai_settings.domain.models import ProviderCode
from app.modules.assessments.domain import assistant
from app.tests.test_api_assessments import ana
from app.tests.test_api_cv_batches import (
    API,
    admin,
    app,
    model,
    other,
    prompt,
    providers,
    recruiter,
    upload,
    vacancy_id,
)
from app.tests.test_api_recruitment import assign, by_name, evaluated, new_bank, reply


def test_la_sintesis_propone_preguntas_y_guarda_su_historial(
    ana, recruiter, admin, providers, clock
):
    assign(admin, "SINTESIS_EXPEDIENTES")
    fake = providers[ProviderCode.ANTHROPIC]
    url = f"{API}/applications/{ana}/syntheses"
    empty = recruiter.get(url).json()
    assert empty == {"latest": None, "total": 0, "history": [], "hidden": False}

    fake.prompts = []
    fake.script = [
        reply(
            {
                "hechos_documentados": ["Trabajó en nómina de 2021 a 2024"],
                "discrepancias_verificables": [
                    "El CV no dice el motivo de salida del último empleo"
                ],
                "preguntas_sugeridas": [
                    "¿Cuál fue el motivo de salida de tu último empleo?",
                    "  ¿Qué   sistema de nómina usabas a diario?  ",
                    "¿Cuál fue el motivo de salida de tu último empleo?",  # repetida
                    7,
                    *[f"Pregunta sobrante {n}" for n in range(1, 9)],
                ],
                # Nada de esto se conserva.
                "recomendacion": "Contratar",
                "puntuacion_global": 92,
            }
        )
    ]
    first = recruiter.post(url)
    assert first.status_code in (200, 201), first.text
    result = first.json()["result"]
    assert set(result) == set(assistant.SYNTHESIS_LISTS)
    assert result["preguntas_sugeridas"][:2] == [
        "¿Cuál fue el motivo de salida de tu último empleo?",
        "¿Qué sistema de nómina usabas a diario?",
    ]
    assert len(result["preguntas_sugeridas"]) == assistant.MAX_SUGGESTED_QUESTIONS
    # La instrucción limita de qué pueden tratar las preguntas.
    system = fake.prompts[0][1]
    assert system == assistant.SYNTHESIS_SYSTEM
    assert "nunca sobre edad, estado civil, hijos, embarazo, religión, salud" in system.replace(
        "\n", " "
    )

    # Una segunda síntesis no borra la primera: ambas quedan en el historial.
    clock.advance(seconds=5)
    fake.script = [reply({"hechos_documentados": ["Confirmó en llamada su motivo de salida"]})]
    second = recruiter.post(url)
    assert second.status_code in (200, 201), second.text
    assert second.json()["result"]["preguntas_sugeridas"] == []
    view = recruiter.get(url).json()
    assert view["total"] == 2 and view["latest"]["id"] == second.json()["id"]
    assert [item["id"] for item in view["history"]] == [second.json()["id"], first.json()["id"]]
    assert view["history"][1]["result"]["preguntas_sugeridas"][0].startswith("¿Cuál fue el motivo")

    # Unas preguntas sin nada del expediente no cuentan como síntesis.
    fake.script = [reply({"preguntas_sugeridas": ["¿Por qué quieres el puesto?"]})]
    assert recruiter.post(url).status_code == 503
    assert recruiter.get(url).json()["total"] == 2


def test_la_sintesis_relaciona_las_etapas_sin_valorar_ni_decidir(ana, recruiter, admin, providers):
    assign(admin, "SINTESIS_EXPEDIENTES")
    fake = providers[ProviderCode.ANTHROPIC]
    url = f"{API}/applications/{ana}/syntheses"
    fake.prompts = []
    fake.script = [
        reply(
            {
                "hechos_documentados": ["Trabajó en nómina de 2021 a 2024 (CV)"],
                "coincidencias_entre_fuentes": [
                    "El CV indica nómina de 2021 a 2024 (CV) y lo repitió (llamada 1)",
                    "  El CV indica nómina   de 2021 a 2024 (CV) y lo repitió (llamada 1)  ",
                    *[f"Coincidencia sobrante {n}" for n in range(1, 20)],
                ],
                "avance_por_etapa": [
                    "CV: documenta tres años en nómina.",
                    "Llamada: confirma los años del CV y añade el tamaño de la nómina.",
                    *[f"Etapa sobrante {n}" for n in range(1, 20)],
                ],
                # Nada de esto se conserva.
                "nivel_de_idoneidad": "alto",
                "conclusion": "Conviene avanzar",
            }
        )
    ]
    made = recruiter.post(url)
    assert made.status_code in (200, 201), made.text
    result = made.json()["result"]
    assert set(result) == set(assistant.SYNTHESIS_LISTS)
    assert result["coincidencias_entre_fuentes"][0].endswith("(llamada 1)")
    assert len(result["coincidencias_entre_fuentes"]) == assistant.MAX_MATCHES
    assert result["avance_por_etapa"][:2] == [
        "CV: documenta tres años en nómina.",
        "Llamada: confirma los años del CV y añade el tamaño de la nómina.",
    ]
    assert len(result["avance_por_etapa"]) == assistant.MAX_STAGE_NOTES

    # Las instrucciones piden relacionar con datos, y prohíben valorar o decidir.
    system = " ".join(fake.prompts[0][1].split())
    assert "citando cada fuente y el dato de cada una" in system
    assert "qué confirma de las etapas anteriores y qué deja abierto" in system
    assert "describe; no valores" in system
    assert "solo puedes relacionar la interpretación escrita por el profesional" in system
    assert "No relaciones con ninguna otra fuente las fotografías del estudio" in system
    assert "No recomiendes contratar, rechazar ni avanzar" in system

    # Relaciones sueltas, sin nada del expediente, no cuentan como síntesis.
    fake.script = [reply({"avance_por_etapa": ["CV: algo"], "coincidencias_entre_fuentes": ["x"]})]
    assert recruiter.post(url).status_code == 503
    assert recruiter.get(url).json()["total"] == 1
