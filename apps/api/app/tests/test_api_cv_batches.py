"""Evaluación de CV por lotes a través de la API.

Todos los CV son sintéticos y el proveedor de IA es simulado: ningún documento
sale del equipo de pruebas.
"""

from __future__ import annotations

import csv
import io
import json
import uuid
import zipfile
from datetime import timedelta
from decimal import Decimal

import pytest
from openpyxl import load_workbook

from app.composition import cv_jobs
from app.core.config.settings import Environment, Settings
from app.core.security.master_key import MasterKey, generate_key_text
from app.infrastructure.ai_providers.http_clients import Generation
from app.main import create_app
from app.modules.ai_settings.domain.models import ProviderCode, ProviderError
from app.modules.cv_processing.application.exports import safe_cell
from app.modules.cv_processing.domain.scoring import (
    Classification,
    CriterionSpec,
    InvalidResponseError,
    evaluate,
    mask_contacts,
    parse_json,
)
from app.tests.conftest import (
    ADMIN_EMAIL,
    ADMIN_PASSWORD,
    OTHER_PASSWORD,
    RECRUITER_EMAIL,
    RECRUITER_PASSWORD,
    VACANCY,
    login,
    share,
)
from app.tests.support.sample_files import PDF, docx_cv, pdf_cv
from app.tests.test_api_ai_settings import FAKE_KEY, FakeProvider
from app.tests.test_api_evaluation_setup import save_profile, step

API = "/api/v1"


# --- Reglas de puntuación (sin API) ------------------------------------------------------

SPECS = [CriterionSpec("C1", Decimal("3")), CriterionSpec("C2", Decimal("1"))]


def criterion(code, level, **extra):
    return {
        "id": code,
        "nivel": level,
        "sin_evidencia": level is None,
        "evidencia": "cita",
        "justificacion": "porque",
        **extra,
    }


def payload(*criteria, **extra):
    return {"evaluable": True, "criterios": list(criteria), **extra}


def test_la_puntuacion_es_el_promedio_ponderado_de_los_niveles():
    result = evaluate(payload(criterion("C1", 4), criterion("C2", 2)), SPECS, Decimal("60"))
    # (3*4 + 1*2) / (4 * 4) * 100 = 87.5
    assert result.score == Decimal("87.50")
    assert result.classification is Classification.ACEPTADO_IA
    low = evaluate(payload(criterion("C1", 1), criterion("C2", 4)), SPECS, Decimal("60"))
    assert low.score == Decimal("43.75") and low.classification is Classification.RECHAZADO_IA


def test_el_umbral_exacto_acepta():
    result = evaluate(payload(criterion("C1", 2), criterion("C2", 2)), SPECS, Decimal("50"))
    assert result.score == Decimal("50.00")
    assert result.classification is Classification.ACEPTADO_IA


def test_sin_evidencia_aporta_cero_y_se_informa_aparte():
    result = evaluate(payload(criterion("C1", 4), criterion("C2", None)), SPECS, Decimal("60"))
    assert result.score == Decimal("75.00")
    assert [s.no_evidence for s in result.scores] == [False, True]
    assert result.scores[1].level is None


def test_sin_evidencia_en_todo_no_es_un_rechazo():
    result = evaluate(payload(criterion("C1", None), criterion("C2", None)), SPECS, Decimal("60"))
    assert result.classification is Classification.NO_EVALUABLE and result.score is None
    marked = evaluate({"evaluable": False, "motivo_no_evaluable": "Está vacío"}, SPECS, Decimal(1))
    assert marked.classification is Classification.NO_EVALUABLE and marked.reason == "Está vacío"


def test_la_calidad_documental_no_cambia_la_puntuacion():
    quality = {
        "redaccion": 0,
        "ortografia": 0,
        "organizacion": 0,
        "claridad": 0,
        "coherencia": 0,
        "completitud": 0,
        "posible_error_de_digitalizacion": True,
    }
    base = payload(criterion("C1", 4), criterion("C2", 4))
    with_quality = evaluate({**base, "calidad_documental": quality}, SPECS, Decimal("60"))
    assert with_quality.score == evaluate(base, SPECS, Decimal("60")).score == Decimal("100.00")
    assert with_quality.digitization_suspect is True
    assert with_quality.quality == {k: 0 for k in quality if k != "posible_error_de_digitalizacion"}


