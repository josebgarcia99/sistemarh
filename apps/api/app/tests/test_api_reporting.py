"""Fase 7: resultados finales, tableros, históricos y reportes.

Todo con datos sintéticos y un proveedor de IA simulado.
"""

# ruff: noqa: F401, F811  (las fixtures se importan de otro módulo de pruebas)
from __future__ import annotations

import io
import uuid
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest
from openpyxl import load_workbook

from app.modules.reporting.domain import metrics
from app.modules.reporting.domain.models import (
    ApplicationFact,
    CvFact,
    DateKind,
    Facts,
    MovementFact,
    OutcomeFact,
    ReportFilter,
    StageFact,
    VacancyFact,
    Viewer,
)
from app.tests.conftest import (
    ADMIN_EMAIL,
    ADMIN_PASSWORD,
    CSRF_HEADER,
    OTHER_PASSWORD,
    RECRUITER_EMAIL,
    RECRUITER_PASSWORD,
    VACANCY,
    share,
)
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
    vacancy_id,
)
from app.tests.test_api_recruitment import (
    assign,
    board,
    by_name,
    evaluated,
    move,
    new_bank,
    stage_id,
)

MEXICO = ZoneInfo("America/Mexico_City")
ANA, BETO = "Ana Pérez Ficticia", "Beto López Ficticio"


# --- Reglas sin API ----------------------------------------------------------------------


def test_el_periodo_se_cuenta_en_hora_local_con_ambos_dias_incluidos():
    period = metrics.period_of(date(2026, 11, 1), date(2026, 11, 30), MEXICO)
    # Ciudad de México va seis horas detrás de UTC.
    assert period.start == datetime(2026, 11, 1, 6, tzinfo=UTC)
    assert period.end == datetime(2026, 12, 1, 6, tzinfo=UTC)
    assert period.has(datetime(2026, 12, 1, 5, 59, tzinfo=UTC))
    assert not period.has(datetime(2026, 12, 1, 6, tzinfo=UTC))
    assert not period.has(datetime(2026, 11, 1, 5, 59, tzinfo=UTC))
    assert not period.has(None)
    todo = metrics.period_of(None, None, MEXICO)
    assert todo.has(datetime(2000, 1, 1, tzinfo=UTC))


def _facts() -> tuple[Facts, dict[str, uuid.UUID]]:
    """Dos vacantes de Rosa (una compartida con Luis) y cuatro postulaciones."""
    ids = {name: uuid.uuid4() for name in ("rosa", "luis", "v1", "v2", "p")}
    names = ("Evaluación de CV", "Revisión local RH", "Llamada telefónica", "Resultado final")
    kinds = ("EVALUACION_CV", "REVISION_RH", "LLAMADA", "RESULTADO")
    stages = [
        StageFact(uuid.uuid4(), ids["p"], position, name, kind)
        for position, (name, kind) in enumerate(zip(names, kinds, strict=True), start=1)
    ]
    cv, rh, call, final = (stage.id for stage in stages)
    day = datetime(2026, 11, 2, 15, tzinfo=UTC)
    vacancies = [
        VacancyFact(
            ids["v1"], "Analista", "Finanzas", "ABIERTA", 1, ids["rosa"], "Rosa", day,
            collaborators=frozenset({ids["luis"]}),
        ),
        VacancyFact(ids["v2"], "Chofer", "Logística", "CERRADA", 1, ids["rosa"], "Rosa", day),
    ]  # fmt: skip
    people = {name: uuid.uuid4() for name in ("ana", "beto", "caro", "dani")}

    def application(name: str, vacancy: str, stage: uuid.UUID, status: str) -> ApplicationFact:
        return ApplicationFact(
            people[name], ids[vacancy], name.title(), stage, status, day, day,
            ai_classification="ACEPTADO_IA", ai_score=Decimal("80"),
        )  # fmt: skip

    applications = [
        application("ana", "v1", final, "CONTRATADA"),
        application("beto", "v1", call, "ACTIVA"),
        application("caro", "v1", rh, "DESISTIO"),
        application("dani", "v2", rh, "ACTIVA"),
    ]

    def steps(name: str, *items: tuple[str, uuid.UUID | None, uuid.UUID | None, int]):
        return [
            MovementFact(people[name], sequence, kind, day + timedelta(days=days), origin, target)
            for sequence, (kind, origin, target, days) in enumerate(items, start=1)
        ]

    movements = [
        # Ana: alta automática, 2 días en RH, 4 en llamada, 1 en resultado y contratada.
        *steps(
            "ana",
            ("ALTA", None, cv, 0),
            ("AVANCE", cv, rh, 0),
            ("AVANCE", rh, call, 2),
            ("AVANCE", call, final, 6),
            ("CONTRATACION", final, None, 7),
        ),
        # Beto: 4 días en RH y sigue en llamada.
        *steps("beto", ("ALTA", None, cv, 0), ("AVANCE", cv, rh, 0), ("AVANCE", rh, call, 4)),
        # Caro: desiste a los 3 días, en RH.
        *steps("caro", ("ALTA", None, rh, 0), ("DESISTIMIENTO", rh, None, 3)),
        *steps("dani", ("ALTA", None, rh, 0)),
    ]
    outcomes = [
        OutcomeFact(people["ana"], ids["v1"], "CONTRATADO", day + timedelta(days=7), "Rosa"),
        OutcomeFact(
            people["caro"], ids["v1"], "DESISTIO", day + timedelta(days=3), "Rosa", "Otra oferta"
        ),
    ]
    cvs = [
        CvFact(ids["v1"], "EVALUADO", day, "ACEPTADO_IA"),
        CvFact(ids["v1"], "EVALUADO", day, "RECHAZADO_IA"),
        CvFact(ids["v1"], "FALLIDO", day, None),
    ]
    facts = Facts(vacancies, {s.id: s for s in stages}, applications, movements, outcomes, cvs)
    return facts, ids


