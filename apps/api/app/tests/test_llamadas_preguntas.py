"""Cada llamada tiene su propia lista de preguntas: empieza con las generales de
la empresa y, en esa llamada, se quitan, se redactan distinto, se suman las de
otros bancos o se escriben nuevas, sin tocar los bancos."""

# ruff: noqa: F401, F811  (las fixtures se importan de otro módulo de pruebas)
from __future__ import annotations

import json
import uuid

import sqlalchemy as sa

from app.modules.ai_settings.domain.models import ProviderCode
from app.modules.phone_calls.infrastructure.orm import (
    CallSessionBankRow,
    CallSessionRow,
    QuestionBankVersionRow,
)
from app.tests.test_api_assessments import ana
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
from app.tests.test_api_recruitment import ANALYSIS, assign, by_name, evaluated, new_bank, reply

GENERAL = [
    {"text": "¿Por qué te interesa la vacante?", "guidance": "Motivos ligados al puesto"},
    {"text": "¿Cuál es tu expectativa de sueldo?", "guidance": "Una cifra o un rango"},
]
EXTRA = [
    {"text": "¿Has usado CONTPAQi Nóminas?", "guidance": "Sí o no, y cuánto tiempo"},
    {"text": "¿Has timbrado recibos?", "guidance": ""},
]


def _item(question: dict, **changes) -> dict:
    """Una pregunta de la llamada tal como la envía la pantalla al guardar."""
    return {"id": question["id"], "text": question["text"], "omitted": False, **changes}


def _texts(call: dict, *, omitted: bool = False) -> list[str]:
    return [q["text"] for q in call["questions"] if q["omitted"] is omitted]


def _general(admin) -> dict:
    created = admin.post(
        f"{API}/question-banks",
        json={"name": "Preguntas generales", "general": True, "questions": GENERAL},
    )
    assert created.status_code == 201, created.text
    return created.json()


def test_la_llamada_empieza_con_las_generales_y_suma_los_bancos_elegidos(ana, recruiter, admin):
    calls_url = f"{API}/applications/{ana}/calls"
    # Sin preguntas generales y sin elegir banco, la llamada se abre vacía:
    # las preguntas se escriben ahí mismo.
    empty = recruiter.post(calls_url, json={})
    assert empty.status_code == 201, empty.text
    assert empty.json()["questions"] == [] and empty.json()["sources"] == []

    _general(admin)
    payroll = new_bank(recruiter)
    extra = new_bank(recruiter, name="Banco de sistemas", questions=EXTRA)

    # Solo con las generales: aparecen solas, sin elegir nada.
    alone = recruiter.post(calls_url, json={"bank_ids": []}).json()
    assert _texts(alone) == [q["text"] for q in GENERAL]
    assert {q["source"] for q in alone["questions"]} == {"GENERAL"}
    assert alone["sources"] == ["Preguntas generales"]

    # Con dos bancos: primero las generales y después cada banco, en el orden elegido.
    both = recruiter.post(calls_url, json={"bank_ids": [extra["id"], payroll["id"]]}).json()
    assert [(q["source"], q["bank_name"]) for q in both["questions"]] == [
        ("GENERAL", "Preguntas generales"),
        ("GENERAL", "Preguntas generales"),
        ("BANCO", "Banco de sistemas"),
        ("BANCO", "Banco de sistemas"),
        ("BANCO", "Banco de nómina"),
        ("BANCO", "Banco de nómina"),
    ]
    assert both["sources"] == ["Preguntas generales", "Banco de sistemas", "Banco de nómina"]
    assert all(q["omitted"] is False and q["original_text"] is None for q in both["questions"])
    # Elegir dos veces el mismo banco, o el general, no repite preguntas.
    again = recruiter.post(calls_url, json={"bank_ids": [payroll["id"], payroll["id"]]}).json()
    assert len(again["questions"]) == 4