@pytest.mark.parametrize(
    "body",
    [
        {"criterios": []},
        {"evaluable": "sí", "criterios": []},
        payload(criterion("C1", 4)),
        payload(criterion("C1", 4), criterion("C2", 2), criterion("C9", 1)),
        payload(criterion("C1", 4), criterion("C1", 2)),
        payload(criterion("C1", 5), criterion("C2", 2)),
        payload(criterion("C1", True), criterion("C2", 2)),
        payload(criterion("C1", "4"), criterion("C2", 2)),
        payload(criterion("C1", None, sin_evidencia=False), criterion("C2", 2)),
        payload(criterion("C1", 4), "C2"),
    ],
)
def test_una_respuesta_que_no_cumple_el_formato_se_rechaza(body):
    with pytest.raises(InvalidResponseError):
        evaluate(body, SPECS, Decimal("60"))


def test_la_respuesta_se_lee_aunque_venga_en_un_bloque_de_codigo():
    assert parse_json('```json\n{"evaluable": false}\n```') == {"evaluable": False}
    for text in ("no es json", "[1, 2]", ""):
        with pytest.raises(InvalidResponseError):
            parse_json(text)


def test_los_datos_de_contacto_se_ocultan_y_las_fechas_no():
    masked = mask_contacts(
        "Ana ana.perez@correo.com.mx, tel +52 (55) 1234-5678 o 5512345678. "
        "Empleo 2019-2023, 01/2020-12/2021, CP 06700."
    )
    assert "@" not in masked and "1234" not in masked and "5512345678" not in masked
    assert masked.count("[teléfono]") == 2 and "[correo]" in masked
    assert "2019-2023" in masked and "01/2020-12/2021" in masked and "06700" in masked


def test_un_texto_que_parece_formula_no_se_ejecuta_en_excel():
    for text in ("=CMD()", "+1", "-1", "@SUM(A1)", "\tx"):
        assert safe_cell(text) == "'" + text
    assert safe_cell("Ana") == "Ana" and safe_cell(3) == 3


# --- API ---------------------------------------------------------------------------------


@pytest.fixture
def providers() -> dict[ProviderCode, FakeProvider]:
    return {code: FakeProvider() for code in ProviderCode}


@pytest.fixture
def app(seeded, backend, hasher, clock, storage, providers):
    return create_app(
        settings=Settings(
            environment=Environment.TEST, storage_min_free_bytes=0, ai_allow_real_documents=True
        ),
        health_checks={"c": lambda: True},
        backend=backend,
        hasher=hasher,
        clock=clock,
        storage=storage,
        master_key=MasterKey.from_text(generate_key_text()),
        ai_clients=providers,
        ai_sleep=lambda seconds: None,
        job_mode="inline",
    )


@pytest.fixture
def admin(app):
    client = login(app, ADMIN_EMAIL, ADMIN_PASSWORD)
    client.put(f"{API}/ai/providers/ANTHROPIC/key", json={"api_key": FAKE_KEY})
    client.post(f"{API}/ai/providers/ANTHROPIC/test")
    client.put(f"{API}/ai/providers/ANTHROPIC", json={"enabled": True})
    return client


@pytest.fixture
def model(admin) -> dict:
    found = next(
        m for m in admin.get(f"{API}/ai/models").json() if m["model_id"] == "modelo-grande-1"
    )
    admin.put(f"{API}/ai/assignments/EVALUACION_DOCUMENTAL", json={"model_id": found["id"]})
    return found


@pytest.fixture
def recruiter(app):
    return login(app, RECRUITER_EMAIL, RECRUITER_PASSWORD)


@pytest.fixture
def other(app, admin) -> tuple:
    """Una segunda reclutadora con sesión en la misma aplicación, y su identificador."""
    created = admin.post(
        f"{API}/users",
        json={
            "email": "segunda@ejemplo.test",
            "full_name": "Segunda Reclutadora",
            "password": OTHER_PASSWORD,
            "role": "RECLUTADOR",
        },
    ).json()
    return login(app, "segunda@ejemplo.test", OTHER_PASSWORD), created["id"]