def test_indicadores_embudo_tiempos_y_cobertura_salen_de_los_movimientos():
    facts, ids = _facts()
    period = metrics.period_of(date(2026, 11, 1), date(2026, 11, 30), MEXICO)
    data = metrics.overview(facts, period, Viewer(ids["rosa"], is_admin=True), zone=MEXICO)

    assert data.snapshot == metrics.Snapshot(
        vacancies=2,
        vacancies_open=1,
        own=2,
        shared=0,
        active_applications=2,
        in_calls=1,
        tests_pending=0,
        interviews_pending=0,
    )
    totals = data.totals
    assert (totals.cv_analyzed, totals.ai_accepted, totals.ai_rejected) == (2, 1, 1)
    assert (totals.applications, totals.closed, totals.hires, totals.withdrawals) == (4, 2, 1, 1)
    assert totals.coverage_days == 7.0 and data.cv_failures == 1

    stages = {stage.name: stage for stage in data.stages}
    # Llegaron a cada etapa o más allá: las cuatro pasan por RH, dos llegan a
    # llamada y una al resultado final.
    assert [stage.reached for stage in data.stages] == [4, 4, 2, 1]
    assert stages["Revisión local RH"].conversion == 50.0
    assert stages["Llamada telefónica"].conversion == 50.0
    assert stages["Resultado final"].conversion is None and data.funnel_hired == 1
    # RH: Ana 2 días, Beto 4 y Caro 3. La evaluación de CV dura cero y no cuenta.
    assert stages["Revisión local RH"].average_days == 3.0
    assert stages["Revisión local RH"].stays == 3
    assert stages["Llamada telefónica"].average_days == 4.0
    assert stages["Evaluación de CV"].average_days is None
    assert [stage.active for stage in data.stages] == [0, 1, 1, 0]

    first, second = data.vacancies
    assert (first.name, first.hires, first.hires_total, first.active, first.closed) == (
        "Analista",
        1,
        1,
        1,
        2,
    )
    assert (second.name, second.hires, second.active) == ("Chofer", 0, 1)
    assert data.months == [metrics.MonthRow("2026-11", 2, 4, 2, 1, 1)]
    assert data.recent[0].kind == "CONTRATACION" and data.recent[0].candidate == "Ana"


def test_una_contratacion_se_cuenta_una_vez_aunque_la_vacante_tenga_colaboradores():
    facts, ids = _facts()
    period = metrics.period_of(None, None, MEXICO)
    data = metrics.overview(facts, period, Viewer(ids["luis"], is_admin=True), zone=MEXICO)
    assert data.totals.hires == 1
    # Solo figura la responsable; Luis colabora, pero la contratación no es suya.
    assert [(row.name, row.hires, row.vacancies) for row in data.recruiters] == [("Rosa", 1, 2)]
    assert data.snapshot.own == 0 and data.snapshot.shared == 1
    # Fuera del periodo no hay hechos, pero la fotografía de hoy no cambia.
    empty = metrics.overview(
        facts,
        metrics.period_of(date(2025, 1, 1), date(2025, 1, 31), MEXICO),
        Viewer(ids["rosa"], is_admin=False),
        zone=MEXICO,
    )
    assert empty.totals.hires == 0 and empty.totals.cv_analyzed == 0 and empty.months == []
    assert empty.snapshot.active_applications == 2
    assert empty.recruiters is None and empty.ai is None and empty.cv_failures is None


