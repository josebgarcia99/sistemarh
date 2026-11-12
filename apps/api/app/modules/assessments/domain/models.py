"""Evaluaciones posteriores de una postulación y síntesis del expediente.

Cuatro tipos de evaluación, todos ligados a una postulación:

- PSICOMETRIA: prueba psicométrica. Dato sensible: exige el permiso adicional.
- ENTREVISTA: entrevista con el gerente, capturada por RH.
- PRUEBA_TECNICA: prueba técnica opcional, con rúbrica y resultado calculado.
- ESTUDIO_SOCIOECONOMICO: formulario configurable con verificación documental.
  Dato sensible: exige el permiso adicional. No tiene puntuación de ningún tipo.

La IA puede resumir documentos y organizar lo capturado. No diagnostica, no
declara aptitud y no decide: cada conclusión es de una persona.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any, Protocol


class Kind(StrEnum):
    PSICOMETRIA = "PSICOMETRIA"
    ENTREVISTA = "ENTREVISTA"
    PRUEBA_TECNICA = "PRUEBA_TECNICA"
    ESTUDIO_SOCIOECONOMICO = "ESTUDIO_SOCIOECONOMICO"


# Tipos que exigen el permiso adicional sobre la vacante, además del acceso.
SENSITIVE_KINDS = frozenset({Kind.PSICOMETRIA, Kind.ESTUDIO_SOCIOECONOMICO})

STATUSES: dict[Kind, tuple[str, ...]] = {
    Kind.PSICOMETRIA: (
        "PENDIENTE",
        "PRESENTADA",
        "NO_PRESENTADA",
        "INCOMPLETA",
        "NO_APLICA",
        "ANULADA",
        "VALIDADA",
    ),
    Kind.ENTREVISTA: ("PROGRAMADA", "REALIZADA", "NO_REALIZADA", "CANCELADA"),
    Kind.PRUEBA_TECNICA: (
        "PENDIENTE",
        "REALIZADA",
        "NO_PRESENTADA",
        "INCOMPLETA",
        "NO_APLICA",
        "ANULADA",
    ),
    Kind.ESTUDIO_SOCIOECONOMICO: ("PENDIENTE", "EN_PROCESO", "COMPLETADO", "NO_APLICA", "ANULADO"),
}
ALL_STATUSES = tuple(dict.fromkeys(status for group in STATUSES.values() for status in group))


@dataclass
class Assessment:
    id: uuid.UUID
    application_id: uuid.UUID
    vacancy_id: uuid.UUID
    kind: Kind
    status: str
    # Lo capturado, ya validado según el tipo.
    data: dict[str, Any]
    created_at: datetime
    created_by: uuid.UUID
    updated_at: datetime
    updated_by: uuid.UUID
    # Aumenta con cada guardado: evita que dos personas se pisen.
    version: int = 1
    event_date: datetime | None = None
    file_id: uuid.UUID | None = None
    template_version_id: uuid.UUID | None = None
    # Resultado de una prueba técnica con rúbrica, calculado por el sistema (0 a 100).
    score: Decimal | None = None
    # Último resumen de IA, con su fecha y quién lo pidió. No es una conclusión.
    ai_summary: dict[str, Any] | None = None
    ai_summary_at: datetime | None = None
    ai_summary_by: uuid.UUID | None = None


class FieldType(StrEnum):
    TEXTO = "TEXTO"
    PARRAFO = "PARRAFO"
    FECHA = "FECHA"
    NUMERO = "NUMERO"
    OPCIONES = "OPCIONES"
    CASILLA = "CASILLA"
    DOCUMENTO = "DOCUMENTO"
    OBSERVACION = "OBSERVACION"
    # Filas con las mismas columnas (por ejemplo, los familiares o los estudios).
    TABLA = "TABLA"


@dataclass(frozen=True)
class FormField:
    id: str
    label: str
    type: FieldType
    required: bool = False
    options: tuple[str, ...] = ()
    minimum: Decimal | None = None
    maximum: Decimal | None = None
    # Encabezados de las columnas de una tabla.
    columns: tuple[str, ...] = ()
    # Solo lo captura una persona: la IA no lo llena al leer un documento.
    manual_only: bool = False


@dataclass(frozen=True)
class FormSection:
    title: str
    fields: tuple[FormField, ...]


@dataclass
class FormTemplate:
    id: uuid.UUID
    name: str
    status: str  # ACTIVA o ARCHIVADA
    created_at: datetime
    updated_at: datetime
    description: str | None = None


@dataclass(frozen=True)
class FormTemplateVersion:
    id: uuid.UUID
    template_id: uuid.UUID
    version_number: int
    sections: tuple[FormSection, ...]
    created_at: datetime
    created_by: uuid.UUID | None

    @property
    def fields(self) -> tuple[FormField, ...]:
        return tuple(item for section in self.sections for item in section.fields)


@dataclass(frozen=True)
class Synthesis:
    id: uuid.UUID
    application_id: uuid.UUID
    vacancy_id: uuid.UUID
    created_at: datetime
    created_by: uuid.UUID
    result: dict[str, Any]
    # Incluyó resultados psicométricos validados: verla exige el permiso adicional.
    includes_psychometrics: bool = False
    # Incluyó descripciones de fotografías del estudio socioeconómico: verla
    # exige el permiso adicional del estudio.
    includes_study: bool = False
    # Qué fuentes se usaron (por ejemplo, "2 llamadas").
    sources: tuple[str, ...] = ()


# --- Puertos -----------------------------------------------------------------------------


class Actor(Protocol):
    id: uuid.UUID

    @property
    def is_admin(self) -> bool: ...


@dataclass(frozen=True)
class ApplicationRef:
    id: uuid.UUID
    vacancy_id: uuid.UUID
    active: bool


@dataclass(frozen=True)
class DossierMaterial:
    """Lo que el resto del expediente aporta a la síntesis."""

    requirements: tuple[str, ...] = ()
    cv: dict[str, Any] = field(default_factory=dict)
    evaluation: dict[str, Any] = field(default_factory=dict)
    calls: tuple[dict[str, Any], ...] = ()


class Applications(Protocol):
    def get(self, application_id: uuid.UUID) -> ApplicationRef | None: ...

    def material(self, application_id: uuid.UUID) -> DossierMaterial: ...


class AssessmentAccess(Protocol):
    def require(self, actor: Actor, vacancy_id: uuid.UUID, kind: Kind, *, write: bool) -> None:
        """Lanza si el usuario no puede leer (o escribir) ese tipo en la vacante."""
        ...

    def readable(self, actor: Actor, vacancy_id: uuid.UUID) -> frozenset[Kind]:
        """Tipos que puede consultar. Lanza si no tiene acceso a la vacante."""
        ...


@dataclass(frozen=True)
class PhotoNote:
    """Descripción guardada junto a una fotografía del estudio."""

    label: str
    description: str
    # La propuso la IA y una persona la guardó, o la escribió una persona.
    proposed_by_ai: bool


@dataclass(frozen=True)
class Photo:
    media_type: str  # image/jpeg
    data: bytes


class DocumentError(Exception):
    """El documento no se puede usar. Mensaje apto para mostrarse."""


class Documents(Protocol):
    def belongs(self, vacancy_id: uuid.UUID, file_id: uuid.UUID, kind: Kind) -> bool:
        """El documento es de la vacante y del tipo que corresponde a la evaluación."""
        ...

    def read_text(self, vacancy_id: uuid.UUID, file_id: uuid.UUID) -> tuple[str, bool]:
        """Texto del documento y si se obtuvo por OCR. Lanza ``DocumentError``."""
        ...

    def read_photo(self, vacancy_id: uuid.UUID, file_id: uuid.UUID) -> Photo:
        """Fotografía lista para enviarse a la IA: reducida y sin metadatos (fecha,
        cámara, coordenadas). Lanza ``DocumentError`` si el documento no es una imagen."""
        ...


@dataclass(frozen=True)
class AssistantAnswer:
    ok: bool
    text: str
    complete: bool
    error: str | None


class Assistant(Protocol):
    def ask(
        self,
        operation: str,
        *,
        system: str,
        user: str,
        vacancy_id: uuid.UUID,
        actor_user_id: uuid.UUID,
        photos: tuple[Photo, ...] = (),
    ) -> AssistantAnswer: ...


class AssessmentRepository(Protocol):
    def get(self, assessment_id: uuid.UUID) -> Assessment | None: ...

    def for_application(self, application_id: uuid.UUID) -> list[Assessment]:
        """De la más antigua a la más reciente."""
        ...

    def add(self, assessment: Assessment) -> None: ...

    def save(self, assessment: Assessment, *, expected_version: int) -> bool:
        """Guarda si la versión coincide. Falso si otra persona la cambió."""
        ...

    def templates(self) -> list[FormTemplate]: ...

    def template(self, template_id: uuid.UUID) -> FormTemplate | None: ...

    def add_template(self, template: FormTemplate) -> None: ...

    def save_template(self, template: FormTemplate) -> None: ...

    def template_versions(self, template_id: uuid.UUID) -> list[FormTemplateVersion]:
        """De la más reciente a la más antigua."""
        ...

    def template_version(self, version_id: uuid.UUID) -> FormTemplateVersion | None: ...

    def add_template_version(self, version: FormTemplateVersion) -> None: ...

    def add_synthesis(self, synthesis: Synthesis) -> None: ...

    def syntheses(self, application_id: uuid.UUID) -> list[Synthesis]:
        """De la más reciente a la más antigua."""
        ...