@pytest.fixture
def vacancy_id(recruiter) -> str:
    return recruiter.post(f"{API}/vacancies", json=VACANCY).json()["id"]


@pytest.fixture
def prompt(recruiter, vacancy_id) -> dict:
    """Prompt aprobado de la vacante."""
    assert save_profile(recruiter, vacancy_id).status_code == 201
    draft = recruiter.post(f"{API}/vacancies/{vacancy_id}/prompts").json()
    in_review = step(recruiter, draft, "submit").json()
    approved = step(recruiter, in_review, "approve")
    assert approved.status_code == 200, approved.text
    return approved.json()


def upload(client, vacancy_id, name, content, document_type="CV"):
    # El orden del lote es el de carga: cada documento llega un segundo después.
    client.app.state.context.clock.advance(seconds=1)
    response = client.post(
        f"{API}/vacancies/{vacancy_id}/files",
        params={"document_type": document_type, "filename": name},
        content=content,
    )
    assert response.status_code == 201, response.text
    return response.json()["file"]


def cv(seed: str) -> bytes:
    return pdf_cv(
        f"Curriculum ficticio {seed}",
        "Analista de nomina con experiencia en calculo de IMSS e ISR",
        "Correo: persona@ejemplo.test  Telefono: 55 1234 5678",
    )


def answer(prompt, level, **extra) -> Generation:
    body = {
        "evaluable": True,
        "motivo_no_evaluable": None,
        "criterios": [
            {
                "id": c["code"],
                "nivel": level,
                "sin_evidencia": False,
                "evidencia": "Analista de nomina",
                "justificacion": "Coincide con el requisito.",
            }
            for c in prompt["criteria"]
        ],
        "calidad_documental": {
            "redaccion": 3,
            "ortografia": 4,
            "organizacion": 3,
            "claridad": 3,
            "coherencia": 3,
            "completitud": 2,
            "posible_error_de_digitalizacion": False,
        },
        "observaciones": "=HYPERLINK(1)",
        **extra,
    }
    return Generation(json.dumps(body), 1000, 500, True)


def start(client, vacancy_id, **body):
    client.app.state.context.clock.advance(seconds=1)
    return client.post(f"{API}/vacancies/{vacancy_id}/cv-batches", json=body)


def overview(client, vacancy_id) -> dict:
    return client.get(f"{API}/vacancies/{vacancy_id}/cv-batches").json()


def download(client, file_id) -> bytes:
    response = client.get(f"{API}/files/{file_id}/download")
    assert response.status_code == 200, response.text
    return response.content


def audit(client, action: str) -> list[dict]:
    return client.get(f"{API}/audit/events", params={"action": action, "page_size": 100}).json()[
        "items"
    ]


def by_name(detail: dict) -> dict[str, dict]:
    return {item["file_name"]: item for item in detail["items"]}


def test_sin_prompt_aprobado_o_sin_cv_no_se_crea_un_lote(recruiter, vacancy_id, model):
    upload(recruiter, vacancy_id, "a.pdf", cv("A"))
    response = start(recruiter, vacancy_id)
    assert response.status_code == 422 and "aprobado" in response.json()["detail"]
    state = overview(recruiter, vacancy_id)
    assert state["approved_prompt"] is None and state["total_cvs"] == 1 and state["batches"] == []


def test_sin_cv_o_sin_modelo_asignado_no_se_crea_un_lote(recruiter, vacancy_id, prompt, admin):
    response = start(recruiter, vacancy_id)
    assert response.status_code == 422 and "No hay CV" in response.json()["detail"]
    upload(recruiter, vacancy_id, "a.pdf", cv("A"))
    # Un perfil de puesto no es un CV.
    upload(recruiter, vacancy_id, "perfil.pdf", cv("P"), document_type="PERFIL_PUESTO")
    assert overview(recruiter, vacancy_id)["pending_cvs"] == 1
    response = start(recruiter, vacancy_id)
    assert response.status_code == 422 and "modelo asignado" in response.json()["detail"]
    assert overview(recruiter, vacancy_id)["batches"] == []


