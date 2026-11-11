"""Conecta el reclutamiento y las llamadas con los CV evaluados, el perfil y la IA."""

from __future__ import annotations

import uuid

from app.modules.ai_settings.application.service import AiSettingsService
from app.modules.ai_settings.domain.models import Operation
from app.modules.cv_processing.domain.models import BatchItem, CvBatchRepository
from app.modules.evaluation_setup.domain.models import EvaluationSetupRepository
from app.modules.file_management.domain.models import DocumentType, FileRepository, FileStatus
from app.modules.phone_calls.domain.models import ApplicationRef, AssistantAnswer
from app.modules.recruitment.domain.models import (
    ApplicationStatus,
    EvaluatedCv,
    RecruitmentRepository,
)


class BatchEvaluatedCvs:
    """Los CV evaluados por lotes, como los ve el reclutamiento."""

    def __init__(self, batches: CvBatchRepository, files: FileRepository) -> None:
        self._batches = batches
        self._files = files

    def _evaluated(self, item: BatchItem) -> EvaluatedCv:
        asset = self._files.get(item.file_id)
        return EvaluatedCv(
            file_id=item.file_id,
            file_name=asset.original_name if asset else "CV",
            item_id=item.id,
            classification=item.classification.value if item.classification else "NO_EVALUABLE",
            score=item.score,
            extraction=item.extraction or {},
            result=item.result or {},
        )

    def first_evaluations(self, vacancy_id: uuid.UUID) -> list[EvaluatedCv]:
        first: dict[uuid.UUID, BatchItem] = {}
        for item in self._batches.evaluated_items(vacancy_id):
            first.setdefault(item.file_id, item)
        return [self._evaluated(item) for item in first.values()]

    def evaluation(self, item_id: uuid.UUID) -> EvaluatedCv | None:
        item = self._batches.get_item(item_id)
        return self._evaluated(item) if item is not None else None

    def is_cv_of(self, vacancy_id: uuid.UUID, file_id: uuid.UUID) -> bool:
        asset = self._files.get(file_id)
        return (
            asset is not None
            and asset.vacancy_id == vacancy_id
            and asset.status is FileStatus.CONFIRMADO
            and asset.document_type is DocumentType.CV
        )


def _profile_text(
    setup: EvaluationSetupRepository, vacancy_id: uuid.UUID
) -> tuple[str, tuple[str, ...]] | None:
    versions = setup.profile_versions(vacancy_id)
    if not versions:
        return None
    content = versions[0].content
    lines = [f"Objetivo: {content.objective}"]
    for label, items in (
        ("Requisitos indispensables", content.must_have),
        ("Requisitos deseables", content.nice_to_have),
        ("Funciones", content.functions),
        ("Conocimientos", content.knowledge),
        ("Habilidades", content.skills),
    ):
        if items:
            lines.append(f"{label}:")
            lines += [f"- {item}" for item in items]
    return "\n".join(lines), (*content.must_have, *content.nice_to_have)


class CallApplications:
    def __init__(
        self,
        recruitment: RecruitmentRepository,
        batches: CvBatchRepository,
        setup: EvaluationSetupRepository,
    ) -> None:
        self._recruitment = recruitment
        self._batches = batches
        self._setup = setup

    def get(self, application_id: uuid.UUID) -> ApplicationRef | None:
        application = self._recruitment.application(application_id)
        if application is None:
            return None
        candidate = self._recruitment.candidate(application.candidate_id)
        item = (
            self._batches.get_item(application.evaluation_item_id)
            if application.evaluation_item_id
            else None
        )
        profile = _profile_text(self._setup, application.vacancy_id)
        return ApplicationRef(
            id=application.id,
            vacancy_id=application.vacancy_id,
            active=application.status is ApplicationStatus.ACTIVA,
            candidate_name=candidate.full_name if candidate else "",
            cv=(item.extraction if item else None) or {},
            requirements=profile[1] if profile else (),
        )


class VacancyProfiles:
    def __init__(self, setup: EvaluationSetupRepository) -> None:
        self._setup = setup

    def summary(self, vacancy_id: uuid.UUID) -> str | None:
        profile = _profile_text(self._setup, vacancy_id)
        return profile[0] if profile else None


class CallAssistant:
    def __init__(self, ai: AiSettingsService) -> None:
        self._ai = ai

    def ask(
        self,
        operation: str,
        *,
        system: str,
        user: str,
        vacancy_id: uuid.UUID,
        actor_user_id: uuid.UUID,
        carries_document: bool,
    ) -> AssistantAnswer:
        result = self._ai.execute(
            Operation(operation),
            system=system,
            user=user,
            actor_user_id=actor_user_id,
            vacancy_id=vacancy_id,
            carries_document=carries_document,
        )
        return AssistantAnswer(
            ok=result.ok, text=result.text, complete=result.complete, error=result.error
        )
