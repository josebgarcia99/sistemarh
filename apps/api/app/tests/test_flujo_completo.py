"""Flujo completo (sección 32.5 del documento maestro).

Un solo proceso sintético, de principio a fin y en el orden que marca el
documento: desde que la administradora crea usuarios hasta que la vacante se
transfiere a otra persona, comprobando al final que los documentos siguen
disponibles y que los permisos cambiaron.

Todas las personas y documentos son ficticios y la IA es un proveedor simulado.
"""

# ruff: noqa: F401, F811  (las fixtures se importan de otros módulos de pruebas)
from __future__ import annotations

import io
import zipfile

from openpyxl import load_workbook

from app.modules.ai_settings.domain.models import ProviderCode
from app.tests.conftest import VACANCY, login, share
from app.tests.support.sample_files import docx_cv
from app.tests.test_api_cv_batches import (
    API,
    admin,
    answer,
    app,
    audit,
    providers,
    start,
    upload,
)
from app.tests.test_api_evaluation_ai import ANSWER as PROFILE_ANSWER
from app.tests.test_api_evaluation_ai import SOURCE_TEXT
from app.tests.test_api_evaluation_setup import PROFILE, step
from app.tests.test_api_recruitment import (
    ANA,
    ANALYSIS,
    BETO,
    QUESTIONS,
    assign,
    board,
    by_name,
    move,
    person_cv,
    reply,
    stage_id,
)

PASSWORD = "Clave-Flujo-Completo-2026"
OPERATIONS = (
    "ANALISIS_PERFILES",
    "EVALUACION_DOCUMENTAL",
    "EXTRACCION_CV",
    "ANALISIS_LLAMADAS",
    "RESUMEN_PRUEBAS",
    "LECTURA_DOCUMENTOS",
)


def ok(response, status: int = 200) -> dict:
    assert response.status_code == status, response.text
    return response.json() if response.content else {}


def new_user(admin, app, email: str, name: str):
    created = ok(
        admin.post(
            f"{API}/users",
            json={"email": email, "full_name": name, "password": PASSWORD, "role": "RECLUTADOR"},
        ),
        201,
    )
    return login(app, email, PASSWORD), created["id"]


def download(client, file_id):
    return client.get(f"{API}/files/{file_id}/download")


