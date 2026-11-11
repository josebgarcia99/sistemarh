"""Perfil de puesto y prompt de evaluación de una vacante."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, Request, status
from pydantic import BaseModel, Field, model_validator

from app.composition.backend import Repositories
from app.composition.context import AppContext, client_ip, get_context
from app.core.exceptions.errors import ServiceUnavailableError
from app.modules.authentication.api.dependencies import Principal, require_user
from app.modules.evaluation_setup.domain import generator
from app.modules.evaluation_setup.domain.models import (
    LOCKED_LAYERS,
    LayerKey,
    ProfileVersion,
    PromptVersion,
)

router = APIRouter(tags=["perfil y prompt"])

_Items = list[str]


class ProfileIn(BaseModel):
    objective: str = ""
    experience: str = ""
    education: str = ""
    functions: _Items = Field(default_factory=list)
    responsibilities: _Items = Field(default_factory=list)
    knowledge: _Items = Field(default_factory=list)
    skills: _Items = Field(default_factory=list)
    certifications: _Items = Field(default_factory=list)
    must_have: _Items = Field(default_factory=list)
    nice_to_have: _Items = Field(default_factory=list)
    ambiguities: _Items = Field(default_factory=list)
    change_note: str | None = Field(default=None, max_length=300)
    # Número de la versión que la persona tenía a la vista (0 si no había perfil).
    expected_version: int = Field(ge=0)
    # La persona partió de una propuesta de la IA y la revisó.
    from_ai: bool = False
    # Documento de la vacante del que salió la propuesta, si lo hubo.
    source_file_id: uuid.UUID | None = None


class ProfileExtractionIn(BaseModel):
    """Un documento de perfil de la vacante o el texto pegado; uno de los dos."""

    file_id: uuid.UUID | None = None
    text: str | None = Field(default=None, max_length=200_000)

    @model_validator(mode="after")
    def _one_source(self) -> ProfileExtractionIn:
        if (self.file_id is None) == (self.text is None):
            raise ValueError("Elige un documento o pega el texto del perfil.")
        return self


class ProfileProposalOut(BaseModel):
    """Propuesta de la IA. No está guardada."""

    objective: str
    experience: str
    education: str
    functions: _Items
    responsibilities: _Items
    knowledge: _Items
    skills: _Items
    certifications: _Items
    must_have: _Items
    nice_to_have: _Items
    ambiguities: _Items
    truncated: bool
    source_file_id: uuid.UUID | None


class CriterionSuggestionOut(BaseModel):
    id: uuid.UUID
    code: str
    name: str
    description: str
    levels: list[str]


class CriteriaProposalOut(BaseModel):
    """Mejoras de redacción propuestas por la IA. No están guardadas."""

    suggestions: list[CriterionSuggestionOut]
    observations: list[str]


class ProfileVersionOut(BaseModel):
    id: uuid.UUID
    version_number: int
    origin: str
    change_note: str | None
    created_at: datetime
    created_by_name: str | None
    objective: str
    experience: str
    education: str
    functions: _Items
    responsibilities: _Items
    knowledge: _Items
    skills: _Items
    certifications: _Items
    must_have: _Items
    nice_to_have: _Items
    ambiguities: _Items


class CriterionIn(BaseModel):
    id: uuid.UUID | None = None
    name: str
    description: str = ""
    kind: str
    weight: Decimal
    levels: list[str]


class CriterionOut(BaseModel):
    id: uuid.UUID
    code: str
    name: str
    description: str
    kind: str
    weight: Decimal
    levels: list[str]
    origin: str


class LayerOut(BaseModel):
    key: LayerKey
    title: str
    content: str
    # Las capas del sistema no se editan a mano.
    locked: bool


class PromptOut(BaseModel):
    id: uuid.UUID
    vacancy_id: uuid.UUID
    version_number: int
    status: str
    profile_version_number: int | None
    pass_threshold: Decimal
    revision: int
    layers: list[LayerOut]
    criteria: list[CriterionOut]
    rendered: str
    length: int
    max_length: int
    # Lo que falta para poder enviarlo a revisión o aprobarlo.
    issues: list[str]
    duplicated_from: uuid.UUID | None
    created_at: datetime
    created_by_name: str | None
    updated_at: datetime
    approved_at: datetime | None
    approved_by_name: str | None


class PromptEditIn(BaseModel):
    layers: dict[str, str]
    criteria: list[CriterionIn]
    pass_threshold: Decimal
    revision: int = Field(ge=1)


class RevisionIn(BaseModel):
    revision: int = Field(ge=1)


def _names(repos: Repositories, ids: set[uuid.UUID | None]) -> dict[uuid.UUID, str]:
    users = repos.users.get_many([user_id for user_id in ids if user_id is not None])
    return {user_id: user.full_name for user_id, user in users.items()}


def _profile_out(version: ProfileVersion, names: dict[uuid.UUID, str]) -> ProfileVersionOut:
    content = version.content
    return ProfileVersionOut(
        id=version.id,
        version_number=version.version_number,
        origin=version.origin.value,
        change_note=version.change_note,
        created_at=version.created_at,
        created_by_name=names.get(version.created_by),
        objective=content.objective,
        experience=content.experience,
        education=content.education,
        functions=list(content.functions),
        responsibilities=list(content.responsibilities),
        knowledge=list(content.knowledge),
        skills=list(content.skills),
        certifications=list(content.certifications),
        must_have=list(content.must_have),
        nice_to_have=list(content.nice_to_have),
        ambiguities=list(content.ambiguities),
    )


def _prompt_out(repos: Repositories, version: PromptVersion) -> PromptOut:
    names = _names(repos, {version.created_by, version.approved_by})
    profile = repos.evaluation_setup.profile_version(version.profile_version_id)
    rendered = generator.render_prompt(version)
    return PromptOut(
        id=version.id,
        vacancy_id=version.vacancy_id,
        version_number=version.version_number,
        status=version.status.value,
        profile_version_number=profile.version_number if profile else None,
        pass_threshold=version.pass_threshold,
        revision=version.revision,
        layers=[
            LayerOut(
                key=key,
                title=generator.LAYER_TITLES[key],
                content=version.layers.get(key, ""),
                locked=key in LOCKED_LAYERS,
            )
            for key in LayerKey
        ],
        criteria=[
            CriterionOut(
                id=c.id,
                code=c.code,
                name=c.name,
                description=c.description,
                kind=c.kind.value,
                weight=c.weight,
                levels=list(c.levels),
                origin=c.origin.value,
            )
            for c in version.criteria
        ],
        rendered=rendered,
        length=len(rendered),
        max_length=generator.MAX_PROMPT_CHARS,
        issues=version.issues,
        duplicated_from=version.duplicated_from,
        created_at=version.created_at,
        created_by_name=names.get(version.created_by),
        updated_at=version.updated_at,
        approved_at=version.approved_at,
        approved_by_name=names.get(version.approved_by) if version.approved_by else None,
    )


@router.get(
    "/vacancies/{vacancy_id}/profile-versions",
    response_model=list[ProfileVersionOut],
    summary="Versiones del perfil de puesto, de la más reciente a la más antigua",
)
def list_profile_versions(
    vacancy_id: uuid.UUID,
    principal: Principal = Depends(require_user),  # noqa: B008
    context: AppContext = Depends(get_context),  # noqa: B008
) -> list[ProfileVersionOut]:
    with context.require_backend().transaction() as repos:
        versions = context.evaluation_setup(repos).profile_versions(principal.user, vacancy_id)
        names = _names(repos, {version.created_by for version in versions})
    return [_profile_out(version, names) for version in versions]


@router.post(
    "/vacancies/{vacancy_id}/profile-versions",
    response_model=ProfileVersionOut,
    status_code=status.HTTP_201_CREATED,
    summary="Guarda el perfil como una versión nueva",
)
def save_profile(
    vacancy_id: uuid.UUID,
    body: ProfileIn,
    request: Request,
    principal: Principal = Depends(require_user),  # noqa: B008
    context: AppContext = Depends(get_context),  # noqa: B008
) -> ProfileVersionOut:
    data = body.model_dump(exclude={"change_note", "expected_version", "from_ai", "source_file_id"})
    with context.require_backend().transaction() as repos:
        version = context.evaluation_setup(repos).save_profile(
            principal.user,
            vacancy_id,
            data,
            change_note=body.change_note,
            expected_version=body.expected_version,
            from_ai=body.from_ai or body.source_file_id is not None,
            source_file_id=body.source_file_id,
            ip=client_ip(request),
        )
        names = _names(repos, {version.created_by})
    return _profile_out(version, names)


@router.post(
    "/vacancies/{vacancy_id}/profile-extractions",
    response_model=ProfileProposalOut,
    summary="La IA lee un perfil (documento o texto) y lo devuelve como propuesta sin guardar",
)
def extract_profile(
    vacancy_id: uuid.UUID,
    body: ProfileExtractionIn,
    request: Request,
    principal: Principal = Depends(require_user),  # noqa: B008
    context: AppContext = Depends(get_context),  # noqa: B008
) -> ProfileProposalOut:
    with context.require_backend().transaction() as repos:
        proposal = context.evaluation_setup(repos).extract_profile(
            principal.user,
            vacancy_id,
            file_id=body.file_id,
            text=body.text,
            ip=client_ip(request),
        )
    # El consumo de la llamada ya quedó registrado; el fallo se informa después.
    if proposal.content is None:
        raise ServiceUnavailableError(proposal.error)
    content = proposal.content
    return ProfileProposalOut(
        objective=content.objective,
        experience=content.experience,
        education=content.education,
        functions=list(content.functions),
        responsibilities=list(content.responsibilities),
        knowledge=list(content.knowledge),
        skills=list(content.skills),
        certifications=list(content.certifications),
        must_have=list(content.must_have),
        nice_to_have=list(content.nice_to_have),
        ambiguities=list(content.ambiguities),
        truncated=proposal.truncated,
        source_file_id=proposal.source_file_id,
    )


@router.get(
    "/vacancies/{vacancy_id}/prompts",
    response_model=list[PromptOut],
    summary="Versiones del prompt de evaluación",
)
def list_prompts(
    vacancy_id: uuid.UUID,
    principal: Principal = Depends(require_user),  # noqa: B008
    context: AppContext = Depends(get_context),  # noqa: B008
) -> list[PromptOut]:
    with context.require_backend().transaction() as repos:
        versions = context.evaluation_setup(repos).prompt_versions(principal.user, vacancy_id)
        return [_prompt_out(repos, version) for version in versions]


@router.post(
    "/vacancies/{vacancy_id}/prompts",
    response_model=PromptOut,
    status_code=status.HTTP_201_CREATED,
    summary="Genera un borrador a partir del perfil vigente",
)
def generate_prompt(
    vacancy_id: uuid.UUID,
    request: Request,
    principal: Principal = Depends(require_user),  # noqa: B008
    context: AppContext = Depends(get_context),  # noqa: B008
) -> PromptOut:
    with context.require_backend().transaction() as repos:
        version = context.evaluation_setup(repos).generate(
            principal.user, vacancy_id, ip=client_ip(request)
        )
        return _prompt_out(repos, version)


@router.get("/prompts/{version_id}", response_model=PromptOut, summary="Una versión del prompt")
def get_prompt(
    version_id: uuid.UUID,
    principal: Principal = Depends(require_user),  # noqa: B008
    context: AppContext = Depends(get_context),  # noqa: B008
) -> PromptOut:
    with context.require_backend().transaction() as repos:
        version = context.evaluation_setup(repos).prompt_version(principal.user, version_id)
        return _prompt_out(repos, version)


@router.put("/prompts/{version_id}", response_model=PromptOut, summary="Edita un borrador")
def update_prompt(
    version_id: uuid.UUID,
    body: PromptEditIn,
    request: Request,
    principal: Principal = Depends(require_user),  # noqa: B008
    context: AppContext = Depends(get_context),  # noqa: B008
) -> PromptOut:
    with context.require_backend().transaction() as repos:
        version = context.evaluation_setup(repos).update_draft(
            principal.user,
            version_id,
            layers=dict(body.layers),
            criteria=[criterion.model_dump() for criterion in body.criteria],
            pass_threshold=body.pass_threshold,
            expected_revision=body.revision,
            ip=client_ip(request),
        )
        return _prompt_out(repos, version)


def _transition_route(path: str, method: str, summary: str) -> None:
    @router.post(f"/prompts/{{version_id}}/{path}", response_model=PromptOut, summary=summary)
    def _route(
        version_id: uuid.UUID,
        body: RevisionIn,
        request: Request,
        principal: Principal = Depends(require_user),  # noqa: B008
        context: AppContext = Depends(get_context),  # noqa: B008
    ) -> PromptOut:
        with context.require_backend().transaction() as repos:
            action = getattr(context.evaluation_setup(repos), method)
            version = action(
                principal.user, version_id, expected_revision=body.revision, ip=client_ip(request)
            )
            return _prompt_out(repos, version)

    _route.__name__ = f"prompt_{method}"


_transition_route("submit", "submit", "Envía el borrador a revisión")
_transition_route("return", "return_to_draft", "Devuelve a borrador para corregir")
_transition_route("approve", "approve", "Aprueba la versión (queda inmutable)")
_transition_route("archive", "archive", "Archiva la versión")


@router.post(
    "/prompts/{version_id}/criteria-proposals",
    response_model=CriteriaProposalOut,
    summary="La IA propone una mejor redacción de los criterios de un borrador, sin guardar",
)
def propose_criteria(
    version_id: uuid.UUID,
    request: Request,
    principal: Principal = Depends(require_user),  # noqa: B008
    context: AppContext = Depends(get_context),  # noqa: B008
) -> CriteriaProposalOut:
    with context.require_backend().transaction() as repos:
        proposal = context.evaluation_setup(repos).propose_criteria(
            principal.user, version_id, ip=client_ip(request)
        )
    if proposal.suggestions is None:
        raise ServiceUnavailableError(proposal.error)
    return CriteriaProposalOut(
        suggestions=[
            CriterionSuggestionOut(
                id=item.criterion.id,
                code=item.criterion.code,
                name=item.criterion.name,
                description=item.description,
                levels=list(item.levels),
            )
            for item in proposal.suggestions.suggestions
        ],
        observations=list(proposal.suggestions.observations),
    )


@router.post(
    "/prompts/{version_id}/duplicate",
    response_model=PromptOut,
    status_code=status.HTTP_201_CREATED,
    summary="Copia la versión como borrador nuevo",
)
def duplicate_prompt(
    version_id: uuid.UUID,
    request: Request,
    principal: Principal = Depends(require_user),  # noqa: B008
    context: AppContext = Depends(get_context),  # noqa: B008
) -> PromptOut:
    with context.require_backend().transaction() as repos:
        version = context.evaluation_setup(repos).duplicate(
            principal.user, version_id, ip=client_ip(request)
        )
        return _prompt_out(repos, version)
