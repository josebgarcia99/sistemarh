"""Candidatos, postulaciones, convocatorias y etapas.

- Un candidato es una persona, con un identificador global.
- Una postulación es su participación en una convocatoria de una vacante. Las
  evaluaciones, llamadas e historial pertenecen a la postulación, no a la persona.
- Una convocatoria es un periodo de reclutamiento de la vacante; fija la versión
  de las etapas con la que trabaja, para que cambiar las etapas no altere el pasado.
- Cada cambio queda en el historial de movimientos; nada se borra al avanzar.
- El resultado final (contratado, no contratado, desistió…) lo registra siempre
  una persona. Cierra la postulación y guarda quién, cuándo y por qué; si se
  reabre, el registro se anula pero no se borra.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any, Protocol


class StageKind(StrEnum):
    EVALUACION_CV = "EVALUACION_CV"
    REVISION_RH = "REVISION_RH"
    LLAMADA = "LLAMADA"
    PSICOMETRIA = "PSICOMETRIA"
    ENTREVISTA = "ENTREVISTA"
    PRUEBA_TECNICA = "PRUEBA_TECNICA"
    ESTUDIO_SOCIOECONOMICO = "ESTUDIO_SOCIOECONOMICO"
    RESULTADO = "RESULTADO"
    OTRA = "OTRA"


# Etapas iniciales (sección 15): nombre, tipo y si puede omitirse sin motivo.
DEFAULT_STAGES: tuple[tuple[str, StageKind, bool], ...] = (
    ("Evaluación de CV", StageKind.EVALUACION_CV, False),
    ("Revisión local RH", StageKind.REVISION_RH, False),
    ("Llamada telefónica", StageKind.LLAMADA, False),
    ("Pruebas psicométricas", StageKind.PSICOMETRIA, False),
    ("Entrevista con gerente", StageKind.ENTREVISTA, False),
    ("Prueba técnica", StageKind.PRUEBA_TECNICA, True),
    ("Estudio socioeconómico", StageKind.ESTUDIO_SOCIOECONOMICO, False),
    ("Resultado final", StageKind.RESULTADO, False),
)


@dataclass(frozen=True)
class Stage:
    id: uuid.UUID
    pipeline_version_id: uuid.UUID
    position: int
    name: str
    kind: StageKind
    is_optional: bool


@dataclass(frozen=True)
class PipelineVersion:
    id: uuid.UUID
    version_number: int
    created_at: datetime
    created_by: uuid.UUID | None
    stages: tuple[Stage, ...] = ()


class CampaignStatus(StrEnum):
    ABIERTA = "ABIERTA"
    CERRADA = "CERRADA"


@dataclass
class Campaign:
    id: uuid.UUID
    vacancy_id: uuid.UUID
    number: int
    name: str
    status: CampaignStatus
    pipeline_version_id: uuid.UUID
    opened_at: datetime
    opened_by: uuid.UUID | None
    closed_at: datetime | None = None
    closed_by: uuid.UUID | None = None


@dataclass
class Candidate:
    id: uuid.UUID
    full_name: str
    created_at: datetime
    updated_at: datetime
    created_by: uuid.UUID | None = None
    email: str | None = None
    phone: str | None = None


class ApplicationStatus(StrEnum):
    ACTIVA = "ACTIVA"
    DESISTIO = "DESISTIO"
    DESCARTADA = "DESCARTADA"
    CANCELADA = "CANCELADA"
    CONTRATADA = "CONTRATADA"
    NO_LOCALIZADA = "NO_LOCALIZADA"
    OTRO_CIERRE = "OTRO_CIERRE"


class OutcomeKind(StrEnum):
    """Resultados finales de una postulación (sección 23). Mientras no tiene
    ninguno vigente, la postulación está «en proceso»."""

    CONTRATADO = "CONTRATADO"
    NO_CONTRATADO = "NO_CONTRATADO"
    DESISTIO = "DESISTIO"
    NO_LOCALIZADO = "NO_LOCALIZADO"
    VACANTE_CANCELADA = "VACANTE_CANCELADA"
    OTRO_CIERRE = "OTRO_CIERRE"


IN_PROCESS = "EN_PROCESO"

# Cada resultado final deja la postulación en un estado.
OUTCOME_STATUS: dict[OutcomeKind, ApplicationStatus] = {
    OutcomeKind.CONTRATADO: ApplicationStatus.CONTRATADA,
    OutcomeKind.NO_CONTRATADO: ApplicationStatus.DESCARTADA,
    OutcomeKind.DESISTIO: ApplicationStatus.DESISTIO,
    OutcomeKind.NO_LOCALIZADO: ApplicationStatus.NO_LOCALIZADA,
    OutcomeKind.VACANTE_CANCELADA: ApplicationStatus.CANCELADA,
    OutcomeKind.OTRO_CIERRE: ApplicationStatus.OTRO_CIERRE,
}
STATUS_OUTCOME: dict[ApplicationStatus, OutcomeKind] = {
    status: outcome for outcome, status in OUTCOME_STATUS.items()
}


def outcome_of(status: ApplicationStatus) -> str:
    """El resultado final que corresponde a un estado; «EN_PROCESO» si sigue activa."""
    outcome = STATUS_OUTCOME.get(status)
    return outcome.value if outcome else IN_PROCESS


@dataclass
class Application:
    id: uuid.UUID
    candidate_id: uuid.UUID
    campaign_id: uuid.UUID
    vacancy_id: uuid.UUID
    stage_id: uuid.UUID
    status: ApplicationStatus
    created_at: datetime
    updated_at: datetime
    created_by: uuid.UUID | None = None
    cv_file_id: uuid.UUID | None = None
    # Evaluación inicial de la IA con la que entró. Es una copia: no cambia aunque
    # el CV se vuelva a evaluar ni cuando RH mueve a la persona.
    evaluation_item_id: uuid.UUID | None = None
    ai_classification: str | None = None
    ai_score: Decimal | None = None
    # Fecha acordada para la etapa actual (reprogramación).
    due_at: datetime | None = None


class MovementKind(StrEnum):
    ALTA = "ALTA"
    AVANCE = "AVANCE"
    RETROCESO = "RETROCESO"
    OMISION = "OMISION"
    DESISTIMIENTO = "DESISTIMIENTO"
    DESCARTE = "DESCARTE"
    CANCELACION = "CANCELACION"
    REACTIVACION = "REACTIVACION"
    REPROGRAMACION = "REPROGRAMACION"
    INCIDENCIA = "INCIDENCIA"
    CONTRATACION = "CONTRATACION"
    NO_LOCALIZADO = "NO_LOCALIZADO"
    CIERRE = "CIERRE"


OUTCOME_MOVEMENT: dict[OutcomeKind, MovementKind] = {
    OutcomeKind.CONTRATADO: MovementKind.CONTRATACION,
    OutcomeKind.NO_CONTRATADO: MovementKind.DESCARTE,
    OutcomeKind.DESISTIO: MovementKind.DESISTIMIENTO,
    OutcomeKind.NO_LOCALIZADO: MovementKind.NO_LOCALIZADO,
    OutcomeKind.VACANTE_CANCELADA: MovementKind.CANCELACION,
    OutcomeKind.OTRO_CIERRE: MovementKind.CIERRE,
}
MOVEMENT_OUTCOME: dict[MovementKind, OutcomeKind] = {
    movement: outcome for outcome, movement in OUTCOME_MOVEMENT.items()
}


@dataclass(frozen=True)
class Movement:
    id: uuid.UUID
    application_id: uuid.UUID
    kind: MovementKind
    occurred_at: datetime
    # Vacío cuando lo hizo el sistema (por ejemplo, el alta desde un lote).
    actor_user_id: uuid.UUID | None = None
    from_stage_id: uuid.UUID | None = None
    to_stage_id: uuid.UUID | None = None
    note: str | None = None
    due_at: datetime | None = None
    # Agrupa los movimientos de una misma operación masiva.
    group_id: uuid.UUID | None = None
    # Orden dentro del historial de la postulación (1, 2, 3…).
    sequence: int = 0


@dataclass
class Outcome:
    """Registro de un resultado final. Siempre lo captura una persona."""

    id: uuid.UUID
    application_id: uuid.UUID
    vacancy_id: uuid.UUID
    outcome: OutcomeKind
    recorded_at: datetime
    recorded_by: uuid.UUID
    reason: str | None = None
    notes: str | None = None
    # Fecha de incorporación; solo en una contratación.
    start_date: date | None = None
    # Al reabrir la postulación el registro se anula; no se borra.
    voided_at: datetime | None = None
    voided_by: uuid.UUID | None = None
    void_reason: str | None = None


@dataclass(frozen=True)
class EvaluatedCv:
    """Un CV evaluado por la IA, visto desde el reclutamiento."""

    file_id: uuid.UUID
    file_name: str
    item_id: uuid.UUID
    classification: str
    score: Decimal | None
    extraction: dict[str, Any] = field(default_factory=dict)
    result: dict[str, Any] = field(default_factory=dict)


class EvaluatedCvs(Protocol):
    def first_evaluations(self, vacancy_id: uuid.UUID) -> list[EvaluatedCv]:
        """La primera evaluación de cada CV de la vacante."""
        ...

    def evaluation(self, item_id: uuid.UUID) -> EvaluatedCv | None: ...

    def is_cv_of(self, vacancy_id: uuid.UUID, file_id: uuid.UUID) -> bool: ...


class RecruitmentRepository(Protocol):
    def latest_pipeline(self) -> PipelineVersion | None: ...

    def pipeline(self, version_id: uuid.UUID) -> PipelineVersion | None: ...

    def add_pipeline(self, version: PipelineVersion) -> None: ...

    def campaigns(self, vacancy_id: uuid.UUID) -> list[Campaign]:
        """De la más reciente a la más antigua."""
        ...

    def campaign(self, campaign_id: uuid.UUID) -> Campaign | None: ...

    def add_campaign(self, campaign: Campaign) -> None: ...

    def save_campaign(self, campaign: Campaign) -> None: ...

    def candidate(self, candidate_id: uuid.UUID) -> Candidate | None: ...

    def candidates(self, candidate_ids: list[uuid.UUID]) -> dict[uuid.UUID, Candidate]: ...

    def candidate_by_email(self, email: str) -> Candidate | None: ...

    def add_candidate(self, candidate: Candidate) -> None: ...

    def save_candidate(self, candidate: Candidate) -> None: ...

    def application(self, application_id: uuid.UUID) -> Application | None: ...

    def applications(self, campaign_id: uuid.UUID) -> list[Application]: ...

    def application_of(
        self, candidate_id: uuid.UUID, campaign_id: uuid.UUID
    ) -> Application | None: ...

    def files_with_application(self, vacancy_id: uuid.UUID) -> set[uuid.UUID]: ...

    def add_application(self, application: Application) -> None: ...

    def save_application(self, application: Application) -> None: ...

    def add_movements(self, movements: list[Movement]) -> None: ...

    def movement_count(self, application_id: uuid.UUID) -> int: ...

    def movements(self, application_id: uuid.UUID) -> list[Movement]:
        """Del más antiguo al más reciente."""
        ...

    def add_outcome(self, outcome: Outcome) -> None: ...

    def save_outcome(self, outcome: Outcome) -> None: ...

    def outcomes(self, application_id: uuid.UUID) -> list[Outcome]:
        """Del más reciente al más antiguo, incluidos los anulados."""
        ...

    def current_outcome(self, application_id: uuid.UUID) -> Outcome | None: ...

    def hires(self, vacancy_id: uuid.UUID) -> int:
        """Contrataciones vigentes de la vacante."""
        ...
