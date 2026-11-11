"""Evaluación de CV por lotes.

El Excel y los ZIP se descargan con la ruta general de documentos
(``/files/{id}/download``), que evalúa el permiso en ese momento.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, Request, status
from pydantic import BaseModel

from app.composition.context import AppContext, client_ip, get_context
from app.modules.authentication.api.dependencies import Principal, require_user
from app.modules.cv_processing.application.service import BatchView, ItemView, Overview
from app.modules.cv_processing.domain.models import ItemStatus

logger = logging.getLogger(__name__)
router = APIRouter(tags=["evaluación de CV"])


class BatchIn(BaseModel):
    # Volver a evaluar también los CV ya evaluados con el prompt vigente.
    reevaluate: bool = False


class BatchOut(BaseModel):
    id: uuid.UUID
    vacancy_id: uuid.UUID
    status: str
    # En curso según su estado, pero sin ningún proceso atendiéndolo.
    stalled: bool
    total: int
    evaluated: int
    failed: int
    pending: int
    accepted: int
    rejected: int
    unevaluable: int
    error: str | None
    created_at: datetime
    created_by_name: str | None
    started_at: datetime | None
    finished_at: datetime | None
    report_file_id: uuid.UUID | None
    accepted_zip_file_id: uuid.UUID | None
    rejected_zip_file_id: uuid.UUID | None
    unevaluable_zip_file_id: uuid.UUID | None

    @classmethod
    def of(cls, view: BatchView, names: dict[uuid.UUID, str]) -> BatchOut:
        batch, counts = view.batch, view.counts
        return cls(
            id=batch.id,
            vacancy_id=batch.vacancy_id,
            status=batch.status.value,
            stalled=view.stalled,
            total=batch.total,
            evaluated=counts.get("EVALUADO", 0),
            failed=counts.get("FALLIDO", 0),
            pending=counts.get("PENDIENTE", 0),
            accepted=counts.get("ACEPTADO_IA", 0),
            rejected=counts.get("RECHAZADO_IA", 0),
            unevaluable=counts.get("NO_EVALUABLE", 0),
            error=batch.error,
            created_at=batch.created_at,
            created_by_name=names.get(batch.created_by),
            started_at=batch.started_at,
            finished_at=batch.finished_at,
            report_file_id=batch.report_file_id,
            accepted_zip_file_id=batch.accepted_zip_file_id,
            rejected_zip_file_id=batch.rejected_zip_file_id,
            unevaluable_zip_file_id=batch.unevaluable_zip_file_id,
        )


class ApprovedPromptOut(BaseModel):
    id: uuid.UUID
    version_number: int
    pass_threshold: Decimal
    criteria: int


class OverviewOut(BaseModel):
    approved_prompt: ApprovedPromptOut | None
    total_cvs: int
    # CV que aún no se han evaluado con el prompt aprobado vigente.
    pending_cvs: int
    batches: list[BatchOut]


class CriterionResultOut(BaseModel):
    code: str
    level: int | None
    no_evidence: bool
    evidence: str
    justification: str


class ItemOut(BaseModel):
    id: uuid.UUID
    file_id: uuid.UUID
    file_name: str
    position: int
    status: str
    step: str
    classification: str | None
    score: Decimal | None
    reason: str | None
    notes: str | None
    quality: dict[str, int] | None
    digitization_suspect: bool
    truncated: bool
    duplicate: bool
    error_code: str | None
    error_message: str | None
    attempts: int
    criteria: list[CriterionResultOut]

    @classmethod
    def of(cls, view: ItemView) -> ItemOut:
        item = view.item
        result = item.result or {}
        return cls(
            id=item.id,
            file_id=item.file_id,
            file_name=view.file_name,
            position=item.position,
            status=item.status.value,
            step=item.step.value,
            classification=item.classification.value if item.classification else None,
            score=item.score,
            reason=result.get("motivo"),
            notes=result.get("observaciones"),
            quality=result.get("calidad"),
            digitization_suspect=bool(result.get("posible_error_de_digitalizacion")),
            truncated=bool(result.get("texto_recortado")),
            duplicate=item.duplicate_of is not None,
            error_code=item.error_code if item.status is ItemStatus.FALLIDO else None,
            error_message=item.error_message if item.status is ItemStatus.FALLIDO else None,
            attempts=item.attempts,
            criteria=[
                CriterionResultOut(
                    code=str(c.get("id")),
                    level=c.get("nivel"),
                    no_evidence=bool(c.get("sin_evidencia")),
                    evidence=str(c.get("evidencia") or ""),
                    justification=str(c.get("justificacion") or ""),
                )
                for c in result.get("criterios") or []
            ],
        )


class BatchDetailOut(BaseModel):
    batch: BatchOut
    items: list[ItemOut]


def _names(repos, views: list[BatchView]) -> dict[uuid.UUID, str]:  # noqa: ANN001
    users = repos.users.get_many(list({view.batch.created_by for view in views}))
    return {user_id: user.full_name for user_id, user in users.items()}


def _overview_out(overview: Overview, names: dict[uuid.UUID, str]) -> OverviewOut:
    rubric = overview.rubric
    return OverviewOut(
        approved_prompt=ApprovedPromptOut(
            id=rubric.prompt_version_id,
            version_number=rubric.version_number,
            pass_threshold=rubric.threshold,
            criteria=len(rubric.criteria),
        )
        if rubric
        else None,
        total_cvs=overview.total_cvs,
        pending_cvs=overview.pending_cvs,
        batches=[BatchOut.of(view, names) for view in overview.batches],
    )


def _dispatch(context: AppContext, batch_id: uuid.UUID) -> None:
    """Entrega el lote, ya confirmado, para procesarlo. Si la cola no está
    disponible, el lote queda detenido con el motivo y se puede reanudar."""
    try:
        context.dispatch_cv_batch(batch_id)
    except Exception:
        logger.exception("No se pudo entregar un lote de CV a la cola de trabajos")
        with context.require_backend().transaction() as repos:
            context.cv_batches(repos).stop(
                batch_id,
                "No se pudo iniciar el procesamiento en segundo plano. Avisa a Sistemas "
                "y usa «Reintentar».",
            )


def _detail(context: AppContext, principal: Principal, batch_id: uuid.UUID) -> BatchDetailOut:
    with context.require_backend().transaction() as repos:
        view, items = context.cv_batches(repos).detail(principal.user, batch_id)
        names = _names(repos, [view])
    return BatchDetailOut(batch=BatchOut.of(view, names), items=[ItemOut.of(i) for i in items])


@router.get(
    "/vacancies/{vacancy_id}/cv-batches",
    response_model=OverviewOut,
    summary="Estado de la evaluación de CV de una vacante y sus lotes",
)
def list_batches(
    vacancy_id: uuid.UUID,
    principal: Principal = Depends(require_user),  # noqa: B008
    context: AppContext = Depends(get_context),  # noqa: B008
) -> OverviewOut:
    context.require_storage()
    with context.require_backend().transaction() as repos:
        overview = context.cv_batches(repos).overview(principal.user, vacancy_id)
        names = _names(repos, overview.batches)
    return _overview_out(overview, names)


@router.post(
    "/vacancies/{vacancy_id}/cv-batches",
    response_model=BatchDetailOut,
    status_code=status.HTTP_201_CREATED,
    summary="Evalúa en segundo plano los CV de la vacante con el prompt aprobado",
)
def create_batch(
    vacancy_id: uuid.UUID,
    body: BatchIn,
    request: Request,
    principal: Principal = Depends(require_user),  # noqa: B008
    context: AppContext = Depends(get_context),  # noqa: B008
) -> BatchDetailOut:
    context.require_storage()
    with context.require_backend().transaction() as repos:
        batch = context.cv_batches(repos).create(
            principal.user, vacancy_id, reevaluate=body.reevaluate, ip=client_ip(request)
        )
    _dispatch(context, batch.id)
    return _detail(context, principal, batch.id)


@router.get("/cv-batches/{batch_id}", response_model=BatchDetailOut, summary="Lote y sus CV")
def get_batch(
    batch_id: uuid.UUID,
    principal: Principal = Depends(require_user),  # noqa: B008
    context: AppContext = Depends(get_context),  # noqa: B008
) -> BatchDetailOut:
    context.require_storage()
    return _detail(context, principal, batch_id)


@router.post(
    "/cv-batches/{batch_id}/retry",
    response_model=BatchDetailOut,
    summary="Reintenta los CV fallidos y continúa con los pendientes",
)
def retry_batch(
    batch_id: uuid.UUID,
    request: Request,
    principal: Principal = Depends(require_user),  # noqa: B008
    context: AppContext = Depends(get_context),  # noqa: B008
) -> BatchDetailOut:
    context.require_storage()
    with context.require_backend().transaction() as repos:
        context.cv_batches(repos).resume(principal.user, batch_id, ip=client_ip(request))
    _dispatch(context, batch_id)
    return _detail(context, principal, batch_id)


@router.post(
    "/cv-batches/{batch_id}/cancel",
    response_model=BatchDetailOut,
    summary="Cancela un lote en curso; lo ya evaluado se conserva",
)
def cancel_batch(
    batch_id: uuid.UUID,
    request: Request,
    principal: Principal = Depends(require_user),  # noqa: B008
    context: AppContext = Depends(get_context),  # noqa: B008
) -> BatchDetailOut:
    context.require_storage()
    with context.require_backend().transaction() as repos:
        context.cv_batches(repos).cancel(principal.user, batch_id, ip=client_ip(request))
    return _detail(context, principal, batch_id)
