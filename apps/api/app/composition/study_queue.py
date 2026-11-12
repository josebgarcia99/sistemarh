"""Lista de trabajo del analista de estudios socioeconómicos.

Consulta de solo lectura que cruza postulaciones, candidatos, vacantes y
estudios. Devuelve lo mínimo para ubicar a la persona y abrir su estudio: no
incluye el CV, la evaluación de la IA ni ningún otro dato del expediente.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.modules.assessments.infrastructure.orm import AssessmentRow
from app.modules.recruitment.infrastructure.orm import ApplicationRow, CandidateRow
from app.modules.vacancies.infrastructure.orm import VacancyRow

MAX_ITEMS = 300
_STUDY = "ESTUDIO_SOCIOECONOMICO"


@dataclass(frozen=True)
class StudyQueueItem:
    application_id: uuid.UUID
    vacancy_id: uuid.UUID
    candidate_name: str
    vacancy_name: str
    # La postulación sigue en proceso: solo entonces se puede registrar un estudio nuevo.
    active: bool
    # Estado del estudio más reciente que no esté anulado, si lo hay.
    study_status: str | None
    study_updated_at: datetime | None


class SqlStudyQueue:
    def __init__(self, session: Session) -> None:
        self._session = session

    def items(self, search: str | None = None) -> list[StudyQueueItem]:
        """Postulaciones en proceso y las que ya tienen un estudio, de cualquier
        vacante. Primero las de estudio más reciente; después, las que no tienen."""
        study = (
            sa.select(
                AssessmentRow.application_id,
                AssessmentRow.status,
                AssessmentRow.updated_at,
                sa.func.row_number()
                .over(
                    partition_by=AssessmentRow.application_id,
                    order_by=AssessmentRow.updated_at.desc(),
                )
                .label("position"),
            )
            .where(AssessmentRow.kind == _STUDY, AssessmentRow.status != "ANULADO")
            .subquery()
        )
        query = (
            sa.select(
                ApplicationRow.id,
                ApplicationRow.vacancy_id,
                CandidateRow.full_name,
                VacancyRow.name,
                ApplicationRow.status,
                study.c.status,
                study.c.updated_at,
            )
            .join(CandidateRow, CandidateRow.id == ApplicationRow.candidate_id)
            .join(VacancyRow, VacancyRow.id == ApplicationRow.vacancy_id)
            .outerjoin(
                study, sa.and_(study.c.application_id == ApplicationRow.id, study.c.position == 1)
            )
            .where(sa.or_(ApplicationRow.status == "ACTIVA", study.c.status.is_not(None)))
        )
        text = " ".join((search or "").split())[:100]
        if text:
            escaped = text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            pattern = f"%{escaped}%"
            query = query.where(
                sa.or_(
                    CandidateRow.full_name.ilike(pattern, escape="\\"),
                    VacancyRow.name.ilike(pattern, escape="\\"),
                )
            )
        rows = self._session.execute(
            query.order_by(
                sa.case((study.c.updated_at.is_(None), 1), else_=0),
                study.c.updated_at.desc(),
                CandidateRow.full_name,
            ).limit(MAX_ITEMS)
        )
        return [
            StudyQueueItem(
                application_id=row[0],
                vacancy_id=row[1],
                candidate_name=row[2],
                vacancy_name=row[3],
                active=row[4] == "ACTIVA",
                study_status=row[5],
                study_updated_at=row[6],
            )
            for row in rows
        ]