def test_un_lote_evalua_califica_clasifica_y_genera_los_archivos(
    recruiter, admin, vacancy_id, prompt, model, providers
):
    original = cv("A")
    upload(recruiter, vacancy_id, "=ana.pdf", original)
    upload(
        recruiter, vacancy_id, "beto.docx", docx_cv("Chofer repartidor con licencia tipo B." * 3)
    )
    upload(recruiter, vacancy_id, "escaneado.pdf", PDF)
    upload(recruiter, vacancy_id, "ana copia.pdf", original)
    providers[ProviderCode.ANTHROPIC].script = [answer(prompt, 4), answer(prompt, 1)]
    providers[ProviderCode.ANTHROPIC].prompts = []

    response = start(recruiter, vacancy_id)
    assert response.status_code == 201, response.text
    detail = response.json()
    batch = detail["batch"]
    assert batch["status"] == "COMPLETADO" and batch["error"] is None
    assert (batch["total"], batch["evaluated"], batch["failed"], batch["pending"]) == (4, 4, 0, 0)
    assert (batch["accepted"], batch["rejected"], batch["unevaluable"]) == (2, 1, 1)

    items = by_name(detail)
    assert items["=ana.pdf"]["classification"] == "ACEPTADO_IA"
    assert Decimal(items["=ana.pdf"]["score"]) == Decimal("100")
    assert (
        items["=ana.pdf"]["step"] == "CALIFICADO"
        and items["=ana.pdf"]["quality"]["ortografia"] == 4
    )
    assert items["beto.docx"]["classification"] == "RECHAZADO_IA"
    assert Decimal(items["beto.docx"]["score"]) == Decimal("25")
    assert len(items["beto.docx"]["criteria"]) == len(prompt["criteria"])
    # Un PDF sin texto no se envía a la IA y no cuenta como rechazo.
    scanned = items["escaneado.pdf"]
    assert scanned["classification"] == "NO_EVALUABLE" and scanned["score"] is None
    assert scanned["step"] == "RECIBIDO" and scanned["reason"]
    # La copia no se evalúa dos veces: recibe el resultado del original.
    copy = items["ana copia.pdf"]
    assert copy["duplicate"] is True and copy["classification"] == "ACEPTADO_IA"

    calls = providers[ProviderCode.ANTHROPIC].prompts
    assert len(calls) == 2
    _, system, user = calls[0]
    assert system == prompt["rendered"]
    assert "Curriculum ficticio A" in user and "<<<CV" in user
    assert "persona@ejemplo.test" not in user and "1234" not in user

    # Excel: una fila por CV, sin fórmulas ejecutables.
    book = load_workbook(io.BytesIO(download(recruiter, batch["report_file_id"])))
    rows = list(book["Resumen"].iter_rows(values_only=True))
    assert len(rows) == 5
    first = dict(zip(rows[0], rows[1], strict=True))
    assert first["Archivo"] == "'=ana.pdf" and first["Clasificación inicial"] == "Aceptado por IA"
    assert first["Puntuación (0 a 100)"] == 100 and first["Observaciones"] == "'=HYPERLINK(1)"
    assert first["Umbral"] == float(prompt["pass_threshold"])
    assert len(list(book["Criterios"].iter_rows())) == 1 + 3 * len(prompt["criteria"])
    assert all(cell.data_type != "f" for sheet in book for row in sheet.iter_rows() for cell in row)

    # ZIP: los originales intactos, sin choque de nombres y con manifiesto.
    accepted = zipfile.ZipFile(io.BytesIO(download(recruiter, batch["accepted_zip_file_id"])))
    assert accepted.namelist() == ["001_=ana.pdf", "002_ana copia.pdf", "MANIFIESTO.csv"]
    assert accepted.read("001_=ana.pdf") == original
    manifest = list(csv.reader(io.StringIO(accepted.read("MANIFIESTO.csv").decode("utf-8-sig"))))
    assert manifest[1][:2] == ["001_=ana.pdf", "'=ana.pdf"]
    assert manifest[1][4:] == ["ACEPTADO_IA", "100.00"]
    rejected = zipfile.ZipFile(io.BytesIO(download(recruiter, batch["rejected_zip_file_id"])))
    assert rejected.namelist() == ["001_beto.docx", "MANIFIESTO.csv"]
    other_zip = zipfile.ZipFile(io.BytesIO(download(recruiter, batch["unevaluable_zip_file_id"])))
    assert other_zip.namelist() == ["001_escaneado.pdf", "MANIFIESTO.csv"]

    # Los archivos generados no se mezclan con los documentos cargados.
    listed = recruiter.get(f"{API}/vacancies/{vacancy_id}/files").json()
    assert {item["document_type"] for item in listed} == {"CV"}
    assert [e["details"]["cv"] for e in audit(admin, "lote_cv.creado")] == [4]
    assert audit(admin, "lote_cv.terminado")[0]["details"]["estado"] == "COMPLETADO"
    assert len(audit(admin, "exportacion.generada")) == 4
    usage = admin.get(f"{API}/ai/usage", params={"year": 2026, "month": 11}).json()
    assert sum(row["calls"] for row in usage["rows"]) == 2

    # Ya no queda nada por evaluar con este prompt, salvo que se pida repetir.
    assert overview(recruiter, vacancy_id)["pending_cvs"] == 0
    assert start(recruiter, vacancy_id).status_code == 422
    providers[ProviderCode.ANTHROPIC].script = [answer(prompt, 2), answer(prompt, 2)]
    again = start(recruiter, vacancy_id, reevaluate=True).json()
    assert again["batch"]["total"] == 4 and again["batch"]["id"] != batch["id"]
    # La evaluación original no se sobrescribe.
    kept = recruiter.get(f"{API}/cv-batches/{batch['id']}").json()
    assert Decimal(by_name(kept)["=ana.pdf"]["score"]) == Decimal("100")
    assert [b["id"] for b in overview(recruiter, vacancy_id)["batches"]] == [
        again["batch"]["id"],
        batch["id"],
    ]


