"""Cálculo de indicadores a partir de los hechos. Funciones puras, sin base de datos.

Definiciones (son las que se muestran en pantalla):

- **Hoy**: fotografía del momento; no depende del periodo.
- **En el periodo**: hechos cuya fecha cae entre los dos días elegidos, ambos
  incluidos, contados en la hora local configurada.
- **Embudo**: de las postulaciones dadas de alta en el periodo, cuántas
  llegaron a cada etapa o más allá. La conversión es el paso de una etapa a la
  siguiente.
- **Tiempo por etapa**: promedio de días de las estancias que terminaron en el
  periodo. No cuenta las que duran cero (el paso automático tras evaluar el CV).
- **Tiempo de cobertura**: días desde que se abrió la convocatoria hasta que
  se registró la contratación.
- Una contratación es de su vacante y se cuenta una sola vez; en el reparto
  por persona se atribuye al responsable, no a los colaboradores.
"""

from __future__ import annotations

import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time, timedelta, tzinfo
from decimal import Decimal

from app.modules.reporting.domain.models import (
    ACTIVE_STATUS,
    CLOSING_MOVEMENTS,
    HIRED,
    IN_PROCESS,
    OPEN_VACANCY,
    STAGE_MOVEMENTS,
    WITHDREW,
    ApplicationFact,
    CvFact,
    DateKind,
    Facts,
    MovementFact,
    OutcomeFact,
    ReportFilter,
    StageFact,
    Viewer,
)

_SECONDS_PER_DAY = 86_400
RECENT_ACTIVITY = 12
_TEST_KINDS = ("PSICOMETRIA", "PRUEBA_TECNICA")


@dataclass(frozen=True)
class Period:
    """Intervalo en UTC: desde ``start`` (incluido) hasta ``end`` (excluido)."""

    start: datetime | None = None
    end: datetime | None = None

    def has(self, moment: datetime | None) -> bool:
        if moment is None:
            return False
        if self.start is not None and moment < self.start:
            return False
        return self.end is None or moment < self.end


def period_of(date_from: date | None, date_to: date | None, zone: tzinfo) -> Period:
    """Convierte dos días locales (ambos incluidos) en un intervalo UTC."""

    def start_of(day: date) -> datetime:
        return datetime.combine(day, time.min, tzinfo=zone).astimezone(UTC)

    return Period(
        start=start_of(date_from) if date_from else None,
        end=start_of(date_to + timedelta(days=1)) if date_to else None,
    )


@dataclass(frozen=True)
class Snapshot:
    vacancies: int
    vacancies_open: int
    own: int
    shared: int
    active_applications: int
    in_calls: int
    tests_pending: int
    interviews_pending: int


@dataclass(frozen=True)
class Totals:
    cv_analyzed: int
    ai_accepted: int
    ai_rejected: int
    ai_unevaluable: int
    applications: int
    closed: int
    hires: int
    withdrawals: int
    not_hired: int
    not_located: int
    cancelled: int
    other_closures: int
    coverage_days: float | None


@dataclass(frozen=True)
class StageRow:
    name: str
    kind: str
    # Postulaciones activas que hoy están en la etapa.
    active: int
    # Del grupo dado de alta en el periodo, cuántas llegaron aquí o más allá.
    reached: int
    # Porcentaje que pasó de esta etapa a la siguiente.
    conversion: float | None
    average_days: float | None
    stays: int


@dataclass(frozen=True)
class VacancyRow:
    id: uuid.UUID
    name: str
    department: str
    status: str
    owner_name: str
    positions: int
    hires_total: int
    active: int
    cv_analyzed: int
    applications: int
    closed: int
    hires: int
    coverage_days: float | None


@dataclass(frozen=True)
class RecruiterRow:
    user_id: uuid.UUID
    name: str
    vacancies: int
    vacancies_open: int
    # Vacantes de otras personas en las que colabora (solo informativo).
    collaborating: int
    active: int
    closed: int
    hires: int


@dataclass(frozen=True)
class MonthRow:
    month: str
    cv_analyzed: int
    applications: int
    closed: int
    hires: int
    withdrawals: int


@dataclass(frozen=True)
class AiOperationRow:
    operation: str
    calls: int
    failures: int
    cost_usd: Decimal


@dataclass(frozen=True)
class AiUsage:
    calls: int
    failures: int
    cost_usd: Decimal
    operations: list[AiOperationRow]


