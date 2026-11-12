"""Métricas de rendimiento del proceso. Solo para administradores."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from app.modules.authentication.api.dependencies import Principal, require_admin

router = APIRouter(prefix="/system", tags=["salud"])


class RouteMetrics(BaseModel):
    method: str
    route: str
    count: int
    client_errors: int
    server_errors: int
    average_ms: float
    max_ms: float
    # Solicitudes por franja de duración; ver ``bucket_limits_ms``.
    buckets: list[int]


class MetricsResponse(BaseModel):
    uptime_seconds: int
    requests: int
    server_errors: int
    bucket_limits_ms: list[int]
    routes: list[RouteMetrics]


@router.get(
    "/metrics",
    response_model=MetricsResponse,
    summary="Solicitudes atendidas por este proceso: cuántas, errores y duración",
)
def metrics(
    request: Request,
    _: Principal = Depends(require_admin),  # noqa: B008
) -> MetricsResponse:
    return MetricsResponse.model_validate(request.app.state.metrics.snapshot())