def test_un_tipo_generado_no_se_puede_cargar_a_mano(recruiter, vacancy_id):
    response = recruiter.post(
        f"{API}/vacancies/{vacancy_id}/files",
        params={"document_type": "PAQUETE_CV", "filename": "x.pdf"},
        content=cv("X"),
    )
    assert response.status_code == 422


def test_si_el_proveedor_falla_en_un_cv_lo_demas_se_conserva_y_se_reintenta(
    recruiter, vacancy_id, prompt, model, providers
):
    for name in ("a.pdf", "b.pdf", "c.pdf"):
        upload(recruiter, vacancy_id, name, cv(name))
    fake = providers[ProviderCode.ANTHROPIC]
    fake.script = [
        answer(prompt, 4),
        ProviderError("solicitud", "El modelo rechazó la solicitud."),
        answer(prompt, 0),
    ]
    fake.prompts = []

    detail = start(recruiter, vacancy_id).json()
    batch = detail["batch"]
    assert batch["status"] == "COMPLETADO_CON_INCIDENCIAS"
    assert (batch["evaluated"], batch["failed"]) == (2, 1)
    failed = by_name(detail)["b.pdf"]
    assert failed["status"] == "FALLIDO" and failed["error_code"] == "proveedor"
    assert failed["step"] == "TEXTO_EXTRAIDO" and failed["classification"] is None
    assert "rechazó" in failed["error_message"]
    first_report = batch["report_file_id"]
    assert first_report is not None

    fake.script = [answer(prompt, 3)]
    retried = recruiter.post(f"{API}/cv-batches/{batch['id']}/retry").json()
    assert retried["batch"]["status"] == "COMPLETADO" and retried["batch"]["failed"] == 0
    item = by_name(retried)["b.pdf"]
    assert item["classification"] == "ACEPTADO_IA" and item["attempts"] == 2
    # Solo se volvió a enviar el CV que había fallado.
    assert len(fake.prompts) == 4
    assert by_name(retried)["a.pdf"]["attempts"] == 1
    # Se genera un Excel nuevo y el anterior se conserva.
    assert retried["batch"]["report_file_id"] != first_report
    assert len(download(recruiter, first_report)) > 0


