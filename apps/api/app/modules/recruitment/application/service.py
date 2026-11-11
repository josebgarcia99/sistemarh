"""Reclutamiento operativo: candidatos, postulaciones, etapas y movimientos.

Permisos por vacante: con lectura se consulta; con colaboración se dan de
alta candidatos y se mueven entre etapas; abrir o cerrar una convocatoria es
del responsable o de un administrador. Las etapas las configura el
administrador.

Ningún movimiento es automático salvo el alta desde un lote de CV, que deja a
la persona en revisión de RH con la clasificación inicial de la IA. Avanzar,
descartar, contratar o reabrir es siempre una decisión humana y queda
registrada con su responsable.
"""

from __future__ import annotations

import re
import uuid
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import date, datetime

from app.core.exceptions.errors import (
    ConflictError,
    NotFoundError,
    PermissionDeniedError,
    ValidationFailedError,
)
from app.core.ids import new_sequential_uuid
from app.modules.audit.application.service import AuditLog
from app.modules.audit.domain.models import AuditAction
from app.modules.recruitment.domain import tenure
from app.modules.recruitment.domain.models import (
    DEFAULT_STAGES,
    MOVEMENT_OUTCOME,
    OUTCOME_MOVEMENT,
    OUTCOME_STATUS,
    Application,
    ApplicationStatus,
    Campaign,
    CampaignStatus,
    Candidate,
    EvaluatedCv,
    EvaluatedCvs,
    Movement,
    MovementKind,
    Outcome,
    OutcomeKind,
    PipelineVersion,
    RecruitmentRepository,
    Stage,
    StageKind,
)
from app.modules.vacancies.application.access import VacancyAccess
from app.modules.vacancies.domain.models import AccessLevel, UserInfo

_EMAIL = re.compile(r"^[\w.+-]+@[\w-]+(?:\.[\w-]+)+$")
_ENTRY_KINDS = (StageKind.EVALUACION_CV, StageKind.REVISION_RH)
_AI_LABELS = {
    "ACEPTADO_IA": "aceptado",
    "RECHAZADO_IA": "rechazado",
    "NO_EVALUABLE": "no evaluable",
}
_SHORTCUT_OUTCOMES = (
    OutcomeKind.DESISTIO,
    OutcomeKind.NO_CONTRATADO,
    OutcomeKind.VACANTE_CANCELADA,
)
MAX_MASS_MOVE = 200
MAX_OUTCOME_NOTES = 2000
# Una fecha de incorporación a más de dos años de hoy es, casi seguro, un error.
MAX_START_DATE_DAYS = 730


@dataclass(frozen=True)
class ApplicationView:
    application: Application
    candidate: Candidate


@dataclass(frozen=True)
class Board:
    campaigns: list[Campaign]
    campaign: Campaign | None
    pipeline: PipelineVersion | None
    applications: list[ApplicationView]
    # Plazas de la vacante y cuántas están cubiertas por contrataciones vigentes.
    positions: int = 0
    hires: int = 0


@dataclass(frozen=True)
class ApplicationDetail:
    view: ApplicationView
    campaign: Campaign
    pipeline: PipelineVersion
    movements: list[Movement]
    evaluation: EvaluatedCv | None
    tenure: tenure.TenureSummary | None
    # Resultados finales, del más reciente al más antiguo (incluye anulados).
    outcomes: list[Outcome]


def _clean(text: str | None, limit: int) -> str:
    return " ".join((text or "").split())[:limit]


def _name_from_file(file_name: str) -> str:
    stem = re.sub(r"[_\-.]+", " ", file_name.rsplit(".", 1)[0])
    stem = re.sub(r"(?i)\b(cv|curriculum|currículum|vitae|resume)\b", " ", stem)
    return _clean(stem, 200) or "Sin nombre"


