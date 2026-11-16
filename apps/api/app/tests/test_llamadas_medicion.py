"""Llamadas: preguntas generales de la empresa y medición contra lo esperado."""

# ruff: noqa: F401, F811  (las fixtures se importan de otro módulo de pruebas)
from __future__ import annotations

import uuid

from app.modules.ai_settings.domain.models import ProviderCode
from app.modules.phone_calls.domain import assistant
from app.modules.phone_calls.domain.models import Answer, Question
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

GENERAL = [
    {"text": "¿Por qué te interesa la vacante?", "guidance": ""},
    {
        "text": "¿Cuál es tu disponibilidad de horario?",
        "guidance": "Disponible de lunes a viernes en horario de oficina",
    },
]


def _question(text: str, guidance: str = "") -> Question:
    return Question(id=uuid.uuid4(), text=text, guidance=guidance)


def test_la_medicion_la_calcula_el_sistema_con_los_niveles_de_la_ia():
    questions = [
        _question("¿Qué nóminas has calculado?", "Tamaño y periodicidad"),
        _question("¿Qué sistema usabas?", "Menciona un sistema de nómina"),
        _question("¿Por qué te interesa?"),  # sin «qué se espera»: no se mide
        _question("¿Cómo calculas un finiquito?", "Partes proporcionales y prima"),
        _question("¿Manejas IMSS?", "Altas, bajas y modificaciones"),
        _question("¿Y el ISR?", "Tablas y subsidio"),
    ]
    answers = [
        Answer(questions[0].id, "Quincenal de 300 personas"),
        Answer(questions[1].id, "Uno de la empresa"),
        Answer(questions[2].id, "Me gusta"),
        Answer(questions[3].id, "No lo he hecho"),
        Answer(questions[4].id, not_asked=True),  # no se realizó: no se mide
        Answer(questions[5].id, "Sí, con las tablas"),
    ]
    payload = {
        "cobertura": [
            {"pregunta": 1, "nivel": "cumple", "evidencia": "Quincenal de   300 personas"},
            {"pregunta": 2, "nivel": "PARCIAL", "evidencia": "Uno de la empresa"},
            {"pregunta": 3, "nivel": "CUMPLE"},  # no tenía qué se espera: se ignora
            {"pregunta": 4, "nivel": "NO_CUMPLE", "evidencia": "No lo he hecho"},
            {"pregunta": 5, "nivel": "CUMPLE"},  # no se realizó: se ignora
            {"pregunta": 6, "nivel": "EXCELENTE"},  # nivel inventado: queda sin valorar
            {"pregunta": 99, "nivel": "CUMPLE"},
            "no es una fila",
        ],
        # La IA no pone el número.
        "score": 100,
    }
    result = assistant.measurement(payload, questions, answers)
    assert result is not None
    assert [(item["numero"], item["nivel"]) for item in result["items"]] == [
        (1, "CUMPLE"),
        (2, "PARCIAL"),
        (4, "NO_CUMPLE"),
        (6, "SIN_VALORAR"),
    ]
    assert result["items"][0]["evidencia"] == "Quincenal de 300 personas"
    # (1 + 0.5 + 0) / 3 preguntas valoradas = 50.0
    assert result["score"] == 50.0 and result["valoradas"] == 3 and result["sin_valorar"] == 1
    # Sin ninguna valoración no hay número; sin preguntas medibles no hay medición.
    assert assistant.measurement({}, questions, answers)["score"] is None
    assert assistant.measurement(payload, [questions[2]], answers) is None
    request = assistant.analysis_request(questions[:1], answers[:1], "", _application())
    assert "Qué se espera de la respuesta: Tamaño y periodicidad" in request


def _application():
    from app.modules.phone_calls.domain.models import ApplicationRef

    return ApplicationRef(
        id=uuid.uuid4(), vacancy_id=uuid.uuid4(), active=True, candidate_name="Persona Ficticia"
    )