def test_flujo_completo_de_principio_a_fin(app, admin, providers, storage):
    fake = providers[ProviderCode.ANTHROPIC]
    assign(admin, *OPERATIONS)

    # 1. La administradora crea usuarios.
    rosa, rosa_id = new_user(admin, app, "rosa@ejemplo.test", "Rosa Reclutadora Ficticia")
    luis, luis_id = new_user(admin, app, "luis@ejemplo.test", "Luis Reclutador Ficticio")
    nora, nora_id = new_user(admin, app, "nora@ejemplo.test", "Nora Reclutadora Ficticia")

    # 2. La reclutadora crea la vacante (una plaza) y la abre.
    vacancy = ok(rosa.post(f"{API}/vacancies", json={**VACANCY, "positions": 1}), 201)
    vacancy_id = vacancy["id"]
    ok(
        rosa.post(
            f"{API}/vacancies/{vacancy_id}/status",
            json={"status": "ABIERTA", "version": vacancy["version"]},
        )
    )
    assert luis.get(f"{API}/vacancies/{vacancy_id}").status_code == 404

    # 3. La comparte con otro usuario, en colaboración.
    ok(share(rosa, vacancy_id, luis_id, "COLABORACION"), 204)
    assert ok(luis.get(f"{API}/vacancies/{vacancy_id}"))["name"] == VACANCY["name"]
    assert nora.get(f"{API}/vacancies/{vacancy_id}").status_code == 404

    # 4. Carga el perfil: la IA lo propone desde un texto y la persona lo guarda.
    fake.script = [reply(PROFILE_ANSWER)]
    proposal = ok(
        rosa.post(f"{API}/vacancies/{vacancy_id}/profile-extractions", json={"text": SOURCE_TEXT})
    )
    assert proposal["objective"].startswith("Calcular y pagar")
    ok(
        rosa.post(
            f"{API}/vacancies/{vacancy_id}/profile-versions",
            json={**PROFILE, "expected_version": 0},
        ),
        201,
    )

    # 5. Genera, revisa y aprueba el prompt.
    draft = ok(rosa.post(f"{API}/vacancies/{vacancy_id}/prompts"), 201)
    prompt = ok(step(rosa, ok(step(rosa, draft, "submit")), "approve"))
    assert prompt["status"] == "APROBADO" and len(prompt["criteria"]) >= 2

    # 6. Carga los CV.
    cv_ana = upload(rosa, vacancy_id, "cv ana.pdf", person_cv("Ana", "ana@ejemplo.test"))
    cv_beto = upload(rosa, vacancy_id, "cv beto.pdf", person_cv("Beto", "beto@ejemplo.test"))

    # 7 y 8. La IA evalúa y se generan el Excel y los ZIP.
    fake.script = [answer(prompt, 4), reply(ANA), answer(prompt, 1), reply(BETO)]
    batch = ok(start(rosa, vacancy_id), 201)["batch"]
    assert batch["status"] == "COMPLETADO"
    report = load_workbook(io.BytesIO(download(rosa, batch["report_file_id"]).content))
    assert report.active.max_row == 3
    accepted = zipfile.ZipFile(io.BytesIO(download(rosa, batch["accepted_zip_file_id"]).content))
    rejected = zipfile.ZipFile(io.BytesIO(download(rosa, batch["rejected_zip_file_id"]).content))
    assert len(accepted.namelist()) == len(rejected.namelist()) == 2  # un CV y el manifiesto

    # 9. RH revisa: las dos personas están en revisión local con la clasificación de la IA.
    people = board(rosa, vacancy_id)
    ana, beto = (by_name(people)[name] for name in ("Ana Pérez Ficticia", "Beto López Ficticio"))
    assert (ana["ai_classification"], beto["ai_classification"]) == ("ACEPTADO_IA", "RECHAZADO_IA")
    assert ana["stage_id"] == beto["stage_id"] == stage_id(people, "Revisión local RH")

    # 10. Un rechazado por la IA avanza a llamada por decisión humana, con motivo.
    call_stage = stage_id(people, "Llamada telefónica")
    assert move(rosa, vacancy_id, [beto["id"]], call_stage).status_code == 422
    ok(move(rosa, vacancy_id, [beto["id"]], call_stage, "Tiene experiencia que el CV no refleja"))
    moved = ok(rosa.get(f"{API}/applications/{beto['id']}"))
    assert moved["application"]["stage_id"] == call_stage
    assert moved["application"]["ai_classification"] == "RECHAZADO_IA"  # no se reescribe
    assert moved["movements"][-1]["note"] == "Tiene experiencia que el CV no refleja"

    # 11. Se responden las preguntas de la llamada (lo hace el colaborador).
    bank = ok(
        luis.post(
            f"{API}/question-banks",
            json={"name": "Banco de nómina", "shared": False, "questions": QUESTIONS},
        ),
        201,
    )
    call = ok(
        luis.post(f"{API}/applications/{beto['id']}/calls", json={"bank_id": bank["id"]}), 201
    )
    q1, q2 = (question["id"] for question in call["questions"])
    answers = {
        "answers": [
            {"question_id": q1, "answer": "Nómina quincenal de 200 personas durante tres años."},
            {"question_id": q2, "not_asked": True},
        ],
        "notes": "Llamada de 15 minutos",
    }
    ok(luis.put(f"{API}/calls/{call['id']}", json=answers))

    # 12. Se registra el análisis de la IA y se cierra la llamada.
    fake.script = [reply(ANALYSIS)]
    analysis = ok(luis.post(f"{API}/calls/{call['id']}/analysis"))["analysis"]
    assert analysis["resumen"] and "recomendacion" not in analysis
    closed = ok(luis.put(f"{API}/calls/{call['id']}", json={**answers, "close": True}))
    assert closed["status"] == "CERRADA"

    # 13. Se carga la prueba psicométrica (documento sensible, cifrado) y se valida.
    psychometric_file = upload(
        rosa,
        vacancy_id,
        "reporte psicometrico.docx",
        docx_cv("Reporte ficticio de la Prueba X.", "Escala de razonamiento: percentil 70."),
        document_type="PSICOMETRIA",
    )
    assert psychometric_file["encrypted"] is True
    assessments = f"{API}/applications/{beto['id']}/assessments"
    ok(
        rosa.post(
            assessments,
            json={
                "kind": "PSICOMETRIA",
                "status": "VALIDADA",
                "file_id": psychometric_file["id"],
                "event_date": "2026-11-09T16:00:00Z",
                "data": {
                    "instrument": "Prueba Ficticia X",
                    "professional_name": "Psic. Laura Ficticia",
                    "professional_license": "0000000",
                    "result": "Razonamiento percentil 70.",
                },
            },
        ),
        201,
    )

    # 14. Se registra la entrevista con el gerente, con su conclusión.
    ok(
        rosa.post(
            assessments,
            json={
                "kind": "ENTREVISTA",
                "status": "REALIZADA",
                "event_date": "2026-11-09T18:00:00Z",
                "data": {
                    "interviewer": "Gerente Ficticio",
                    "feedback": "Explica con claridad sus procesos.",
                    "conclusion": "Recomiendo contratar.",
                },
            },
        ),
        201,
    )

    # 15. La prueba técnica se marca como «no aplica».
    technical = ok(
        rosa.post(
            assessments,
            json={
                "kind": "PRUEBA_TECNICA",
                "status": "NO_APLICA",
                "data": {"test_type": "No se requiere para este puesto"},
            },
        ),
        201,
    )
    assert technical["status"] == "NO_APLICA" and technical["score"] is None

    # 16. Se digitaliza un formulario del estudio socioeconómico.
    template = ok(rosa.get(f"{API}/form-templates"))[0]
    fields = {f["label"]: f["id"] for section in template["sections"] for f in section["fields"]}
    study = ok(
        rosa.post(
            assessments, json={"kind": "ESTUDIO_SOCIOECONOMICO", "template_id": template["id"]}
        ),
        201,
    )
    scanned = upload(
        rosa,
        vacancy_id,
        "estudio.docx",
        docx_cv("Estudio socioeconómico ficticio.", "Fecha de la visita: 10 de noviembre de 2026."),
        document_type="ESTUDIO_SOCIOECONOMICO",
    )
    fake.script = [
        reply(
            {
                "valores": {
                    fields["Fecha de la visita"]: "2026-11-10",
                    fields["Domicilio declarado"]: "Calle Inventada 123",
                },
                "ilegibles": [],
                "faltantes": [],
            }
        )
    ]
    digitized = ok(
        rosa.post(f"{API}/assessments/{study['id']}/digitization", json={"file_id": scanned["id"]})
    )
    assert digitized["values"][fields["Fecha de la visita"]] == "2026-11-10"
    saved = ok(
        rosa.put(
            f"{API}/assessments/{study['id']}",
            json={
                "status": "EN_PROCESO",
                "event_date": None,
                "file_id": None,
                "version": study["version"],
                "data": {
                    "answers": {
                        key: {"value": value, "source": "IA"}
                        for key, value in digitized["values"].items()
                    }
                },
            },
        )
    )
    # Lo que leyó la IA entra sin verificar: verificar es un acto humano.
    assert all(not item["verified"] for item in saved["data"]["answers"].values())
    assert saved["score"] is None

    # 17. Se registra la contratación: la decide una persona, no la IA.
    hired = ok(
        rosa.post(
            f"{API}/applications/{beto['id']}/outcome",
            json={
                "outcome": "CONTRATADO",
                "start_date": "2026-12-01",
                "notes": "Acepta la oferta.",
            },
        )
    )
    assert hired["application"]["outcome"] == "CONTRATADO"
    assert hired["outcomes"][0]["recorded_by_name"] == "Rosa Reclutadora Ficticia"
    # La vacante tiene una plaza: ya no se puede contratar a otra persona.
    full = rosa.post(f"{API}/applications/{ana['id']}/outcome", json={"outcome": "CONTRATADO"})
    assert full.status_code == 409
    ok(
        rosa.post(
            f"{API}/applications/{ana['id']}/outcome",
            json={"outcome": "NO_CONTRATADO", "reason": "La plaza se cubrió con otra persona"},
        )
    )

    # 18. Se consulta el histórico: coincide con lo ocurrido y respeta permisos.
    overview = ok(rosa.get(f"{API}/reports/overview"))
    assert overview["totals"]["cv_analyzed"] == 2 and overview["totals"]["hires"] == 1
    assert overview["totals"]["closed"] == 2 and overview["snapshot"]["active_applications"] == 0
    history = ok(rosa.get(f"{API}/reports/applications", params={"outcome": "CONTRATADO"}))
    assert [row["candidate"] for row in history["rows"]] == ["Beto López Ficticio"]
    assert ok(luis.get(f"{API}/reports/overview"))["totals"]["hires"] == 1  # colabora
    assert ok(nora.get(f"{API}/reports/overview"))["totals"]["hires"] == 0  # sin acceso
    export = ok(rosa.post(f"{API}/reports/exports", json={"kind": "POSTULACIONES"}), 201)
    export_url = f"{API}/reports/exports/{export['id']}/download"
    assert rosa.get(export_url).status_code == 200

    # 19. La administradora transfiere la vacante a otra reclutadora.
    files_before = sorted(storage.iter_keys())
    transfer = admin.post(
        f"{API}/vacancy-transfers/individual",
        json={
            "vacancy_id": vacancy_id,
            "to_user_id": nora_id,
            "reason": "Reasignación de carga",
            "keep_previous_as_collaborator": False,
        },
    )
    assert transfer.status_code == 204, transfer.text

    # 20. Los documentos permanecen disponibles y los permisos se actualizan.
    assert sorted(storage.iter_keys()) == files_before  # la transferencia no mueve archivos
    assert ok(nora.get(f"{API}/vacancies/{vacancy_id}"))["owner"]["id"] == nora_id
    for file in (cv_ana, cv_beto, scanned):
        assert download(nora, file["id"]).status_code == 200
    assert download(nora, batch["report_file_id"]).status_code == 200
    expediente = ok(nora.get(f"{API}/applications/{beto['id']}"))
    assert expediente["application"]["outcome"] == "CONTRATADO"
    assert [m["kind"] for m in expediente["movements"]][-1] == "CONTRATACION"
    assert len(ok(nora.get(f"{API}/applications/{beto['id']}/calls"))) == 1
    assert ok(nora.get(f"{API}/reports/overview"))["totals"]["hires"] == 1
    # La responsable anterior ya no ve nada, ni siquiera el reporte que generó.
    assert rosa.get(f"{API}/vacancies/{vacancy_id}").status_code == 404
    assert download(rosa, cv_beto["id"]).status_code == 404
    assert rosa.get(f"{API}/applications/{beto['id']}").status_code == 404
    assert ok(rosa.get(f"{API}/reports/overview"))["totals"]["hires"] == 0
    assert rosa.get(export_url).status_code == 403
    # El colaborador conserva su acceso; la autoría de lo ya hecho no cambia.
    assert luis.get(f"{API}/vacancies/{vacancy_id}").status_code == 200
    assert expediente["outcomes"][0]["recorded_by_name"] == "Rosa Reclutadora Ficticia"

    # Todo quedó en la auditoría y el almacenamiento es consistente con la base.
    for action in (
        "usuario.creado",
        "vacante.compartida",
        "postulacion.resultado_registrado",
        "reporte.generado",
        "vacante.transferida",
    ):
        assert audit(admin, action), action
    reconciled = ok(admin.post(f"{API}/storage/reconciliation", json={"verify_hashes": "all"}))
    assert reconciled["orphans_quarantined"] == 0
    assert not reconciled.get("missing") and not reconciled.get("corrupted")
