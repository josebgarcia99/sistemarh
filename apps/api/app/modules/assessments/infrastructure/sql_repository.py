"""Repositorio de evaluaciones posteriores sobre SQL Server (SQLAlchemy)."""

from __future__ import annotations

import json
import uuid
from decimal import Decimal

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.modules.assessments.domain.models import (
    Assessment,
    FieldType,
    FormField,
    FormSection,
    FormTemplate,
    FormTemplateVersion,
    Kind,
    Synthesis,
)
from app.modules.assessments.infrastructure.orm import (
    ApplicationSynthesisRow,
    AssessmentRow,
    FormTemplateRow,
    FormTemplateVersionRow,
)

_PLAIN = (
    "application_id",
    "vacancy_id",
    "status",
    "event_date",
    "file_id",
    "template_version_id",
    "score",
    "ai_summary_at",
    "ai_summary_by",
    "version",
    "created_at",
    "created_by",
    "updated_at",
    "updated_by",
)


def _dumps(value: object) -> str:
    return json.dumps(value, ensure_ascii=False)


def _values(item: Assessment) -> dict[str, object]:
    values = {name: getattr(item, name) for name in _PLAIN}
    values["kind"] = item.kind.value
    values["data"] = _dumps(item.data)
    values["ai_summary"] = _dumps(item.ai_summary) if item.ai_summary is not None else None
    return values


def _to_assessment(row: AssessmentRow) -> Assessment:
    values = {name: getattr(row, name) for name in _PLAIN}
    return Assessment(
        id=row.id,
        kind=Kind(row.kind),
        data=json.loads(row.data),
        ai_summary=json.loads(row.ai_summary) if row.ai_summary else None,
        **values,
    )


def _decimal(value: object) -> Decimal | None:
    return Decimal(str(value)) if value is not None else None


def _to_version(row: FormTemplateVersionRow) -> FormTemplateVersion:
    return FormTemplateVersion(
        id=row.id,
        template_id=row.template_id,
        version_number=row.version_number,
        sections=tuple(
            FormSection(
                title=section["title"],
                fields=tuple(
                    FormField(
                        id=item["id"],
                        label=item["label"],
                        type=FieldType(item["type"]),
                        required=item.get("required", False),
                        options=tuple(item.get("options", ())),
                        minimum=_decimal(item.get("minimum")),
                        maximum=_decimal(item.get("maximum")),
                    )
                    for item in section["fields"]
                ),
            )
            for section in json.loads(row.sections)
        ),
        created_at=row.created_at,
        created_by=row.created_by,
    )


def sections_json(version: FormTemplateVersion) -> str:
    return _dumps(
        [
            {
                "title": section.title,
                "fields": [
                    {
                        "id": item.id,
                        "label": item.label,
                        "type": item.type.value,
                        "required": item.required,
                        "options": list(item.options),
                        "minimum": str(item.minimum) if item.minimum is not None else None,
                        "maximum": str(item.maximum) if item.maximum is not None else None,
                    }
                    for item in section.fields
                ],
            }
            for section in version.sections
        ]
    )


def _to_template(row: FormTemplateRow) -> FormTemplate:
    return FormTemplate(
        id=row.id,
        name=row.name,
        description=row.description,
        status=row.status,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


class SqlAssessmentRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    # --- Evaluaciones --------------------------------------------------------------------

    def get(self, assessment_id: uuid.UUID) -> Assessment | None:
        row = self._session.get(AssessmentRow, assessment_id)
        return _to_assessment(row) if row is not None else None

    def for_application(self, application_id: uuid.UUID) -> list[Assessment]:
        rows = self._session.execute(
            sa.select(AssessmentRow)
            .where(AssessmentRow.application_id == application_id)
            .order_by(AssessmentRow.created_at, AssessmentRow.id)
        ).scalars()
        return [_to_assessment(row) for row in rows]

    def add(self, assessment: Assessment) -> None:
        self._session.add(AssessmentRow(id=assessment.id, **_values(assessment)))
        self._session.flush()

    def save(self, assessment: Assessment, *, expected_version: int) -> bool:
        # La condición sobre la versión hace que dos guardados simultáneos no se pisen.
        result = self._session.execute(
            sa.update(AssessmentRow)
            .where(AssessmentRow.id == assessment.id, AssessmentRow.version == expected_version)
            .values(**_values(assessment))
            .execution_options(synchronize_session=False)
        )
        self._session.expire_all()
        return result.rowcount == 1

    # --- Plantillas de formulario --------------------------------------------------------

    def templates(self) -> list[FormTemplate]:
        rows = self._session.execute(
            sa.select(FormTemplateRow).order_by(FormTemplateRow.name, FormTemplateRow.id)
        ).scalars()
        return [_to_template(row) for row in rows]

    def template(self, template_id: uuid.UUID) -> FormTemplate | None:
        row = self._session.get(FormTemplateRow, template_id)
        return _to_template(row) if row is not None else None

    def add_template(self, template: FormTemplate) -> None:
        self._session.add(
            FormTemplateRow(
                id=template.id,
                name=template.name,
                description=template.description,
                status=template.status,
                created_at=template.created_at,
                updated_at=template.updated_at,
            )
        )
        self._session.flush()

    def save_template(self, template: FormTemplate) -> None:
        row = self._session.get(FormTemplateRow, template.id)
        if row is None:
            raise LookupError("La plantilla no existe.")
        row.name, row.description = template.name, template.description
        row.status, row.updated_at = template.status, template.updated_at
        self._session.flush()

    def template_versions(self, template_id: uuid.UUID) -> list[FormTemplateVersion]:
        rows = self._session.execute(
            sa.select(FormTemplateVersionRow)
            .where(FormTemplateVersionRow.template_id == template_id)
            .order_by(FormTemplateVersionRow.version_number.desc())
        ).scalars()
        return [_to_version(row) for row in rows]

    def template_version(self, version_id: uuid.UUID) -> FormTemplateVersion | None:
        row = self._session.get(FormTemplateVersionRow, version_id)
        return _to_version(row) if row is not None else None

    def add_template_version(self, version: FormTemplateVersion) -> None:
        self._session.add(
            FormTemplateVersionRow(
                id=version.id,
                template_id=version.template_id,
                version_number=version.version_number,
                sections=sections_json(version),
                created_at=version.created_at,
                created_by=version.created_by,
            )
        )
        self._session.flush()

    # --- Síntesis ------------------------------------------------------------------------

    def add_synthesis(self, synthesis: Synthesis) -> None:
        self._session.add(
            ApplicationSynthesisRow(
                id=synthesis.id,
                application_id=synthesis.application_id,
                vacancy_id=synthesis.vacancy_id,
                result=_dumps(synthesis.result),
                sources=_dumps(list(synthesis.sources)),
                includes_psychometrics=synthesis.includes_psychometrics,
                created_at=synthesis.created_at,
                created_by=synthesis.created_by,
            )
        )
        self._session.flush()

    def syntheses(self, application_id: uuid.UUID) -> list[Synthesis]:
        rows = self._session.execute(
            sa.select(ApplicationSynthesisRow)
            .where(ApplicationSynthesisRow.application_id == application_id)
            .order_by(ApplicationSynthesisRow.created_at.desc(), ApplicationSynthesisRow.id.desc())
        ).scalars()
        return [
            Synthesis(
                id=row.id,
                application_id=row.application_id,
                vacancy_id=row.vacancy_id,
                created_at=row.created_at,
                created_by=row.created_by,
                result=json.loads(row.result),
                includes_psychometrics=row.includes_psychometrics,
                sources=tuple(json.loads(row.sources)),
            )
            for row in rows
        ]
