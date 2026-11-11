"""Candidatos, postulaciones, convocatorias y etapas."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from fastapi import APIRouter, Depends, Query, Request, status
from pydantic import BaseModel, Field

from app.composition.backend import Repositories
from app.composition.context import AppContext, client_ip, get_context
from app.modules.authentication.api.dependencies import Principal, require_admin, require_user
from app.modules.recruitment.application.service import ApplicationDetail, ApplicationView, Board
from app.modules.recruitment.domain.models import (
    Campaign,
    Movement,
    MovementKind,
    PipelineVersion,
    StageKind,
)

router = APIRouter(tags=["reclutamiento"])


class StageIn(BaseModel):
    name: str = Field(max_length=100)
    kind: StageKind
    is_optional: bool = False


class PipelineIn(BaseModel):
    stages: list[StageIn]
    expected_version: int


class StageOut(BaseModel):
    id: uuid.UUID
    position: int
    name: str
    kind: str
    is_optional: bool


class PipelineOut(BaseModel):
    id: uuid.UUID
    version_number: int
    created_at: datetime
    stages: list[StageOut]

    @classmethod
    def of(cls, version: PipelineVersion) -> PipelineOut:
        return cls(
            id=version.id,
            version_number=version.version_number,
            created_at=version.created_at,
            stages=[
                StageOut(
                    id=s.id,
                    position=s.position,
                    name=s.name,
                    kind=s.kind.value,
                    is_optional=s.is_optional,
                )
                for s in version.stages
            ],
        )


class CampaignOut(BaseModel):
    id: uuid.UUID
    number: int
    name: str
    status: str
    opened_at: datetime
    closed_at: datetime | None

    @classmethod
    def of(cls, campaign: Campaign) -> CampaignOut:
        return cls(
            id=campaign.id,
            number=campaign.number,
            name=campaign.name,
            status=campaign.status.value,
            opened_at=campaign.opened_at,
            closed_at=campaign.closed_at,
        )


class ApplicationOut(BaseModel):
    id: uuid.UUID
    candidate_id: uuid.UUID
    full_name: str
    email: str | None
    phone: str | None
    stage_id: uuid.UUID
    status: str
    ai_classification: str | None
    ai_score: Decimal | None
    cv_file_id: uuid.UUID | None
    due_at: datetime | None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def of(cls, view: ApplicationView) -> ApplicationOut:
        application, candidate = view.application, view.candidate
        return cls(
            id=application.id,
            candidate_id=candidate.id,
            full_name=candidate.full_name,
            email=candidate.email,
            phone=candidate.phone,
            stage_id=application.stage_id,
            status=application.status.value,
            ai_classification=application.ai_classification,
            ai_score=application.ai_score,
            cv_file_id=application.cv_file_id,
            due_at=application.due_at,
            created_at=application.created_at,
            updated_at=application.updated_at,
        )


class BoardOut(BaseModel):
    campaigns: list[CampaignOut]
    campaign: CampaignOut | None
    pipeline: PipelineOut | None
    applications: list[ApplicationOut]

    @classmethod
    def of(cls, board: Board) -> BoardOut:
        return cls(
            campaigns=[CampaignOut.of(c) for c in board.campaigns],
            campaign=CampaignOut.of(board.campaign) if board.campaign else None,
            pipeline=PipelineOut.of(board.pipeline) if board.pipeline else None,
            applications=[ApplicationOut.of(view) for view in board.applications],
        )


class CandidateIn(BaseModel):
    full_name: str = Field(max_length=200)
    email: str | None = Field(default=None, max_length=254)
    phone: str | None = Field(default=None, max_length=40)


class NewApplicationIn(CandidateIn):
    cv_file_id: uuid.UUID | None = None


class CampaignIn(BaseModel):
    name: str | None = Field(default=None, max_length=100)


class MoveIn(BaseModel):
    application_ids: list[uuid.UUID] = Field(min_length=1)
    to_stage_id: uuid.UUID
    note: str | None = Field(default=None, max_length=500)


class StatusIn(BaseModel):
    action: Literal["DESISTIMIENTO", "DESCARTE", "CANCELACION", "REACTIVACION"]
    note: str = Field(max_length=500)


class NoteIn(BaseModel):
    note: str = Field(max_length=500)
    # Con fecha es una reprogramación; sin ella, una incidencia.
    due_at: datetime | None = None


class MovementOut(BaseModel):
    id: uuid.UUID
    kind: str
    occurred_at: datetime
    # Vacío cuando lo hizo el sistema.
    actor_name: str | None
    from_stage: str | None
    to_stage: str | None
    note: str | None
    due_at: datetime | None
    mass: bool


class JobOut(BaseModel):
    title: str
    company: str
    start: str
    end: str
    current: bool
    months: int | None
    approximate: bool


class TenureOut(BaseModel):
    jobs: list[JobOut]
    average_months: float | None
    median_months: float | None
    total_months: int
    overlaps: int
    incomplete: int


class EvaluationOut(BaseModel):
    classification: str
    score: Decimal | None
    file_name: str
    # Niveles, evidencias y motivo, como los dejó la evaluación inicial.
    result: dict[str, Any]
    # Datos ordenados del CV (estudios, habilidades, etc.).
    extraction: dict[str, Any]


class ApplicationDetailOut(BaseModel):
    application: ApplicationOut
    campaign: CampaignOut
    pipeline: PipelineOut
    movements: list[MovementOut]
    evaluation: EvaluationOut | None
    tenure: TenureOut | None


def _detail_out(repos: Repositories, detail: ApplicationDetail) -> ApplicationDetailOut:
    stages = {stage.id: stage.name for stage in detail.pipeline.stages}
    actors = {m.actor_user_id for m in detail.movements if m.actor_user_id}
    names = {uid: user.full_name for uid, user in repos.users.get_many(list(actors)).items()}

    def movement(m: Movement) -> MovementOut:
        return MovementOut(
            id=m.id,
            kind=m.kind.value,
            occurred_at=m.occurred_at,
            actor_name=names.get(m.actor_user_id) if m.actor_user_id else None,
            from_stage=stages.get(m.from_stage_id) if m.from_stage_id else None,
            to_stage=stages.get(m.to_stage_id) if m.to_stage_id else None,
            note=m.note,
            due_at=m.due_at,
            mass=m.group_id is not None,
        )

    evaluation, summary = detail.evaluation, detail.tenure
    return ApplicationDetailOut(
        application=ApplicationOut.of(detail.view),
        campaign=CampaignOut.of(detail.campaign),
        pipeline=PipelineOut.of(detail.pipeline),
        movements=[movement(m) for m in detail.movements],
        evaluation=EvaluationOut(
            classification=evaluation.classification,
            score=evaluation.score,
            file_name=evaluation.file_name,
            result=evaluation.result,
            extraction=evaluation.extraction,
        )
        if evaluation
        else None,
        tenure=TenureOut(
            jobs=[JobOut(**job.__dict__) for job in summary.jobs],
            average_months=summary.average_months,
            median_months=summary.median_months,
            total_months=summary.total_months,
            overlaps=summary.overlaps,
            incomplete=summary.incomplete,
        )
        if summary
        else None,
    )


_user = Depends(require_user)
_admin = Depends(require_admin)
_context = Depends(get_context)


@router.get("/pipeline", response_model=PipelineOut, summary="Etapas vigentes del proceso")
def get_pipeline(_: Principal = _user, context: AppContext = _context) -> PipelineOut:
    with context.require_backend().transaction() as repos:
        return PipelineOut.of(context.recruitment(repos).current_pipeline())


@router.put(
    "/pipeline",
    response_model=PipelineOut,
    summary="Guarda las etapas como una versión nueva (solo administradores)",
)
def save_pipeline(
    body: PipelineIn,
    request: Request,
    principal: Principal = _admin,
    context: AppContext = _context,
) -> PipelineOut:
    with context.require_backend().transaction() as repos:
        version = context.recruitment(repos).save_pipeline(
            principal.user,
            [stage.model_dump() for stage in body.stages],
            expected_version=body.expected_version,
            ip=client_ip(request),
        )
    return PipelineOut.of(version)


@router.get(
    "/vacancies/{vacancy_id}/applications",
    response_model=BoardOut,
    summary="Postulaciones de una convocatoria de la vacante, con sus etapas",
)
def get_board(
    vacancy_id: uuid.UUID,
    campaign_id: uuid.UUID | None = Query(default=None),  # noqa: B008
    principal: Principal = _user,
    context: AppContext = _context,
) -> BoardOut:
    with context.require_backend().transaction() as repos:
        return BoardOut.of(
            context.recruitment(repos).board(principal.user, vacancy_id, campaign_id)
        )


@router.post(
    "/vacancies/{vacancy_id}/applications",
    response_model=ApplicationDetailOut,
    status_code=status.HTTP_201_CREATED,
    summary="Alta manual de un candidato en la convocatoria abierta",
)
def add_candidate(
    vacancy_id: uuid.UUID,
    body: NewApplicationIn,
    request: Request,
    principal: Principal = _user,
    context: AppContext = _context,
) -> ApplicationDetailOut:
    with context.require_backend().transaction() as repos:
        service = context.recruitment(repos)
        application = service.add_candidate(
            principal.user, vacancy_id, **body.model_dump(), ip=client_ip(request)
        )
        return _detail_out(repos, service.detail(principal.user, application.id))


@router.post(
    "/vacancies/{vacancy_id}/campaigns",
    response_model=CampaignOut,
    status_code=status.HTTP_201_CREATED,
    summary="Abre una convocatoria nueva con las etapas vigentes",
)
def open_campaign(
    vacancy_id: uuid.UUID,
    body: CampaignIn,
    request: Request,
    principal: Principal = _user,
    context: AppContext = _context,
) -> CampaignOut:
    with context.require_backend().transaction() as repos:
        return CampaignOut.of(
            context.recruitment(repos).open_campaign(
                principal.user, vacancy_id, body.name, ip=client_ip(request)
            )
        )


@router.post(
    "/campaigns/{campaign_id}/close", response_model=CampaignOut, summary="Cierra la convocatoria"
)
def close_campaign(
    campaign_id: uuid.UUID,
    request: Request,
    principal: Principal = _user,
    context: AppContext = _context,
) -> CampaignOut:
    with context.require_backend().transaction() as repos:
        return CampaignOut.of(
            context.recruitment(repos).close_campaign(
                principal.user, campaign_id, ip=client_ip(request)
            )
        )


@router.post(
    "/vacancies/{vacancy_id}/application-moves",
    response_model=list[ApplicationOut],
    summary="Mueve una o varias postulaciones a una etapa",
)
def move_applications(
    vacancy_id: uuid.UUID,
    body: MoveIn,
    request: Request,
    principal: Principal = _user,
    context: AppContext = _context,
) -> list[ApplicationOut]:
    with context.require_backend().transaction() as repos:
        service = context.recruitment(repos)
        moved = service.move(
            principal.user,
            vacancy_id,
            body.application_ids,
            body.to_stage_id,
            note=body.note,
            ip=client_ip(request),
        )
        candidates = repos.recruitment.candidates([a.candidate_id for a in moved])
        return [ApplicationOut.of(ApplicationView(a, candidates[a.candidate_id])) for a in moved]


@router.get(
    "/applications/{application_id}",
    response_model=ApplicationDetailOut,
    summary="Expediente de una postulación",
)
def get_application(
    application_id: uuid.UUID, principal: Principal = _user, context: AppContext = _context
) -> ApplicationDetailOut:
    with context.require_backend().transaction() as repos:
        return _detail_out(repos, context.recruitment(repos).detail(principal.user, application_id))


@router.put(
    "/applications/{application_id}/candidate",
    response_model=ApplicationDetailOut,
    summary="Corrige los datos de la persona",
)
def update_candidate(
    application_id: uuid.UUID,
    body: CandidateIn,
    request: Request,
    principal: Principal = _user,
    context: AppContext = _context,
) -> ApplicationDetailOut:
    with context.require_backend().transaction() as repos:
        service = context.recruitment(repos)
        service.update_candidate(
            principal.user, application_id, **body.model_dump(), ip=client_ip(request)
        )
        return _detail_out(repos, service.detail(principal.user, application_id))


@router.post(
    "/applications/{application_id}/status",
    response_model=ApplicationDetailOut,
    summary="Desistimiento, descarte, cancelación o reactivación, con motivo",
)
def change_status(
    application_id: uuid.UUID,
    body: StatusIn,
    request: Request,
    principal: Principal = _user,
    context: AppContext = _context,
) -> ApplicationDetailOut:
    with context.require_backend().transaction() as repos:
        service = context.recruitment(repos)
        service.change_status(
            principal.user,
            application_id,
            MovementKind(body.action),
            note=body.note,
            ip=client_ip(request),
        )
        return _detail_out(repos, service.detail(principal.user, application_id))


@router.post(
    "/applications/{application_id}/notes",
    response_model=ApplicationDetailOut,
    summary="Registra una incidencia o reprograma la etapa actual",
)
def annotate(
    application_id: uuid.UUID,
    body: NoteIn,
    request: Request,
    principal: Principal = _user,
    context: AppContext = _context,
) -> ApplicationDetailOut:
    with context.require_backend().transaction() as repos:
        service = context.recruitment(repos)
        service.annotate(
            principal.user,
            application_id,
            note=body.note,
            due_at=body.due_at,
            reschedule=body.due_at is not None,
            ip=client_ip(request),
        )
        return _detail_out(repos, service.detail(principal.user, application_id))
