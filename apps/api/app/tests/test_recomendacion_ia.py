"""Puntos de atención, lectura de las escalas psicométricas, recomendación de la IA,
análisis de cierre y vista previa del prompt de CV. Datos inventados.

Decisiones del titular del 18 de noviembre de 2026: la IA señala lo desfavorable y
emite un veredicto en palabras, marcado como generado por IA; las escalas de la prueba
psicométrica y las fotografías del estudio (solo por el orden) cuentan; una persona
sigue decidiendo.
"""

# ruff: noqa: F401, F811  (las fixtures se importan de otro módulo de pruebas)
from __future__ import annotations

import json

from app.modules.ai_settings.domain.models import ProviderCode
from app.modules.assessments.domain import assistant
from app.tests.support.sample_files import pdf_cv
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
from app.tests.test_api_recruitment import assign, by_name, evaluated, reply

SCALES = [
    # Conducta indeseable en rango bajo: favorable.
    {
        "nombre": "Robo",
        "nivel": 2,
        "maximo": 5,
        "frase": "Tendencia baja a presentar la conducta",
        "lectura": "FAVORABLE",
    },
    # Rango medio: pide atención.
    {
        "nombre": "Soborno",
        "nivel": 3,
        "maximo": 5,
        "frase": "Tendencia media a presentar la conducta",
        "lectura": "INTERMEDIO",
    },
    # Conducta deseable en rango bajo: desfavorable.
    {
        "nombre": "Lealtad",
        "nivel": 1,
        "maximo": 5,
        "frase": "Tendencia baja a presentar la conducta",
        "lectura": "desfavorable",
    },
    # La gráfica y la frase no coinciden: no se da por buena.
    {
        "nombre": "Fraude",
        "nivel": 4,
        "maximo": 5,
        "frase": "Tendencia baja a presentar la conducta",
        "lectura": "DESFAVORABLE",
    },
    # Sin número leído: se conserva la frase.
    {
        "nombre": "Honestidad",
        "nivel": None,
        "maximo": 5,
        "frase": "Tendencia media a presentar la conducta",
        "lectura": "INTERMEDIO",
    },
    # Entradas inservibles: se descartan.
    {"nombre": "", "nivel": 3, "maximo": 5},
    "texto suelto",
    {"nombre": "Violencia", "nivel": 9, "maximo": 5, "frase": "", "lectura": "INVENTADA"},
]


def test_las_escalas_se_comprueban_contra_su_frase_y_de_ahi_salen_los_puntos_de_atencion():
    scales, attention, review = assistant.scales_from_answer(SCALES)
    assert scales == [
        "Robo: 2 de 5 · «Tendencia baja a presentar la conducta» · lectura favorable",
        "Soborno: 3 de 5 · «Tendencia media a presentar la conducta» · lectura intermedia",
        "Lealtad: 1 de 5 · «Tendencia baja a presentar la conducta» · lectura desfavorable",
        "Fraude: 4 de 5 · «Tendencia baja a presentar la conducta» · lectura desfavorable",
        "Honestidad: nivel no leído de la gráfica · «Tendencia media a presentar la conducta» "
        "· lectura intermedia",
        # Un nivel fuera de su escala no se usa, ni una lectura que no sea de las cuatro.
        "Violencia: nivel no leído de la gráfica · lectura sin determinar",
    ]
    assert attention == [
        "Soborno: el reporte la ubica en 3 de 5 · «Tendencia media a presentar la conducta» "
        "(lectura intermedia).",
        "Lealtad: el reporte la ubica en 1 de 5 · «Tendencia baja a presentar la conducta» "
        "(lectura desfavorable).",
        "Honestidad: el reporte la ubica en «Tendencia media a presentar la conducta» "
        "(lectura intermedia).",
    ]
    # La escala cuyo número no coincide con su frase no es punto de atención: se revisa.
    assert review == [
        "Fraude: la gráfica se leyó como 4 de 5, pero el texto dice «Tendencia baja a "
        "presentar la conducta». Revisa el reporte antes de usar este resultado."
    ]
    assert assistant.scales_from_answer(None) == ([], [], [])
    assert assistant.scales_from_answer({"nombre": "x"}) == ([], [], [])


def _psychometric(recruiter, vacancy_id, ana, **data) -> dict:
    report = upload(
        recruiter,
        vacancy_id,
        "reporte.pdf",
        pdf_cv("Reporte ficticio de honestidad.", "Soborno: tendencia media."),
        document_type="PSICOMETRIA",
    )
    test = create(recruiter, ana, "PSICOMETRIA", data={"instrument": "Prueba H", **data}).json()
    presented = update(
        recruiter,
        test,
        status="PRESENTADA",
        file_id=report["id"],
        event_date="2026-11-09T16:00:00Z",
    )
    assert presented.status_code == 200, presented.text
    return presented.json()