def test_en_la_llamada_se_quitan_se_redactan_y_se_agregan_preguntas_sin_tocar_los_bancos(
    ana, recruiter, admin, other, vacancy_id
):
    general = _general(admin)
    payroll = new_bank(recruiter)
    extra = new_bank(recruiter, name="Banco de sistemas", questions=EXTRA)
    call = recruiter.post(
        f"{API}/applications/{ana}/calls", json={"bank_ids": [payroll["id"]]}
    ).json()
    url = f"{API}/calls/{call['id']}"
    interest, salary, first, second = call["questions"]
    written = str(uuid.uuid4())
    taken = extra["questions"][0]

    body = {
        "answers": [
            {"question_id": interest["id"], "answer": "Le interesa el área"},
            # Lo anotado en una pregunta quitada se conserva mientras es borrador.
            {"question_id": salary["id"], "answer": "Entre 16 y 18 mil"},
            {"question_id": written, "answer": "Sí, de lunes a viernes"},
        ],
        "notes": "",
        "questions": [
            _item(interest),
            _item(salary, omitted=True),
            _item(first, text="  ¿Qué nóminas has calculado   y con qué sistema?  "),
            _item(second),
            # Una pregunta tomada de otro banco y otra escrita solo para esta llamada.
            {"id": taken["id"], "text": taken["text"], "bank_id": extra["id"]},
            {"id": written, "text": "¿Puedes trabajar en sitio?", "guidance": "Sí o no"},
        ],
    }
    saved = recruiter.put(url, json=body)
    assert saved.status_code == 200, saved.text
    result = saved.json()
    assert _texts(result) == [
        "¿Por qué te interesa la vacante?",
        "¿Qué nóminas has calculado y con qué sistema?",
        second["text"],
        "¿Has usado CONTPAQi Nóminas?",
        "¿Puedes trabajar en sitio?",
    ]
    assert _texts(result, omitted=True) == ["¿Cuál es tu expectativa de sueldo?"]
    by_id = {q["id"]: q for q in result["questions"]}
    assert by_id[first["id"]]["original_text"] == first["text"]
    assert by_id[first["id"]]["guidance"] == first["guidance"]  # lo demás no cambia
    assert by_id[taken["id"]]["source"] == "BANCO"
    assert by_id[taken["id"]]["bank_name"] == "Banco de sistemas"
    assert by_id[taken["id"]]["guidance"] == "Sí o no, y cuánto tiempo"
    assert by_id[written]["source"] == "LLAMADA" and by_id[written]["bank_id"] is None
    assert by_id[written]["guidance"] == "Sí o no"
    assert by_id[written]["answer"] == "Sí, de lunes a viernes"
    assert by_id[salary["id"]]["answer"] == "Entre 16 y 18 mil"
    assert result["sources"] == [
        "Preguntas generales",
        "Banco de nómina",
        "Banco de sistemas",
        "Preguntas escritas para esta llamada",
    ]

    # Los bancos no cambian: ni su redacción ni su versión.
    for bank in (general, payroll, extra):
        detail = recruiter.get(f"{API}/question-banks/{bank['id']}").json()["bank"]
        assert detail["version_number"] == bank["version_number"]
        assert [q["text"] for q in detail["questions"]] == [q["text"] for q in bank["questions"]]

    # Volver a la redacción del banco quita la marca; lo que no se menciona se conserva.
    stored = result["questions"]
    back = recruiter.put(
        url,
        json={
            "answers": body["answers"],
            "notes": "",
            "questions": [
                _item(by_id[first["id"]], text=first["text"]),
                _item(by_id[salary["id"]]),  # se vuelve a incluir, con lo que tenía anotado
            ],
        },
    ).json()
    restored = {q["id"]: q for q in back["questions"]}
    assert restored[first["id"]]["original_text"] is None
    assert restored[salary["id"]]["omitted"] is False
    assert restored[salary["id"]]["answer"] == "Entre 16 y 18 mil"
    assert len(back["questions"]) == len(stored)
    # Sin enviar la lista, las preguntas no cambian.
    same = recruiter.put(url, json={"answers": body["answers"], "notes": ""}).json()
    assert [q["id"] for q in same["questions"]] == [q["id"] for q in back["questions"]]

    # Lo que no se acepta.
    def refused(questions: list[dict]) -> tuple[int, str]:
        response = recruiter.put(url, json={"answers": [], "notes": "", "questions": questions})
        return response.status_code, response.json()["detail"]

    assert refused([_item(first, text="   ")]) == (422, "Hay preguntas sin texto.")
    assert refused([_item(first), _item(first)])[1] == "Hay preguntas repetidas en la llamada."
    missing = {"id": str(uuid.uuid4()), "text": "No existe", "bank_id": extra["id"]}
    assert "ya no está en el banco «Banco de sistemas»" in refused([missing])[1]
    recruiter.post(f"{API}/question-banks/{extra['id']}/archive")
    other_question = extra["questions"][1]
    archived = {"id": other_question["id"], "text": other_question["text"], "bank_id": extra["id"]}
    assert refused([archived]) == (409, "El banco «Banco de sistemas» está archivado; elige otro.")
    recruiter.post(f"{API}/question-banks/{extra['id']}/restore")
    many = [{"id": str(uuid.uuid4()), "text": f"Pregunta {n}"} for n in range(81)]
    assert recruiter.put(url, json={"answers": [], "questions": many}).status_code == 422
    assert "como máximo 80" in refused(many[:76])[1]
    # Un banco privado de otra persona no se puede usar, ni siquiera por identificador.
    stranger, stranger_id = other
    private = new_bank(stranger, name="Banco ajeno")
    foreign = private["questions"][0]
    assert (
        refused([{"id": foreign["id"], "text": foreign["text"], "bank_id": private["id"]}])[0]
        == 404
    )
    assert len(recruiter.get(url).json()["questions"]) == len(stored)