def test_una_respuesta_invalida_se_pide_de_nuevo_y_si_persiste_el_cv_falla(
    recruiter, vacancy_id, prompt, model, providers
):
    upload(recruiter, vacancy_id, "a.pdf", cv("a"))
    upload(recruiter, vacancy_id, "b.pdf", cv("b"))
    fake = providers[ProviderCode.ANTHROPIC]
    cut = Generation(answer(prompt, 4).text, 1000, 500, False)
    fake.script = [
        Generation("Claro, aquí va mi evaluación", 10, 10, True),
        answer(prompt, 4),
        cut,
        Generation('{"evaluable": true, "criterios": []}', 10, 10, True),
    ]
    detail = start(recruiter, vacancy_id).json()
    items = by_name(detail)
    assert items["a.pdf"]["classification"] == "ACEPTADO_IA"
    assert items["b.pdf"]["status"] == "FALLIDO"
    assert (
        items["b.pdf"]["error_code"] == "respuesta_invalida"
        and items["b.pdf"]["step"] == "ANALIZADO"
    )
    assert "Faltan criterios" in items["b.pdf"]["error_message"]
    assert detail["batch"]["status"] == "COMPLETADO_CON_INCIDENCIAS"


def test_si_el_proveedor_deja_de_responder_el_lote_se_detiene_sin_perder_nada(
    recruiter, vacancy_id, prompt, model, providers
):
    for index in range(6):
        upload(recruiter, vacancy_id, f"cv{index}.pdf", cv(str(index)))
    fake = providers[ProviderCode.ANTHROPIC]
    down = ProviderError("solicitud", "Servicio no disponible.")
    fake.script = [answer(prompt, 4), down, down, down]
    fake.prompts = []
    detail = start(recruiter, vacancy_id).json()
    batch = detail["batch"]
    assert batch["status"] == "FALLIDO" and "no está respondiendo" in batch["error"]
    assert (batch["evaluated"], batch["failed"], batch["pending"]) == (1, 3, 2)
    assert len(fake.prompts) == 4

    fake.script = [answer(prompt, 4)] * 5
    resumed = recruiter.post(f"{API}/cv-batches/{batch['id']}/retry").json()["batch"]
    assert resumed["status"] == "COMPLETADO" and resumed["evaluated"] == 6
    assert resumed["error"] is None and resumed["report_file_id"]


def test_al_alcanzar_el_limite_de_gasto_el_lote_se_detiene_y_luego_continua(
    recruiter, admin, vacancy_id, prompt, model, providers
):
    admin.put(
        f"{API}/ai/models/{model['id']}/prices", json={"input_price": "3", "output_price": "15"}
    )
    admin.put(f"{API}/ai/providers/ANTHROPIC", json={"enabled": True, "monthly_limit_usd": "0.01"})
    for name in ("a.pdf", "b.pdf"):
        upload(recruiter, vacancy_id, name, cv(name))
    providers[ProviderCode.ANTHROPIC].script = [answer(prompt, 4), answer(prompt, 4)]

    batch = start(recruiter, vacancy_id).json()["batch"]
    assert batch["status"] == "FALLIDO" and "límite de gasto" in batch["error"]
    assert (batch["evaluated"], batch["pending"], batch["failed"]) == (1, 1, 0)
    # Mientras el límite siga alcanzado no se reanuda.
    blocked = recruiter.post(f"{API}/cv-batches/{batch['id']}/retry")
    assert blocked.status_code == 409 and "límite" in blocked.json()["detail"]

    admin.put(f"{API}/ai/providers/ANTHROPIC", json={"enabled": True, "monthly_limit_usd": "5"})
    resumed = recruiter.post(f"{API}/cv-batches/{batch['id']}/retry").json()["batch"]
    assert resumed["status"] == "COMPLETADO" and resumed["evaluated"] == 2