def test_el_historico_filtra_por_resultado_fecha_y_calificacion():
    facts, _ = _facts()
    todo = metrics.period_of(None, None, MEXICO)

    def names(flt: ReportFilter, period: metrics.Period = todo) -> list[str]:
        return sorted(row.candidate for row in metrics.history(facts, flt, period))

    assert names(ReportFilter()) == ["Ana", "Beto", "Caro", "Dani"]
    assert names(ReportFilter(outcome="CONTRATADO")) == ["Ana"]
    assert names(ReportFilter(outcome="EN_PROCESO")) == ["Beto", "Dani"]
    assert names(ReportFilter(candidate="  CAR ")) == ["Caro"]
    assert names(ReportFilter(stage="llamada telefónica")) == ["Beto"]
    assert names(ReportFilter(score_min=Decimal("90"))) == []
    # Cierres del 5 de noviembre en adelante: solo la contratación de Ana (día 9).
    late = metrics.period_of(date(2026, 11, 6), None, MEXICO)
    assert names(ReportFilter(date_kind=DateKind.CIERRE), late) == ["Ana"]
    assert names(ReportFilter(date_kind=DateKind.MOVIMIENTO), late) == ["Ana", "Beto"]
    assert names(ReportFilter(date_kind=DateKind.EVALUACION), late) == []
    caro = next(row for row in metrics.history(facts, ReportFilter(candidate="caro"), todo))
    assert caro.outcome == "DESISTIO" and caro.outcome_reason == "Otra oferta"
    assert caro.closed_by_name == "Rosa"


# --- Resultados finales ------------------------------------------------------------------