def test_las_preguntas_generales_se_agregan_a_toda_llamada_y_la_llamada_se_mide(
    ana, recruiter, admin, providers
):
    # Solo un administrador define las preguntas generales de la empresa.
    refused = recruiter.post(
        f"{API}/question-banks",
        json={"name": "Generales", "general": True, "questions": GENERAL},
    )
    assert refused.status_code == 403 and "administrador" in refused.json()["detail"]
    general = new_bank(admin, name="Preguntas generales", general=True, questions=GENERAL)
    assert general["general"] is True and general["shared"] is False
    # Los reclutadores las ven, pero no las cambian.
    seen = {item["name"]: item for item in recruiter.get(f"{API}/question-banks").json()}
    assert seen["Preguntas generales"]["general"] is True
    assert seen["Preguntas generales"]["can_edit"] is False
    locked = recruiter.put(
        f"{API}/question-banks/{general['id']}",
        json={"name": "Otro", "general": True, "questions": GENERAL, "expected_version": 1},
    )
    assert locked.status_code == 403

    bank = new_bank(recruiter)
    opened = recruiter.post(f"{API}/applications/{ana}/calls", json={"bank_id": bank["id"]})
    assert opened.status_code == 201, opened.text
    call = opened.json()
    texts = [(question["text"], question["general"]) for question in call["questions"]]
    assert texts[:2] == [
        ("¿Por qué te interesa la vacante?", True),
        ("¿Cuál es tu disponibilidad de horario?", True),
    ]
    assert all(not is_general for _, is_general in texts[2:]) and len(texts) > 2

    # El administrador cambia las generales: la llamada abierta conserva las suyas…
    changed = admin.put(
        f"{API}/question-banks/{general['id']}",
        json={
            "name": "Preguntas generales",
            "general": True,
            "questions": [{"text": "¿Cuándo podrías empezar?", "guidance": ""}],
            "expected_version": 1,
        },
    )
    assert changed.status_code == 200, changed.text
    url = f"{API}/calls/{call['id']}"
    assert [q["text"] for q in recruiter.get(url).json()["questions"]][:2] == [
        t for t, _ in texts[:2]
    ]
    # …y una llamada nueva usa las vigentes.
    later = recruiter.post(f"{API}/applications/{ana}/calls", json={"bank_id": bank["id"]}).json()
    assert [q["text"] for q in later["questions"] if q["general"]] == ["¿Cuándo podrías empezar?"]
    # Abrir una llamada con el propio banco general no repite sus preguntas.
    only = admin.post(f"{API}/applications/{ana}/calls", json={"bank_id": general["id"]}).json()
    assert [q["text"] for q in only["questions"]] == ["¿Cuándo podrías empezar?"]

    # Se capturan todas (generales y del banco) y la llamada se analiza y se mide.
    answers = [
        {"question_id": question["id"], "answer": f"Respuesta inventada {number}"}
        for number, question in enumerate(call["questions"], start=1)
    ]
    saved = recruiter.put(url, json={"answers": answers, "notes": "", "close": True})
    assert saved.status_code == 200, saved.text
    assign(admin, "ANALISIS_LLAMADAS")
    fake = providers[ProviderCode.ANTHROPIC]
    fake.prompts = []
    measured = [n for n, q in enumerate(call["questions"], start=1) if q["guidance"]]
    fake.script = [
        reply(
            {
                "resumen": "Llamada inventada.",
                "cobertura": [
                    {
                        "pregunta": measured[0],
                        "nivel": "CUMPLE",
                        "evidencia": "Respuesta inventada",
                    },
                    {"pregunta": measured[1], "nivel": "PARCIAL", "evidencia": ""},
                ],
                "calificacion": 99,
                "recomendacion": "Avanzar",
            }
        )
    ]
    analyzed = recruiter.post(f"{url}/analysis")
    assert analyzed.status_code == 200, analyzed.text
    analysis = analyzed.json()["analysis"]
    assert "calificacion" not in analysis and "recomendacion" not in analysis
    measurement = analysis["medicion"]
    assert measurement["valoradas"] == 2
    assert measurement["sin_valorar"] == len(measured) - 2
    assert measurement["score"] == 75.0  # (1 + 0.5) / 2
    assert [item["nivel"] for item in measurement["items"]][:2] == ["CUMPLE", "PARCIAL"]
    sent = fake.prompts[0][2]
    assert "Qué se espera de la respuesta: Disponible de lunes a viernes" in sent
    assert "No pongas ningún número ni calificación" in fake.prompts[0][1].replace("\n", " ")