def test_un_lote_en_cola_bloquea_otro_se_cancela_y_se_reanuda(
    app, recruiter, vacancy_id, prompt, model, providers, clock, monkeypatch
):
    delivered = []
    monkeypatch.setattr(cv_jobs, "dispatch", lambda context, batch_id: delivered.append(batch_id))
    context = app.state.context
    kept = upload(recruiter, vacancy_id, "a.pdf", cv("a"))
    removed = upload(recruiter, vacancy_id, "b.pdf", cv("b"))

    batch = start(recruiter, vacancy_id).json()["batch"]
    batch_id = uuid.UUID(batch["id"])
    assert batch["status"] == "EN_COLA" and batch["pending"] == 2 and delivered == [batch_id]
    assert batch["stalled"] is False
    assert start(recruiter, vacancy_id, reevaluate=True).status_code == 409

    # Dos procesos no atienden el mismo lote a la vez.
    with context.require_backend().transaction() as repos:
        assert context.cv_batches(repos).claim(batch_id, "proceso-1") is True
    with context.require_backend().transaction() as repos:
        assert context.cv_batches(repos).claim(batch_id, "proceso-2") is False
    assert recruiter.post(f"{API}/cv-batches/{batch['id']}/retry").status_code == 409
    # Si el primero muere, su reserva caduca y el lote aparece como detenido.
    clock.advance(minutes=11)
    assert overview(recruiter, vacancy_id)["batches"][0]["stalled"] is True

    cancelled = recruiter.post(f"{API}/cv-batches/{batch['id']}/cancel").json()["batch"]
    assert cancelled["status"] == "CANCELADO" and cancelled["pending"] == 2
    assert recruiter.post(f"{API}/cv-batches/{batch['id']}/cancel").status_code == 409
    cv_jobs.run_batch(context, batch_id)
    assert providers[ProviderCode.ANTHROPIC].prompts is None  # cancelado: no se evalúa nada

    # Un CV eliminado después de crear el lote falla solo; el resto se evalúa.
    admin = login(app, ADMIN_EMAIL, ADMIN_PASSWORD)
    deletion = admin.post(
        f"{API}/files/{removed['id']}/deletion", json={"reason": "Se cargó por error"}
    )
    assert deletion.status_code == 204
    resumed = recruiter.post(f"{API}/cv-batches/{batch['id']}/retry").json()["batch"]
    assert resumed["status"] == "EN_COLA" and delivered == [batch_id, batch_id]
    providers[ProviderCode.ANTHROPIC].script = [answer(prompt, 4)]
    cv_jobs.run_batch(context, batch_id)
    detail = recruiter.get(f"{API}/cv-batches/{batch['id']}").json()
    assert detail["batch"]["status"] == "COMPLETADO_CON_INCIDENCIAS"
    statuses = {item["file_id"]: item for item in detail["items"]}
    assert statuses[kept["id"]]["classification"] == "ACEPTADO_IA"
    assert statuses[removed["id"]]["error_code"] == "archivo_no_disponible"
    assert statuses[removed["id"]]["file_name"] == "CV eliminado"


def test_si_la_cola_no_esta_disponible_el_lote_queda_detenido_y_se_puede_reanudar(
    seeded,
    backend,
    hasher,
    clock,
    storage,
    providers,
    app,
    admin,
    model,
    recruiter,
    vacancy_id,
    prompt,
):
    upload(recruiter, vacancy_id, "a.pdf", cv("a"))
    # Misma base y mismo disco, pero con la cola de trabajos sin configurar.
    broken = create_app(
        settings=Settings(
            environment=Environment.TEST, storage_min_free_bytes=0, ai_allow_real_documents=True
        ),
        health_checks={"c": lambda: True},
        backend=backend,
        hasher=hasher,
        clock=clock,
        storage=storage,
        master_key=app.state.context.master_key,
        ai_clients=providers,
        job_mode="celery",
    )
    client = login(broken, RECRUITER_EMAIL, RECRUITER_PASSWORD)
    batch = start(client, vacancy_id).json()["batch"]
    assert batch["status"] == "FALLIDO" and "segundo plano" in batch["error"]
    assert batch["pending"] == 1

    providers[ProviderCode.ANTHROPIC].script = [answer(prompt, 4)]
    resumed = recruiter.post(f"{API}/cv-batches/{batch['id']}/retry").json()["batch"]
    assert resumed["status"] == "COMPLETADO"


