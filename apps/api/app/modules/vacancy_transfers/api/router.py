"""Transferencias de responsable e historial."""

from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from app.composition.context import AppContext, client_ip, get_context
from app.modules.authentication.api.dependencies import Principal, require_admin, require_user
from app.modules.vacancies.api.schemas import PersonOut

router = APIRouter(tags=["transferencias"])


class OwnershipChangeOut(BaseModel):
    previous_owner: PersonOut | None
    new_owner: PersonOut | None
    changed_at: datetime
    reason: str
    authorized_by: PersonOut | None
    part_of_mass_transfer: bool


class IndividualTransferIn(BaseModel):
    vacancy_id: uuid.UUID
    to_user_id: uuid.UUID
    reason: str = Field(max_length=500)
    keep_previous_as_collaborator: bool = False


class MassPreviewIn(BaseModel):
    from_user_id: uuid.UUID
    to_user_id: uuid.UUID


class VacancyBrief(BaseModel):
    id: uuid.UUID
    name: str
    status: str


class MassPreviewOut(BaseModel):
    from_user: PersonOut
    to_user: PersonOut
    vacancies: list[VacancyBrief]
    memberships_to_revoke: int
    grants_to_revoke: int
    preview_token: str


class MassTransferIn(MassPreviewIn):
    # Lo genera el cliente una vez por operación: repetir la llamada no la duplica.
    operation_id: uuid.UUID
    reason: str = Field(max_length=500)
    preview_token: str = Field(max_length=64)


class MassTransferOut(BaseModel):
    operation_id: uuid.UUID
    completed_at: datetime
    vacancies_transferred: int
    memberships_revoked: int
    grants_revoked: int
    user_deactivated: bool


@router.get(
    "/vacancies/{vacancy_id}/ownership-history",
    response_model=list[OwnershipChangeOut],
    summary="Historial de responsables de la vacante",
)
def ownership_history(
    vacancy_id: uuid.UUID,
    principal: Principal = Depends(require_user),  # noqa: B008
    context: AppContext = Depends(get_context),  # noqa: B008
) -> list[OwnershipChangeOut]:
    with context.require_backend().transaction() as repos:
        changes = context.transfer_service(repos).history(principal.user, vacancy_id)
        ids = {
            user_id
            for change in changes
            for user_id in (change.previous_owner_id, change.new_owner_id, change.authorized_by)
            if user_id is not None
        }
        users = repos.users.get_many(ids)
    return [
        OwnershipChangeOut(
            previous_owner=PersonOut.from_user(users.get(change.previous_owner_id)),
            new_owner=PersonOut.from_user(users.get(change.new_owner_id)),
            changed_at=change.changed_at,
            reason=change.reason,
            authorized_by=PersonOut.from_user(users.get(change.authorized_by)),
            part_of_mass_transfer=change.transfer_id is not None,
        )
        for change in changes
    ]


@router.post(
    "/vacancy-transfers/individual",
    status_code=204,
    summary="Cambiar el responsable de una vacante",
)
def transfer_vacancy(
    body: IndividualTransferIn,
    request: Request,
    principal: Principal = Depends(require_admin),  # noqa: B008
    context: AppContext = Depends(get_context),  # noqa: B008
) -> None:
    with context.require_backend().transaction() as repos:
        context.transfer_service(repos).transfer(
            principal.user,
            body.vacancy_id,
            to_user_id=body.to_user_id,
            reason=body.reason,
            keep_previous_as_collaborator=body.keep_previous_as_collaborator,
            ip=client_ip(request),
        )


@router.post(
    "/vacancy-transfers/mass/preview",
    response_model=MassPreviewOut,
    summary="Vista previa de la baja de un reclutador",
)
def preview_mass_transfer(
    body: MassPreviewIn,
    principal: Principal = Depends(require_admin),  # noqa: B008
    context: AppContext = Depends(get_context),  # noqa: B008
) -> MassPreviewOut:
    with context.require_backend().transaction() as repos:
        preview = context.transfer_service(repos).preview_mass(
            principal.user, from_user_id=body.from_user_id, to_user_id=body.to_user_id
        )
    return MassPreviewOut(
        from_user=PersonOut.from_user(preview.from_user),
        to_user=PersonOut.from_user(preview.to_user),
        vacancies=[
            VacancyBrief(id=v.id, name=v.name, status=v.status.value) for v in preview.vacancies
        ],
        memberships_to_revoke=preview.memberships_to_revoke,
        grants_to_revoke=preview.grants_to_revoke,
        preview_token=preview.token,
    )


@router.post(
    "/vacancy-transfers/mass",
    response_model=MassTransferOut,
    summary="Transferir todo lo de un reclutador y darlo de baja",
)
def execute_mass_transfer(
    body: MassTransferIn,
    request: Request,
    principal: Principal = Depends(require_admin),  # noqa: B008
    context: AppContext = Depends(get_context),  # noqa: B008
) -> MassTransferOut:
    with context.require_backend().transaction() as repos:
        transfer = context.transfer_service(repos).execute_mass(
            principal.user,
            operation_id=body.operation_id,
            from_user_id=body.from_user_id,
            to_user_id=body.to_user_id,
            reason=body.reason,
            preview_token=body.preview_token,
            ip=client_ip(request),
        )
    return MassTransferOut(
        operation_id=transfer.id,
        completed_at=transfer.completed_at,
        vacancies_transferred=transfer.vacancies_transferred,
        memberships_revoked=transfer.memberships_revoked,
        grants_revoked=transfer.grants_revoked,
        user_deactivated=transfer.user_deactivated,
    )