@dataclass(frozen=True)
class Activity:
    occurred_at: datetime
    kind: str
    candidate: str
    vacancy_id: uuid.UUID
    vacancy: str
    stage: str | None
    actor_name: str | None


@dataclass(frozen=True)
class Overview:
    snapshot: Snapshot
    totals: Totals
    stages: list[StageRow]
    # Del grupo del embudo, cuántas terminaron contratadas.
    funnel_hired: int
    vacancies: list[VacancyRow]
    months: list[MonthRow]
    recent: list[Activity]
    # Solo para administradores.
    recruiters: list[RecruiterRow] | None = None
    ai: AiUsage | None = None
    cv_failures: int | None = None


@dataclass(frozen=True)
class HistoryRow:
    application_id: uuid.UUID
    vacancy_id: uuid.UUID
    candidate: str
    vacancy: str
    department: str
    owner_name: str
    stage: str
    outcome: str
    created_at: datetime
    outcome_reason: str | None = None
    ai_classification: str | None = None
    ai_score: Decimal | None = None
    model: str | None = None
    prompt_version: int | None = None
    cv_uploaded_at: datetime | None = None
    evaluated_at: datetime | None = None
    last_movement_at: datetime | None = None
    closed_at: datetime | None = None
    closed_by_name: str | None = None
    start_date: date | None = None


@dataclass
class _Journey:
    """Recorrido de una postulación por las etapas, según sus movimientos."""

    entered: set[uuid.UUID] = field(default_factory=set)
    # (etapa, entrada, salida) de las estancias ya terminadas.
    stays: list[tuple[uuid.UUID, datetime, datetime]] = field(default_factory=list)
    moments: list[datetime] = field(default_factory=list)

    @property
    def last_movement_at(self) -> datetime | None:
        return self.moments[-1] if self.moments else None


def _journeys(movements: list[MovementFact]) -> dict[uuid.UUID, _Journey]:
    grouped: dict[uuid.UUID, list[MovementFact]] = defaultdict(list)
    for movement in movements:
        grouped[movement.application_id].append(movement)
    journeys: dict[uuid.UUID, _Journey] = {}
    for application_id, items in grouped.items():
        journey = _Journey()
        current: uuid.UUID | None = None
        since: datetime | None = None
        for m in sorted(items, key=lambda item: item.sequence):
            journey.moments.append(m.occurred_at)
            if m.kind == "ALTA" and m.to_stage_id is not None:
                current, since = m.to_stage_id, m.occurred_at
                journey.entered.add(current)
            elif m.kind in STAGE_MOVEMENTS and m.to_stage_id is not None:
                if current is not None and since is not None:
                    journey.stays.append((current, since, m.occurred_at))
                current, since = m.to_stage_id, m.occurred_at
                journey.entered.add(current)
            elif m.kind in CLOSING_MOVEMENTS:
                if current is not None and since is not None:
                    journey.stays.append((current, since, m.occurred_at))
                since = None
            elif m.kind == "REACTIVACION":
                since = m.occurred_at
        journeys[application_id] = journey
    return journeys


def _stage_key(stage: StageFact) -> tuple[str, str]:
    return stage.kind, stage.name.casefold()


def _average(values: list[float]) -> float | None:
    return round(sum(values) / len(values), 1) if values else None


def _days(start: datetime, end: datetime) -> float:
    return (end - start).total_seconds() / _SECONDS_PER_DAY


def _month(moment: datetime, zone: tzinfo) -> str:
    return moment.astimezone(zone).strftime("%Y-%m")


