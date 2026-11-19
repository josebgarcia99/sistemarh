"""Bancos de preguntas y llamadas telefónicas: reglas y permisos.

Bancos: cada persona ve los suyos y los compartidos; el administrador ve
todos. Solo el propietario o un administrador los modifica, comparte o
archiva. Cualquiera que vea un banco puede duplicarlo como propio.

Llamadas: pertenecen a una postulación y siguen el permiso de su vacante
(lectura para consultar, colaboración para capturar y pedir el análisis).
"""

from __future__ import annotations

import uuid
from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace
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
    MAX_CALL_QUESTIONS,
    Answer,
    Applications,
    Assistant,
    Bank,
    BankScope,
    BankStatus,
    BankVersion,
    CallQuestion,
    CallSession,
    CallStatus,
    JobProfiles,
    PhoneCallRepository,
    Question,
    QuestionSource,
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

    @property
    def questions(self) -> tuple[CallQuestion, ...]:
        """Todas las preguntas de la llamada, incluidas las quitadas."""
        return self.call.questions

    @property
    def sources(self) -> tuple[str, ...]:
        """De dónde salen las preguntas que sí se hacen: los nombres de los
        bancos, en orden, y al final las escritas para la llamada."""
        names = [q.bank_name for q in self.call.active_questions if q.bank_name]
        if any(q.source is QuestionSource.LLAMADA for q in self.call.active_questions):
            names.append("Preguntas escritas para esta llamada")
        return tuple(dict.fromkeys(names))


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
            actor.is_admin
            or bank.owner_user_id == actor.id
            or bank.scope in (BankScope.COMPARTIDO, BankScope.GENERAL)
        )

    @staticmethod
    def _can_edit(actor: UserInfo, bank: Bank) -> bool:
        if bank.scope is BankScope.GENERAL:
            # Son de toda la empresa: las mantiene cualquier reclutador o
            # administrador. Cada cambio crea una versión y queda en la auditoría.
            return True
        return actor.is_admin or bank.owner_user_id == actor.id

    @staticmethod
    def _scope(actor: UserInfo, shared: bool, general: bool) -> BankScope:
        if general:
            return BankScope.GENERAL
        return BankScope.COMPARTIDO if shared else BankScope.PRIVADO

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
        general: bool = False,
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
            scope=self._scope(actor, shared, general),
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
        general: bool = False,
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
        bank.scope = self._scope(actor, shared, general)
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

    @staticmethod
    def _view(call: CallSession) -> CallView:
        return CallView(call)

    def calls(self, actor: UserInfo, application_id: uuid.UUID) -> list[CallView]:
        application = self._applications.get(application_id)
        if application is None:
            raise NotFoundError("La postulación no existe.")
        self._access.require(actor, application.vacancy_id, AccessLevel.LECTURA)
        return [self._view(call) for call in self._repo.calls(application_id)]

    def call(self, actor: UserInfo, call_id: uuid.UUID) -> CallView:
        return self._view(self._call(actor, call_id, AccessLevel.LECTURA))

    def _usable_bank(self, actor: UserInfo, bank_id: uuid.UUID) -> tuple[Bank, BankVersion]:
        """Un banco del que la persona puede tomar preguntas, con su versión vigente."""
        bank = self._bank(actor, bank_id)
        if bank.status is BankStatus.ARCHIVADO:
            raise ConflictError(f"El banco «{bank.name}» está archivado; elige otro.")
        return bank, self._repo.versions(bank_id)[0]

    @staticmethod
    def _from_bank(bank: Bank, version: BankVersion, question: Question) -> CallQuestion:
        general = bank.scope is BankScope.GENERAL
        return CallQuestion(
            id=question.id,
            text=question.text,
            competency=question.competency,
            guidance=question.guidance,
            origin=question.origin,
            source=QuestionSource.GENERAL if general else QuestionSource.BANCO,
            bank_id=bank.id,
            bank_name=bank.name,
            bank_version=version.version_number,
        )

    def open_call(
        self,
        actor: UserInfo,
        application_id: uuid.UUID,
        bank_ids: Sequence[uuid.UUID] = (),
        *,
        ip: str | None = None,
    ) -> CallView:
        """Abre una llamada. Sus preguntas son las generales de la empresa
        vigentes hoy y, después, las de los bancos elegidos (puede no elegirse
        ninguno). A partir de ahí la lista es propia de la llamada."""
        application = self._applications.get(application_id)
        if application is None:
            raise NotFoundError("La postulación no existe.")
        self._access.require(actor, application.vacancy_id, AccessLevel.COLABORACION)
        if not application.active:
            raise ConflictError("La postulación no está activa.")
        chosen = [self._usable_bank(actor, bank_id) for bank_id in dict.fromkeys(bank_ids)]
        general = sorted(
            (
                item
                for item in self._repo.banks()
                if item.scope is BankScope.GENERAL and item.status is BankStatus.ACTIVO
            ),
            key=lambda item: (item.created_at, item.name),
        )
        general_versions = self._repo.latest_versions([item.id for item in general])
        questions: dict[uuid.UUID, CallQuestion] = {}
        for bank, version in (*((item, general_versions[item.id]) for item in general), *chosen):
            for question in version.questions:
                questions.setdefault(question.id, self._from_bank(bank, version, question))
        if len(questions) > MAX_CALL_QUESTIONS:
            raise ValidationFailedError(
                f"Una llamada admite como máximo {MAX_CALL_QUESTIONS} preguntas; "
                "elige menos bancos."
            )
        first = next((v for bank, v in chosen if bank.scope is not BankScope.GENERAL), None)
        now = self._clock()
        call = CallSession(
            id=new_sequential_uuid(),
            application_id=application.id,
            vacancy_id=application.vacancy_id,
            bank_version_id=first.id if first is not None else None,
            status=CallStatus.BORRADOR,
            called_at=now,
            created_at=now,
            created_by=actor.id,
            updated_at=now,
            questions=tuple(questions.values()),
            # Referencia de las versiones generales usadas (la columna guarda hasta 20).
            general_version_ids=tuple(general_versions[item.id].id for item in general)[:20],
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
                "bancos": [str(bank.id) for bank, _ in chosen],
                "preguntas": len(call.questions),
                "preguntas_generales": sum(
                    1 for q in call.questions if q.source is QuestionSource.GENERAL
                ),
            },
        )
        return self._view(call)

    def _merge_questions(
        self,
        actor: UserInfo,
        current: tuple[CallQuestion, ...],
        wanted: list[dict[str, object]],
    ) -> tuple[CallQuestion, ...]:
        """La lista de preguntas de la llamada tal como la dejó la persona.

        - Una pregunta que ya estaba conserva su origen; cambia su redacción y
          si está quitada. Si venía de un banco, se guarda la redacción original.
        - Una pregunta nueva con banco se toma de la versión vigente de ese banco.
        - Una pregunta nueva sin banco es una escrita solo para esta llamada.
        - Las que ya estaban y no se mencionan se conservan, al final."""
        existing = {question.id: question for question in current}
        banks: dict[uuid.UUID, tuple[Bank, BankVersion]] = {}
        result: dict[uuid.UUID, CallQuestion] = {}
        for item in wanted:
            question_id = item.get("id")
            if not isinstance(question_id, uuid.UUID) or question_id in result:
                raise ValidationFailedError("Hay preguntas repetidas en la llamada.")
            text = _clean(item.get("text"), 1000)
            if not text:
                raise ValidationFailedError("Hay preguntas sin texto.")
            omitted = item.get("omitted") is True
            bank_id = item.get("bank_id")
            if question_id in existing:
                old = existing[question_id]
                if old.source is QuestionSource.LLAMADA:
                    new = replace(
                        old,
                        text=text,
                        competency=_clean(item.get("competency"), 100),
                        guidance=_clean(item.get("guidance"), 1000),
                        omitted=omitted,
                    )
                else:
                    base = old.original_text or old.text
                    new = replace(
                        old,
                        text=text,
                        original_text=None if text == base else base,
                        omitted=omitted,
                    )
            elif isinstance(bank_id, uuid.UUID):
                if bank_id not in banks:
                    banks[bank_id] = self._usable_bank(actor, bank_id)
                bank, version = banks[bank_id]
                source = next((q for q in version.questions if q.id == question_id), None)
                if source is None:
                    raise ValidationFailedError(
                        f"Una pregunta ya no está en el banco «{bank.name}». Vuelve a elegirla."
                    )
                new = replace(
                    self._from_bank(bank, version, source),
                    text=text,
                    original_text=None if text == source.text else source.text,
                    omitted=omitted,
                )
            else:
                new = CallQuestion(
                    id=question_id,
                    text=text,
                    competency=_clean(item.get("competency"), 100),
                    guidance=_clean(item.get("guidance"), 1000),
                    source=QuestionSource.LLAMADA,
                    omitted=omitted,
                )
            result[question_id] = new
        for question in current:
            result.setdefault(question.id, question)
        if len(result) > MAX_CALL_QUESTIONS:
            raise ValidationFailedError(
                f"Una llamada admite como máximo {MAX_CALL_QUESTIONS} preguntas."
            )
        return tuple(result.values())

    def save_call(
        self,
        actor: UserInfo,
        call_id: uuid.UUID,
        *,
        answers: list[dict[str, object]],
        notes: str | None,
        called_at: datetime | None,
        questions: list[dict[str, object]] | None = None,
        close: bool = False,
        autosave: bool = False,
        ip: str | None = None,
    ) -> CallView:
        """Guarda lo capturado. Con ``questions`` cambia además la lista de
        preguntas de esta llamada. Con ``close`` queda cerrada y fija.

        ``autosave`` es el guardado que hace la pantalla sola mientras la persona
        escribe: guarda lo mismo, pero no deja un evento de auditoría cada pocos
        segundos. El guardado que pide la persona y el cierre sí se auditan."""
        call = self._call(actor, call_id, AccessLevel.COLABORACION)
        if call.status is CallStatus.CERRADA:
            raise ConflictError("La llamada está cerrada y ya no se modifica.")
        asked_before = [(q.id, q.text) for q in call.active_questions]
        if questions is not None:
            call.questions = self._merge_questions(actor, call.questions, questions)
        valid = {question.id for question in call.questions}
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
        active = call.active_questions
        if close:
            if not active:
                raise ValidationFailedError(
                    "Para cerrar, la llamada debe tener al menos una pregunta."
                )
            pending = [
                number
                for number, question in enumerate(active, start=1)
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
        # Mientras es borrador, lo anotado en una pregunta quitada se conserva por
        # si se vuelve a incluir. Al cerrar solo queda lo de las preguntas hechas.
        kept = active if close else call.questions
        call.answers = tuple(cleaned[q.id] for q in kept if q.id in cleaned)
        call.notes = _block(notes, 6000)
        call.updated_at = now
        # El análisis numera las preguntas: si cambiaron, ya no corresponde.
        stale = call.analysis is not None and asked_before != [(q.id, q.text) for q in active]
        if stale:
            call.analysis, call.analysis_at, call.analysis_by = None, None, None
        if close:
            call.status = CallStatus.CERRADA
            call.closed_at = now
        self._repo.save_call(call)
        if autosave and not close:
            return self._view(call)
        self._audit.record(
            AuditAction.LLAMADA_CERRADA if close else AuditAction.LLAMADA_GUARDADA,
            actor_user_id=actor.id,
            resource_type="llamada",
            resource_id=call.id,
            ip=ip,
            details={
                "vacante": str(call.vacancy_id),
                "respuestas": len(call.answers),
                "preguntas": len(active),
                "quitadas": len(call.questions) - len(active),
                "redaccion_cambiada": sum(1 for q in active if q.original_text is not None),
                "escritas": sum(1 for q in active if q.source is QuestionSource.LLAMADA),
                "analisis_retirado": stale,
            },
        )
        return self._view(call)

    def analyze_call(
        self, actor: UserInfo, call_id: uuid.UUID, *, ip: str | None = None
    ) -> tuple[CallView, str | None]:
        """Pide a la IA un resumen de la llamada. Devuelve la llamada y, si la IA
        falló, el motivo. El análisis anterior se sustituye solo si este sirve."""
        call = self._call(actor, call_id, AccessLevel.COLABORACION)
        view = self._view(call)
        asked = call.active_questions
        asked_ids = {question.id for question in asked}
        answers = tuple(answer for answer in call.answers if answer.question_id in asked_ids)
        if not any(answer.answer for answer in answers):
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
            user=assistant.analysis_request(asked, answers, call.notes, application),
            vacancy_id=call.vacancy_id,
            actor_user_id=actor.id,
            # Lleva lo dicho por una persona candidata: misma regla que un documento.
            carries_document=True,
        )
        proposal = self._proposal(
            answer,
            lambda text: assistant.analysis_from_answer(text, asked, answers),
        )
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