class RecruitmentService:
    def __init__(
        self,
        repo: RecruitmentRepository,
        access: VacancyAccess,
        evaluated: EvaluatedCvs,
        audit: AuditLog,
        clock: Callable[[], datetime],
    ) -> None:
        self._repo = repo
        self._access = access
        self._evaluated = evaluated
        self._audit = audit
        self._clock = clock

    # --- Etapas configurables ------------------------------------------------------------

    def current_pipeline(self) -> PipelineVersion:
        """La versión vigente de las etapas; la primera vez crea las iniciales."""
        latest = self._repo.latest_pipeline()
        if latest is not None:
            return latest
        return self._new_pipeline(
            1, [(name, kind, optional) for name, kind, optional in DEFAULT_STAGES], None
        )

    def _new_pipeline(
        self, number: int, stages: list[tuple[str, StageKind, bool]], actor_id: uuid.UUID | None
    ) -> PipelineVersion:
        version_id = new_sequential_uuid()
        version = PipelineVersion(
            id=version_id,
            version_number=number,
            created_at=self._clock(),
            created_by=actor_id,
            stages=tuple(
                Stage(new_sequential_uuid(), version_id, position, name, kind, optional)
                for position, (name, kind, optional) in enumerate(stages, start=1)
            ),
        )
        self._repo.add_pipeline(version)
        return version

    def save_pipeline(
        self,
        actor: UserInfo,
        stages: list[dict[str, object]],
        *,
        expected_version: int,
        ip: str | None = None,
    ) -> PipelineVersion:
        """Guarda las etapas como una versión nueva. Las convocatorias abiertas
        conservan la suya; la nueva se usa en las que se abran después."""
        if not actor.is_admin:
            raise PermissionDeniedError("Solo un administrador configura las etapas.")
        current = self.current_pipeline()
        if expected_version != current.version_number:
            raise ConflictError("Otra persona cambió las etapas. Vuelve a cargarlas.")
        cleaned: list[tuple[str, StageKind, bool]] = []
        for stage in stages:
            name = _clean(str(stage.get("name") or ""), 100)
            if not name:
                raise ValidationFailedError("Todas las etapas deben tener nombre.")
            try:
                kind = StageKind(str(stage.get("kind")))
            except ValueError as error:
                raise ValidationFailedError("El tipo de una etapa no es válido.") from error
            cleaned.append((name, kind, stage.get("is_optional") is True))
        if not 2 <= len(cleaned) <= 20:
            raise ValidationFailedError("El proceso debe tener entre 2 y 20 etapas.")
        names = [name.casefold() for name, _, _ in cleaned]
        if len(set(names)) != len(names):
            raise ValidationFailedError("Hay etapas con el mismo nombre.")
        if cleaned == [(s.name, s.kind, s.is_optional) for s in current.stages]:
            raise ValidationFailedError("Las etapas no tienen cambios.")
        version = self._new_pipeline(current.version_number + 1, cleaned, actor.id)
        self._audit.record(
            AuditAction.ETAPAS_VERSION_CREADA,
            actor_user_id=actor.id,
            resource_type="etapas",
            resource_id=version.id,
            ip=ip,
            details={"version": version.version_number, "etapas": len(cleaned)},
        )
        return version

    # --- Convocatorias -------------------------------------------------------------------

    def _open_campaign(self, vacancy_id: uuid.UUID) -> Campaign | None:
        for campaign in self._repo.campaigns(vacancy_id):
            if campaign.status is CampaignStatus.ABIERTA:
                return campaign
        return None

    def _create_campaign(
        self, vacancy_id: uuid.UUID, name: str | None, actor_id: uuid.UUID | None
    ) -> Campaign:
        existing = self._repo.campaigns(vacancy_id)
        number = existing[0].number + 1 if existing else 1
        campaign = Campaign(
            id=new_sequential_uuid(),
            vacancy_id=vacancy_id,
            number=number,
            name=_clean(name, 100) or f"Convocatoria {number}",
            status=CampaignStatus.ABIERTA,
            pipeline_version_id=self.current_pipeline().id,
            opened_at=self._clock(),
            opened_by=actor_id,
        )
        self._repo.add_campaign(campaign)
        return campaign

    def open_campaign(
        self, actor: UserInfo, vacancy_id: uuid.UUID, name: str | None, *, ip: str | None = None
    ) -> Campaign:
        self._access.require(actor, vacancy_id, AccessLevel.RESPONSABLE)
        if self._open_campaign(vacancy_id) is not None:
            raise ConflictError("La vacante ya tiene una convocatoria abierta. Ciérrala primero.")
        campaign = self._create_campaign(vacancy_id, name, actor.id)
        self._audit.record(
            AuditAction.CONVOCATORIA_ABIERTA,
            actor_user_id=actor.id,
            resource_type="convocatoria",
            resource_id=campaign.id,
            ip=ip,
            details={"vacante": str(vacancy_id), "numero": campaign.number},
        )
        return campaign

    def close_campaign(
        self, actor: UserInfo, campaign_id: uuid.UUID, *, ip: str | None = None
    ) -> Campaign:
        campaign = self._repo.campaign(campaign_id)
        if campaign is None:
            raise NotFoundError("La convocatoria no existe.")
        self._access.require(actor, campaign.vacancy_id, AccessLevel.RESPONSABLE)
        if campaign.status is not CampaignStatus.ABIERTA:
            raise ConflictError("La convocatoria ya está cerrada.")
        campaign.status = CampaignStatus.CERRADA
        campaign.closed_at = self._clock()
        campaign.closed_by = actor.id
        self._repo.save_campaign(campaign)
        self._audit.record(
            AuditAction.CONVOCATORIA_CERRADA,
            actor_user_id=actor.id,
            resource_type="convocatoria",
            resource_id=campaign.id,
            ip=ip,
            details={"vacante": str(campaign.vacancy_id), "numero": campaign.number},
        )
        return campaign

    # --- Alta de postulaciones -----------------------------------------------------------

    @staticmethod
    def _entry_stage(pipeline: PipelineVersion, *, evaluated: bool) -> Stage:
        """Dónde entra una postulación: tras la evaluación de CV si ya fue evaluada."""
        stages = pipeline.stages
        if evaluated and stages[0].kind is StageKind.EVALUACION_CV:
            return stages[1]
        for stage in stages:
            if stage.kind is StageKind.REVISION_RH:
                return stage
        return stages[0]

    def _movements(self, entries: list[Movement]) -> None:
        """Añade los movimientos al historial, numerados por postulación."""
        counters: dict[uuid.UUID, int] = {}
        numbered = []
        for entry in entries:
            if entry.application_id not in counters:
                counters[entry.application_id] = self._repo.movement_count(entry.application_id)
            counters[entry.application_id] += 1
            numbered.append(replace(entry, sequence=counters[entry.application_id]))
        self._repo.add_movements(numbered)

    def _register(
        self,
        campaign: Campaign,
        pipeline: PipelineVersion,
        candidate: Candidate,
        *,
        cv_file_id: uuid.UUID | None,
        evaluation: EvaluatedCv | None,
        actor_id: uuid.UUID | None,
    ) -> Application:
        now = self._clock()
        stage = self._entry_stage(pipeline, evaluated=evaluation is not None)
        application = Application(
            id=new_sequential_uuid(),
            candidate_id=candidate.id,
            campaign_id=campaign.id,
            vacancy_id=campaign.vacancy_id,
            stage_id=stage.id,
            status=ApplicationStatus.ACTIVA,
            created_at=now,
            updated_at=now,
            created_by=actor_id,
            cv_file_id=cv_file_id,
            evaluation_item_id=evaluation.item_id if evaluation else None,
            ai_classification=evaluation.classification if evaluation else None,
            ai_score=evaluation.score if evaluation else None,
        )
        self._repo.add_application(application)
        first = pipeline.stages[0]
        if evaluation is not None and first.id != stage.id:
            label = _AI_LABELS.get(evaluation.classification, evaluation.classification)
            score = f", {evaluation.score} de 100" if evaluation.score is not None else ""
            entries = [
                Movement(
                    new_sequential_uuid(),
                    application.id,
                    MovementKind.ALTA,
                    now,
                    actor_id,
                    to_stage_id=first.id,
                    note=f"Clasificación inicial de la IA: {label}{score}.",
                ),
                Movement(
                    new_sequential_uuid(),
                    application.id,
                    MovementKind.AVANCE,
                    now,
                    actor_id,
                    from_stage_id=first.id,
                    to_stage_id=stage.id,
                    note="Pasa a revisión de RH al terminar la evaluación.",
                ),
            ]
        else:
            entries = [
                Movement(
                    new_sequential_uuid(),
                    application.id,
                    MovementKind.ALTA,
                    now,
                    actor_id,
                    to_stage_id=stage.id,
                    note="Alta manual." if actor_id else None,
                )
            ]
        self._movements(entries)
        return application

    def _new_candidate(
        self, full_name: str, email: str | None, phone: str | None, actor_id: uuid.UUID | None
    ) -> Candidate:
        now = self._clock()
        candidate = Candidate(
            id=new_sequential_uuid(),
            full_name=full_name,
            email=email,
            phone=phone,
            created_at=now,
            updated_at=now,
            created_by=actor_id,
        )
        self._repo.add_candidate(candidate)
        return candidate

    def sync_evaluated(self, vacancy_id: uuid.UUID) -> int:
        """Crea la postulación de cada CV evaluado que aún no la tiene. Lo
        ejecuta el sistema al terminar un lote; repetirlo no duplica nada."""
        registered = self._repo.files_with_application(vacancy_id)
        pending = [
            cv
            for cv in self._evaluated.first_evaluations(vacancy_id)
            if cv.file_id not in registered
        ]
        if not pending:
            return 0
        campaign = self._open_campaign(vacancy_id) or self._create_campaign(vacancy_id, None, None)
        pipeline = self._repo.pipeline(campaign.pipeline_version_id) or self.current_pipeline()
        created = 0
        for cv in pending:
            email = _clean(str(cv.extraction.get("correo") or ""), 254).lower() or None
            if email is not None and not _EMAIL.match(email):
                email = None
            candidate = self._repo.candidate_by_email(email) if email else None
            if candidate is None:
                name = _clean(str(cv.extraction.get("nombre") or ""), 200)
                phone = _clean(str(cv.extraction.get("telefono") or ""), 40) or None
                candidate = self._new_candidate(
                    name or _name_from_file(cv.file_name), email, phone, None
                )
            elif self._repo.application_of(candidate.id, campaign.id) is not None:
                # La misma persona con otro archivo: ya tiene su postulación.
                continue
            self._register(
                campaign, pipeline, candidate, cv_file_id=cv.file_id, evaluation=cv, actor_id=None
            )
            created += 1
        if created:
            self._audit.record(
                AuditAction.POSTULACIONES_CREADAS,
                resource_type="convocatoria",
                resource_id=campaign.id,
                details={"vacante": str(vacancy_id), "postulaciones": created, "origen": "lote"},
            )
        return created

    def add_candidate(
        self,
        actor: UserInfo,
        vacancy_id: uuid.UUID,
        *,
        full_name: str,
        email: str | None,
        phone: str | None,
        cv_file_id: uuid.UUID | None = None,
        ip: str | None = None,
    ) -> Application:
        """Alta manual de una persona que no llegó por un lote de CV."""
        self._access.require(actor, vacancy_id, AccessLevel.COLABORACION)
        name, email, phone = self._contact(full_name, email, phone)
        if cv_file_id is not None:
            if not self._evaluated.is_cv_of(vacancy_id, cv_file_id):
                raise ValidationFailedError("El CV indicado no es un currículum de esta vacante.")
            if cv_file_id in self._repo.files_with_application(vacancy_id):
                raise ConflictError("Ese CV ya pertenece a una postulación de la vacante.")
        campaign = self._open_campaign(vacancy_id) or self._create_campaign(vacancy_id, None, None)
        candidate = self._repo.candidate_by_email(email) if email else None
        if candidate is None:
            candidate = self._new_candidate(name, email, phone, actor.id)
        elif self._repo.application_of(candidate.id, campaign.id) is not None:
            raise ConflictError("Esa persona ya tiene una postulación en esta convocatoria.")
        pipeline = self._repo.pipeline(campaign.pipeline_version_id) or self.current_pipeline()
        application = self._register(
            campaign, pipeline, candidate, cv_file_id=cv_file_id, evaluation=None, actor_id=actor.id
        )
        self._audit.record(
            AuditAction.POSTULACIONES_CREADAS,
            actor_user_id=actor.id,
            resource_type="postulacion",
            resource_id=application.id,
            ip=ip,
            details={"vacante": str(vacancy_id), "postulaciones": 1, "origen": "manual"},
        )
        return application

    @staticmethod
    def _contact(
        full_name: str, email: str | None, phone: str | None
    ) -> tuple[str, str | None, str | None]:
        name = _clean(full_name, 200)
        if len(name) < 3:
            raise ValidationFailedError("Escribe el nombre completo de la persona.")
        email = _clean(email, 254).lower() or None
        if email is not None and not _EMAIL.match(email):
            raise ValidationFailedError("El correo no tiene un formato válido.")
        return name, email, _clean(phone, 40) or None

    # --- Consulta ------------------------------------------------------------------------

    def board(
        self, actor: UserInfo, vacancy_id: uuid.UUID, campaign_id: uuid.UUID | None = None
    ) -> Board:
        vacancy, _ = self._access.require(actor, vacancy_id, AccessLevel.LECTURA)
        # Por si un lote terminó sin poder registrar sus postulaciones.
        self.sync_evaluated(vacancy_id)
        capacity = {"positions": vacancy.positions, "hires": self._repo.hires(vacancy_id)}
        campaigns = self._repo.campaigns(vacancy_id)
        campaign = next((c for c in campaigns if c.id == campaign_id), None)
        if campaign_id is not None and campaign is None:
            raise NotFoundError("La convocatoria no existe.")
        campaign = campaign or (campaigns[0] if campaigns else None)
        if campaign is None:
            return Board(campaigns, None, None, [], **capacity)
        applications = self._repo.applications(campaign.id)
        candidates = self._repo.candidates([a.candidate_id for a in applications])
        return Board(
            campaigns,
            campaign,
            self._repo.pipeline(campaign.pipeline_version_id),
            [ApplicationView(a, candidates[a.candidate_id]) for a in applications],
            **capacity,
        )

    def _load(
        self, actor: UserInfo, application_id: uuid.UUID, minimum: AccessLevel
    ) -> Application:
        application = self._repo.application(application_id)
        if application is None:
            raise NotFoundError("La postulación no existe.")
        self._access.require(actor, application.vacancy_id, minimum)
        return application

    def _view(self, application: Application) -> ApplicationView:
        candidate = self._repo.candidate(application.candidate_id)
        if candidate is None:
            raise NotFoundError("El candidato no existe.")
        return ApplicationView(application, candidate)

    def detail(self, actor: UserInfo, application_id: uuid.UUID) -> ApplicationDetail:
        application = self._load(actor, application_id, AccessLevel.LECTURA)
        campaign = self._repo.campaign(application.campaign_id)
        pipeline = self._repo.pipeline(campaign.pipeline_version_id) if campaign else None
        if campaign is None or pipeline is None:
            raise NotFoundError("La convocatoria de la postulación no existe.")
        evaluation = (
            self._evaluated.evaluation(application.evaluation_item_id)
            if application.evaluation_item_id
            else None
        )
        jobs = (evaluation.extraction.get("experiencia") if evaluation else None) or []
        return ApplicationDetail(
            view=self._view(application),
            campaign=campaign,
            pipeline=pipeline,
            movements=self._repo.movements(application.id),
            evaluation=evaluation,
            tenure=tenure.summarize(jobs, self._clock().date()) if jobs else None,
            outcomes=self._repo.outcomes(application.id),
        )

    # --- Cambios sobre una postulación ---------------------------------------------------

    def update_candidate(
        self,
        actor: UserInfo,
        application_id: uuid.UUID,
        *,
        full_name: str,
        email: str | None,
        phone: str | None,
        ip: str | None = None,
    ) -> ApplicationView:
        application = self._load(actor, application_id, AccessLevel.COLABORACION)
        view = self._view(application)
        candidate = view.candidate
        name, email, phone = self._contact(full_name, email, phone)
        if email and email != candidate.email:
            other = self._repo.candidate_by_email(email)
            if other is not None and other.id != candidate.id:
                raise ConflictError("Ya existe otro candidato con ese correo.")
        candidate.full_name, candidate.email, candidate.phone = name, email, phone
        candidate.updated_at = self._clock()
        self._repo.save_candidate(candidate)
        self._audit.record(
            AuditAction.CANDIDATO_ACTUALIZADO,
            actor_user_id=actor.id,
            resource_type="candidato",
            resource_id=candidate.id,
            ip=ip,
            details={"vacante": str(application.vacancy_id)},
        )
        return view

    def move(
        self,
        actor: UserInfo,
        vacancy_id: uuid.UUID,
        application_ids: list[uuid.UUID],
        to_stage_id: uuid.UUID,
        *,
        note: str | None,
        ip: str | None = None,
    ) -> list[Application]:
        """Mueve una o varias postulaciones a una etapa. Todo o nada."""
        self._access.require(actor, vacancy_id, AccessLevel.COLABORACION)
        ids = list(dict.fromkeys(application_ids))
        if not ids:
            raise ValidationFailedError("Elige al menos una postulación.")
        if len(ids) > MAX_MASS_MOVE:
            raise ValidationFailedError(f"Se mueven como máximo {MAX_MASS_MOVE} a la vez.")
        note = _clean(note, 500) or None
        applications = [self._repo.application(application_id) for application_id in ids]
        if any(a is None or a.vacancy_id != vacancy_id for a in applications):
            raise NotFoundError("Alguna postulación no existe en esta vacante.")
        loaded = [a for a in applications if a is not None]
        if len({a.campaign_id for a in loaded}) != 1:
            raise ValidationFailedError("Las postulaciones deben ser de la misma convocatoria.")
        campaign = self._repo.campaign(loaded[0].campaign_id)
        pipeline = self._repo.pipeline(campaign.pipeline_version_id) if campaign else None
        if campaign is None or pipeline is None:
            raise NotFoundError("La convocatoria no existe.")
        if campaign.status is not CampaignStatus.ABIERTA:
            raise ConflictError("La convocatoria está cerrada; ya no admite movimientos.")
        by_id = {stage.id: stage for stage in pipeline.stages}
        target = by_id.get(to_stage_id)
        if target is None:
            raise ValidationFailedError("La etapa no pertenece al proceso de esta convocatoria.")

        now = self._clock()
        group_id = new_sequential_uuid() if len(loaded) > 1 else None
        entries: list[Movement] = []
        for application in loaded:
            if application.status is not ApplicationStatus.ACTIVA:
                raise ConflictError("Solo se mueven postulaciones activas. Reactívala primero.")
            origin = by_id[application.stage_id]
            if origin.id == target.id:
                raise ValidationFailedError("Alguna postulación ya está en esa etapa.")
            forward = target.position > origin.position
            skipped = [s for s in pipeline.stages if origin.position < s.position < target.position]
            if not note:
                if not forward:
                    raise ValidationFailedError("Escribe el motivo para regresar de etapa.")
                if any(not stage.is_optional for stage in skipped):
                    raise ValidationFailedError("Escribe el motivo para omitir etapas.")
                if (
                    application.ai_classification in ("RECHAZADO_IA", "NO_EVALUABLE")
                    and origin.kind in _ENTRY_KINDS
                ):
                    raise ValidationFailedError(
                        "La IA no clasificó como aceptada a esta persona. Escribe el motivo "
                        "de tu decisión de avanzarla."
                    )
            common = {"actor_user_id": actor.id, "group_id": group_id}
            entries += [
                Movement(
                    new_sequential_uuid(),
                    application.id,
                    MovementKind.OMISION,
                    now,
                    from_stage_id=stage.id,
                    note=note,
                    **common,
                )
                for stage in skipped
            ]
            entries.append(
                Movement(
                    new_sequential_uuid(),
                    application.id,
                    MovementKind.AVANCE if forward else MovementKind.RETROCESO,
                    now,
                    from_stage_id=origin.id,
                    to_stage_id=target.id,
                    note=note,
                    **common,
                )
            )
            application.stage_id = target.id
            application.due_at = None
            application.updated_at = now
            self._repo.save_application(application)
        self._movements(entries)
        self._audit.record(
            AuditAction.POSTULACION_MOVIDA,
            actor_user_id=actor.id,
            resource_type="convocatoria",
            resource_id=campaign.id,
            ip=ip,
            details={
                "vacante": str(vacancy_id),
                "postulaciones": len(loaded),
                "etapa": target.name,
                "con_motivo": note is not None,
                # Decisión humana sobre personas que la IA no clasificó como aceptadas.
                "no_aceptadas_por_ia": sum(
                    1 for a in loaded if a.ai_classification in ("RECHAZADO_IA", "NO_EVALUABLE")
                ),
            },
        )
        return loaded

    def record_outcome(
        self,
        actor: UserInfo,
        application_id: uuid.UUID,
        outcome: OutcomeKind,
        *,
        reason: str | None,
        notes: str | None = None,
        start_date: date | None = None,
        ip: str | None = None,
    ) -> Application:
        """Registra el resultado final de una postulación y la cierra.

        Lo captura una persona con permiso de colaboración sobre la vacante;
        el sistema nunca lo decide. Todo resultado lleva motivo, salvo la
        contratación, que puede llevar la fecha de incorporación.
        """
        application = self._load(actor, application_id, AccessLevel.COLABORACION)
        if application.status is not ApplicationStatus.ACTIVA:
            raise ConflictError(
                "La postulación ya tiene un resultado final. Reábrela para cambiarlo."
            )
        hired = outcome is OutcomeKind.CONTRATADO
        reason = _clean(reason, 500) or None
        if not hired and len(reason or "") < 5:
            raise ValidationFailedError("Escribe el motivo.")
        notes = (notes or "").strip()[:MAX_OUTCOME_NOTES] or None
        now = self._clock()
        if start_date is not None:
            if not hired:
                raise ValidationFailedError(
                    "La fecha de incorporación solo aplica a una contratación."
                )
            if abs((start_date - now.date()).days) > MAX_START_DATE_DAYS:
                raise ValidationFailedError("Revisa la fecha de incorporación.")
        if hired:
            vacancy, _ = self._access.require(
                actor, application.vacancy_id, AccessLevel.COLABORACION
            )
            if self._repo.hires(vacancy.id) >= vacancy.positions:
                plazas = "1 plaza" if vacancy.positions == 1 else f"{vacancy.positions} plazas"
                raise ConflictError(
                    f"La vacante tiene {plazas} y ya está cubierta. Si se abrió otra plaza, "
                    "actualiza la vacante antes de registrar la contratación."
                )
        application.status = OUTCOME_STATUS[outcome]
        application.updated_at = now
        self._repo.save_application(application)
        self._repo.add_outcome(
            Outcome(
                id=new_sequential_uuid(),
                application_id=application.id,
                vacancy_id=application.vacancy_id,
                outcome=outcome,
                recorded_at=now,
                recorded_by=actor.id,
                reason=reason,
                notes=notes,
                start_date=start_date,
            )
        )
        self._movements(
            [
                Movement(
                    new_sequential_uuid(),
                    application.id,
                    OUTCOME_MOVEMENT[outcome],
                    now,
                    actor.id,
                    from_stage_id=application.stage_id,
                    note=reason,
                )
            ]
        )
        self._audit.record(
            AuditAction.RESULTADO_FINAL_REGISTRADO,
            actor_user_id=actor.id,
            resource_type="postulacion",
            resource_id=application.id,
            ip=ip,
            details={
                "vacante": str(application.vacancy_id),
                "resultado": outcome.value,
                # Decisión humana sobre una persona que la IA no clasificó como aceptada.
                "no_aceptada_por_ia": hired
                and application.ai_classification in ("RECHAZADO_IA", "NO_EVALUABLE"),
            },
        )
        return application

    def reopen(
        self,
        actor: UserInfo,
        application_id: uuid.UUID,
        *,
        reason: str | None,
        ip: str | None = None,
    ) -> Application:
        """Reabre una postulación cerrada. El resultado anterior queda anulado,
        con quién lo anuló y por qué; no se borra."""
        application = self._load(actor, application_id, AccessLevel.COLABORACION)
        if application.status is ApplicationStatus.ACTIVA:
            raise ConflictError("La postulación ya está activa.")
        reason = _clean(reason, 500)
        if len(reason) < 5:
            raise ValidationFailedError("Escribe el motivo.")
        now = self._clock()
        previous = self._repo.current_outcome(application.id)
        if previous is not None:
            previous.voided_at, previous.voided_by, previous.void_reason = now, actor.id, reason
            self._repo.save_outcome(previous)
        application.status = ApplicationStatus.ACTIVA
        application.updated_at = now
        self._repo.save_application(application)
        self._movements(
            [
                Movement(
                    new_sequential_uuid(),
                    application.id,
                    MovementKind.REACTIVACION,
                    now,
                    actor.id,
                    from_stage_id=application.stage_id,
                    note=reason,
                )
            ]
        )
        self._audit.record(
            AuditAction.RESULTADO_FINAL_ANULADO,
            actor_user_id=actor.id,
            resource_type="postulacion",
            resource_id=application.id,
            ip=ip,
            details={
                "vacante": str(application.vacancy_id),
                "resultado_anulado": previous.outcome.value if previous else None,
            },
        )
        return application

    def change_status(
        self,
        actor: UserInfo,
        application_id: uuid.UUID,
        action: MovementKind,
        *,
        note: str | None,
        ip: str | None = None,
    ) -> Application:
        """Atajos de desistimiento, descarte, cancelación y reactivación.
        Son resultados finales: quedan registrados igual que los demás."""
        if action is MovementKind.REACTIVACION:
            return self.reopen(actor, application_id, reason=note, ip=ip)
        outcome = MOVEMENT_OUTCOME.get(action)
        if outcome is None or outcome not in _SHORTCUT_OUTCOMES:
            raise ValidationFailedError("La acción no es válida.")
        return self.record_outcome(actor, application_id, outcome, reason=note, ip=ip)

    def annotate(
        self,
        actor: UserInfo,
        application_id: uuid.UUID,
        *,
        note: str | None,
        due_at: datetime | None = None,
        reschedule: bool = False,
        ip: str | None = None,
    ) -> Application:
        """Registra una incidencia o reprograma la etapa actual. No cambia de etapa."""
        application = self._load(actor, application_id, AccessLevel.COLABORACION)
        note = _clean(note, 500)
        if len(note) < 5:
            raise ValidationFailedError("Describe lo ocurrido.")
        if reschedule and due_at is None:
            raise ValidationFailedError("Indica la nueva fecha.")
        now = self._clock()
        if reschedule:
            application.due_at = due_at
            application.updated_at = now
            self._repo.save_application(application)
        self._movements(
            [
                Movement(
                    new_sequential_uuid(),
                    application.id,
                    MovementKind.REPROGRAMACION if reschedule else MovementKind.INCIDENCIA,
                    now,
                    actor.id,
                    from_stage_id=application.stage_id,
                    note=note,
                    due_at=due_at if reschedule else None,
                )
            ]
        )
        self._audit.record(
            AuditAction.POSTULACION_ANOTADA,
            actor_user_id=actor.id,
            resource_type="postulacion",
            resource_id=application.id,
            ip=ip,
            details={
                "vacante": str(application.vacancy_id),
                "tipo": "reprogramacion" if reschedule else "incidencia",
            },
        )
        return application