def overview(
    facts: Facts, period: Period, viewer: Viewer, *, zone: tzinfo, months_limit: int = 36
) -> Overview:
    vacancies = {v.id: v for v in facts.vacancies}
    applications = [a for a in facts.applications if a.vacancy_id in vacancies]
    by_id = {a.id: a for a in applications}
    outcomes = [o for o in facts.outcomes if o.application_id in by_id]
    journeys = _journeys([m for m in facts.movements if m.application_id in by_id])
    stages = facts.stages
    active = [a for a in applications if a.status == ACTIVE_STATUS]

    def active_in(*kinds: str) -> int:
        return sum(1 for a in active if stages[a.stage_id].kind in kinds)

    snapshot = Snapshot(
        vacancies=len(vacancies),
        vacancies_open=sum(1 for v in vacancies.values() if v.status == OPEN_VACANCY),
        own=sum(1 for v in vacancies.values() if v.owner_id == viewer.user_id),
        shared=sum(1 for v in vacancies.values() if viewer.user_id in v.collaborators),
        active_applications=len(active),
        in_calls=active_in("LLAMADA"),
        tests_pending=active_in(*_TEST_KINDS),
        interviews_pending=active_in("ENTREVISTA"),
    )

    evaluated = [c for c in facts.cvs if c.classification and period.has(c.updated_at)]
    created = [a for a in applications if period.has(a.created_at)]
    closed = [o for o in outcomes if period.has(o.recorded_at)]
    hires = [o for o in closed if o.outcome == HIRED]

    def coverage(items: list[OutcomeFact]) -> float | None:
        return _average(
            [_days(by_id[o.application_id].campaign_opened_at, o.recorded_at) for o in items]
        )

    def closed_as(kind: str) -> int:
        return sum(1 for o in closed if o.outcome == kind)

    totals = Totals(
        cv_analyzed=len(evaluated),
        ai_accepted=sum(1 for c in evaluated if c.classification == "ACEPTADO_IA"),
        ai_rejected=sum(1 for c in evaluated if c.classification == "RECHAZADO_IA"),
        ai_unevaluable=sum(1 for c in evaluated if c.classification == "NO_EVALUABLE"),
        applications=len(created),
        closed=len(closed),
        hires=len(hires),
        withdrawals=closed_as(WITHDREW),
        not_hired=closed_as("NO_CONTRATADO"),
        not_located=closed_as("NO_LOCALIZADO"),
        cancelled=closed_as("VACANTE_CANCELADA"),
        other_closures=closed_as("OTRO_CIERRE"),
        coverage_days=coverage(hires),
    )

    # --- Etapas: fotografía, embudo y tiempos -------------------------------------------
    by_pipeline: dict[uuid.UUID, list[StageFact]] = defaultdict(list)
    for stage in stages.values():
        by_pipeline[stage.pipeline_version_id].append(stage)
    labels: dict[tuple[str, str], str] = {}
    positions: dict[tuple[str, str], list[int]] = defaultdict(list)
    active_now: dict[tuple[str, str], int] = defaultdict(int)
    reached: dict[tuple[str, str], int] = defaultdict(int)
    durations: dict[tuple[str, str], list[float]] = defaultdict(list)

    def seen(stage: StageFact) -> tuple[str, str]:
        key = _stage_key(stage)
        labels.setdefault(key, stage.name)
        positions[key].append(stage.position)
        return key

    # Todas las etapas de los procesos en uso aparecen, aunque nadie haya llegado.
    for pipeline_id in {stages[a.stage_id].pipeline_version_id for a in applications}:
        for stage in by_pipeline[pipeline_id]:
            seen(stage)
    for application in active:
        active_now[seen(stages[application.stage_id])] += 1
    for application in created:
        journey = journeys.get(application.id)
        entered = (journey.entered if journey else set()) | {application.stage_id}
        furthest = max(stages[stage_id].position for stage_id in entered)
        pipeline = stages[application.stage_id].pipeline_version_id
        for stage in by_pipeline[pipeline]:
            if stage.position <= furthest:
                reached[seen(stage)] += 1
    for journey in journeys.values():
        for stage_id, start, end in journey.stays:
            if end > start and period.has(end):
                durations[seen(stages[stage_id])].append(_days(start, end))

    ordered = sorted(labels, key=lambda key: (sum(positions[key]) / len(positions[key]), key[1]))
    stage_rows: list[StageRow] = []
    for index, key in enumerate(ordered):
        following = reached[ordered[index + 1]] if index + 1 < len(ordered) else None
        stage_rows.append(
            StageRow(
                name=labels[key],
                kind=key[0],
                active=active_now[key],
                reached=reached[key],
                conversion=round(100 * following / reached[key], 1)
                if following is not None and reached[key]
                else None,
                average_days=_average(durations[key]),
                stays=len(durations[key]),
            )
        )
    created_ids = {a.id for a in created}
    funnel_hired = sum(
        1 for o in outcomes if o.outcome == HIRED and o.application_id in created_ids
    )

    # --- Por vacante y por persona -------------------------------------------------------
    def per_vacancy(
        items: list[CvFact] | list[ApplicationFact] | list[OutcomeFact],
    ) -> dict[uuid.UUID, int]:
        counts: dict[uuid.UUID, int] = defaultdict(int)
        for item in items:
            counts[item.vacancy_id] += 1
        return counts

    cv_by, created_by, closed_by, hires_by, active_by = (
        per_vacancy(evaluated),
        per_vacancy(created),
        per_vacancy(closed),
        per_vacancy(hires),
        per_vacancy(active),
    )
    hires_total = per_vacancy([o for o in outcomes if o.outcome == HIRED])
    vacancy_rows = [
        VacancyRow(
            id=v.id,
            name=v.name,
            department=v.department,
            status=v.status,
            owner_name=v.owner_name,
            positions=v.positions,
            hires_total=hires_total[v.id],
            active=active_by[v.id],
            cv_analyzed=cv_by[v.id],
            applications=created_by[v.id],
            closed=closed_by[v.id],
            hires=hires_by[v.id],
            coverage_days=coverage([o for o in hires if o.vacancy_id == v.id]),
        )
        for v in sorted(vacancies.values(), key=lambda v: (v.name.casefold(), str(v.id)))
    ]

    recruiters: list[RecruiterRow] | None = None
    if viewer.is_admin:
        owners: dict[uuid.UUID, str] = {v.owner_id: v.owner_name for v in vacancies.values()}
        collaborating: dict[uuid.UUID, int] = defaultdict(int)
        for v in vacancies.values():
            for user_id in v.collaborators:
                collaborating[user_id] += 1
        recruiters = sorted(
            (
                RecruiterRow(
                    user_id=owner_id,
                    name=name,
                    vacancies=sum(1 for v in vacancies.values() if v.owner_id == owner_id),
                    vacancies_open=sum(
                        1
                        for v in vacancies.values()
                        if v.owner_id == owner_id and v.status == OPEN_VACANCY
                    ),
                    collaborating=collaborating[owner_id],
                    active=sum(1 for a in active if vacancies[a.vacancy_id].owner_id == owner_id),
                    closed=sum(1 for o in closed if vacancies[o.vacancy_id].owner_id == owner_id),
                    hires=sum(1 for o in hires if vacancies[o.vacancy_id].owner_id == owner_id),
                )
                for owner_id, name in owners.items()
            ),
            key=lambda row: (-row.active, row.name.casefold()),
        )

    # --- Histórico mensual ----------------------------------------------------------------
    monthly: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for cv in evaluated:
        monthly[_month(cv.updated_at, zone)]["cv_analyzed"] += 1
    for application in created:
        monthly[_month(application.created_at, zone)]["applications"] += 1
    for outcome in closed:
        bucket = monthly[_month(outcome.recorded_at, zone)]
        bucket["closed"] += 1
        if outcome.outcome == HIRED:
            bucket["hires"] += 1
        elif outcome.outcome == WITHDREW:
            bucket["withdrawals"] += 1
    months = [
        MonthRow(
            month=month,
            cv_analyzed=values["cv_analyzed"],
            applications=values["applications"],
            closed=values["closed"],
            hires=values["hires"],
            withdrawals=values["withdrawals"],
        )
        for month, values in sorted(monthly.items())
    ][-months_limit:]

    # --- Actividad reciente ---------------------------------------------------------------
    latest = sorted(
        (m for m in facts.movements if m.application_id in by_id),
        key=lambda m: (m.occurred_at, m.sequence),
        reverse=True,
    )[:RECENT_ACTIVITY]
    recent = []
    for m in latest:
        application = by_id[m.application_id]
        stage_id = m.to_stage_id or m.from_stage_id
        recent.append(
            Activity(
                occurred_at=m.occurred_at,
                kind=m.kind,
                candidate=application.candidate_name,
                vacancy_id=application.vacancy_id,
                vacancy=vacancies[application.vacancy_id].name,
                stage=stages[stage_id].name if stage_id in stages else None,
                actor_name=m.actor_name,
            )
        )

    ai: AiUsage | None = None
    cv_failures: int | None = None
    if viewer.is_admin:
        operations: dict[str, list[int | Decimal]] = defaultdict(lambda: [0, 0, Decimal(0)])
        for execution in facts.ai:
            row = operations[execution.operation]
            row[0] += 1
            row[1] += 0 if execution.ok else 1
            row[2] += execution.cost_usd or Decimal(0)
        rows = [
            AiOperationRow(operation, int(calls), int(failures), Decimal(cost))
            for operation, (calls, failures, cost) in sorted(operations.items())
        ]
        ai = AiUsage(
            calls=sum(row.calls for row in rows),
            failures=sum(row.failures for row in rows),
            cost_usd=sum((row.cost_usd for row in rows), Decimal(0)),
            operations=rows,
        )
        cv_failures = sum(
            1 for c in facts.cvs if c.status == "FALLIDO" and period.has(c.updated_at)
        )

    return Overview(
        snapshot=snapshot,
        totals=totals,
        stages=stage_rows,
        funnel_hired=funnel_hired,
        vacancies=vacancy_rows,
        months=months,
        recent=recent,
        recruiters=recruiters,
        ai=ai,
        cv_failures=cv_failures,
    )