def renew(client, email: str, password: str) -> None:
    """Vuelve a iniciar sesión: al pasar los días, la sesión anterior caduca."""
    response = client.post(f"{API}/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    client.headers[CSRF_HEADER] = response.json()["csrf_token"]


def outcome(client, application_id, **body):
    return client.post(f"{API}/applications/{application_id}/outcome", json=body)


def test_contratacion_con_fecha_de_incorporacion_historial_y_auditoria(
    evaluated, recruiter, admin, vacancy_id
):
    ana = by_name(evaluated)[ANA]["id"]
    assert by_name(evaluated)[ANA]["outcome"] == "EN_PROCESO"
    assert (evaluated["positions"], evaluated["hires"]) == (2, 0)

    # La fecha de incorporación solo acompaña a una contratación.
    wrong = outcome(
        recruiter, ana, outcome="NO_CONTRATADO", reason="Perfil", start_date="2026-12-01"
    )
    assert wrong.status_code == 422
    assert outcome(recruiter, ana, outcome="CONTRATADO", start_date="2031-01-01").status_code == 422

    hired = outcome(
        recruiter,
        ana,
        outcome="CONTRATADO",
        notes="Acepta la oferta.\nEntra en quincena.",
        start_date="2026-12-01",
    )
    assert hired.status_code == 200, hired.text
    detail = hired.json()
    assert detail["application"]["status"] == "CONTRATADA"
    assert detail["application"]["outcome"] == "CONTRATADO"
    [current] = detail["outcomes"]
    assert current["outcome"] == "CONTRATADO" and current["start_date"] == "2026-12-01"
    assert current["recorded_by_name"] == "Reclutadora de Prueba"
    assert current["notes"] == "Acepta la oferta.\nEntra en quincena."
    assert current["voided_at"] is None and current["reason"] is None
    assert detail["movements"][-1]["kind"] == "CONTRATACION"
    assert board(recruiter, vacancy_id)["hires"] == 1

    # Con resultado final ya no se registra otro ni se mueve de etapa.
    assert outcome(recruiter, ana, outcome="OTRO_CIERRE", reason="Duplicado").status_code == 409
    target = stage_id(evaluated, "Llamada telefónica")
    assert move(recruiter, vacancy_id, [ana], target).status_code == 409

    [event] = audit(admin, "postulacion.resultado_registrado")
    assert event["details"]["resultado"] == "CONTRATADO"
    assert event["details"]["no_aceptada_por_ia"] is False


def test_los_demas_resultados_exigen_motivo_y_reabrir_anula_sin_borrar(
    evaluated, recruiter, admin, vacancy_id, clock
):
    beto = by_name(evaluated)[BETO]["id"]
    for kind in ("NO_CONTRATADO", "DESISTIO", "NO_LOCALIZADO", "VACANTE_CANCELADA", "OTRO_CIERRE"):
        assert outcome(recruiter, beto, outcome=kind, reason="  ").status_code == 422
    assert outcome(recruiter, beto, outcome="EN_PROCESO", reason="No aplica").status_code == 422

    lost = outcome(recruiter, beto, outcome="NO_LOCALIZADO", reason="No contestó en tres intentos")
    assert lost.status_code == 200
    assert lost.json()["application"]["status"] == "NO_LOCALIZADA"
    assert lost.json()["movements"][-1]["kind"] == "NO_LOCALIZADO"

    clock.advance(minutes=5)
    url = f"{API}/applications/{beto}/reopening"
    assert recruiter.post(url, json={"reason": ""}).status_code == 422
    reopened = recruiter.post(url, json={"reason": "Devolvió la llamada"})
    assert reopened.status_code == 200
    detail = reopened.json()
    assert detail["application"]["outcome"] == "EN_PROCESO"
    [voided] = detail["outcomes"]
    assert voided["outcome"] == "NO_LOCALIZADO" and voided["voided_at"] is not None
    assert voided["void_reason"] == "Devolvió la llamada"
    assert voided["voided_by_name"] == "Reclutadora de Prueba"
    assert recruiter.post(url, json={"reason": "Otra vez"}).status_code == 409

    # Los atajos de la fase 5 también dejan su resultado final.
    clock.advance(minutes=5)
    gone = recruiter.post(
        f"{API}/applications/{beto}/status",
        json={"action": "DESISTIMIENTO", "note": "Aceptó otra oferta"},
    )
    assert gone.status_code == 200
    latest, old = gone.json()["outcomes"]
    assert latest["outcome"] == "DESISTIO" and latest["reason"] == "Aceptó otra oferta"
    assert latest["voided_at"] is None and old["voided_at"] is not None
    [undone] = audit(admin, "postulacion.resultado_anulado")
    assert undone["details"]["resultado_anulado"] == "NO_LOCALIZADO"


def test_no_se_contrata_a_mas_personas_que_plazas_y_una_persona_decide_sobre_la_ia(
    evaluated, recruiter, admin, vacancy_id
):
    people = by_name(evaluated)
    # Beto fue rechazado por la IA: contratarlo es una decisión humana que se anota.
    assert outcome(recruiter, people[BETO]["id"], outcome="CONTRATADO").status_code == 200
    assert audit(admin, "postulacion.resultado_registrado")[0]["details"]["no_aceptada_por_ia"]
    assert outcome(recruiter, people[ANA]["id"], outcome="CONTRATADO").status_code == 200

    extra = recruiter.post(
        f"{API}/vacancies/{vacancy_id}/applications",
        json={"full_name": "Caro Ruiz Ficticia", "email": None, "phone": None},
    ).json()["application"]
    full = outcome(recruiter, extra["id"], outcome="CONTRATADO")
    assert full.status_code == 409 and "2 plazas" in full.json()["detail"]

    # Si una contratación se cae, la plaza vuelve a estar libre.
    reopened = recruiter.post(
        f"{API}/applications/{people[ANA]['id']}/reopening", json={"reason": "No se presentó"}
    )
    assert reopened.status_code == 200
    assert outcome(recruiter, extra["id"], outcome="CONTRATADO").status_code == 200
    assert board(recruiter, vacancy_id)["hires"] == 2


def test_solo_quien_colabora_en_la_vacante_registra_resultados(
    evaluated, recruiter, vacancy_id, other
):
    other_client, other_id = other
    ana = by_name(evaluated)[ANA]["id"]
    body = {"outcome": "DESISTIO", "reason": "Aceptó otra oferta"}
    # Sin acceso, la postulación no existe para esa persona.
    assert outcome(other_client, ana, **body).status_code == 404
    share(recruiter, vacancy_id, other_id, "LECTURA")
    assert outcome(other_client, ana, **body).status_code == 403
    assert (
        other_client.post(f"{API}/applications/{ana}/reopening", json={"reason": "x" * 5})
    ).status_code == 403
    share(recruiter, vacancy_id, other_id, "COLABORACION")
    done = outcome(other_client, ana, **body)
    assert done.status_code == 200
    assert done.json()["outcomes"][0]["recorded_by_name"] == "Segunda Reclutadora"


# --- Tableros ----------------------------------------------------------------------------


def report(client, path="overview", **params) -> dict:
    response = client.get(f"{API}/reports/{path}", params=params)
    assert response.status_code == 200, response.text
    return response.json()


@pytest.fixture
def flow(evaluated, recruiter, admin, vacancy_id, clock) -> dict:
    """Ana pasa dos días en revisión y uno en llamada, y se contrata; Beto
    desiste al tercer día."""
    people = by_name(evaluated)
    ana, beto = people[ANA]["id"], people[BETO]["id"]
    clock.advance(days=2)
    renew(recruiter, RECRUITER_EMAIL, RECRUITER_PASSWORD)
    assert (
        move(recruiter, vacancy_id, [ana], stage_id(evaluated, "Llamada telefónica")).status_code
        == 200
    )
    clock.advance(days=1)
    renew(recruiter, RECRUITER_EMAIL, RECRUITER_PASSWORD)
    renew(admin, ADMIN_EMAIL, ADMIN_PASSWORD)
    assert (
        outcome(recruiter, beto, outcome="DESISTIO", reason="Aceptó otra oferta").status_code == 200
    )
    assert outcome(recruiter, ana, outcome="CONTRATADO", start_date="2026-12-01").status_code == 200
    return {"ana": ana, "beto": beto}


def test_el_tablero_de_la_reclutadora_coincide_con_el_flujo(flow, recruiter, vacancy_id):
    data = report(recruiter)
    assert data["snapshot"] == {
        "vacancies": 1,
        "vacancies_open": 0,
        "own": 1,
        "shared": 0,
        "active_applications": 0,
        "in_calls": 0,
        "tests_pending": 0,
        "interviews_pending": 0,
    }
    totals = data["totals"]
    assert (totals["cv_analyzed"], totals["ai_accepted"], totals["ai_rejected"]) == (2, 1, 1)
    assert (totals["applications"], totals["closed"]) == (2, 2)
    assert (totals["hires"], totals["withdrawals"]) == (1, 1)
    # La convocatoria se abrió al terminar el lote; la contratación, tres días después.
    assert totals["coverage_days"] == 3.0
    stages = {stage["name"]: stage for stage in data["stages"]}
    assert stages["Revisión local RH"]["reached"] == 2
    assert stages["Llamada telefónica"]["reached"] == 1
    assert stages["Revisión local RH"]["conversion"] == 50.0
    # En revisión: Ana dos días y Beto tres.
    assert stages["Revisión local RH"]["average_days"] == 2.5
    assert stages["Llamada telefónica"]["average_days"] == 1.0
    assert data["funnel_hired"] == 1
    [vacancy] = data["vacancies"]
    assert vacancy["id"] == vacancy_id and vacancy["hires_total"] == 1 and vacancy["positions"] == 2
    assert [month["month"] for month in data["months"]] == ["2026-11"]
    assert data["recent"][0]["kind"] == "CONTRATACION" and data["recent"][0]["candidate"] == ANA
    assert data["recent"][0]["actor_name"] == "Reclutadora de Prueba"
    # Uso de IA, errores técnicos y reparto por persona son solo para administradores.
    assert data["recruiters"] is None and data["ai"] is None and data["cv_failures"] is None


def test_el_periodo_acota_los_hechos_pero_no_la_fotografia(flow, recruiter):
    before = report(recruiter, date_from="2026-01-01", date_to="2026-11-09")
    assert before["totals"]["cv_analyzed"] == 0 and before["totals"]["hires"] == 0
    assert before["snapshot"]["vacancies"] == 1 and before["months"] == []
    # El lote se evaluó el día 10; los cierres son del 13.
    first = report(recruiter, date_from="2026-11-10", date_to="2026-11-10")
    assert first["totals"]["cv_analyzed"] == 2 and first["totals"]["closed"] == 0
    last = report(recruiter, date_from="2026-11-13", date_to="2026-11-13")
    assert last["totals"]["cv_analyzed"] == 0 and last["totals"]["hires"] == 1
    wrong = recruiter.get(
        f"{API}/reports/overview", params={"date_from": "2026-11-13", "date_to": "2026-11-01"}
    )
    assert wrong.status_code == 422


def test_cada_persona_ve_solo_sus_vacantes_y_el_administrador_todas(
    flow, recruiter, admin, vacancy_id, other
):
    other_client, other_id = other
    renew(other_client, "segunda@ejemplo.test", OTHER_PASSWORD)
    nothing = report(other_client)
    assert nothing["snapshot"]["vacancies"] == 0 and nothing["totals"]["hires"] == 0
    assert nothing["vacancies"] == [] and nothing["recent"] == []
    # Pedir expresamente una vacante ajena no la muestra.
    assert report(other_client, vacancy_id=vacancy_id)["vacancies"] == []
    assert report(other_client, "applications", vacancy_id=vacancy_id) == {"rows": [], "total": 0}

    share(recruiter, vacancy_id, other_id, "LECTURA")
    shared = report(other_client)
    assert (shared["snapshot"]["own"], shared["snapshot"]["shared"]) == (0, 1)
    assert shared["totals"]["hires"] == 1 and shared["recruiters"] is None

    own = admin.post(
        f"{API}/vacancies", json={**VACANCY, "name": "Chofer", "department": "Logística"}
    )
    assert own.status_code == 201
    everything = report(admin)
    assert everything["snapshot"]["vacancies"] == 2 and everything["totals"]["hires"] == 1
    # La contratación es de la responsable, no de quien colabora ni del administrador.
    rows = {row["name"]: row for row in everything["recruiters"]}
    assert rows["Reclutadora de Prueba"]["hires"] == 1
    assert rows["Reclutadora de Prueba"]["vacancies"] == 1
    assert rows["Administradora de Prueba"]["hires"] == 0
    assert "Segunda Reclutadora" not in rows
    assert sum(row["hires"] for row in everything["recruiters"]) == everything["totals"]["hires"]
    # Dos evaluaciones y dos extracciones de datos, sin fallos.
    assert everything["ai"]["calls"] == 4 and everything["ai"]["failures"] == 0
    operations = {row["operation"]: row["calls"] for row in everything["ai"]["operations"]}
    assert operations == {"EVALUACION_DOCUMENTAL": 2, "EXTRACCION_CV": 2}
    assert everything["cv_failures"] == 0

    # Filtros de vacante: por departamento, responsable y colaborador.
    assert [v["name"] for v in report(admin, department="Logística")["vacancies"]] == ["Chofer"]
    assert report(admin, department="Logística")["ai"]["calls"] == 0
    by_collaborator = report(admin, collaborator_id=other_id)
    assert [v["id"] for v in by_collaborator["vacancies"]] == [vacancy_id]
    assert by_collaborator["totals"]["hires"] == 1
    assert report(admin, owner_id=other_id)["vacancies"] == []
    assert report(admin, vacancy_status="ABIERTA")["vacancies"] == []


# --- Histórico y reportes ----------------------------------------------------------------


def test_el_historico_de_postulaciones_admite_todos_los_filtros(
    flow, recruiter, admin, vacancy_id, prompt, clock
):
    everything = report(recruiter, "applications")
    assert everything["total"] == 2
    ana = next(row for row in everything["rows"] if row["candidate"] == ANA)
    assert ana["outcome"] == "CONTRATADO" and ana["start_date"] == "2026-12-01"
    assert ana["stage"] == "Llamada telefónica" and ana["vacancy"] == "Analista de Nómina"
    assert ana["model"] == "modelo-grande-1" and ana["prompt_version"] == 1
    assert ana["ai_classification"] == "ACEPTADO_IA" and ana["closed_by_name"]
    assert ana["cv_uploaded_at"] < ana["evaluated_at"] < ana["closed_at"]

    def names(**params) -> list[str]:
        return sorted(
            row["candidate"] for row in report(recruiter, "applications", **params)["rows"]
        )

    assert names(outcome="DESISTIO") == [BETO]
    assert names(outcome="EN_PROCESO") == []
    assert names(ai_classification="RECHAZADO_IA") == [BETO]
    assert names(score_min="60") == [ANA] and names(score_max="59.99") == [BETO]
    assert names(candidate="pérez") == [ANA]
    assert names(stage="Revisión local RH") == [BETO]
    assert names(model="modelo-grande-1") == [ANA, BETO] and names(model="otro") == []
    assert names(prompt_version_id=prompt["id"]) == [ANA, BETO]
    assert names(prompt_version_id=str(uuid.uuid4())) == []
    assert names(date_from="2026-11-13", date_kind="CIERRE") == [ANA, BETO]
    assert names(date_from="2026-11-12", date_to="2026-11-12", date_kind="MOVIMIENTO") == [ANA]
    assert names(date_from="2026-11-11", date_kind="CARGA") == []
    assert names(date_to="2026-11-10", date_kind="EVALUACION") == [ANA, BETO]
    assert report(recruiter, "applications", limit=1, offset=1)["total"] == 2
    assert len(report(recruiter, "applications", limit=1, offset=1)["rows"]) == 1
    for params in ({"outcome": "CUALQUIERA"}, {"ai_classification": "X"}, {"score_min": "101"}):
        assert recruiter.get(f"{API}/reports/applications", params=params).status_code == 422
    wrong = {"score_min": "80", "score_max": "20"}
    assert recruiter.get(f"{API}/reports/applications", params=wrong).status_code == 422

    # Banco de preguntas: solo quien tuvo una llamada con ese banco.
    bank = new_bank(recruiter)
    caro = recruiter.post(
        f"{API}/vacancies/{vacancy_id}/applications",
        json={"full_name": "Caro Ruiz Ficticia", "email": None, "phone": None},
    ).json()["application"]
    call = recruiter.post(f"{API}/applications/{caro['id']}/calls", json={"bank_id": bank["id"]})
    assert call.status_code == 201, call.text
    assert names(bank_id=bank["id"]) == ["Caro Ruiz Ficticia"]
    # Sin CV, la fecha de carga es la del alta; no tiene evaluación ni modelo.
    assert names(outcome="EN_PROCESO") == ["Caro Ruiz Ficticia"]
    assert names(date_from="2026-11-13", date_kind="CARGA") == ["Caro Ruiz Ficticia"]
    assert names(date_from="2026-11-13", date_kind="EVALUACION") == []

    options = report(recruiter, "options")
    assert [item["name"] for item in options["vacancies"]] == ["Analista de Nómina"]
    assert options["departments"] == ["Finanzas"] and options["models"] == ["modelo-grande-1"]
    assert options["stages"][0] == "Evaluación de CV" and len(options["stages"]) == 8
    assert [item["name"] for item in options["owners"]] == ["Reclutadora de Prueba"]
    assert [item["name"] for item in options["prompt_versions"]] == [
        "Analista de Nómina · versión 1"
    ]
    assert [item["name"] for item in options["banks"]] == ["Banco de nómina"]


def export(client, **body):
    return client.post(f"{API}/reports/exports", json=body)


def workbook(client, export_id):
    response = client.get(f"{API}/reports/exports/{export_id}/download")
    assert response.status_code == 200, response.text
    return load_workbook(io.BytesIO(response.content)), response


def test_el_excel_de_postulaciones_se_guarda_en_el_servidor_y_no_ejecuta_formulas(
    flow, recruiter, admin, vacancy_id, storage
):
    # Un nombre que Excel podría tomar por fórmula.
    risky = recruiter.post(
        f"{API}/vacancies/{vacancy_id}/applications",
        json={"full_name": "=HYPERLINK(1) Trampa", "email": None, "phone": None},
    )
    assert risky.status_code == 201
    created = export(
        recruiter, kind="POSTULACIONES", candidate="=HYPERLINK", date_from="2026-11-01"
    )
    assert created.status_code == 201, created.text
    record = created.json()
    assert record["row_count"] == 1 and record["name"].startswith("Postulaciones_2026111")
    assert record["filters"] == {
        "Desde": "2026-11-01",
        "Fecha que se compara": "Carga del CV",
        "Candidato": "=HYPERLINK",
    }

    book, response = workbook(recruiter, record["id"])
    assert "attachment" in response.headers["content-disposition"]
    assert response.headers["cache-control"] == "no-store"
    sheet = book["Postulaciones"]
    assert sheet["A1"].value == "Candidato" and sheet["A2"].value == "'=HYPERLINK(1) Trampa"
    assert sheet["F2"].value == "En proceso" and sheet.max_row == 2
    about = {row[0].value: row[1].value for row in book["Acerca del reporte"].iter_rows()}
    assert about["Generado por"] == "Reclutadora de Prueba" and about["Postulaciones"] == 1
    assert about["Candidato"] == "'=HYPERLINK" and about["Zona horaria"] == "America/Mexico_City"

    # El archivo queda en el almacenamiento del servidor, con su huella.
    import hashlib

    [stored] = [key for key in storage.iter_keys() if key.startswith("generated/reports/")]
    assert storage.sha256(stored) == record["sha256"]
    assert hashlib.sha256(response.content).hexdigest() == record["sha256"]
    assert len(response.content) == record["size_bytes"]
    # La conciliación del almacenamiento lo reconoce y no lo aparta.
    reconciled = admin.post(f"{API}/storage/reconciliation", json={}).json()
    assert reconciled["orphans_quarantined"] == 0 and storage.exists(stored)

    recruiter.app.state.context.clock.advance(seconds=1)
    full = export(recruiter, kind="POSTULACIONES").json()
    rows = list(workbook(recruiter, full["id"])[0]["Postulaciones"].iter_rows(values_only=True))
    ana = next(row for row in rows if row[0] == ANA)
    assert ana[5] == "Contratado" and ana[7] == "Aceptado por IA" and ana[17] == "2026-12-01"
    # Las fechas van en hora local: el lote se evaluó a las 9 de la mañana.
    assert isinstance(ana[13], datetime) and (ana[13].day, ana[13].hour) == (10, 9)
    beto = next(row for row in rows if row[0] == BETO)
    assert beto[5] == "Desistió" and beto[6] == "Aceptó otra oferta"

    listed = recruiter.get(f"{API}/reports/exports").json()
    assert [item["id"] for item in listed] == [full["id"], record["id"]]
    assert len(audit(admin, "reporte.generado")) == 2
    assert len(audit(admin, "reporte.descargado")) == 2


def test_el_excel_de_indicadores_da_a_cada_quien_lo_que_puede_ver(
    flow, recruiter, admin, vacancy_id
):
    mine = export(recruiter, kind="INDICADORES", date_from="2026-11-01", date_to="2026-11-30")
    assert mine.status_code == 201
    book, _ = workbook(recruiter, mine.json()["id"])
    assert book.sheetnames == ["Resumen", "Etapas", "Vacantes", "Mensual"]
    summary = {row[0]: row[1] for row in book["Resumen"].iter_rows(values_only=True) if row[0]}
    assert summary["Contrataciones"] == 1 and summary["Desistimientos"] == 1
    assert summary["CV analizados"] == 2 and summary["Desde"] == "2026-11-01"
    assert summary["Tiempo de cobertura promedio (días)"] == 3
    assert "Fallos de IA" not in summary
    vacancies = list(book["Vacantes"].iter_rows(values_only=True))
    assert vacancies[1][:4] == (
        "Analista de Nómina",
        "Finanzas",
        "Borrador",
        "Reclutadora de Prueba",
    )

    full = export(admin, kind="INDICADORES", vacancy_id=vacancy_id)
    assert full.status_code == 201 and full.json()["filters"] == {"Vacante": "Analista de Nómina"}
    book, _ = workbook(admin, full.json()["id"])
    assert book.sheetnames == ["Resumen", "Etapas", "Vacantes", "Reclutadores", "Mensual", "IA"]
    people = list(book["Reclutadores"].iter_rows(values_only=True))
    assert people[1][0] == "Reclutadora de Prueba" and people[1][6] == 1
    usage = list(book["IA"].iter_rows(values_only=True))
    assert [row[0] for row in usage[1:]] == ["Evaluación de CV", "Extracción de CV"]


def test_un_reporte_solo_se_descarga_mientras_se_conserva_el_acceso(
    flow, recruiter, admin, vacancy_id, other
):
    other_client, other_id = other
    renew(other_client, "segunda@ejemplo.test", OTHER_PASSWORD)
    share(recruiter, vacancy_id, other_id, "LECTURA")
    created = export(other_client, kind="POSTULACIONES")
    assert created.status_code == 201 and created.json()["row_count"] == 2
    url = f"{API}/reports/exports/{created.json()['id']}/download"
    assert other_client.get(url).status_code == 200
    # El reporte de otra persona no existe para los demás; sí para un administrador.
    assert recruiter.get(url).status_code == 404
    assert admin.get(url).status_code == 200
    assert recruiter.get(f"{API}/reports/exports").json() == []
    assert recruiter.get(f"{API}/reports/exports/{uuid.uuid4()}/download").status_code == 404

    # Al perder el acceso a la vacante, el reporte ya generado deja de descargarse.
    revoked = recruiter.delete(f"{API}/vacancies/{vacancy_id}/members/{other_id}")
    assert revoked.status_code in (200, 204)
    denied = other_client.get(url)
    assert denied.status_code == 403 and "ya no tienes acceso" in denied.json()["detail"]
    assert export(other_client, kind="POSTULACIONES").json()["row_count"] == 0
