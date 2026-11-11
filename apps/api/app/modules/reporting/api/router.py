"""Tableros, históricos y reportes en Excel."""

from __future__ import annotations

import uuid
from dataclasses import asdict
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated
from urllib.parse import quote

from fastapi import APIRouter, Depends, Query, Request, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.composition.context import AppContext, client_ip, get_context
from app.modules.authentication.api.dependencies import Principal, require_user
from app.modules.reporting.domain.models import (
    DateKind,
    ExportKind,
    ReportExport,
    ReportFilter,
    Viewer,
)

router = APIRouter(tags=["reportes"])

_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


class FilterParams(BaseModel):
    """Filtros comunes. Las fechas son días locales, ambos incluidos."""

    date_from: date | None = None
    date_to: date | None = None
    vacancy_id: uuid.UUID | None = None
    owner_id: uuid.UUID | None = None
    collaborator_id: uuid.UUID | None = None
    department: str | None = Field(default=None, max_length=120)
    vacancy_status: str | None = Field(default=None, max_length=20)
    date_kind: DateKind = DateKind.CARGA
    stage: str | None = Field(default=None, max_length=100)
    candidate: str | None = Field(default=None, max_length=200)
    ai_classification: str | None = Field(default=None, max_length=20)
    score_min: Decimal | None = Field(default=None, ge=0, le=100)
    score_max: Decimal | None = Field(default=None, ge=0, le=100)
    model: str | None = Field(default=None, max_length=200)
    prompt_version_id: uuid.UUID | None = None
    bank_id: uuid.UUID | None = None
    outcome: str | None = Field(default=None, max_length=20)

    def to_filter(self) -> ReportFilter:
        return ReportFilter(**self.model_dump())


class SnapshotOut(BaseModel):
    vacancies: int
    vacancies_open: int
    own: int
    shared: int
    active_applications: int
    in_calls: int
    tests_pending: int
    interviews_pending: int


class TotalsOut(BaseModel):
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


class StageOut(BaseModel):
    name: str
    kind: str
    active: int
    reached: int
    conversion: float | None
    average_days: float | None
    stays: int


class VacancyOut(BaseModel):
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


class RecruiterOut(BaseModel):
    user_id: uuid.UUID
    name: str
    vacancies: int
    vacancies_open: int
    collaborating: int
    active: int
    closed: int
    hires: int


class MonthOut(BaseModel):
    month: str
    cv_analyzed: int
    applications: int
    closed: int
    hires: int
    withdrawals: int


class AiOperationOut(BaseModel):
    operation: str
    calls: int
    failures: int
    cost_usd: Decimal


class AiUsageOut(BaseModel):
    calls: int
    failures: int
    cost_usd: Decimal
    operations: list[AiOperationOut]


class ActivityOut(BaseModel):
    occurred_at: datetime
    kind: str
    candidate: str
    vacancy_id: uuid.UUID
    vacancy: str
    stage: str | None
    actor_name: str | None


class OverviewOut(BaseModel):
    snapshot: SnapshotOut
    totals: TotalsOut
    stages: list[StageOut]
    funnel_hired: int
    vacancies: list[VacancyOut]
    months: list[MonthOut]
    recent: list[ActivityOut]
    # Solo para administradores; vacío para el resto.
    recruiters: list[RecruiterOut] | None
    ai: AiUsageOut | None
    cv_failures: int | None


class HistoryRowOut(BaseModel):
    application_id: uuid.UUID
    vacancy_id: uuid.UUID
    candidate: str
    vacancy: str
    department: str
    owner_name: str
    stage: str
    outcome: str
    outcome_reason: str | None
    ai_classification: str | None
    ai_score: Decimal | None
    model: str | None
    prompt_version: int | None
    created_at: datetime
    cv_uploaded_at: datetime | None
    evaluated_at: datetime | None
    last_movement_at: datetime | None
    closed_at: datetime | None
    closed_by_name: str | None
    start_date: date | None


class HistoryOut(BaseModel):
    rows: list[HistoryRowOut]
    total: int


class OptionOut(BaseModel):
    id: str
    name: str


