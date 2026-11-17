"""Referencias laborales y personales: las capturan RH y la analista de
estudios, la IA las ordena y las contrasta con el CV, y entran a la síntesis.
Datos inventados."""

# ruff: noqa: F401, F811  (las fixtures se importan de otro módulo de pruebas)
from __future__ import annotations

from app.modules.ai_settings.domain.models import ProviderCode
from app.modules.assessments.domain import assistant
from app.tests.test_analista_estudios import analyst
from app.tests.test_api_assessments import ana, create, listing, update
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

LABORAL = {
    "type": "LABORAL",
    "name": "Jefa Ficticia Uno",
    "relation": "Comercial Ficticia SA",
    "position": "Gerente de nómina",
    "phone": "55 0000 0001",
    "period": "2021 a 2024",
    "contacted_by": "Analista de Estudios Ficticia",
    "contacted_on": "2026-11-14",
    "result": "CONTACTADA",
    "comments": "Confirma el puesto de analista de nómina de 2021 a 2023. Salió por renuncia.",
}
PERSONAL = {
    "type": "PERSONAL",
    "name": "Vecino Ficticio Dos",
    "relation": "Vecino desde hace diez años",
    "phone": "55 0000 0002",
    "result": "NO_LOCALIZADA",
}


def test_reglas_de_captura_de_las_referencias(ana, recruiter):
    created = create(recruiter, ana, "REFERENCIAS", data={})
    assert created.status_code == 201, created.text
    item = created.json()
    assert item["status"] == "PENDIENTE" and item["data"] == {"references": [], "notes": ""}
    assert item["statuses"] == ["PENDIENTE", "EN_PROCESO", "COMPLETADO", "NO_APLICA", "ANULADO"]

    def rejected(status="EN_PROCESO", **row):
        answer = update(recruiter, item, status=status, data={"references": [{**LABORAL, **row}]})
        assert answer.status_code == 422, answer.text
        return answer.json()["detail"]

    assert "escribe el nombre" in rejected(name=" ")
    assert "laboral o personal" in rejected(type="FAMILIAR")
    assert "resultado del contacto" in rejected(result="BIEN")
    assert "fecha de contacto" in rejected(contacted_on="14/11/2026")
    assert "anota lo que dijo" in rejected(comments="")
    # No se completan con una referencia todavía sin contactar, ni vacías.
    assert "cada referencia debe quedar" in rejected(status="COMPLETADO", result="PENDIENTE")
    empty = update(recruiter, item, status="COMPLETADO", data={"references": []})
    assert empty.status_code == 422 and "al menos una referencia" in empty.json()["detail"]
    too_many = update(recruiter, item, data={"references": [LABORAL] * 13})
    assert too_many.status_code == 422 and "como máximo 12" in too_many.json()["detail"]

    saved = update(
        recruiter,
        item,
        status="COMPLETADO",
        data={"references": [LABORAL, {}, PERSONAL], "notes": "  Se llamó   dos veces. "},
    )
    assert saved.status_code == 200, saved.text
    data = saved.json()["data"]
    # La fila vacía se descarta y lo que falta queda en blanco, no inventado.
    assert [row["name"] for row in data["references"]] == [
        "Jefa Ficticia Uno",
        "Vecino Ficticio Dos",
    ]
    assert data["references"][1]["comments"] == "" and data["references"][1]["position"] == ""
    assert saved.json()["score"] is None  # Las referencias no se califican.


