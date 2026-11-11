"""Consulta de auditoría. Solo administradores."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from app.composition.context import AppContext, get_context
from app.modules.authentication.api.dependencies import Principal, require_admin

router = APIRouter(prefix="/audit", tags=["auditoría"])


class AuditEventOut(BaseModel):
    id: uuid.UUID
    occurred_at: datetime
    action: str
    result: str
    actor_user_id: uuid.UUID | None
    actor_name: str | None
    resource_type: str | None
    resource_id: str | None
    ip: str | None
    correlation_id: str | None
    details: dict[str, Any]


class AuditPage(BaseModel):
    items: list[AuditEventOut]
    total: int
    page: int
    page_size: int


@router.get("/events", response_model=AuditPage, summary="Eventos de auditoría")
def list_events(
    action: str | None = Query(default=None, max_length=80),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
    _: Principal = Depends(require_admin),  # noqa: B008
    context: AppContext = Depends(get_context),  # noqa: B008
) -> AuditPage:
    with context.require_backend().transaction() as repos:
        events, total = context.audit(repos).list(
            action=action, offset=(page - 1) * page_size, limit=page_size
        )
        actors = repos.users.get_many(e.actor_user_id for e in events if e.actor_user_id)
    return AuditPage(
        items=[
            AuditEventOut(
                **vars(event),
                actor_name=actors[event.actor_user_id].full_name
                if event.actor_user_id in actors
                else None,
            )
            for event in events
        ],
        total=total,
        page=page,
        page_size=page_size,
    )