def test_al_cerrar_y_al_analizar_solo_cuentan_las_preguntas_que_se_hicieron(
    ana, recruiter, admin, providers
):
    _general(admin)
    payroll = new_bank(recruiter)
    call = recruiter.post(
        f"{API}/applications/{ana}/calls", json={"bank_ids": [payroll["id"]]}
    ).json()
    url = f"{API}/calls/{call['id']}"
    interest, salary, first, second = call["questions"]
    written = str(uuid.uuid4())
    questions = [
        _item(interest, omitted=True),
        _item(salary),
        _item(first, text="¿Qué nóminas has calculado y de qué tamaño?"),
        _item(second, omitted=True),
        {"id": written, "text": "¿Puedes trabajar en sitio?", "guidance": "Sí o no"},
    ]
    answers = [
        {"question_id": interest["id"], "answer": "Anotado antes de quitarla"},
        {"question_id": salary["id"], "answer": "Entre 16 y 18 mil"},
        {"question_id": first["id"], "answer": "Quincenal de 200 personas"},
    ]
    body = {"answers": answers, "notes": "", "questions": questions}
    assert recruiter.put(url, json=body).status_code == 200

    # Para cerrar solo se exigen las que siguen en la llamada, con su número actual.
    unfinished = recruiter.put(url, json={**body, "close": True})
    assert unfinished.status_code == 422 and unfinished.json()["detail"].endswith("Faltan: 3.")
    nothing = [_item(q, omitted=True) for q in (interest, salary, first, second)]
    emptied = recruiter.put(url, json={"answers": [], "notes": "", "questions": nothing[:4]})
    assert emptied.status_code == 200
    assert (
        "al menos una pregunta"
        in recruiter.put(
            url,
            json={
                "answers": [],
                "questions": [*nothing, {"id": written, "text": "x", "omitted": True}],
                "close": True,
            },
        ).json()["detail"]
    )
    answers.append({"question_id": written, "answer": "Sí"})
    body = {"answers": answers, "notes": "", "questions": questions}
    assert recruiter.put(url, json=body).status_code == 200

    # A la IA le llegan solo las preguntas hechas, con la redacción de la llamada.
    assign(admin, "ANALISIS_LLAMADAS")
    fake = providers[ProviderCode.ANTHROPIC]
    fake.prompts = []
    coverage = [
        {"pregunta": 1, "nivel": "CUMPLE", "evidencia": "Entre 16 y 18 mil"},
        {"pregunta": 3, "nivel": "PARCIAL", "evidencia": "Sí"},
    ]
    fake.script = [reply({**ANALYSIS, "cobertura": coverage})] * 2
    analyzed = recruiter.post(f"{url}/analysis")
    assert analyzed.status_code == 200, analyzed.text
    _, _, user = fake.prompts[0]
    assert "Pregunta 1: ¿Cuál es tu expectativa de sueldo?" in user
    assert "Pregunta 2: ¿Qué nóminas has calculado y de qué tamaño?" in user
    assert "Pregunta 3: ¿Puedes trabajar en sitio?" in user and "Pregunta 4" not in user
    assert "¿Por qué te interesa la vacante?" not in user
    assert "Anotado antes de quitarla" not in user and second["text"] not in user
    measured = analyzed.json()["analysis"]["medicion"]
    # Se miden las respondidas que tienen definido qué se espera, con su número actual.
    assert [(item["numero"], item["question_id"], item["nivel"]) for item in measured["items"]] == [
        (1, salary["id"], "CUMPLE"),
        (2, first["id"], "SIN_VALORAR"),
        (3, written, "PARCIAL"),
    ]

    # Cambiar solo respuestas conserva el análisis; cambiar las preguntas lo retira,
    # porque el análisis las numera.
    kept = recruiter.put(url, json={"answers": answers, "notes": "Nota", "questions": questions})
    assert kept.json()["analysis"] is not None
    questions[1] = _item(salary, text="¿Cuál es tu expectativa de sueldo mensual?")
    changed = recruiter.put(url, json={"answers": answers, "notes": "", "questions": questions})
    assert changed.status_code == 200 and changed.json()["analysis"] is None
    assert recruiter.post(f"{url}/analysis").status_code == 200

    # Al cerrar queda solo lo de las preguntas hechas; las quitadas se ven como tales.
    closed = recruiter.put(url, json={"answers": answers, "notes": "", "close": True}).json()
    assert closed["status"] == "CERRADA" and closed["analysis"] is not None
    final = {q["id"]: q for q in closed["questions"]}
    assert final[interest["id"]]["omitted"] is True and final[interest["id"]]["answer"] == ""
    assert final[written]["answer"] == "Sí"
    assert recruiter.put(url, json=body).status_code == 409

    # Al expediente (y a su síntesis) llega lo respondido en las preguntas hechas,
    # también en las generales y en las escritas, con la redacción de la llamada.
    from app.composition.assessments import AssessmentApplications

    with recruiter.app.state.context.require_backend().transaction() as repos:
        source = AssessmentApplications(
            repos.recruitment, repos.cv_batches, repos.phone_calls, repos.evaluation_setup
        )
        [material] = source.material(uuid.UUID(ana)).calls
    assert [row["pregunta"] for row in material["preguntas"]] == [
        "¿Cuál es tu expectativa de sueldo mensual?",
        "¿Qué nóminas has calculado y de qué tamaño?",
        "¿Puedes trabajar en sitio?",
    ]

    last = audit(admin, "llamada.cerrada")[0]["details"]
    assert (last["preguntas"], last["quitadas"], last["escritas"]) == (3, 2, 1)
    assert last["redaccion_cambiada"] == 2
    assert any(e["details"]["analisis_retirado"] for e in audit(admin, "llamada.guardada"))


