"""Bancos de preguntas y llamadas telefónicas."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Request, status
from pydantic import BaseModel, Field

from app.composition.backend import Repositories
from app.composition.context import AppContext, client_ip, get_context
from app.core.exceptions.errors import ServiceUnavailableError
from app.modules.authentication.api.dependencies import Principal, require_user
from app.modules.phone_calls.application.service import BankView, CallView
from app.modules.phone_calls.domain.models import MAX_CALL_QUESTIONS, BankVersion

router = APIRouter(tags=["bancos de preguntas y llamadas"])
_user = Depends(require_user)
_context = Depends(get_context)


class QuestionIn(BaseModel):
    id: uuid.UUID | None = None
    text: str = Field(max_length=1000)
    competency: str = Field(default="", max_length=100)
    guidance: str = Field(default="", max_length=1000)
    origin: str = "MANUAL"


class QuestionOut(BaseModel):
    id: uuid.UUID
    text: str
    competency: str
    guidance: str
    origin: str


class BankIn(BaseModel):
    name: str = Field(max_length=150)
    description: str | None = Field(default=None, max_length=500)
    shared: bool = False
    # Preguntas generales de la empresa: se agregan a toda llamada. Solo administradores.
    general: bool = False
    questions: list[QuestionIn]


class BankUpdateIn(BankIn):
    change_note: str | None = Field(default=None, max_length=300)
    expected_version: int


class BankOut(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    owner_name: str | None
    mine: bool
    can_edit: bool
    shared: bool
    general: bool
    status: str
    version_number: int
    questions: list[QuestionOut]
    updated_at: datetime


class BankVersionOut(BaseModel):
    version_number: int
    questions: int
    change_note: str | None
    created_at: datetime
    created_by_name: str | None


class BankDetailOut(BaseModel):
    bank: BankOut
    versions: list[BankVersionOut]


class ProposalIn(BaseModel):
    vacancy_id: uuid.UUID
    count: int = Field(default=8, ge=1, le=15)


class ProposedQuestionOut(BaseModel):
    text: str
    competency: str
    guidance: str


class AnswerIn(BaseModel):
    question_id: uuid.UUID
    answer: str = Field(default="", max_length=6000)
    notes: str = Field(default="", max_length=1000)
    not_asked: bool = False


class CallQuestionIn(BaseModel):
    """Una pregunta de la lista propia de la llamada."""

    # El que ya tenía en la llamada o en su banco. Para una pregunta escrita
    # solo para esta llamada, uno nuevo generado por quien la escribe.
    id: uuid.UUID
    text: str = Field(max_length=1000)
    competency: str = Field(default="", max_length=100)
    guidance: str = Field(default="", max_length=1000)
    # Quitada de esta llamada (se puede volver a incluir mientras es borrador).
    omitted: bool = False
    # Banco del que se toma, cuando la pregunta todavía no está en la llamada.
    bank_id: uuid.UUID | None = None


class CallIn(BaseModel):
    answers: list[AnswerIn]
    notes: str = Field(default="", max_length=6000)
    called_at: datetime | None = None
    # La lista de preguntas de esta llamada, en orden. Si no se envía, no cambia.
    questions: list[CallQuestionIn] | None = Field(default=None, max_length=MAX_CALL_QUESTIONS)
    # Cerrar la llamada: ya no se podrá modificar.
    close: bool = False
    # Guardado que hace la pantalla sola mientras la persona escribe.
    autosave: bool = False


class NewCallIn(BaseModel):
    # Bancos cuyas preguntas se suman a las generales de la empresa. Puede ir vacío.
    bank_ids: list[uuid.UUID] = Field(default_factory=list, max_length=10)
    # Forma anterior (un solo banco). Se acepta para que una pantalla abierta
    # antes de la actualización siga funcionando.
    bank_id: uuid.UUID | None = None


class CallQuestionOut(QuestionOut):
    # De dónde salió: GENERAL (de la empresa), BANCO o LLAMADA (escrita para esta).
    source: str
    # Pregunta general de la empresa.
    general: bool
    bank_id: uuid.UUID | None
    bank_name: str
    # Redacción del banco, si se cambió para esta llamada.
    original_text: str | None
    # Quitada de esta llamada.
    omitted: bool
    answer: str
    notes: str
    not_asked: bool


class CallOut(BaseModel):
    id: uuid.UUID
    application_id: uuid.UUID
    status: str
    # De dónde salen las preguntas que se hacen: bancos y, si las hay, las escritas.
    sources: list[str]
    # Forma anterior (un solo banco por llamada). Se conserva para que una
    # pantalla abierta antes de la actualización siga mostrando las llamadas.
    bank_name: str
    bank_version: int
    called_at: datetime
    created_by_name: str | None
    notes: str
    questions: list[CallQuestionOut]
    analysis: dict[str, Any] | None
    analysis_at: datetime | None
    closed_at: datetime | None


def _names(repos: Repositories, ids: set[uuid.UUID | None]) -> dict[uuid.UUID, str]:
    users = repos.users.get_many([uid for uid in ids if uid is not None])
    return {uid: user.full_name for uid, user in users.items()}


def _questions(version: BankVersion) -> list[QuestionOut]:
    return [
        QuestionOut(
            id=q.id, text=q.text, competency=q.competency, guidance=q.guidance, origin=q.origin
        )
        for q in version.questions
    ]


def _bank_out(view: BankView, principal: Principal, names: dict[uuid.UUID, str]) -> BankOut:
    bank = view.bank
    return BankOut(
        id=bank.id,
        name=bank.name,
        description=bank.description,
        owner_name=names.get(bank.owner_user_id),
        mine=bank.owner_user_id == principal.user.id,
        can_edit=view.can_edit,
        shared=bank.scope.value == "COMPARTIDO",
        general=bank.scope.value == "GENERAL",
        status=bank.status.value,
        version_number=view.latest.version_number,
        questions=_questions(view.latest),
        updated_at=bank.updated_at,
    )


def _call_out(view: CallView, names: dict[uuid.UUID, str]) -> CallOut:
    call = view.call
    answers = {answer.question_id: answer for answer in call.answers}
    return CallOut(
        id=call.id,
        application_id=call.application_id,
        status=call.status.value,
        sources=list(view.sources),
        bank_name=" + ".join(view.sources),
        bank_version=next((q.bank_version for q in view.questions if q.bank_version), 0),
        called_at=call.called_at,
        created_by_name=names.get(call.created_by),
        notes=call.notes,
        questions=[
            CallQuestionOut(
                id=q.id,
                text=q.text,
                competency=q.competency,
                guidance=q.guidance,
                origin=q.origin,
                source=q.source.value,
                general=q.source.value == "GENERAL",
                bank_id=q.bank_id,
                bank_name=q.bank_name,
                original_text=q.original_text,
                omitted=q.omitted,
                answer=answers[q.id].answer if q.id in answers else "",
                notes=answers[q.id].notes if q.id in answers else "",
                not_asked=answers[q.id].not_asked if q.id in answers else False,
            )
            for q in view.questions
        ],
        analysis=call.analysis,
        analysis_at=call.analysis_at,
        closed_at=call.closed_at,
    )


# --- Bancos ------------------------------------------------------------------------------


@router.get("/question-banks", response_model=list[BankOut], summary="Bancos propios y compartidos")
def list_banks(principal: Principal = _user, context: AppContext = _context) -> list[BankOut]:
    with context.require_backend().transaction() as repos:
        views = context.phone_calls(repos).banks(principal.user)
        names = _names(repos, {view.bank.owner_user_id for view in views})
    return [_bank_out(view, principal, names) for view in views]


@router.post(
    "/question-banks",
    response_model=BankOut,
    status_code=status.HTTP_201_CREATED,
    summary="Crea un banco de preguntas",
)
def create_bank(
    body: BankIn, request: Request, principal: Principal = _user, context: AppContext = _context
) -> BankOut:
    with context.require_backend().transaction() as repos:
        view = context.phone_calls(repos).create_bank(
            principal.user,
            name=body.name,
            description=body.description,
            shared=body.shared,
            general=body.general,
            questions=[q.model_dump() for q in body.questions],
            ip=client_ip(request),
        )
        names = _names(repos, {view.bank.owner_user_id})
    return _bank_out(view, principal, names)


@router.post(
    "/question-banks/question-proposals",
    response_model=list[ProposedQuestionOut],
    summary="La IA propone preguntas a partir del perfil de una vacante, sin guardar",
)
def propose_questions(
    body: ProposalIn, request: Request, principal: Principal = _user, context: AppContext = _context
) -> list[ProposedQuestionOut]:
    with context.require_backend().transaction() as repos:
        proposal = context.phone_calls(repos).propose_questions(
            principal.user, body.vacancy_id, body.count, ip=client_ip(request)
        )
    # El consumo de la llamada ya quedó registrado; el fallo se informa después.
    if proposal.content is None:
        raise ServiceUnavailableError(proposal.error)
    return [ProposedQuestionOut(**item) for item in proposal.content]  # type: ignore[union-attr]


@router.get(
    "/question-banks/{bank_id}", response_model=BankDetailOut, summary="Banco y sus versiones"
)
def get_bank(
    bank_id: uuid.UUID, principal: Principal = _user, context: AppContext = _context
) -> BankDetailOut:
    with context.require_backend().transaction() as repos:
        view, versions = context.phone_calls(repos).bank(principal.user, bank_id)
        names = _names(repos, {view.bank.owner_user_id, *(v.created_by for v in versions)})
    return BankDetailOut(
        bank=_bank_out(view, principal, names),
        versions=[
            BankVersionOut(
                version_number=v.version_number,
                questions=len(v.questions),
                change_note=v.change_note,
                created_at=v.created_at,
                created_by_name=names.get(v.created_by),
            )
            for v in versions
        ],
    )


@router.put(
    "/question-banks/{bank_id}",
    response_model=BankOut,
    summary="Guarda el banco; si cambian las preguntas crea una versión nueva",
)
def update_bank(
    bank_id: uuid.UUID,
    body: BankUpdateIn,
    request: Request,
    principal: Principal = _user,
    context: AppContext = _context,
) -> BankOut:
    with context.require_backend().transaction() as repos:
        view = context.phone_calls(repos).update_bank(
            principal.user,
            bank_id,
            name=body.name,
            description=body.description,
            shared=body.shared,
            general=body.general,
            questions=[q.model_dump() for q in body.questions],
            change_note=body.change_note,
            expected_version=body.expected_version,
            ip=client_ip(request),
        )
        names = _names(repos, {view.bank.owner_user_id})
    return _bank_out(view, principal, names)


def _bank_action(path: str, summary: str, code: int = status.HTTP_200_OK) -> None:
    @router.post(
        f"/question-banks/{{bank_id}}/{path}",
        response_model=BankOut,
        summary=summary,
        status_code=code,
    )
    def _route(
        bank_id: uuid.UUID,
        request: Request,
        principal: Principal = _user,
        context: AppContext = _context,
    ) -> BankOut:
        with context.require_backend().transaction() as repos:
            service = context.phone_calls(repos)
            if path == "duplicate":
                view = service.duplicate_bank(principal.user, bank_id, ip=client_ip(request))
            else:
                view = service.set_archived(
                    principal.user, bank_id, path == "archive", ip=client_ip(request)
                )
            names = _names(repos, {view.bank.owner_user_id})
        return _bank_out(view, principal, names)

    _route.__name__ = f"bank_{path}"


_bank_action("archive", "Archiva el banco")
_bank_action("restore", "Restaura un banco archivado")
_bank_action("duplicate", "Copia el banco como propio y privado", status.HTTP_201_CREATED)


# --- Llamadas ----------------------------------------------------------------------------


@router.get(
    "/applications/{application_id}/calls",
    response_model=list[CallOut],
    summary="Llamadas de una postulación",
)
def list_calls(
    application_id: uuid.UUID, principal: Principal = _user, context: AppContext = _context
) -> list[CallOut]:
    with context.require_backend().transaction() as repos:
        views = context.phone_calls(repos).calls(principal.user, application_id)
        names = _names(repos, {view.call.created_by for view in views})
    return [_call_out(view, names) for view in views]


@router.post(
    "/applications/{application_id}/calls",
    response_model=CallOut,
    status_code=status.HTTP_201_CREATED,
    summary="Abre una llamada con las preguntas generales y las de los bancos elegidos",
)
def open_call(
    application_id: uuid.UUID,
    body: NewCallIn,
    request: Request,
    principal: Principal = _user,
    context: AppContext = _context,
) -> CallOut:
    with context.require_backend().transaction() as repos:
        view = context.phone_calls(repos).open_call(
            principal.user,
            application_id,
            [*body.bank_ids, *([body.bank_id] if body.bank_id else [])],
            ip=client_ip(request),
        )
        names = _names(repos, {view.call.created_by})
    return _call_out(view, names)


@router.get("/calls/{call_id}", response_model=CallOut, summary="Una llamada")
def get_call(
    call_id: uuid.UUID, principal: Principal = _user, context: AppContext = _context
) -> CallOut:
    with context.require_backend().transaction() as repos:
        view = context.phone_calls(repos).call(principal.user, call_id)
        names = _names(repos, {view.call.created_by})
    return _call_out(view, names)


@router.put("/calls/{call_id}", response_model=CallOut, summary="Guarda o cierra la llamada")
def save_call(
    call_id: uuid.UUID,
    body: CallIn,
    request: Request,
    principal: Principal = _user,
    context: AppContext = _context,
) -> CallOut:
    with context.require_backend().transaction() as repos:
        view = context.phone_calls(repos).save_call(
            principal.user,
            call_id,
            answers=[answer.model_dump() for answer in body.answers],
            questions=(
                [question.model_dump() for question in body.questions]
                if body.questions is not None
                else None
            ),
            notes=body.notes,
            called_at=body.called_at,
            close=body.close,
            autosave=body.autosave,
            ip=client_ip(request),
        )
        names = _names(repos, {view.call.created_by})
    return _call_out(view, names)


@router.post(
    "/calls/{call_id}/analysis",
    response_model=CallOut,
    summary="La IA resume lo que aporta la llamada; no decide nada",
)
def analyze_call(
    call_id: uuid.UUID,
    request: Request,
    principal: Principal = _user,
    context: AppContext = _context,
) -> CallOut:
    with context.require_backend().transaction() as repos:
        view, error = context.phone_calls(repos).analyze_call(
            principal.user, call_id, ip=client_ip(request)
        )
        names = _names(repos, {view.call.created_by})
    if error is not None:
        raise ServiceUnavailableError(error)
    return _call_out(view, names)