def test_permisos_sobre_los_lotes(recruiter, admin, vacancy_id, prompt, model, providers, other):
    other_client, other_id = other
    upload(recruiter, vacancy_id, "a.pdf", cv("a"))
    providers[ProviderCode.ANTHROPIC].script = [answer(prompt, 4)]
    batch = start(recruiter, vacancy_id).json()["batch"]
    urls = (
        ("get", f"{API}/vacancies/{vacancy_id}/cv-batches"),
        ("post", f"{API}/vacancies/{vacancy_id}/cv-batches"),
        ("get", f"{API}/cv-batches/{batch['id']}"),
        ("post", f"{API}/cv-batches/{batch['id']}/retry"),
        ("post", f"{API}/cv-batches/{batch['id']}/cancel"),
    )
    # Sin acceso a la vacante, el lote no existe.
    for method, url in urls:
        kwargs = {"json": {}} if url.endswith("cv-batches") and method == "post" else {}
        assert getattr(other_client, method)(url, **kwargs).status_code == 404, url
    assert other_client.get(f"{API}/files/{batch['report_file_id']}/download").status_code == 404

    # Con lectura se consulta y se descarga, pero no se opera.
    share(recruiter, vacancy_id, other_id, "LECTURA")
    assert other_client.get(urls[0][1]).status_code == 200
    assert other_client.get(urls[2][1]).status_code == 200
    assert len(download(other_client, batch["accepted_zip_file_id"])) > 0
    assert other_client.post(urls[1][1], json={"reevaluate": True}).status_code == 403
    assert other_client.post(urls[3][1]).status_code == 403
    assert other_client.post(urls[4][1]).status_code == 403
    # Con colaboración sí se evalúa.
    share(recruiter, vacancy_id, other_id, "COLABORACION")
    providers[ProviderCode.ANTHROPIC].script = [answer(prompt, 0)]
    assert other_client.post(urls[1][1], json={"reevaluate": True}).status_code == 201
    assert recruiter.get(f"{API}/cv-batches/{uuid.uuid4()}").status_code == 404


def test_un_prompt_nuevo_deja_todos_los_cv_pendientes_de_evaluar(
    recruiter, vacancy_id, prompt, model, providers
):
    upload(recruiter, vacancy_id, "a.pdf", cv("a"))
    providers[ProviderCode.ANTHROPIC].script = [answer(prompt, 4)]
    first = start(recruiter, vacancy_id).json()["batch"]
    assert overview(recruiter, vacancy_id)["pending_cvs"] == 0

    copy = recruiter.post(
        f"{API}/prompts/{prompt['id']}/duplicate", json={"revision": prompt["revision"]}
    ).json()
    approved = step(recruiter, step(recruiter, copy, "submit").json(), "approve").json()
    state = overview(recruiter, vacancy_id)
    assert state["approved_prompt"]["version_number"] == approved["version_number"]
    assert state["pending_cvs"] == 1
    # El lote anterior conserva sus resultados y sigue consultable.
    assert recruiter.get(f"{API}/cv-batches/{first['id']}").json()["batch"]["accepted"] == 1


def test_la_reserva_caduca_y_otro_proceso_puede_tomar_el_lote(
    app, recruiter, vacancy_id, prompt, model, clock, monkeypatch
):
    monkeypatch.setattr(cv_jobs, "dispatch", lambda context, batch_id: None)
    upload(recruiter, vacancy_id, "a.pdf", cv("a"))
    batch_id = uuid.UUID(start(recruiter, vacancy_id).json()["batch"]["id"])
    context = app.state.context

    def claim(token):
        with context.require_backend().transaction() as repos:
            return context.cv_batches(repos).claim(batch_id, token)

    assert claim("uno") is True and claim("uno") is True and claim("dos") is False
    clock.now += timedelta(minutes=10, seconds=1)
    assert claim("dos") is True and claim("uno") is False