def test_la_ia_ordena_las_referencias_y_las_contrasta_con_el_cv(ana, recruiter, admin, providers):
    item = create(recruiter, ana, "REFERENCIAS", data={"references": [PERSONAL]}).json()
    base = f"{API}/assessments/{item['id']}/summary"
    # Sin nada que alguien haya dicho, no hay qué analizar.
    early = recruiter.post(base)
    assert early.status_code == 422 and "lo que dijo al menos una" in early.json()["detail"]

    item = update(
        recruiter, item, status="EN_PROCESO", data={"references": [LABORAL, PERSONAL]}
    ).json()
    assign(admin, "ANALISIS_LLAMADAS")
    fake = providers[ProviderCode.ANTHROPIC]
    fake.prompts = []
    fake.script = [
        reply(
            {
                "resumen": "Una referencia laboral contactada y una personal sin localizar.",
                "referencias_laborales": [
                    "Jefa Ficticia Uno indicó que fue analista de nómina de 2021 a 2023."
                ],
                "referencias_personales": [],
                "coincidencias_con_cv": ["Empresa y puesto coinciden con el CV."],
                "discrepancias_verificables": [
                    "El CV indica hasta 2024; la referencia indicó hasta 2023."
                ],
                "sin_confirmar": ["Vecino Ficticio Dos no fue localizado."],
                "preguntas_para_la_siguiente_etapa": [
                    "¿En qué mes de 2023 o 2024 dejaste ese empleo?"
                ],
                # Nada de esto se conserva.
                "recomendacion": "Contratar",
                "confiabilidad": "alta",
            }
        )
    ]
    analyzed = recruiter.post(base)
    assert analyzed.status_code == 200, analyzed.text
    summary = analyzed.json()["ai_summary"]
    assert set(summary) == {
        "resumen",
        "referencias_laborales",
        "referencias_personales",
        "coincidencias_con_cv",
        "discrepancias_verificables",
        "sin_confirmar",
        "preguntas_para_la_siguiente_etapa",
    }
    assert summary["preguntas_para_la_siguiente_etapa"] == [
        "¿En qué mes de 2023 o 2024 dejaste ese empleo?"
    ]
    assert summary["discrepancias_verificables"] == [
        "El CV indica hasta 2024; la referencia indicó hasta 2023."
    ]
    # Lo que se envía: las referencias sin nombre ni teléfono, y los empleos del CV.
    _, system, user = fake.prompts[0][:3]
    assert system == assistant.REFERENCES_SYSTEM
    assert "no la recomiendes ni la descartes" in system.replace("\n", " ")
    assert "Referencia 1 (laboral): Comercial Ficticia SA, Gerente de nómina, 2021 a 2024" in user
    assert "Confirma el puesto" in user and "no se localizó" in user
    assert "Jefa Ficticia Uno" not in user and "Vecino Ficticio Dos" not in user
    assert "55 0000" not in user
    [event] = audit(admin, "evaluacion.resumida")
    assert event["result"] == "PERMITIDO" and event["details"]["tipo"] == "REFERENCIAS"


def test_la_analista_trabaja_las_referencias_y_nada_mas(
    ana, analyst, recruiter, admin, other, providers
):
    assert listing(analyst, ana)["writable"] == ["ESTUDIO_SOCIOECONOMICO", "REFERENCIAS"]
    created = create(analyst, ana, "REFERENCIAS", data={"references": [LABORAL]})
    assert created.status_code == 201, created.text
    item = created.json()
    assign(admin, "ANALISIS_LLAMADAS")
    providers[ProviderCode.ANTHROPIC].script = [
        reply({"resumen": "Una referencia laboral contactada.", "referencias_laborales": ["x"]})
    ]
    analyzed = analyst.post(f"{API}/assessments/{item['id']}/summary")
    assert analyzed.status_code == 200, analyzed.text
    row = next(i for i in analyst.get(f"{API}/study-queue").json() if i["application_id"] == ana)
    assert row["references_status"] == "PENDIENTE" and row["study_status"] is None
    # La reclutadora ve y continúa lo que capturó la analista.
    seen = [i for i in listing(recruiter, ana)["items"] if i["kind"] == "REFERENCIAS"]
    assert [i["id"] for i in seen] == [item["id"]]
    assert update(recruiter, analyzed.json(), status="EN_PROCESO").status_code == 200

    # Sigue sin entrar a entrevistas ni a pruebas técnicas, ni siquiera a resumirlas.
    assert create(analyst, ana, "ENTREVISTA", data={"interviewer": "X"}).status_code == 403
    interview = create(recruiter, ana, "ENTREVISTA", data={"interviewer": "Gerente Ficticio"})
    blocked = analyst.post(f"{API}/assessments/{interview.json()['id']}/summary")
    assert blocked.status_code == 403, blocked.text
    assert analyst.get(f"{API}/assessments/{interview.json()['id']}").status_code == 403
    # Quien no tiene la vacante compartida tampoco ve las referencias.
    stranger, _ = other
    assert stranger.get(f"{API}/assessments/{item['id']}").status_code in (403, 404)


def test_las_referencias_contactadas_entran_a_la_sintesis(ana, recruiter, admin, providers):
    item = create(recruiter, ana, "REFERENCIAS", data={}).json()
    update(recruiter, item, status="COMPLETADO", data={"references": [LABORAL, PERSONAL]})
    assign(admin, "SINTESIS_EXPEDIENTES")
    fake = providers[ProviderCode.ANTHROPIC]
    fake.prompts = []
    fake.script = [reply({"declaraciones": ["Una referencia laboral indicó que renunció."]})]
    made = recruiter.post(f"{API}/applications/{ana}/syntheses")
    assert made.status_code in (200, 201), made.text
    assert "1 referencias" in made.json()["sources"]
    user = fake.prompts[0][2]
    assert "REFERENCIAS (lo que dijeron terceros; no son hechos comprobados)" in user
    assert "Confirma el puesto de analista de nómina" in user
    # La que no se localizó no aporta nada dicho; nombres y teléfonos no viajan.
    assert "Vecino desde hace diez años" not in user
    assert "Jefa Ficticia Uno" not in user and "55 0000" not in user