def _history_date(
    kind: DateKind,
    application: ApplicationFact,
    journey: _Journey | None,
    closed_at: datetime | None,
) -> datetime | None:
    if kind is DateKind.EVALUACION:
        return application.evaluated_at
    if kind is DateKind.MOVIMIENTO:
        return journey.last_movement_at if journey else None
    if kind is DateKind.CIERRE:
        return closed_at
    return application.cv_uploaded_at or application.created_at


def history(
    facts: Facts,
    flt: ReportFilter,
    period: Period,
    *,
    with_bank: set[uuid.UUID] | None = None,
) -> list[HistoryRow]:
    """Postulaciones que cumplen los filtros, de la fecha más reciente a la más antigua.

    ``with_bank``: postulaciones con una llamada hecha con el banco de preguntas
    pedido; ``None`` si no se filtró por banco.
    """
    vacancies = {v.id: v for v in facts.vacancies}
    outcomes = {o.application_id: o for o in facts.outcomes}
    journeys = _journeys(facts.movements)
    bounded = period.start is not None or period.end is not None
    needle = (flt.candidate or "").strip().casefold()
    stage_name = (flt.stage or "").strip().casefold()
    rows: list[tuple[datetime, HistoryRow]] = []
    for application in facts.applications:
        vacancy = vacancies.get(application.vacancy_id)
        if vacancy is None:
            continue
        outcome = outcomes.get(application.id)
        journey = journeys.get(application.id)
        stage = facts.stages[application.stage_id]
        result = outcome.outcome if outcome and application.status != ACTIVE_STATUS else IN_PROCESS
        if application.status != ACTIVE_STATUS and outcome is None:
            # Cerrada antes de que existieran los resultados finales.
            result = "OTRO_CIERRE"
        closed_at = outcome.recorded_at if outcome and result != IN_PROCESS else None
        moment = _history_date(flt.date_kind, application, journey, closed_at)
        if flt.date_kind is DateKind.MOVIMIENTO and bounded:
            # Basta con que algún movimiento caiga en el periodo.
            if not journey or not any(period.has(at) for at in journey.moments):
                continue
        elif bounded and not period.has(moment):
            continue
        if needle and needle not in application.candidate_name.casefold():
            continue
        if stage_name and stage.name.casefold() != stage_name:
            continue
        if flt.ai_classification and application.ai_classification != flt.ai_classification:
            continue
        if flt.score_min is not None and (
            application.ai_score is None or application.ai_score < flt.score_min
        ):
            continue
        if flt.score_max is not None and (
            application.ai_score is None or application.ai_score > flt.score_max
        ):
            continue
        if flt.model and application.model != flt.model:
            continue
        if flt.prompt_version_id and application.prompt_version_id != flt.prompt_version_id:
            continue
        if with_bank is not None and application.id not in with_bank:
            continue
        if flt.outcome and result != flt.outcome:
            continue
        rows.append(
            (
                moment or application.created_at,
                HistoryRow(
                    application_id=application.id,
                    vacancy_id=vacancy.id,
                    candidate=application.candidate_name,
                    vacancy=vacancy.name,
                    department=vacancy.department,
                    owner_name=vacancy.owner_name,
                    stage=stage.name,
                    outcome=result,
                    created_at=application.created_at,
                    outcome_reason=outcome.reason if closed_at else None,
                    ai_classification=application.ai_classification,
                    ai_score=application.ai_score,
                    model=application.model,
                    prompt_version=application.prompt_version_number,
                    cv_uploaded_at=application.cv_uploaded_at,
                    evaluated_at=application.evaluated_at,
                    last_movement_at=journey.last_movement_at if journey else None,
                    closed_at=closed_at,
                    closed_by_name=outcome.recorded_by_name if closed_at and outcome else None,
                    start_date=outcome.start_date if closed_at and outcome else None,
                ),
            )
        )
    rows.sort(key=lambda pair: (pair[0], str(pair[1].application_id)), reverse=True)
    return [row for _, row in rows]


def default_range(today: date, days: int) -> tuple[date, date]:
    return today - timedelta(days=days - 1), today
