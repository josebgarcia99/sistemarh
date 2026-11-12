"""Repositorio de perfiles y prompts sobre SQL Server (SQLAlchemy)."""

from __future__ import annotations

import json
import uuid

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.modules.evaluation_setup.domain.models import (
    Criterion,
    CriterionKind,
    CriterionOrigin,
    LayerKey,
    ProfileContent,
    ProfileOrigin,
    ProfileVersion,
    PromptStatus,
    PromptVersion,
)
from app.modules.evaluation_setup.infrastructure.orm import (
    JobProfileVersionRow,
    PromptVersionRow,
    RubricCriterionRow,
)

_PROMPT_FIELDS = (
    "vacancy_id",
    "version_number",
    "profile_version_id",
    "pass_threshold",
    "revision",
    "duplicated_from",
    "created_at",
    "created_by",
    "updated_at",
    "updated_by",
    "submitted_at",
    "submitted_by",
    "approved_at",
    "approved_by",
    "archived_at",
    "archived_by",
)


def _to_profile(row: JobProfileVersionRow) -> ProfileVersion:
    return ProfileVersion(
        id=row.id,
        vacancy_id=row.vacancy_id,
        version_number=row.version_number,
        origin=ProfileOrigin(row.origin),
        content=ProfileContent.from_stored(json.loads(row.content)),
        change_note=row.change_note,
        source_file_id=row.source_file_id,
        created_at=row.created_at,
        created_by=row.created_by,
    )


class SqlEvaluationSetupRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    # --- Perfil --------------------------------------------------------------------------

    def profile_versions(self, vacancy_id: uuid.UUID) -> list[ProfileVersion]:
        rows = self._session.execute(
            sa.select(JobProfileVersionRow)
            .where(JobProfileVersionRow.vacancy_id == vacancy_id)
            .order_by(JobProfileVersionRow.version_number.desc())
        ).scalars()
        return [_to_profile(row) for row in rows]

    def profile_version(self, version_id: uuid.UUID) -> ProfileVersion | None:
        row = self._session.get(JobProfileVersionRow, version_id)
        return _to_profile(row) if row is not None else None

    def add_profile_version(self, version: ProfileVersion) -> None:
        self._session.add(
            JobProfileVersionRow(
                id=version.id,
                vacancy_id=version.vacancy_id,
                version_number=version.version_number,
                origin=version.origin.value,
                content=json.dumps(version.content.to_dict(), ensure_ascii=False),
                change_note=version.change_note,
                source_file_id=version.source_file_id,
                created_at=version.created_at,
                created_by=version.created_by,
            )
        )
        self._session.flush()

    # --- Prompts -------------------------------------------------------------------------

    def _criteria(self, version_id: uuid.UUID) -> list[Criterion]:
        rows = self._session.execute(
            sa.select(RubricCriterionRow)
            .where(RubricCriterionRow.prompt_version_id == version_id)
            .order_by(RubricCriterionRow.position)
        ).scalars()
        return [
            Criterion(
                id=row.id,
                position=row.position,
                name=row.name,
                description=row.description,
                kind=CriterionKind(row.kind),
                weight=row.weight,
                levels=tuple(json.loads(row.levels)),
                origin=CriterionOrigin(row.origin),
            )
            for row in rows
        ]

    def _to_prompt(self, row: PromptVersionRow) -> PromptVersion:
        return PromptVersion(
            id=row.id,
            status=PromptStatus(row.status),
            layers={LayerKey(key): value for key, value in json.loads(row.layers).items()},
            criteria=self._criteria(row.id),
            **{name: getattr(row, name) for name in _PROMPT_FIELDS},
        )

    def prompt_versions(self, vacancy_id: uuid.UUID) -> list[PromptVersion]:
        rows = self._session.execute(
            sa.select(PromptVersionRow)
            .where(PromptVersionRow.vacancy_id == vacancy_id)
            .order_by(PromptVersionRow.version_number.desc())
        ).scalars()
        return [self._to_prompt(row) for row in rows]

    def prompt_version(self, version_id: uuid.UUID) -> PromptVersion | None:
        row = self._session.get(PromptVersionRow, version_id)
        return self._to_prompt(row) if row is not None else None

    @staticmethod
    def _layers_json(version: PromptVersion) -> str:
        return json.dumps(
            {key.value: text for key, text in version.layers.items()}, ensure_ascii=False
        )

    def _add_criteria(self, version: PromptVersion) -> None:
        for criterion in version.criteria:
            self._session.add(
                RubricCriterionRow(
                    id=criterion.id,
                    prompt_version_id=version.id,
                    position=criterion.position,
                    name=criterion.name,
                    description=criterion.description,
                    kind=criterion.kind.value,
                    weight=criterion.weight,
                    levels=json.dumps(list(criterion.levels), ensure_ascii=False),
                    origin=criterion.origin.value,
                )
            )

    def add_prompt_version(self, version: PromptVersion) -> None:
        self._session.add(
            PromptVersionRow(
                id=version.id,
                status=version.status.value,
                layers=self._layers_json(version),
                **{name: getattr(version, name) for name in _PROMPT_FIELDS},
            )
        )
        self._session.flush()
        self._add_criteria(version)
        self._session.flush()

    def save_prompt_version(self, version: PromptVersion, *, expected_revision: int) -> bool:
        values = {name: getattr(version, name) for name in _PROMPT_FIELDS}
        values["status"] = version.status.value
        values["layers"] = self._layers_json(version)
        result = self._session.execute(
            sa.update(PromptVersionRow)
            .where(
                PromptVersionRow.id == version.id, PromptVersionRow.revision == expected_revision
            )
            .values(**values)
        )
        if result.rowcount != 1:
            return False
        # Los criterios solo se reescriben si cambiaron (es decir, en un borrador):
        # los de una versión aprobada conservan sus filas y sus identificadores.
        if self._criteria(version.id) != version.criteria:
            self._session.execute(
                sa.delete(RubricCriterionRow).where(
                    RubricCriterionRow.prompt_version_id == version.id
                )
            )
            self._session.flush()
            self._add_criteria(version)
            self._session.flush()
        return True
