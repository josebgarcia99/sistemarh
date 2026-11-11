"""Rutas de salud. No exponen datos de negocio ni detalles internos."""

from __future__ import annotations

from collections.abc import Mapping

from fastapi import APIRouter, Depends, Request, Response, status
from pydantic import BaseModel

from app.modules.system.application.health import HealthCheck, check_readiness

router = APIRouter(prefix="/health", tags=["salud"])


class LivenessResponse(BaseModel):
    status: str


class ComponentResponse(BaseModel):
    name: str
    status: str


class ReadinessResponse(BaseModel):
    ready: bool
    components: list[ComponentResponse]


def get_health_checks(request: Request) -> Mapping[str, HealthCheck]:
    return request.app.state.health_checks


@router.get("/live", response_model=LivenessResponse, summary="El proceso responde")
def live() -> LivenessResponse:
    return LivenessResponse(status="ok")


@router.get(
    "/ready",
    response_model=ReadinessResponse,
    summary="SQL Server, Redis y almacenamiento responden",
    responses={503: {"model": ReadinessResponse}},
)
def ready(
    response: Response,
    checks: Mapping[str, HealthCheck] = Depends(get_health_checks),  # noqa: B008
) -> ReadinessResponse:
    report = check_readiness(checks)
    if not report.ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return ReadinessResponse(
        ready=report.ready,
        components=[
            ComponentResponse(name=c.name, status=c.status.value) for c in report.components
        ],
    )