def test_una_llamada_anterior_conserva_sus_preguntas_y_los_reportes_la_encuentran(
    ana, recruiter, admin, vacancy_id
):
    general = _general(admin)
    payroll = new_bank(recruiter)
    extra = new_bank(recruiter, name="Banco de sistemas", questions=EXTRA)
    call = recruiter.post(
        f"{API}/applications/{ana}/calls", json={"bank_ids": [payroll["id"]]}
    ).json()
    url = f"{API}/calls/{call['id']}"
    call_id = uuid.UUID(call["id"])

    # Se deja la fila como la guardaba la versión anterior: sin lista propia.
    backend = recruiter.app.state.context.require_backend()
    with backend.transaction() as repos:
        row = repos.phone_calls._session.get(CallSessionRow, call_id)
        assert [item["source"] for item in json.loads(row.questions)].count("GENERAL") == 2
        row.questions = None
    old = recruiter.get(url).json()
    assert _texts(old) == [q["text"] for q in (*GENERAL, *payroll["questions"])]
    assert [q["source"] for q in old["questions"]] == ["GENERAL", "GENERAL", "BANCO", "BANCO"]
    assert old["questions"][2]["bank_name"] == "Banco de nómina"

    # Al guardarla, queda con su lista propia y admite los cambios nuevos.
    taken = extra["questions"][0]
    saved = recruiter.put(
        url,
        json={
            "answers": [],
            "notes": "",
            "questions": [
                _item(old["questions"][0], omitted=True),
                {"id": taken["id"], "text": taken["text"], "bank_id": extra["id"]},
            ],
        },
    )
    assert saved.status_code == 200, saved.text
    assert len(saved.json()["questions"]) == 5
    with backend.transaction() as repos:
        assert repos.phone_calls._session.get(CallSessionRow, call_id).questions is not None
        linked = set(
            repos.phone_calls._session.execute(
                sa.select(CallSessionBankRow.bank_id).where(CallSessionBankRow.call_id == call_id)
            ).scalars()
        )
    # Queda ligada a los bancos de los que tomó preguntas, no al general.
    assert linked == {uuid.UUID(payroll["id"]), uuid.UUID(extra["id"])}

    def names(bank: dict) -> list[str]:
        params = {"bank_id": bank["id"]}
        rows = recruiter.get(f"{API}/reports/applications", params=params).json()["rows"]
        return [row["candidate"] for row in rows]

    assert names(payroll) == names(extra) == ["Ana Pérez Ficticia"]
    assert names(general) == []
    options = recruiter.get(f"{API}/reports/options").json()
    assert [item["name"] for item in options["banks"]] == ["Banco de nómina", "Banco de sistemas"]
