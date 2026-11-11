"""Bancos de preguntas y llamadas telefónicas: reglas y permisos.

Bancos: cada persona ve los suyos y los compartidos; el administrador ve
todos. Solo el propietario o un administrador los modifica, comparte o
archiva. Cualquiera que vea un banco puede duplicarlo como propio.

Llamadas: pertenecen a una postulación y siguen el permiso de su vacante
(lectura para consultar, colaboración para capturar y pedir el análisis).
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from app.core.exceptions.errors import (
    ConflictError,
    NotFoundError,
    PermissionDeniedError,
    ServiceUnavailableError,
    ValidationFailedError,
)
from app.core.ids import new_sequential_uuid
from app.modules.audit.application.service import AuditLog
from app.modules.audit.domain.models import AuditAction, AuditResult
from app.modules.phone_calls.domain import assistant
from app.modules.phone_calls.domain.models import (
    Answer,
    Applications,
    Assistant,
    Bank,
    BankScope,
    BankStatus,
    BankVersion,
    CallSession,
    CallStatus,
    JobProfiles,
    PhoneCallRepository,
    Question,
)
from app.modules.vacancies.application.access import VacancyAccess
from app.modules.vacancies.domain.models import AccessLevel, UserInfo

MAX_QUESTIONS = 60
_BAD_ANSWER = "La IA no devolvió una respuesta utilizable. Inténtalo de nuevo."


@dataclass(frozen=True)
class BankView:
    bank: Bank
    latest: BankVersion
    can_edit: bool


@dataclass(frozen=True)
class Proposal:
    """Resultado de una ayuda de IA: el contenido o el motivo del fallo."""

    content: object | None
    error: str | None = None


@dataclass(frozen=True)
class CallView:
    call: CallSession
    version: BankVersion
    bank: Bank


def _clean(text: object, limit: int) -> str:
    return " ".join(str(text or "").split())[:limit]


def _block(text: object, limit: int) -> str:
    lines = [" ".join(line.split()) for line in str(text or "").strip().splitlines()]
    return "\n".join(lines)[:limit].strip()


class PhoneCallService:
    def __init__(
        self,
        repo: PhoneCallRepository,
        access: VacancyAccess,
        applications: Applications,
        profiles: JobProfiles,
        ai: Assistant,
        audit: AuditLog,
        clock: Callable[[], datetime],
    ) -> None:
        self._repo = repo
        self._access = access
        self._applications = applications
        self._profiles = profiles
        self._ai = ai
        self._audit = audit
        self._clock = clock

    # --- Bancos: consulta ----------------------------------------------------------------

    @staticmethod
    def _can_see(actor: UserInfo, bank: Bank) -> bool:
        return (
            actor.is_admin or bank.owner_user_id == actor.id or bank.scope is BankScope.COMPARTIDO
        )

    @staticmethod
    def _can_edit(actor: UserInfo, bank: Bank) -> bool:
        return actor.is_admin or bank.owner_user_id == actor.id

    def banks(self, actor: UserInfo) -> list[BankView]:
        visible = [bank for bank in self._repo.banks() if self._can_see(actor, bank)]
        latest = self._repo.latest_versions([bank.id for bank in visible])
        return [BankView(bank, latest[bank.id], self._can_edit(actor, bank)) for bank in visible]

    def _bank(self, actor: UserInfo, bank_id: uuid.UUID, *, edit: bool = False) -> Bank:
        bank = self._repo.bank(bank_id)
        # Un banco privado ajeno responde igual que uno inexistente.
        if bank is None or not self._can_see(actor, bank):
            raise NotFoundError("El banco de preguntas no existe.")
        if edit and not self._can_edit(actor, bank):
            raise PermissionDeniedError("Solo su propietario o un administrador lo modifica.")
        return bank

    def bank(self, actor: UserInfo, bank_id: uuid.UUID) -> tuple[BankView, list[BankVersion]]:
        bank = self._bank(actor, bank_id)
        versions = self._repo.versions(bank_id)
        return BankView(bank, versions[0], self._can_edit(actor, bank)), versions

    # --- Bancos: cambios -----------------------------------------------------------------

    @staticmethod
    def _questions(
        raw: list[dict[str, object]], previous: tuple[Question, ...] = ()
    ) -> tuple[Question, ...]:
        known = {question.id for question in previous}
        questions: list[Question] = []
        for item in raw:
            text = _clean(item.get("text"), 1000)
            if not text:
                raise ValidationFailedError("Hay preguntas sin texto.")
            # Una pregunta conserva su identificador entre versiones mientras exista.
            given = item.get("id")
            question_id = given if isinstance(given, uuid.UUID) and given in known else None
            questions.append(
                Question(
                    id=question_id or new_sequential_uuid(),
                    text=text,
                    competency=_clean(item.get("competency"), 100),
                    guidance=_clean(item.get("guidance"), 1000),
                    origin="IA" if item.get("origin") == "IA" else "MANUAL",
                )
            )
        if not questions:
            raise ValidationFailedError("El banco necesita al menos una pregunta.")
        if len(questions) > MAX_QUESTIONS:
            raise ValidationFailedError(f"Un banco admite como máximo {MAX_QUESTIONS} preguntas.")
        if len({q.id for q in questions}) != len(questions):
            raise ValidationFailedError("Hay preguntas repetidas.")
        return tuple(questions)

    @staticmethod
    def _header(name: str, description: str | None) -> tuple[str, str | None]:
        name = _clean(name, 150)
        if len(name) < 3:
            raise ValidationFailedError("Escribe el nombre del banco.")
        return name, _clean(description, 500) or None

    def _record(self, action: AuditAction, actor: UserInfo, bank: Bank, ip: str | None, **extra):  # noqa: ANN003, ANN202
        self._audit.record(
            action,
            actor_user_id=actor.id,
            resource_type="banco_preguntas",
            resource_id=bank.id,
            ip=ip,
            details=extra,
        )

    def create_bank(
        self,
        actor: UserInfo,
        *,
        name: str,
        description: str | None,
        shared: bool,
        questions: list[dict[str, object]],
        ip: str | None = None,
        duplicated_from: uuid.UUID | None = None,
    ) -> BankView:
        name, description = self._header(name, description)
        now = self._clock()
        bank = Bank(
            id=new_sequential_uuid(),
            name=name,
            description=description,
            owner_user_id=actor.id,
            scope=BankScope.COMPARTIDO if shared else BankScope.PRIVADO,
            status=BankStatus.ACTIVO,
            created_at=now,
            updated_at=now,
            duplicated_from=duplicated_from,
        )
        version = BankVersion(
            id=new_sequential_uuid(),
            bank_id=bank.id,
            version_number=1,
            questions=self._questions(questions),
            created_at=now,
            created_by=actor.id,
        )
        self._repo.add_bank(bank)
        self._repo.add_version(version)
        self._record(AuditAction.BANCO_CREADO, actor, bank, ip, preguntas=len(version.questions))
        return BankView(bank, version, True)

    def update_bank(
        self,
        actor: UserInfo,
        bank_id: uuid.UUID,
        *,
        name: str,
        description: str | None,
        shared: bool,
        questions: list[dict[str, object]],
        change_note: str | None,
        expected_version: int,
        ip: str | None = None,
    ) -> BankView:
        """Guarda los datos del banco. Si cambian las preguntas, crea una versión
        nueva; las llamadas ya hechas conservan la suya."""
        bank = self._bank(actor, bank_id, edit=True)
        if bank.status is BankStatus.ARCHIVADO:
            raise ConflictError("El banco está archivado. Restáuralo para cambiarlo.")
        latest = self._repo.versions(bank_id)[0]
        if expected_version != latest.version_number:
            raise ConflictError("Otra persona guardó una versión más reciente. Vuelve a cargarlo.")
        bank.name, bank.description = self._header(name, description)
        bank.scope = BankScope.COMPARTIDO if shared else BankScope.PRIVADO
        bank.updated_at = self._clock()
        self._repo.save_bank(bank)
        new_questions = self._questions(questions, latest.questions)
        if new_questions != latest.questions:
            latest = BankVersion(
                id=new_sequential_uuid(),
                bank_id=bank.id,
                version_number=latest.version_number + 1,
                questions=new_questions,
                created_at=bank.updated_at,
                created_by=actor.id,
                change_note=_clean(change_note, 300) or None,
            )
            self._repo.add_version(latest)
        self._record(
            AuditAction.BANCO_ACTUALIZADO,
            actor,
            bank,
            ip,
            version=latest.version_number,
            compartido=shared,
        )
        return BankView(bank, latest, True)

    def set_archived(
        self, actor: UserInfo, bank_id: uuid.UUID, archived: bool, *, ip: str | None = None
    ) -> BankView:
        bank = self._bank(actor, bank_id, edit=True)
        bank.status = BankStatus.ARCHIVADO if archived else BankStatus.ACTIVO
        bank.updated_at = self._clock()
        self._repo.save_bank(bank)
        self._record(AuditAction.BANCO_ACTUALIZADO, actor, bank, ip, estado=bank.status.value)
        return BankView(bank, self._repo.versions(bank_id)[0], True)

    def duplicate_bank(
        self, actor: UserInfo, bank_id: uuid.UUID, *, ip: str | None = None
    ) -> BankView:
        source = self._bank(actor, bank_id)
        latest = self._repo.versions(bank_id)[0]
        return self.create_bank(
            actor,
            name=f"{source.name} (copia)"[:150],
            description=source.description,
            shared=False,
            questions=[
                {
                    "text": q.text,
                    "competency": q.competency,
                    "guidance": q.guidance,
                    "origin": q.origin,
                }
                for q in latest.questions
            ],
            ip=ip,
            duplicated_from=source.id,
        )

    def propose_questions(
        self, actor: UserInfo, vacancy_id: uuid.UUID, count: int, *, ip: str | None = None
    ) -> Proposal:
        """La IA propone preguntas a partir del perfil de la vacante. No guarda
        nada: la persona elige cuáles añade a su banco."""
        self._access.require(actor, vacancy_id, AccessLevel.LECTURA)
        profile = self._profiles.summary(vacancy_id)
        if profile is None:
            raise ValidationFailedError("La vacante todavía no tiene un perfil de puesto.")
        answer = self._ai.ask(
            assistant.PROFILE_ANALYSIS,
            system=assistant.QUESTIONS_SYSTEM,
            user=assistant.questions_request(profile, max(1, min(count, assistant.MAX_PROPOSALS))),
            vacancy_id=vacancy_id,
            actor_user_id=actor.id,
            carries_document=False,
        )
        proposal = self._proposal(answer, assistant.questions_from_answer)
        self._audit.record(
            AuditAction.BANCO_PREGUNTAS_PROPUESTAS,
            result=AuditResult.PERMITIDO if proposal.content else AuditResult.FALLIDO,
            actor_user_id=actor.id,
            resource_type="vacante",
            resource_id=vacancy_id,
            ip=ip,
        )
        return proposal

    @staticmethod
    def _proposal(answer, parse) -> Proposal:  # noqa: ANN001
        if not answer.ok:
            return Proposal(None, answer.error or "El proveedor de IA no respondió.")
        try:
            if not answer.complete:
                raise assistant.InvalidAnswerError("Respuesta incompleta.")
            return Proposal(parse(answer.text))
        except assistant.InvalidAnswerError:
            return Proposal(None, _BAD_ANSWER)

    # --- Llamadas ------------------------------------------------------------------------

    def _call(self, actor: UserInfo, call_id: uuid.UUID, minimum: AccessLevel) -> CallSession:
        call = self._repo.call(call_id)
        if call is None:
            raise NotFoundError("La llamada no existe.")
        self._access.require(actor, call.vacancy_id, minimum)
        return call

    def _view(self, call: CallSession) -> CallView:
        version = self._repo.version(call.bank_version_id)
        bank = self._repo.bank(version.bank_id) if version else None
        if version is None or bank is None:
            raise NotFoundError("El banco de preguntas de la llamada ya no existe.")
        return CallView(call, version, bank)

    def calls(self, actor: UserInfo, application_id: uuid.UUID) -> list[CallView]:
        application = self._applications.get(application_id)
        if application is None:
            raise NotFoundError("La postulación no existe.")
        self._access.require(actor, application.vacancy_id, AccessLevel.LECTURA)
        return [self._view(call) for call in self._repo.calls(application_id)]

    def call(self, actor: UserInfo, call_id: uuid.UUID) -> CallView:
        return self._view(self._call(actor, call_id, AccessLevel.LECTURA))

    def open_call(
        self,
        actor: UserInfo,
        application_id: uuid.UUID,
        bank_id: uuid.UUID,
        *,
        ip: str | None = None,
    ) -> CallView:
        application = self._applications.get(application_id)
        if application is None:
            raise NotFoundError("La postulación no existe.")
        self._access.require(actor, application.vacancy_id, AccessLevel.COLABORACION)
        if not application.active:
            raise ConflictError("La postulación no está activa.")
        bank = self._bank(actor, bank_id)
        if bank.status is BankStatus.ARCHIVADO:
            raise ConflictError("El banco está archivado; elige otro.")
        version = self._repo.versions(bank_id)[0]
        now = self._clock()
        call = CallSession(
            id=new_sequential_uuid(),
            application_id=application.id,
            vacancy_id=application.vacancy_id,
            bank_version_id=version.id,
            status=CallStatus.BORRADOR,
            called_at=now,
            created_at=now,
            created_by=actor.id,
            updated_at=now,
        )
        self._repo.add_call(call)
        self._audit.record(
            AuditAction.LLAMADA_ABIERTA,
            actor_user_id=actor.id,
            resource_type="llamada",
            resource_id=call.id,
            ip=ip,
            details={
                "vacante": str(call.vacancy_id),
                "postulacion": str(application.id),
                "banco": str(bank.id),
                "version": version.version_number,
            },
        )
        return CallView(call, version, bank)

    def save_call(
        self,
        actor: UserInfo,
        call_id: uuid.UUID,
        *,
        answers: list[dict[str, object]],
        notes: str | None,
        called_at: datetime | None,
        close: bool = False,
        ip: str | None = None,
    ) -> CallView:
        """Guarda lo capturado. Con ``close`` la llamada queda cerrada y fija."""
        call = self._call(actor, call_id, AccessLevel.COLABORACION)
        if call.status is CallStatus.CERRADA:
            raise ConflictError("La llamada está cerrada y ya no se modifica.")
        view = self._view(call)
        valid = {question.id for question in view.version.questions}
        cleaned: dict[uuid.UUID, Answer] = {}
        for item in answers:
            question_id = item.get("question_id")
            if question_id not in valid:
                raise ValidationFailedError("Una respuesta no corresponde a ninguna pregunta.")
            cleaned[question_id] = Answer(  # type: ignore[index]
                question_id=question_id,  # type: ignore[arg-type]
                answer=_block(item.get("answer"), 6000),
                notes=_clean(item.get("notes"), 1000),
                not_asked=item.get("not_asked") is True,
            )
        if close:
            pending = [
                number
                for number, question in enumerate(view.version.questions, start=1)
                if not (
                    (answer := cleaned.get(question.id)) and (answer.not_asked or answer.answer)
                )
            ]
            if pending:
                raise ValidationFailedError(
                    "Para cerrar, cada pregunta debe tener respuesta o marcarse como no "
                    "realizada. Faltan: " + ", ".join(str(n) for n in pending) + "."
                )
        now = self._clock()
        if called_at is not None:
            if called_at > now:
                raise ValidationFailedError("La fecha de la llamada no puede ser futura.")
            call.called_at = called_at
        call.answers = tuple(cleaned[q.id] for q in view.version.questions if q.id in cleaned)
        call.notes = _block(notes, 6000)
        call.updated_at = now
        if close:
            call.status = CallStatus.CERRADA
            call.closed_at = now
        self._repo.save_call(call)
        self._audit.record(
            AuditAction.LLAMADA_CERRADA if close else AuditAction.LLAMADA_GUARDADA,
            actor_user_id=actor.id,
            resource_type="llamada",
            resource_id=call.id,
            ip=ip,
            details={"vacante": str(call.vacancy_id), "respuestas": len(call.answers)},
        )
        return view

    def analyze_call(
        self, actor: UserInfo, call_id: uuid.UUID, *, ip: str | None = None
    ) -> tuple[CallView, str | None]:
        """Pide a la IA un resumen de la llamada. Devuelve la llamada y, si la IA
        falló, el motivo. El análisis anterior se sustituye solo si este sirve."""
        call = self._call(actor, call_id, AccessLevel.COLABORACION)
        view = self._view(call)
        if not any(answer.answer for answer in call.answers):
            raise ValidationFailedError(
                "Captura y guarda al menos una respuesta antes de analizar."
            )
        application = self._applications.get(call.application_id)
        if application is None:
            raise NotFoundError("La postulación no existe.")
        if self._ai is None:
            raise ServiceUnavailableError("La ayuda de IA no está disponible.")
        answer = self._ai.ask(
            assistant.CALL_ANALYSIS,
            system=assistant.ANALYSIS_SYSTEM,
            user=assistant.analysis_request(
                view.version.questions, call.answers, call.notes, application
            ),
            vacancy_id=call.vacancy_id,
            actor_user_id=actor.id,
            # Lleva lo dicho por una persona candidata: misma regla que un documento.
            carries_document=True,
        )
        proposal = self._proposal(answer, assistant.analysis_from_answer)
        if proposal.content is not None:
            call.analysis = proposal.content  # type: ignore[assignment]
            call.analysis_at = self._clock()
            call.analysis_by = actor.id
            self._repo.save_call(call)
        self._audit.record(
            AuditAction.LLAMADA_ANALIZADA,
            result=AuditResult.PERMITIDO if proposal.content else AuditResult.FALLIDO,
            actor_user_id=actor.id,
            resource_type="llamada",
            resource_id=call.id,
            ip=ip,
            details={"vacante": str(call.vacancy_id)},
        )
        return view, proposal.error
