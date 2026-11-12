"""Indicadores, históricos y reportes.

Este módulo solo lee. No guarda cifras: cada consulta se calcula de nuevo a
partir de lo que registraron los demás módulos (vacantes, evaluaciones de CV,
postulaciones, movimientos, resultados finales y consumo de IA). Así un
tablero nunca contradice al expediente y los históricos respetan siempre los
permisos que la persona tiene hoy, no los que tenía cuando ocurrieron los
hechos.

Lo único que se guarda es el registro de cada Excel generado: qué contiene,
quién lo pidió, cuándo y su huella.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import BinaryIO, Protocol

IN_PROCESS = "EN_PROCESO"
HIRED = "CONTRATADO"
WITHDREW = "DESISTIO"
OUTCOMES = (
    HIRED,
    "NO_CONTRATADO",
    WITHDREW,
    "NO_LOCALIZADO",
    "VACANTE_CANCELADA",
    "OTRO_CIERRE",
)
ACTIVE_STATUS = "ACTIVA"
OPEN_VACANCY = "ABIERTA"

# Movimientos que cierran, reabren o cambian de etapa a una postulación.
CLOSING_MOVEMENTS = frozenset(
    {"DESISTIMIENTO", "DESCARTE", "CANCELACION", "CONTRATACION", "NO_LOCALIZADO", "CIERRE"}
)
STAGE_MOVEMENTS = frozenset({"AVANCE", "RETROCESO"})


class DateKind(StrEnum):
    """Qué fecha se compara con el periodo en el histórico de postulaciones."""

    CARGA = "CARGA"
    EVALUACION = "EVALUACION"
    MOVIMIENTO = "MOVIMIENTO"
    CIERRE = "CIERRE"


class ExportKind(StrEnum):
    INDICADORES = "INDICADORES"
    POSTULACIONES = "POSTULACIONES"


@dataclass(frozen=True)
class Viewer:
    """Quién consulta. Un reclutador solo ve sus vacantes y las compartidas."""

    user_id: uuid.UUID
    is_admin: bool


@dataclass(frozen=True)
class VacancySelection:
    """Qué vacantes entran en la consulta. ``visible_to`` vacío = todas."""

    visible_to: uuid.UUID | None = None
    vacancy_id: uuid.UUID | None = None
    owner_id: uuid.UUID | None = None
    collaborator_id: uuid.UUID | None = None
    department: str | None = None
    status: str | None = None

    @property
    def filtered(self) -> bool:
        """Si se pidió algo más que «todo lo que puedo ver»."""
        return any(
            (self.vacancy_id, self.owner_id, self.collaborator_id, self.department, self.status)
        )


@dataclass(frozen=True)
class ReportFilter:
    date_from: date | None = None
    date_to: date | None = None
    vacancy_id: uuid.UUID | None = None
    owner_id: uuid.UUID | None = None
    collaborator_id: uuid.UUID | None = None
    department: str | None = None
    vacancy_status: str | None = None
    # Solo para el histórico de postulaciones.
    date_kind: DateKind = DateKind.CARGA
    stage: str | None = None
    candidate: str | None = None
    ai_classification: str | None = None
    score_min: Decimal | None = None
    score_max: Decimal | None = None
    model: str | None = None
    prompt_version_id: uuid.UUID | None = None
    bank_id: uuid.UUID | None = None
    outcome: str | None = None


# --- Hechos: lo que se lee de los demás módulos ------------------------------------------


@dataclass(frozen=True)
class VacancyFact:
    id: uuid.UUID
    name: str
    department: str
    status: str
    positions: int
    owner_id: uuid.UUID
    owner_name: str
    created_at: datetime
    opened_at: datetime | None = None
    closed_at: datetime | None = None
    # Personas con acceso compartido vigente.
    collaborators: frozenset[uuid.UUID] = frozenset()


@dataclass(frozen=True)
class StageFact:
    id: uuid.UUID
    pipeline_version_id: uuid.UUID
    position: int
    name: str
    kind: str


@dataclass(frozen=True)
class ApplicationFact:
    id: uuid.UUID
    vacancy_id: uuid.UUID
    candidate_name: str
    stage_id: uuid.UUID
    status: str
    created_at: datetime
    campaign_opened_at: datetime
    ai_classification: str | None = None
    ai_score: Decimal | None = None
    # Del CV con el que entró y de su evaluación inicial.
    cv_uploaded_at: datetime | None = None
    evaluated_at: datetime | None = None
    model: str | None = None
    prompt_version_id: uuid.UUID | None = None
    prompt_version_number: int | None = None


@dataclass(frozen=True)
class MovementFact:
    application_id: uuid.UUID
    sequence: int
    kind: str
    occurred_at: datetime
    from_stage_id: uuid.UUID | None = None
    to_stage_id: uuid.UUID | None = None


@dataclass(frozen=True)
class RecentFact:
    """Un movimiento reciente, ya con los nombres para mostrarlo."""

    occurred_at: datetime
    kind: str
    candidate: str
    vacancy_id: uuid.UUID
    vacancy: str
    stage: str | None = None
    actor_name: str | None = None


# Intervalo en UTC: desde el primer valor (incluido) hasta el segundo (excluido).
Window = tuple[datetime | None, datetime | None]


@dataclass(frozen=True)
class OutcomeFact:
    """Resultado final vigente de una postulación."""

    application_id: uuid.UUID
    vacancy_id: uuid.UUID
    outcome: str
    recorded_at: datetime
    recorded_by_name: str
    reason: str | None = None
    start_date: date | None = None


@dataclass(frozen=True)
class CvFact:
    """Un CV que pasó por un lote de evaluación."""

    vacancy_id: uuid.UUID
    status: str
    updated_at: datetime
    classification: str | None = None


@dataclass(frozen=True)
class AiFact:
    occurred_at: datetime
    operation: str
    ok: bool
    cost_usd: Decimal | None = None


@dataclass(frozen=True)
class Option:
    id: str
    name: str


@dataclass(frozen=True)
class FilterOptions:
    vacancies: list[Option]
    owners: list[Option]
    collaborators: list[Option]
    departments: list[str]
    stages: list[str]
    models: list[str]
    prompt_versions: list[Option]
    banks: list[Option]


@dataclass(frozen=True)
class Facts:
    vacancies: list[VacancyFact]
    stages: dict[uuid.UUID, StageFact]
    applications: list[ApplicationFact]
    movements: list[MovementFact]
    outcomes: list[OutcomeFact]
    cvs: list[CvFact]
    # Vacío cuando quien consulta no es administrador.
    ai: list[AiFact] = field(default_factory=list)
    recent: list[RecentFact] = field(default_factory=list)


# --- Exportaciones -----------------------------------------------------------------------


@dataclass(frozen=True)
class StoredFile:
    key: str
    size_bytes: int
    sha256: str


@dataclass(frozen=True)
class ReportExport:
    id: uuid.UUID
    kind: ExportKind
    name: str
    # Filtros con los que se generó, tal como se pidieron.
    filters: dict[str, str]
    # Vacantes cuyos datos contiene. Al descargar se comprueba que quien lo
    # pide las siga viendo todas.
    vacancy_ids: list[uuid.UUID]
    row_count: int
    storage_key: str
    size_bytes: int
    sha256: str
    created_at: datetime
    created_by: uuid.UUID


class ReportStore(Protocol):
    """Dónde se guardan los Excel generados: el almacenamiento del servidor."""

    def save(self, file_id: uuid.UUID, write: Callable[[BinaryIO], None]) -> StoredFile: ...

    def exists(self, key: str) -> bool: ...


class ReportingSource(Protocol):
    def vacancies(self, selection: VacancySelection) -> list[VacancyFact]: ...

    def stages(self) -> dict[uuid.UUID, StageFact]: ...

    def study_photos(self, application_ids: set[uuid.UUID]) -> dict[uuid.UUID, str]:
        """Descripciones guardadas junto a las fotografías del estudio
        socioeconómico de cada postulación, como texto. Sin el resto del estudio."""
        ...

    def applications(
        self, selection: VacancySelection, window: Window | None = None
    ) -> list[ApplicationFact]:
        """Postulaciones de las vacantes elegidas. Con ``window``, solo las que
        importan para ese periodo: las activas, las dadas de alta en él y las
        que tuvieron algún movimiento en él."""
        ...

    def movements(
        self, selection: VacancySelection, window: Window | None = None
    ) -> list[MovementFact]:
        """Historial completo de las postulaciones que devuelve ``applications``."""
        ...

    def outcomes(self, selection: VacancySelection) -> list[OutcomeFact]: ...

    def cvs(self, selection: VacancySelection, window: Window | None = None) -> list[CvFact]: ...

    def recent(self, selection: VacancySelection, limit: int) -> list[RecentFact]: ...

    def last_movements(self, selection: VacancySelection) -> dict[uuid.UUID, datetime]:
        """Fecha del último movimiento de cada postulación."""
        ...

    def moved_within(self, selection: VacancySelection, window: Window) -> set[uuid.UUID]:
        """Postulaciones con algún movimiento dentro del intervalo."""
        ...

    def ai_executions(
        self, start: datetime | None, end: datetime | None, selection: VacancySelection
    ) -> list[AiFact]:
        """Consumo de IA del periodo; si hay filtros de vacante, solo el de esas vacantes."""
        ...

    def applications_with_bank(
        self, selection: VacancySelection, bank_id: uuid.UUID
    ) -> set[uuid.UUID]: ...

    def options(self, selection: VacancySelection) -> FilterOptions: ...

    def add_export(self, export: ReportExport) -> None: ...

    def export(self, export_id: uuid.UUID) -> ReportExport | None: ...

    def exports_of(self, user_id: uuid.UUID, limit: int) -> list[ReportExport]: ...

    def export_keys(self) -> set[str]:
        """Rutas de todos los reportes guardados (para la conciliación)."""
        ...

    def export_files(self) -> list[tuple[uuid.UUID, StoredFile]]:
        """Todos los reportes guardados, con su tamaño y huella (para respaldos)."""
        ...
