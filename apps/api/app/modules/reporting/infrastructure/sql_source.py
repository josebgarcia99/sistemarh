"""Lectura de los hechos para los reportes, sobre SQL Server (SQLAlchemy).

Es un modelo de lectura: consulta las tablas de los demás módulos, pero no
escribe en ellas. Las vacantes que entran se deciden en una sola subconsulta
(permisos y filtros de vacante), que después acota todas las demás.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Session, aliased

from app.modules.ai_settings.infrastructure.orm import AiExecutionRow
from app.modules.cv_processing.infrastructure.orm import CvBatchItemRow, CvBatchRow
from app.modules.evaluation_setup.infrastructure.orm import PromptVersionRow
from app.modules.file_management.infrastructure.orm import FileAssetRow
from app.modules.phone_calls.infrastructure.orm import (
    CallSessionRow,
    QuestionBankRow,
    QuestionBankVersionRow,
)
from app.modules.recruitment.infrastructure.orm import (
    ApplicationMovementRow,
    ApplicationOutcomeRow,
    ApplicationRow,
    CampaignRow,
    CandidateRow,
    PipelineStageRow,
)
from app.modules.reporting.domain.models import (
    AiFact,
    ApplicationFact,
    CvFact,
    ExportKind,
    FilterOptions,
    MovementFact,
    Option,
    OutcomeFact,
    ReportExport,
    StageFact,
    VacancyFact,
    VacancySelection,
)
from app.modules.reporting.infrastructure.orm import ReportExportRow
from app.modules.users.infrastructure.orm import UserRow
from app.modules.vacancies.infrastructure.orm import VacancyMemberRow, VacancyRow

_OK = "CORRECTA"


def _member_of(user_id: uuid.UUID) -> sa.ColumnElement[bool]:
    return sa.exists().where(
        VacancyMemberRow.vacancy_id == VacancyRow.id,
        VacancyMemberRow.user_id == user_id,
        VacancyMemberRow.revoked_at.is_(None),
    )


def _selected(selection: VacancySelection) -> sa.Select[tuple[uuid.UUID]]:
    """Identificadores de las vacantes que entran en la consulta."""
    query = sa.select(VacancyRow.id)
    if selection.visible_to is not None:
        query = query.where(
            sa.or_(
                VacancyRow.owner_user_id == selection.visible_to,
                _member_of(selection.visible_to),
            )
        )
    if selection.vacancy_id is not None:
        query = query.where(VacancyRow.id == selection.vacancy_id)
    if selection.owner_id is not None:
        query = query.where(VacancyRow.owner_user_id == selection.owner_id)
    if selection.collaborator_id is not None:
        query = query.where(_member_of(selection.collaborator_id))
    if selection.department:
        query = query.where(VacancyRow.department == selection.department)
    if selection.status:
        query = query.where(VacancyRow.status == selection.status)
    return query


class SqlReportingSource:
    def __init__(self, session: Session) -> None:
        self._session = session

    def vacancies(self, selection: VacancySelection) -> list[VacancyFact]:
        ids = _selected(selection)
        members: dict[uuid.UUID, set[uuid.UUID]] = {}
        for vacancy_id, user_id in self._session.execute(
            sa.select(VacancyMemberRow.vacancy_id, VacancyMemberRow.user_id).where(
                VacancyMemberRow.revoked_at.is_(None), VacancyMemberRow.vacancy_id.in_(ids)
            )
        ):
            members.setdefault(vacancy_id, set()).add(user_id)
        rows = self._session.execute(
            sa.select(VacancyRow, UserRow.full_name)
            .join(UserRow, UserRow.id == VacancyRow.owner_user_id)
            .where(VacancyRow.id.in_(ids))
        )
        return [
            VacancyFact(
                id=v.id,
                name=v.name,
                department=v.department,
                status=v.status,
                positions=v.positions,
                owner_id=v.owner_user_id,
                owner_name=owner_name,
                created_at=v.created_at,
                opened_at=v.opened_at,
                closed_at=v.closed_at,
                collaborators=frozenset(members.get(v.id, ())),
            )
            for v, owner_name in rows
        ]

    def stages(self) -> dict[uuid.UUID, StageFact]:
        rows = self._session.execute(sa.select(PipelineStageRow)).scalars()
        return {
            s.id: StageFact(s.id, s.pipeline_version_id, s.position, s.name, s.kind) for s in rows
        }

    def applications(self, selection: VacancySelection) -> list[ApplicationFact]:
        rows = self._session.execute(
            sa.select(
                ApplicationRow,
                CandidateRow.full_name,
                CampaignRow.opened_at,
                FileAssetRow.created_at,
                CvBatchItemRow.updated_at,
                AiExecutionRow.model_id,
                PromptVersionRow.id,
                PromptVersionRow.version_number,
            )
            .join(CandidateRow, CandidateRow.id == ApplicationRow.candidate_id)
            .join(CampaignRow, CampaignRow.id == ApplicationRow.campaign_id)
            .outerjoin(FileAssetRow, FileAssetRow.id == ApplicationRow.cv_file_id)
            .outerjoin(CvBatchItemRow, CvBatchItemRow.id == ApplicationRow.evaluation_item_id)
            .outerjoin(CvBatchRow, CvBatchRow.id == CvBatchItemRow.batch_id)
            .outerjoin(PromptVersionRow, PromptVersionRow.id == CvBatchRow.prompt_version_id)
            .outerjoin(AiExecutionRow, AiExecutionRow.id == CvBatchItemRow.execution_id)
            .where(ApplicationRow.vacancy_id.in_(_selected(selection)))
        )
        return [
            ApplicationFact(
                id=a.id,
                vacancy_id=a.vacancy_id,
                candidate_name=name,
                stage_id=a.stage_id,
                status=a.status,
                created_at=a.created_at,
                campaign_opened_at=opened_at,
                ai_classification=a.ai_classification,
                ai_score=a.ai_score,
                cv_uploaded_at=uploaded_at,
                evaluated_at=evaluated_at,
                model=model,
                prompt_version_id=prompt_id,
                prompt_version_number=prompt_number,
            )
            for a, name, opened_at, uploaded_at, evaluated_at, model, prompt_id, prompt_number in (
                rows
            )
        ]

    def movements(self, selection: VacancySelection) -> list[MovementFact]:
        rows = self._session.execute(
            sa.select(ApplicationMovementRow, UserRow.full_name)
            .join(ApplicationRow, ApplicationRow.id == ApplicationMovementRow.application_id)
            .outerjoin(UserRow, UserRow.id == ApplicationMovementRow.actor_user_id)
            .where(ApplicationRow.vacancy_id.in_(_selected(selection)))
        )
        return [
            MovementFact(
                application_id=m.application_id,
                sequence=m.sequence,
                kind=m.kind,
                occurred_at=m.occurred_at,
                from_stage_id=m.from_stage_id,
                to_stage_id=m.to_stage_id,
                actor_name=actor_name,
            )
            for m, actor_name in rows
        ]

    def outcomes(self, selection: VacancySelection) -> list[OutcomeFact]:
        rows = self._session.execute(
            sa.select(ApplicationOutcomeRow, UserRow.full_name)
            .join(UserRow, UserRow.id == ApplicationOutcomeRow.recorded_by)
            .where(
                ApplicationOutcomeRow.voided_at.is_(None),
                ApplicationOutcomeRow.vacancy_id.in_(_selected(selection)),
            )
        )
        return [
            OutcomeFact(
                application_id=o.application_id,
                vacancy_id=o.vacancy_id,
                outcome=o.outcome,
                recorded_at=o.recorded_at,
                recorded_by_name=name,
                reason=o.reason,
                start_date=o.start_date,
            )
            for o, name in rows
        ]

    def cvs(self, selection: VacancySelection) -> list[CvFact]:
        rows = self._session.execute(
            sa.select(
                CvBatchRow.vacancy_id,
                CvBatchItemRow.status,
                CvBatchItemRow.updated_at,
                CvBatchItemRow.classification,
            )
            .join(CvBatchRow, CvBatchRow.id == CvBatchItemRow.batch_id)
            .where(CvBatchRow.vacancy_id.in_(_selected(selection)))
        )
        return [CvFact(*row) for row in rows]

    def ai_executions(
        self, start: datetime | None, end: datetime | None, selection: VacancySelection
    ) -> list[AiFact]:
        query = sa.select(
            AiExecutionRow.occurred_at,
            AiExecutionRow.operation,
            AiExecutionRow.status,
            sa.func.coalesce(AiExecutionRow.confirmed_cost_usd, AiExecutionRow.estimated_cost_usd),
        )
        if start is not None:
            query = query.where(AiExecutionRow.occurred_at >= start)
        if end is not None:
            query = query.where(AiExecutionRow.occurred_at < end)
        if selection.filtered:
            query = query.where(AiExecutionRow.vacancy_id.in_(_selected(selection)))
        return [
            AiFact(occurred_at, operation, status == _OK, cost)
            for occurred_at, operation, status, cost in self._session.execute(query)
        ]

    def applications_with_bank(
        self, selection: VacancySelection, bank_id: uuid.UUID
    ) -> set[uuid.UUID]:
        return set(
            self._session.execute(
                sa.select(CallSessionRow.application_id)
                .join(
                    QuestionBankVersionRow,
                    QuestionBankVersionRow.id == CallSessionRow.bank_version_id,
                )
                .where(
                    QuestionBankVersionRow.bank_id == bank_id,
                    CallSessionRow.vacancy_id.in_(_selected(selection)),
                )
            ).scalars()
        )

    def options(self, selection: VacancySelection) -> FilterOptions:
        ids = _selected(selection)
        vacancies = self._session.execute(
            sa.select(VacancyRow.id, VacancyRow.name, VacancyRow.department, UserRow)
            .join(UserRow, UserRow.id == VacancyRow.owner_user_id)
            .where(VacancyRow.id.in_(ids))
            .order_by(VacancyRow.name, VacancyRow.id)
        ).all()
        member = aliased(UserRow)
        collaborators = self._session.execute(
            sa.select(member.id, member.full_name)
            .join(VacancyMemberRow, VacancyMemberRow.user_id == member.id)
            .where(VacancyMemberRow.revoked_at.is_(None), VacancyMemberRow.vacancy_id.in_(ids))
            .distinct()
            .order_by(member.full_name)
        ).all()
        stages = self._session.execute(
            sa.select(PipelineStageRow.name, sa.func.min(PipelineStageRow.position))
            .group_by(PipelineStageRow.name)
            .order_by(sa.func.min(PipelineStageRow.position), PipelineStageRow.name)
        ).all()
        evaluated = (
            sa.select(CvBatchItemRow.execution_id, CvBatchRow.prompt_version_id)
            .join(CvBatchRow, CvBatchRow.id == CvBatchItemRow.batch_id)
            .where(CvBatchRow.vacancy_id.in_(ids))
            .subquery()
        )
        models = self._session.execute(
            sa.select(AiExecutionRow.model_id)
            .where(AiExecutionRow.id.in_(sa.select(evaluated.c.execution_id)))
            .distinct()
            .order_by(AiExecutionRow.model_id)
        ).scalars()
        prompts = self._session.execute(
            sa.select(PromptVersionRow.id, PromptVersionRow.version_number, VacancyRow.name)
            .join(VacancyRow, VacancyRow.id == PromptVersionRow.vacancy_id)
            .where(PromptVersionRow.id.in_(sa.select(evaluated.c.prompt_version_id)))
            .order_by(VacancyRow.name, PromptVersionRow.version_number)
        ).all()
        banks = self._session.execute(
            sa.select(QuestionBankRow.id, QuestionBankRow.name)
            .join(QuestionBankVersionRow, QuestionBankVersionRow.bank_id == QuestionBankRow.id)
            .join(CallSessionRow, CallSessionRow.bank_version_id == QuestionBankVersionRow.id)
            .where(CallSessionRow.vacancy_id.in_(ids))
            .distinct()
            .order_by(QuestionBankRow.name)
        ).all()
        owners = {owner.id: owner.full_name for _, _, _, owner in vacancies}
        return FilterOptions(
            vacancies=[Option(str(vacancy_id), name) for vacancy_id, name, _, _ in vacancies],
            owners=[
                Option(str(user_id), name)
                for user_id, name in sorted(owners.items(), key=lambda item: item[1].casefold())
            ],
            collaborators=[Option(str(user_id), name) for user_id, name in collaborators],
            departments=sorted({department for _, _, department, _ in vacancies}, key=str.casefold),
            stages=[name for name, _ in stages],
            models=list(models),
            prompt_versions=[
                Option(str(prompt_id), f"{vacancy} · versión {number}")
                for prompt_id, number, vacancy in prompts
            ],
            banks=[Option(str(bank_id), name) for bank_id, name in banks],
        )

    # --- Reportes generados --------------------------------------------------------------

    @staticmethod
    def _export(row: ReportExportRow) -> ReportExport:
        return ReportExport(
            id=row.id,
            kind=ExportKind(row.kind),
            name=row.name,
            filters=json.loads(row.filters),
            vacancy_ids=[uuid.UUID(value) for value in json.loads(row.vacancy_ids)],
            row_count=row.row_count,
            storage_key=row.storage_key,
            size_bytes=row.size_bytes,
            sha256=row.sha256,
            created_at=row.created_at,
            created_by=row.created_by,
        )

    def add_export(self, export: ReportExport) -> None:
        self._session.add(
            ReportExportRow(
                id=export.id,
                kind=export.kind.value,
                name=export.name,
                filters=json.dumps(export.filters, ensure_ascii=False),
                vacancy_ids=json.dumps([str(value) for value in export.vacancy_ids]),
                row_count=export.row_count,
                storage_key=export.storage_key,
                size_bytes=export.size_bytes,
                sha256=export.sha256,
                created_at=export.created_at,
                created_by=export.created_by,
            )
        )
        self._session.flush()

    def export(self, export_id: uuid.UUID) -> ReportExport | None:
        row = self._session.get(ReportExportRow, export_id)
        return self._export(row) if row is not None else None

    def exports_of(self, user_id: uuid.UUID, limit: int) -> list[ReportExport]:
        rows = self._session.execute(
            sa.select(ReportExportRow)
            .where(ReportExportRow.created_by == user_id)
            .order_by(ReportExportRow.created_at.desc(), ReportExportRow.id.desc())
            .limit(limit)
        ).scalars()
        return [self._export(row) for row in rows]

    def export_keys(self) -> set[str]:
        """Rutas de todos los reportes guardados (para la conciliación)."""
        return set(self._session.execute(sa.select(ReportExportRow.storage_key)).scalars())
