"""Perfil de puesto y prompt de evaluación de una vacante.

- El perfil se guarda por versiones: cada corrección crea una versión nueva y
  las anteriores no cambian.
- El prompt se compone de diez capas y una rúbrica. Solo una versión APROBADA
  puede usarse para evaluar CV, y una versión aprobada es inmutable.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Protocol

# El perfil sigue el formato de la empresa «SGC.F15.RH. Perfil de puesto».
# Datos de una sola línea (identificación del puesto y datos del documento).
PROFILE_LINE_FIELDS = (
    "position_name",
    "area",
    "location",
    "reports_to",
    "supervises",
    "contract_type",
    "work_mode",
    "schedule",
    "offer",
    "specialty",
    "document_version",
    "document_date",
)
# Textos de varias líneas.
PROFILE_TEXT_FIELDS = (
    "objective",
    "internal_relations",
    "external_relations",
    "experience",
    "education",
)
PROFILE_LIST_FIELDS = (
    "education_levels",
    "functions",
    "responsibilities",
    "knowledge",
    "skills",
    "certifications",
    "must_have",
    "nice_to_have",
    "ambiguities",
)
# Niveles de «Formación académica» del formato, en el orden en que se muestran.
EDUCATION_LEVELS = (
    "Maestría",
    "Licenciatura",
    "Ingeniería",
    "TSU",
    "Bachillerato",
    "Secundaria",
)
# Periodicidad de una actividad, como la pide el formato.
FREQUENCIES = ("Ocasional", "Diaria", "Semanal", "Mensual", "Anual")


@dataclass(frozen=True)
class Activity:
    """Actividad del puesto y cada cuánto se hace."""

    description: str
    frequency: str = ""


@dataclass(frozen=True)
class Kpi:
    """Indicador de desempeño del puesto, con su meta y su fórmula."""

    name: str
    goal: str = ""
    formula: str = ""


@dataclass(frozen=True)
class ProfileContent:
    # Identificación del puesto.
    position_name: str = ""
    area: str = ""
    location: str = ""
    reports_to: str = ""
    supervises: str = ""
    contract_type: str = ""
    work_mode: str = ""
    schedule: str = ""
    offer: str = ""
    # «Versión del perfil» y «Fecha de actualización» escritas en el documento.
    document_version: str = ""
    document_date: str = ""
    # Propósito del puesto.
    objective: str = ""
    # Alcance y relaciones clave.
    internal_relations: str = ""
    external_relations: str = ""
    # Requisitos del puesto.
    education_levels: tuple[str, ...] = ()
    specialty: str = ""
    education: str = ""
    experience: str = ""
    # Requisitos indispensables (conocimientos) y deseables: de aquí sale la rúbrica.
    must_have: tuple[str, ...] = ()
    nice_to_have: tuple[str, ...] = ()
    knowledge: tuple[str, ...] = ()
    skills: tuple[str, ...] = ()
    certifications: tuple[str, ...] = ()
    # Funciones y actividades principales.
    functions: tuple[str, ...] = ()
    responsibilities: tuple[str, ...] = ()
    activities: tuple[Activity, ...] = ()
    # Indicadores y medición de desempeño.
    kpis: tuple[Kpi, ...] = ()
    # Requisitos del perfil que no están claros y conviene precisar.
    ambiguities: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        """Forma en la que se guarda y se devuelve: textos, listas y filas."""
        data: dict[str, object] = {}
        for name in (*PROFILE_LINE_FIELDS, *PROFILE_TEXT_FIELDS):
            data[name] = getattr(self, name)
        for name in PROFILE_LIST_FIELDS:
            data[name] = list(getattr(self, name))
        data["activities"] = [
            {"description": a.description, "frequency": a.frequency} for a in self.activities
        ]
        data["kpis"] = [{"name": k.name, "goal": k.goal, "formula": k.formula} for k in self.kpis]
        return data

    @classmethod
    def from_stored(cls, data: dict[str, object]) -> ProfileContent:
        """Reconstruye un perfil guardado. Las versiones anteriores al formato
        de la empresa no traen los campos nuevos: quedan vacíos."""
        values: dict[str, object] = {}
        for name in (*PROFILE_LINE_FIELDS, *PROFILE_TEXT_FIELDS):
            values[name] = str(data.get(name) or "")
        for name in PROFILE_LIST_FIELDS:
            values[name] = tuple(str(item) for item in (data.get(name) or ()))  # type: ignore[union-attr]
        activities = data.get("activities") or ()
        values["activities"] = tuple(
            Activity(str(a.get("description") or ""), str(a.get("frequency") or ""))
            for a in activities  # type: ignore[union-attr]
            if isinstance(a, dict)
        )
        kpis = data.get("kpis") or ()
        values["kpis"] = tuple(
            Kpi(str(k.get("name") or ""), str(k.get("goal") or ""), str(k.get("formula") or ""))
            for k in kpis  # type: ignore[union-attr]
            if isinstance(k, dict)
        )
        return cls(**values)  # type: ignore[arg-type]


class ProfileOrigin(StrEnum):
    MANUAL = "MANUAL"
    IA = "IA"
    # Leído directamente del formato de la empresa en Excel, sin IA.
    FORMATO = "FORMATO"


@dataclass(frozen=True)
class ProfileVersion:
    id: uuid.UUID
    vacancy_id: uuid.UUID
    version_number: int
    origin: ProfileOrigin
    content: ProfileContent
    change_note: str | None
    source_file_id: uuid.UUID | None
    created_at: datetime
    created_by: uuid.UUID


class PromptStatus(StrEnum):
    BORRADOR = "BORRADOR"
    EN_REVISION = "EN_REVISION"
    APROBADO = "APROBADO"
    ARCHIVADO = "ARCHIVADO"


class LayerKey(StrEnum):
    """Las diez capas, en el orden en que forman el prompt."""

    INSTRUCCIONES = "INSTRUCCIONES"
    PERFIL = "PERFIL"
    REQUISITOS = "REQUISITOS"
    RUBRICA = "RUBRICA"
    EVIDENCIAS = "EVIDENCIAS"
    AMBIGUEDADES = "AMBIGUEDADES"
    DATOS_FALTANTES = "DATOS_FALTANTES"
    RESTRICCIONES = "RESTRICCIONES"
    FORMATO_JSON = "FORMATO_JSON"
    REGLAS_VALIDACION = "REGLAS_VALIDACION"


# Capas que escribe el sistema: la rúbrica sale de los criterios, y el formato y
# las reglas deben coincidir con lo que el sistema valida al recibir la respuesta.
LOCKED_LAYERS = frozenset({LayerKey.RUBRICA, LayerKey.FORMATO_JSON, LayerKey.REGLAS_VALIDACION})


class CriterionKind(StrEnum):
    INDISPENSABLE = "INDISPENSABLE"
    DESEABLE = "DESEABLE"


class CriterionOrigin(StrEnum):
    PERFIL = "PERFIL"  # derivado de un requisito del perfil
    MANUAL = "MANUAL"  # añadido por una persona


@dataclass
class Criterion:
    id: uuid.UUID
    position: int
    name: str
    description: str
    kind: CriterionKind
    weight: Decimal
    # Descripción de los niveles 0 a 4.
    levels: tuple[str, str, str, str, str]
    origin: CriterionOrigin

    @property
    def code(self) -> str:
        return f"C{self.position}"


@dataclass
class PromptVersion:
    id: uuid.UUID
    vacancy_id: uuid.UUID
    version_number: int
    status: PromptStatus
    profile_version_id: uuid.UUID
    # Puntuación mínima (0 a 100) para clasificar un CV como aceptado.
    pass_threshold: Decimal
    layers: dict[LayerKey, str]
    criteria: list[Criterion]
    created_at: datetime
    created_by: uuid.UUID
    updated_at: datetime
    updated_by: uuid.UUID
    # Aumenta con cada edición del borrador: evita que dos personas se pisen.
    revision: int = 1
    duplicated_from: uuid.UUID | None = None
    submitted_at: datetime | None = None
    submitted_by: uuid.UUID | None = None
    approved_at: datetime | None = None
    approved_by: uuid.UUID | None = None
    archived_at: datetime | None = None
    archived_by: uuid.UUID | None = None
    issues: list[str] = field(default_factory=list)


class EvaluationSetupRepository(Protocol):
    def profile_versions(self, vacancy_id: uuid.UUID) -> list[ProfileVersion]:
        """De la más reciente a la más antigua."""
        ...

    def profile_version(self, version_id: uuid.UUID) -> ProfileVersion | None: ...

    def add_profile_version(self, version: ProfileVersion) -> None: ...

    def prompt_versions(self, vacancy_id: uuid.UUID) -> list[PromptVersion]:
        """De la más reciente a la más antigua."""
        ...

    def prompt_version(self, version_id: uuid.UUID) -> PromptVersion | None: ...

    def add_prompt_version(self, version: PromptVersion) -> None: ...

    def save_prompt_version(self, version: PromptVersion, *, expected_revision: int) -> bool:
        """Guarda si la revisión coincide. Devuelve falso si otra persona la cambió."""
        ...
