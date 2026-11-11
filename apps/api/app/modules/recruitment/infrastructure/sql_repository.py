"""Repositorio de reclutamiento sobre SQL Server (SQLAlchemy)."""

from __future__ import annotations

import uuid
from dataclasses import fields

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.modules.recruitment.domain.models import (
    Application,
    ApplicationStatus,
    Campaign,
    CampaignStatus,
    Candidate,
    Movement,
    MovementKind,
    PipelineVersion,
    Stage,
    StageKind,
)
from app.modules.recruitment.infrastructure.orm import (
    ApplicationMovementRow,
    ApplicationRow,
    CampaignRow,
    CandidateRow,
    PipelineStageRow,
    PipelineVersionRow,
)


def _names(model: type) -> tuple[str, ...]:
    return tuple(f.name for f in fields(model) if f.name != "id")


_CAMPAIGN, _CANDIDATE, _APPLICATION, _MOVEMENT = (
    _names(Campaign),
    _names(Candidate),
    _names(Application),
    _names(Movement),
)
_ENUMS = {
    Campaign: {"status": CampaignStatus},
    Application: {"status": ApplicationStatus},
    Movement: {"kind": MovementKind},
    Candidate: {},
}


def _values(entity: object, names: tuple[str, ...]) -> dict[str, object]:
    values = {name: getattr(entity, name) for name in names}
    for name in _ENUMS[type(entity)]:
        values[name] = values[name].value
    return values


def _entity(model: type, row: object, names: tuple[str, ...]):  # noqa: ANN202
    values = {name: getattr(row, name) for name in names}
    for name, enum in _ENUMS[model].items():
        values[name] = enum(values[name])
    return model(id=row.id, **values)  # type: ignore[attr-defined]


class SqlRecruitmentRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def _save(self, row_type: type, entity: object, names: tuple[str, ...]) -> None:
        row = self._session.get(row_type, entity.id)  # type: ignore[attr-defined]
        if row is None:
            raise LookupError("El registro no existe.")
        for name, value in _values(entity, names).items():
            setattr(row, name, value)
        self._session.flush()

    # --- Etapas --------------------------------------------------------------------------

    def _pipeline(self, row: PipelineVersionRow | None) -> PipelineVersion | None:
        if row is None:
            return None
        stages = self._session.execute(
            sa.select(PipelineStageRow)
            .where(PipelineStageRow.pipeline_version_id == row.id)
            .order_by(PipelineStageRow.position)
        ).scalars()
        return PipelineVersion(
            id=row.id,
            version_number=row.version_number,
            created_at=row.created_at,
            created_by=row.created_by,
            stages=tuple(
                Stage(
                    s.id,
                    s.pipeline_version_id,
                    s.position,
                    s.name,
                    StageKind(s.kind),
                    s.is_optional,
                )
                for s in stages
            ),
        )

    def latest_pipeline(self) -> PipelineVersion | None:
        row = self._session.execute(
            sa.select(PipelineVersionRow)
            .order_by(PipelineVersionRow.version_number.desc())
            .limit(1)
        ).scalar_one_or_none()
        return self._pipeline(row)

    def pipeline(self, version_id: uuid.UUID) -> PipelineVersion | None:
        return self._pipeline(self._session.get(PipelineVersionRow, version_id))

    def add_pipeline(self, version: PipelineVersion) -> None:
        self._session.add(
            PipelineVersionRow(
                id=version.id,
                version_number=version.version_number,
                created_at=version.created_at,
                created_by=version.created_by,
            )
        )
        self._session.flush()
        self._session.add_all(
            PipelineStageRow(
                id=s.id,
                pipeline_version_id=version.id,
                position=s.position,
                name=s.name,
                kind=s.kind.value,
                is_optional=s.is_optional,
            )
            for s in version.stages
        )
        self._session.flush()

    # --- Convocatorias -------------------------------------------------------------------

    def campaigns(self, vacancy_id: uuid.UUID) -> list[Campaign]:
        rows = self._session.execute(
            sa.select(CampaignRow)
            .where(CampaignRow.vacancy_id == vacancy_id)
            .order_by(CampaignRow.number.desc())
        ).scalars()
        return [_entity(Campaign, row, _CAMPAIGN) for row in rows]

    def campaign(self, campaign_id: uuid.UUID) -> Campaign | None:
        row = self._session.get(CampaignRow, campaign_id)
        return _entity(Campaign, row, _CAMPAIGN) if row is not None else None

    def add_campaign(self, campaign: Campaign) -> None:
        self._session.add(CampaignRow(id=campaign.id, **_values(campaign, _CAMPAIGN)))
        self._session.flush()

    def save_campaign(self, campaign: Campaign) -> None:
        self._save(CampaignRow, campaign, _CAMPAIGN)

    # --- Candidatos ----------------------------------------------------------------------

    def candidate(self, candidate_id: uuid.UUID) -> Candidate | None:
        row = self._session.get(CandidateRow, candidate_id)
        return _entity(Candidate, row, _CANDIDATE) if row is not None else None

    def candidates(self, candidate_ids: list[uuid.UUID]) -> dict[uuid.UUID, Candidate]:
        if not candidate_ids:
            return {}
        rows = self._session.execute(
            sa.select(CandidateRow).where(CandidateRow.id.in_(candidate_ids))
        ).scalars()
        return {row.id: _entity(Candidate, row, _CANDIDATE) for row in rows}

    def candidate_by_email(self, email: str) -> Candidate | None:
        row = self._session.execute(
            sa.select(CandidateRow).where(CandidateRow.email == email)
        ).scalar_one_or_none()
        return _entity(Candidate, row, _CANDIDATE) if row is not None else None

    def add_candidate(self, candidate: Candidate) -> None:
        self._session.add(CandidateRow(id=candidate.id, **_values(candidate, _CANDIDATE)))
        self._session.flush()

    def save_candidate(self, candidate: Candidate) -> None:
        self._save(CandidateRow, candidate, _CANDIDATE)

    # --- Postulaciones -------------------------------------------------------------------

    def application(self, application_id: uuid.UUID) -> Application | None:
        row = self._session.get(ApplicationRow, application_id)
        return _entity(Application, row, _APPLICATION) if row is not None else None

    def applications(self, campaign_id: uuid.UUID) -> list[Application]:
        rows = self._session.execute(
            sa.select(ApplicationRow)
            .where(ApplicationRow.campaign_id == campaign_id)
            .order_by(ApplicationRow.created_at, ApplicationRow.id)
        ).scalars()
        return [_entity(Application, row, _APPLICATION) for row in rows]

    def application_of(self, candidate_id: uuid.UUID, campaign_id: uuid.UUID) -> Application | None:
        row = self._session.execute(
            sa.select(ApplicationRow).where(
                ApplicationRow.candidate_id == candidate_id,
                ApplicationRow.campaign_id == campaign_id,
            )
        ).scalar_one_or_none()
        return _entity(Application, row, _APPLICATION) if row is not None else None

    def files_with_application(self, vacancy_id: uuid.UUID) -> set[uuid.UUID]:
        return set(
            self._session.execute(
                sa.select(ApplicationRow.cv_file_id).where(
                    ApplicationRow.vacancy_id == vacancy_id,
                    ApplicationRow.cv_file_id.is_not(None),
                )
            ).scalars()
        )

    def add_application(self, application: Application) -> None:
        self._session.add(ApplicationRow(id=application.id, **_values(application, _APPLICATION)))
        self._session.flush()

    def save_application(self, application: Application) -> None:
        self._save(ApplicationRow, application, _APPLICATION)

    # --- Movimientos ---------------------------------------------------------------------

    def add_movements(self, movements: list[Movement]) -> None:
        self._session.add_all(
            ApplicationMovementRow(id=m.id, **_values(m, _MOVEMENT)) for m in movements
        )
        self._session.flush()

    def movement_count(self, application_id: uuid.UUID) -> int:
        return self._session.execute(
            sa.select(sa.func.count()).where(
                ApplicationMovementRow.application_id == application_id
            )
        ).scalar_one()

    def movements(self, application_id: uuid.UUID) -> list[Movement]:
        rows = self._session.execute(
            sa.select(ApplicationMovementRow)
            .where(ApplicationMovementRow.application_id == application_id)
            .order_by(ApplicationMovementRow.sequence)
        ).scalars()
        return [_entity(Movement, row, _MOVEMENT) for row in rows]