def test_el_resumen_psicometrico_envia_las_paginas_como_imagen_y_marca_los_puntos_de_atencion(
    ana, recruiter, admin, vacancy_id, providers
):
    test = _psychometric(recruiter, vacancy_id, ana)
    assign(admin, "RESUMEN_PRUEBAS")
    fake = providers[ProviderCode.ANTHROPIC]
    fake.prompts, fake.images = [], []
    fake.script = [
        reply(
            {
                "resumen": "El reporte documenta cinco escalas.",
                "escalas": SCALES,
                "puntos_de_atencion": ["El reporte advierte respuestas demasiado favorables."],
                # Nada de esto se conserva.
                "diagnostico": "Consumo de sustancias",
                "apto": False,
            }
        )
    ]
    summarized = recruiter.post(f"{API}/assessments/{test['id']}/summary")
    assert summarized.status_code == 200, summarized.text
    summary = summarized.json()["ai_summary"]
    assert "diagnostico" not in summary and "apto" not in summary
    assert len(summary["escalas"]) == 6 and summary["escalas"][1].startswith("Soborno: 3 de 5")
    # Primero las escalas que piden atención; después, los avisos propios del reporte.
    assert [line.split(":")[0] for line in summary["puntos_de_atencion"]] == [
        "Soborno",
        "Lealtad",
        "Honestidad",
        "El reporte advierte respuestas demasiado favorables.",
    ]
    assert summary["revisar_en_el_reporte"][0].startswith("Fraude: la gráfica se leyó como 4 de 5")

    # La página del reporte viajó como imagen JPEG junto con su texto.
    [page] = fake.images
    assert page.media_type == "image/jpeg" and page.data[:3] == b"\xff\xd8\xff"
    _, system, user = fake.prompts[0]
    assert "Se adjuntan 1 imágenes con las páginas del documento" in user
    assert "Soborno: tendencia media." in user
    rules = " ".join(system.split())
    assert "Léelo de la imagen de la página" in rules and "no lo adivines" in rules
    assert "en una conducta indeseable (robo, acoso, uso de sustancias)" in rules


SYNTHESIS = {
    "hechos_documentados": ["Tres años en nómina (CV)"],
    "puntos_de_atencion": [
        "Prueba psicométrica: el reporte ubica Soborno en 3 de 5 (prueba psicométrica)"
    ],
    "contrastes": [
        "Organización: dijo ser muy organizada (llamada 1); el reporte la ubica en 3 de 5 "
        "(prueba psicométrica). Conclusión: lo declarado se sostiene solo en parte."
    ],
    "veredicto": "RECOMENDABLE_CON_RESERVAS",
    "razones": ["Cumple la experiencia (CV)", "Soborno en rango medio (prueba psicométrica)"],
    "conclusion": "Cumple lo indispensable; conviene aclarar un punto.",
    # Nada de esto se conserva.
    "puntuacion_global": 71,
    "decision": "Contratar",
}


def test_la_sintesis_da_un_veredicto_con_razones_y_usa_las_escalas_leidas(
    ana, recruiter, admin, vacancy_id, providers
):
    test = _psychometric(recruiter, vacancy_id, ana)
    assign(admin, "RESUMEN_PRUEBAS", "SINTESIS_EXPEDIENTES")
    fake = providers[ProviderCode.ANTHROPIC]
    fake.script = [reply({"resumen": "Cinco escalas.", "escalas": SCALES})]
    assert recruiter.post(f"{API}/assessments/{test['id']}/summary").status_code == 200

    fake.prompts = []
    fake.script = [reply(SYNTHESIS)]
    url = f"{API}/applications/{ana}/syntheses"
    made = recruiter.post(url)
    assert made.status_code == 201, made.text
    result = made.json()["result"]
    assert result["veredicto"] == "RECOMENDABLE_CON_RESERVAS"
    assert result["razones"] == SYNTHESIS["razones"] and result["contrastes"]
    assert result["conclusion"].startswith("Cumple lo indispensable")
    assert "puntuacion_global" not in result and "decision" not in result

    # A la IA le llegan las escalas leídas del reporte y lo que pide atención; la escala
    # que no coincide con su frase va marcada para que no la use.
    sent = fake.prompts[0][2]
    assert "- Escala leída del reporte: Soborno: 3 de 5" in sent
    assert "- Punto de atención del reporte: Lealtad: el reporte la ubica en 1 de 5" in sent
    assert "- Escala para revisar en el reporte (no la uses): Fraude" in sent
    # Y cada criterio del CV con su nivel, por su título y sin su código, para que la IA
    # lo cite por su nombre.
    names = recruiter.get(f"{API}/applications/{ana}").json()["evaluation"]["criteria_names"]
    assert len(names) == 3
    for name in names.values():
        assert f"- Criterio «{name}»: nivel 4." in sent
    criteria_lines = [line for line in sent.splitlines() if line.startswith("- Criterio ")]
    assert len(criteria_lines) == 3 and not any("C1" in line for line in criteria_lines)
    rules = " ".join(fake.prompts[0][1].split())
    assert "No uses códigos como C1 o C2: quien lee no los conoce." in rules

    # Emitir el veredicto no mueve a la persona ni cierra su postulación.
    detail = recruiter.get(f"{API}/applications/{ana}").json()
    assert detail["application"]["status"] == "ACTIVA" and len(detail["movements"]) == 2