class OptionsOut(BaseModel):
    vacancies: list[OptionOut]
    owners: list[OptionOut]
    collaborators: list[OptionOut]
    departments: list[str]
    stages: list[str]
    models: list[str]
    prompt_versions: list[OptionOut]
    banks: list[OptionOut]


class ExportIn(FilterParams):
    kind: ExportKind


class ExportOut(BaseModel):
    id: uuid.UUID
    kind: str
    name: str
    filters: dict[str, str]
    row_count: int
    size_bytes: int
    sha256: str
    created_at: datetime

    @classmethod
    def of(cls, export: ReportExport) -> ExportOut:
        return cls(
            id=export.id,
            kind=export.kind.value,
            name=export.name,
            filters=export.filters,
            row_count=export.row_count,
            size_bytes=export.size_bytes,
            sha256=export.sha256,
            created_at=export.created_at,
        )


_user = Depends(require_user)
_context = Depends(get_context)
_Filters = Annotated[FilterParams, Query()]


def _viewer(principal: Principal) -> Viewer:
    return Viewer(user_id=principal.user.id, is_admin=principal.user.is_admin)


@router.get(
    "/reports/overview",
    response_model=OverviewOut,
    summary="Indicadores de las vacantes que la persona puede ver",
)
def get_overview(
    filters: _Filters, principal: Principal = _user, context: AppContext = _context
) -> OverviewOut:
    with context.require_backend().transaction() as repos:
        data = context.reporting(repos).overview(_viewer(principal), filters.to_filter())
    return OverviewOut.model_validate(asdict(data))


@router.get(
    "/reports/applications",
    response_model=HistoryOut,
    summary="Histórico de postulaciones con filtros",
)
def get_history(
    filters: _Filters,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    principal: Principal = _user,
    context: AppContext = _context,
) -> HistoryOut:
    with context.require_backend().transaction() as repos:
        page = context.reporting(repos).history(
            _viewer(principal), filters.to_filter(), limit=limit, offset=offset
        )
    return HistoryOut(
        rows=[HistoryRowOut.model_validate(asdict(row)) for row in page.rows], total=page.total
    )


@router.get("/reports/options", response_model=OptionsOut, summary="Valores para los filtros")
def get_options(principal: Principal = _user, context: AppContext = _context) -> OptionsOut:
    with context.require_backend().transaction() as repos:
        options = context.reporting(repos).options(_viewer(principal))
    return OptionsOut.model_validate(asdict(options))


@router.get(
    "/reports/exports", response_model=list[ExportOut], summary="Reportes que generó la persona"
)
def list_exports(principal: Principal = _user, context: AppContext = _context) -> list[ExportOut]:
    with context.require_backend().transaction() as repos:
        return [ExportOut.of(e) for e in context.reporting(repos).exports(_viewer(principal))]


@router.post(
    "/reports/exports",
    response_model=ExportOut,
    status_code=status.HTTP_201_CREATED,
    summary="Genera un Excel y lo guarda en el servidor",
)
def create_export(
    body: ExportIn,
    request: Request,
    principal: Principal = _user,
    context: AppContext = _context,
) -> ExportOut:
    flt = ReportFilter(**body.model_dump(exclude={"kind"}))
    with context.require_backend().transaction() as repos:
        export = context.reporting(repos).create_export(
            _viewer(principal), principal.user.full_name, body.kind, flt, ip=client_ip(request)
        )
        return ExportOut.of(export)


@router.get("/reports/exports/{export_id}/download", summary="Descarga un reporte generado")
def download_export(
    export_id: uuid.UUID,
    request: Request,
    principal: Principal = _user,
    context: AppContext = _context,
) -> StreamingResponse:
    storage = context.require_storage()
    with context.require_backend().transaction() as repos:
        export = context.reporting(repos).prepare_download(
            _viewer(principal), export_id, ip=client_ip(request)
        )
    return StreamingResponse(
        storage.read_chunks(export.storage_key),
        media_type=_XLSX,
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{quote(export.name)}",
            "Content-Length": str(export.size_bytes),
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "no-store",
        },
    )
