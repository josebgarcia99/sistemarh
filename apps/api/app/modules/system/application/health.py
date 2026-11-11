"""Caso de uso: comprobar que las dependencias del sistema responden."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from enum import StrEnum


class ComponentStatus(StrEnum):
    OK = "ok"
    FAILED = "fallo"
    NOT_CONFIGURED = "sin_configurar"


@dataclass(frozen=True)
class ComponentReport:
    name: str
    status: ComponentStatus


@dataclass(frozen=True)
class ReadinessReport:
    components: tuple[ComponentReport, ...]

    @property
    def ready(self) -> bool:
        # Un componente sin configurar no es un fallo en desarrollo, pero tampoco
        # permite declarar el sistema listo.
        return all(c.status is ComponentStatus.OK for c in self.components)


# Una comprobación devuelve True si el componente responde, False si falla y
# None si no está configurado. Nunca debe lanzar excepciones hacia afuera.
HealthCheck = Callable[[], bool | None]


def check_readiness(checks: Mapping[str, HealthCheck]) -> ReadinessReport:
    reports: list[ComponentReport] = []
    for name, check in checks.items():
        try:
            result = check()
        except Exception:  # noqa: BLE001 - una comprobación rota cuenta como fallo
            result = False
        if result is None:
            status = ComponentStatus.NOT_CONFIGURED
        elif result:
            status = ComponentStatus.OK
        else:
            status = ComponentStatus.FAILED
        reports.append(ComponentReport(name=name, status=status))
    return ReadinessReport(components=tuple(reports))