def test_no_viable_lo_decide_una_persona_y_la_ia_redacta_el_analisis_de_cierre(
    ana, recruiter, admin, vacancy_id, providers
):
    assign(admin, "SINTESIS_EXPEDIENTES")
    fake = providers[ProviderCode.ANTHROPIC]
    url = f"{API}/applications/{ana}/syntheses"

    # Mientras la postulación siga activa no hay nada que cerrar.
    early = recruiter.post(url, json={"closing": True})
    assert early.status_code == 422 and "ya se cerró" in early.json()["detail"]

    closed = recruiter.post(
        f"{API}/applications/{ana}/outcome",
        json={"outcome": "NO_CONTRATADO", "reason": "No viable: no acepta el horario"},
    )
    assert closed.status_code == 200, closed.text

    fake.prompts = []
    fake.script = [
        reply(
            {
                "analisis_de_cierre": "Llegó a la revisión de RH.\n\nEl expediente no documenta "
                "este motivo.",
                "avance_por_etapa": ["CV: tres años en nómina."],
                "puntos_de_atencion": ["CV: sin evidencia de finiquitos (CV)"],
                "informacion_pendiente": ["No se realizó la llamada."],
                # Nada de esto se conserva: la decisión ya la tomó una persona.
                "veredicto": "RECOMENDABLE",
                "reabrir": True,
            }
        ),
        reply({"avance_por_etapa": ["CV: algo"]}),
    ]
    made = recruiter.post(url, json={"closing": True})
    assert made.status_code == 201, made.text
    result = made.json()["result"]
    assert set(result) == {
        "tipo",
        "etapa",
        "resultado",
        "motivo",
        "analisis_de_cierre",
        "avance_por_etapa",
        "puntos_de_atencion",
        "informacion_pendiente",
    }
    # La etapa, el resultado y el motivo los pone el sistema con lo que registró la persona.
    assert result["tipo"] == "CIERRE" and result["etapa"] == "Revisión local RH"
    assert result["resultado"] == "No contratado"
    assert result["motivo"] == "No viable: no acepta el horario"
    assert result["analisis_de_cierre"].count("\n\n") == 1

    _, system, sent = fake.prompts[0]
    assert system == assistant.CLOSING_SYSTEM
    rules = " ".join(system.split())
    assert "La decisión ya la tomó esa persona: tú la documentas" in rules
    assert "CIERRE REGISTRADO POR RECURSOS HUMANOS" in sent
    assert "- Etapa en la que se quedó: Revisión local RH" in sent
    assert "- Motivo escrito por quien decidió: No viable: no acepta el horario" in sent
    # Un cierre sin análisis no sirve y no se guarda.
    assert recruiter.post(url, json={"closing": True}).status_code == 503
    view = recruiter.get(url).json()
    assert view["total"] == 1 and view["latest"]["result"]["tipo"] == "CIERRE"

    # La postulación sigue cerrada por la persona; la IA no la tocó.
    detail = recruiter.get(f"{API}/applications/{ana}").json()
    assert detail["application"]["status"] != "ACTIVA"
    kinds = [e["details"]["tipo"] for e in audit(admin, "expediente.sintetizado")]
    assert set(kinds) == {"CIERRE"}


def test_la_pestana_de_cv_muestra_el_prompt_completo_con_el_que_se_evalua(
    recruiter, vacancy_id, prompt, model
):
    overview = recruiter.get(f"{API}/vacancies/{vacancy_id}/cv-batches").json()
    approved = overview["approved_prompt"]
    # Las instrucciones son las mismas que usa un lote: llevan la rúbrica y sus niveles.
    assert "C1" in approved["instructions"] and len(approved["instructions"]) > 400
    # Y el mensaje que acompaña a cada CV, con el lugar del currículum indicado.
    assert approved["cv_message"].startswith("Evalúa el siguiente CV con la rúbrica.")
    assert (
        "[Aquí va el texto de cada CV, con correos y teléfonos ocultos]" in approved["cv_message"]
    )
    assert "Los datos de contacto se ocultaron." in approved["cv_message"]
