"""Evaluaciones posteriores, formularios del estudio socioeconómico y síntesis."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, Request, status
from pydantic import BaseModel, Field

from app.composition.backend import Repositories
from app.composition.context import AppContext, client_ip, get_context
from app.core.exceptions.errors import ServiceUnavailableError
from app.modules.assessments.domain.models import (
    STATUSES,
    Assessment,
    FormTemplate,
    FormTemplateVersion,
    Kind,
    Synthesis,
)
from app.modules.authentication.api.dependencies import Principal, require_admin, require_user

router = APIRouter(tags=["evaluaciones posteriores"])
_user = Depends(require_user)
_admin = Depends(require_admin)
_context = Depends(get_context)


class FieldOut(BaseModel):
    id: str
    label: str
    type: str
    required: bool
    options: list[str]
    minimum: Decimal | None
    maximum: Decimal | None
    columns: list[str]
    manual_only: bool


class SectionOut(BaseModel):
    title: str
    fields: list[FieldOut]


class TemplateOut(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    status: str
    version_number: int
    sections: list[SectionOut]


class FieldIn(BaseModel):
    id: str | None = None
    label: str = Field(max_length=200)
    type: str
    required: bool = False
    options: list[str] = Field(default_factory=list)
    minimum: Decimal | None = None
    maximum: Decimal | None = None
    # Encabezados de las columnas, si el campo es una tabla.
    columns: list[str] = Field(default_factory=list)
    # Solo lo captura una persona: la IA no lo llena al leer un documento.
    manual_only: bool = False


class SectionIn(BaseModel):
    title: str = Field(max_length=150)
    fields: list[FieldIn]


class TemplateIn(BaseModel):
    name: str = Field(max_length=150)
    description: str | None = Field(default=None, max_length=500)
    sections: list[SectionIn]
    # Número de la versión que la persona tenía a la vista (0 al crear).
    expected_version: int = 0


class AssessmentIn(BaseModel):
    status: str | None = None
    data: dict[str, Any] = Field(default_factory=dict)
    event_date: datetime | None = None
    file_id: uuid.UUID | None = None


class NewAssessmentIn(AssessmentIn):
    kind: Kind
    # Formulario del estudio socioeconómico (solo para ese tipo).
    template_id: uuid.UUID | None = None


class AssessmentUpdateIn(AssessmentIn):
    status: str
    version: int


class AssessmentOut(BaseModel):
    id: uuid.UUID
    application_id: uuid.UUID
    kind: str
    status: str
    # Estados que admite este tipo de evaluación.
    statuses: list[str]
    event_date: datetime | None
    file_id: uuid.UUID | None
    data: dict[str, Any]
    # Calificación de una prueba técnica con rúbrica, calculada por el sistema.
    score: Decimal | None
    ai_summary: dict[str, Any] | None
    ai_summary_at: datetime | None
    # Formulario con el que se capturó un estudio socioeconómico.
    form: list[SectionOut] | None
    version: int
    updated_at: datetime
    updated_by_name: str | None


class AssessmentListOut(BaseModel):
    items: list[AssessmentOut]
    # Tipos que existen pero que este usuario no puede consultar.
    restricted: list[str]
    # Tipos que este usuario puede capturar.
    writable: list[str]


class DigitizationIn(BaseModel):
    file_id: uuid.UUID


class PhotoDescriptionIn(BaseModel):
    file_id: uuid.UUID
    # Campo del formulario al que pertenece la fotografía (da contexto a la IA).
    field_id: str | None = Field(default=None, max_length=40)


class PhotoDescriptionOut(BaseModel):
    """Descripción propuesta por la IA. No está guardada ni verificada."""

    description: str
    # Lo que la IA indicó que no se distingue en la imagen.
    unclear: list[str]


class DigitizationOut(BaseModel):
    """Propuesta de la IA. No está guardada ni verificada."""

    values: dict[str, Any]
    illegible: list[str]
    missing: list[str]


class SynthesisOut(BaseModel):
    id: uuid.UUID
    created_at: datetime
    created_by_name: str | None
    result: dict[str, list[str]]
    sources: list[str]
    includes_psychometrics: bool
    includes_study: bool


class SynthesisViewOut(BaseModel):
    latest: SynthesisOut | None
    total: int
    # Existen síntesis que este usuario no puede ver por incluir psicometría.
    hidden: bool


def _sections(version: FormTemplateVersion) -> list[SectionOut]:
    return [
        SectionOut(
            title=section.title,
            fields=[
                FieldOut(
                    id=item.id,
                    label=item.label,
                    type=item.type.value,
                    required=item.required,
                    options=list(item.options),
                    minimum=item.minimum,
                    maximum=item.maximum,
                    columns=list(item.columns),
                    manual_only=item.manual_only,
                )
                for item in section.fields
            ],
        )
        for section in version.sections
    ]


def _template_out(template: FormTemplate, version: FormTemplateVersion) -> TemplateOut:
    return TemplateOut(
        id=template.id,
        name=template.name,
        description=template.description,
        status=template.status,
        version_number=version.version_number,
        sections=_sections(version),
    )


def _names(repos: Repositories, ids: set[uuid.UUID]) -> dict[uuid.UUID, str]:
    return {uid: user.full_name for uid, user in repos.users.get_many(list(ids)).items()}


def _out(context: AppContext, repos: Repositories, item: Assessment) -> AssessmentOut:
    names = _names(repos, {item.updated_by})
    form = None
    if item.template_version_id is not None:
        version = context.assessments(repos).template_version(item.template_version_id)
        form = _sections(version) if version else None
    return AssessmentOut(
        id=item.id,
        application_id=item.application_id,
        kind=item.kind.value,
        status=item.status,
        statuses=list(STATUSES[item.kind]),
        event_date=item.event_date,
        file_id=item.file_id,
        data=item.data,
        score=item.score,
        ai_summary=item.ai_summary,
        ai_summary_at=item.ai_summary_at,
        form=form,
        version=item.version,
        updated_at=item.updated_at,
        updated_by_name=names.get(item.updated_by),
    )


def _synthesis_out(repos: Repositories, item: Synthesis) -> SynthesisOut:
    return SynthesisOut(
        id=item.id,
        created_at=item.created_at,
        created_by_name=_names(repos, {item.created_by}).get(item.created_by),
        result=item.result,
        sources=list(item.sources),
        includes_psychometrics=item.includes_psychometrics,
        includes_study=item.includes_study,
    )


# --- Formularios -------------------------------------------------------------------------


@router.get(
    "/form-templates",
    response_model=list[TemplateOut],
    summary="Formularios de estudio socioeconómico",
)
def list_templates(_: Principal = _user, context: AppContext = _context) -> list[TemplateOut]:
    with context.require_backend().transaction() as repos:
        return [_template_out(t, v) for t, v in context.assessments(repos).templates()]


@router.post(
    "/form-templates",
    response_model=TemplateOut,
    status_code=status.HTTP_201_CREATED,
    summary="Crea un formulario (solo administradores)",
)
def create_template(
    body: TemplateIn,
    request: Request,
    principal: Principal = _admin,
    context: AppContext = _context,
) -> TemplateOut:
    with context.require_backend().transaction() as repos:
        return _template_out(
            *context.assessments(repos).save_template(
                principal.user,
                None,
                name=body.name,
                description=body.description,
                sections=[section.model_dump() for section in body.sections],
                ip=client_ip(request),
            )
        )


@router.put(
    "/form-templates/{template_id}",
    response_model=TemplateOut,
    summary="Guarda el formulario; si cambian sus campos crea una versión nueva",
)
def update_template(
    template_id: uuid.UUID,
    body: TemplateIn,
    request: Request,
    principal: Principal = _admin,
    context: AppContext = _context,
) -> TemplateOut:
    with context.require_backend().transaction() as repos:
        return _template_out(
            *context.assessments(repos).save_template(
                principal.user,
                template_id,
                name=body.name,
                description=body.description,
                sections=[section.model_dump() for section in body.sections],
                expected_version=body.expected_version,
                ip=client_ip(request),
            )
        )


def _template_action(path: str, archived: bool, summary: str) -> None:
    @router.post(
        f"/form-templates/{{template_id}}/{path}", response_model=TemplateOut, summary=summary
    )
    def _route(
        template_id: uuid.UUID, principal: Principal = _admin, context: AppContext = _context
    ) -> TemplateOut:
        with context.require_backend().transaction() as repos:
            return _template_out(
                *context.assessments(repos).set_template_archived(
                    principal.user, template_id, archived
                )
            )

    _route.__name__ = f"template_{path}"


_template_action("archive", True, "Archiva el formulario")
_template_action("restore", False, "Restaura un formulario archivado")


# --- Evaluaciones ------------------------------------------------------------------------


@router.get(
    "/applications/{application_id}/assessments",
    response_model=AssessmentListOut,
    summary="Evaluaciones posteriores de una postulación que el usuario puede ver",
)
def list_assessments(
    application_id: uuid.UUID, principal: Principal = _user, context: AppContext = _context
) -> AssessmentListOut:
    with context.require_backend().transaction() as repos:
        found = context.assessments(repos).for_application(principal.user, application_id)
        return AssessmentListOut(
            items=[_out(context, repos, item) for item in found.items],
            restricted=[kind.value for kind in found.restricted],
            writable=sorted(kind.value for kind in found.writable),
        )


@router.post(
    "/applications/{application_id}/assessments",
    response_model=AssessmentOut,
    status_code=status.HTTP_201_CREATED,
    summary="Registra una evaluación de la postulación",
)
def create_assessment(
    application_id: uuid.UUID,
    body: NewAssessmentIn,
    request: Request,
    principal: Principal = _user,
    context: AppContext = _context,
) -> AssessmentOut:
    with context.require_backend().transaction() as repos:
        item = context.assessments(repos).create(
            principal.user,
            application_id,
            body.kind,
            status=body.status,
            data=body.data,
            event_date=body.event_date,
            file_id=body.file_id,
            template_id=body.template_id,
            ip=client_ip(request),
        )
        return _out(context, repos, item)


@router.get("/assessments/{assessment_id}", response_model=AssessmentOut, summary="Una evaluación")
def get_assessment(
    assessment_id: uuid.UUID, principal: Principal = _user, context: AppContext = _context
) -> AssessmentOut:
    with context.require_backend().transaction() as repos:
        return _out(context, repos, context.assessments(repos).get(principal.user, assessment_id))


@router.put(
    "/assessments/{assessment_id}", response_model=AssessmentOut, summary="Guarda la evaluación"
)
def update_assessment(
    assessment_id: uuid.UUID,
    body: AssessmentUpdateIn,
    request: Request,
    principal: Principal = _user,
    context: AppContext = _context,
) -> AssessmentOut:
    with context.require_backend().transaction() as repos:
        item = context.assessments(repos).update(
            principal.user,
            assessment_id,
            status=body.status,
            data=body.data,
            event_date=body.event_date,
            file_id=body.file_id,
            expected_version=body.version,
            ip=client_ip(request),
        )
        return _out(context, repos, item)


@router.post(
    "/assessments/{assessment_id}/summary",
    response_model=AssessmentOut,
    summary="La IA resume lo documentado; no diagnostica ni decide",
)
def summarize_assessment(
    assessment_id: uuid.UUID,
    request: Request,
    principal: Principal = _user,
    context: AppContext = _context,
) -> AssessmentOut:
    with context.require_backend().transaction() as repos:
        item, error = context.assessments(repos).summarize(
            principal.user, assessment_id, ip=client_ip(request)
        )
        body = _out(context, repos, item)
    # El consumo de la llamada ya quedó registrado; el fallo se informa después.
    if error is not None:
        raise ServiceUnavailableError(error)
    return body


@router.post(
    "/assessments/{assessment_id}/digitization",
    response_model=DigitizationOut,
    summary="La IA lee un formulario escaneado y propone valores, sin guardar ni verificar",
)
def digitize_study(
    assessment_id: uuid.UUID,
    body: DigitizationIn,
    request: Request,
    principal: Principal = _user,
    context: AppContext = _context,
) -> DigitizationOut:
    with context.require_backend().transaction() as repos:
        outcome = context.assessments(repos).digitize(
            principal.user, assessment_id, body.file_id, ip=client_ip(request)
        )
    if outcome.content is None:
        raise ServiceUnavailableError(outcome.error)
    return DigitizationOut(**outcome.content)


@router.post(
    "/assessments/{assessment_id}/photo-descriptions",
    response_model=PhotoDescriptionOut,
    summary="La IA describe lo que se ve en una fotografía del estudio, sin guardar nada",
)
def describe_study_photo(
    assessment_id: uuid.UUID,
    body: PhotoDescriptionIn,
    request: Request,
    principal: Principal = _user,
    context: AppContext = _context,
) -> PhotoDescriptionOut:
    with context.require_backend().transaction() as repos:
        outcome = context.assessments(repos).describe_photo(
            principal.user,
            assessment_id,
            body.file_id,
            field_id=body.field_id,
            ip=client_ip(request),
        )
    if outcome.content is None:
        raise ServiceUnavailableError(outcome.error)
    return PhotoDescriptionOut(**outcome.content)


# --- Síntesis ----------------------------------------------------------------------------


@router.get(
    "/applications/{application_id}/syntheses",
    response_model=SynthesisViewOut,
    summary="Última síntesis del expediente que el usuario puede ver",
)
def get_syntheses(
    application_id: uuid.UUID, principal: Principal = _user, context: AppContext = _context
) -> SynthesisViewOut:
    with context.require_backend().transaction() as repos:
        view = context.assessments(repos).syntheses(principal.user, application_id)
        return SynthesisViewOut(
            latest=_synthesis_out(repos, view.latest) if view.latest else None,
            total=view.total,
            hidden=view.hidden,
        )


@router.post(
    "/applications/{application_id}/syntheses",
    response_model=SynthesisOut,
    status_code=status.HTTP_201_CREATED,
    summary="La IA sintetiza el expediente por tipo de fuente; no puntúa ni recomienda",
)
def create_synthesis(
    application_id: uuid.UUID,
    request: Request,
    principal: Principal = _user,
    context: AppContext = _context,
) -> SynthesisOut:
    with context.require_backend().transaction() as repos:
        outcome = context.assessments(repos).synthesize(
            principal.user, application_id, ip=client_ip(request)
        )
        body = _synthesis_out(repos, outcome.content) if outcome.content else None
    if body is None:
        raise ServiceUnavailableError(outcome.error)
    return body
