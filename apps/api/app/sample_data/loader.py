"""Carga los datos de prueba: una vacante ficticia con personas en cada etapa.

Usa los mismos servicios que las pantallas (permisos, validaciones y auditoría
incluidos), con una persona real del sistema como responsable. Todo ocurre en
una sola transacción: si algo falla, la base queda como estaba.

No se puede deshacer desde el sistema (ni vacantes ni candidatos se borran):
por eso se niega a correr en producción salvo autorización expresa.
"""

from __future__ import annotations

import io
import uuid
import zipfile
from dataclasses import dataclass, field, fields
from typing import Any

from app.composition.backend import Repositories
from app.composition.context import AppContext
from app.core.config.settings import Environment
from app.core.exceptions.errors import AppError, ConflictError, ValidationFailedError
from app.modules.assessments.domain.models import Kind
from app.modules.cv_processing.application.service import StepOutcome
from app.modules.file_management.domain.models import DocumentType, FileStatus
from app.modules.recruitment.domain.models import OutcomeKind
from app.modules.users.domain.models import Role, User
from app.modules.vacancies.application.service import VacancyData
from app.modules.vacancies.domain.models import Scope, VacancyStatus, WorkMode
from app.sample_data import content
from app.sample_data.sample_ai import SampleAi

_WORD_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


@dataclass(frozen=True)
class _SampleContext(AppContext):
    """El mismo contexto, con los textos de ejemplo en lugar de la IA."""

    def ai_settings(self, repos: Repositories):  # type: ignore[no-untyped-def, override]  # noqa: ANN201
        return SampleAi()


@dataclass
class Summary:
    vacancy_id: uuid.UUID
    people: dict[str, str] = field(default_factory=dict)  # nombre -> dónde quedó
    warnings: list[str] = field(default_factory=list)


def _docx(lines: list[str]) -> bytes:
    body = "".join(f"<w:p><w:r><w:t>{line}</w:t></w:r></w:p>" for line in lines)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            "[Content_Types].xml",
            '<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/'
            'content-types"><Default Extension="xml" ContentType="application/xml"/></Types>',
        )
        archive.writestr(
            "word/document.xml",
            f'<?xml version="1.0" encoding="UTF-8"?><w:document xmlns:w="{_WORD_NS}">'
            f"<w:body>{body}</w:body></w:document>",
        )
    return buffer.getvalue()


def _blank_pdf() -> bytes:
    """PDF de una página sin texto, como un CV escaneado."""
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] >>",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for number, item in enumerate(objects, start=1):
        offsets.append(len(out))
        out += str(number).encode() + b" 0 obj\n" + item + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 4\n0000000000 65535 f \n"
    for offset in offsets:
        out += f"{offset:010d} 00000 n \n".encode()
    out += b"trailer\n<< /Size 4 /Root 1 0 R >>\nstartxref\n" + str(xref).encode() + b"\n%%EOF\n"
    return bytes(out)


def load(context: AppContext, owner_email: str, *, allow_production: bool = False) -> Summary:
    if context.settings.environment is Environment.PRODUCTION and not allow_production:
        raise ConflictError(
            "Este entorno está configurado como producción. Los datos de prueba no se pueden "
            "borrar después: cárgalos en un entorno de pruebas, o repite el comando con "
            "--allow-production si este servidor todavía no tiene datos reales."
        )
    sample = _SampleContext(**{item.name: getattr(context, item.name) for item in fields(context)})
    with sample.require_backend().transaction() as repos:
        return _Loader(sample, repos, owner_email).run()


class _Loader:
    def __init__(self, context: AppContext, repos: Repositories, owner_email: str) -> None:
        self._context = context
        self._repos = repos
        owner = repos.users.get_by_email(owner_email.strip().lower())
        if owner is None or not owner.is_active:
            raise ValidationFailedError("No hay un usuario activo con ese correo.")
        if owner.role not in (Role.ADMINISTRADOR, Role.RECLUTADOR):
            raise ValidationFailedError(
                "El responsable de la vacante de prueba debe ser administrador o reclutador."
            )
        self._owner: User = owner
        self._summary: Summary | None = None

    # --- Pasos ---------------------------------------------------------------------------

    def run(self) -> Summary:
        vacancy_id = self._vacancy()
        self._summary = Summary(vacancy_id)
        self._profile_and_prompt(vacancy_id)
        self._upload_cvs(vacancy_id)
        self._evaluate(vacancy_id)
        self._advance(vacancy_id)
        return self._summary

    def _vacancy(self) -> uuid.UUID:
        vacancies = self._context.vacancy_service(self._repos)
        existing, _ = vacancies.list(
            self._owner,
            scope=Scope.MINE,
            status=None,
            search=content.VACANCY_NAME,
            page=1,
            page_size=5,
        )
        if any(view.vacancy.name == content.VACANCY_NAME for view in existing):
            raise ConflictError(
                f"Esa persona ya tiene la vacante «{content.VACANCY_NAME}». No se cargó otra vez."
            )
        vacancy = vacancies.create(
            self._owner,
            VacancyData(
                name=content.VACANCY_NAME,
                department="Finanzas",
                location="Monterrey",
                work_mode=WorkMode.HIBRIDA,
                contract_type="Tiempo completo",
                description="Vacante ficticia para conocer el sistema. Todas las personas, "
                "empresas y resultados son inventados, y los textos de IA son ejemplos fijos.",
                positions=2,
            ),
        ).vacancy
        vacancies.change_status(
            self._owner, vacancy.id, VacancyStatus.ABIERTA, expected_version=vacancy.version
        )
        return vacancy.id

    def _profile_and_prompt(self, vacancy_id: uuid.UUID) -> None:
        setup = self._context.evaluation_setup(self._repos)
        setup.save_profile(
            self._owner, vacancy_id, dict(content.PROFILE), change_note=None, expected_version=0
        )
        draft = setup.generate(self._owner, vacancy_id)
        review = setup.submit(self._owner, draft.id, expected_revision=draft.revision)
        setup.approve(self._owner, review.id, expected_revision=review.revision)

    def _upload_cvs(self, vacancy_id: uuid.UUID) -> None:
        files = self._context.file_service(self._repos)
        pipeline = self._context.upload_pipeline()
        uploads = [
            (f"CV {person.name}.docx", _docx(person.cv_lines(number)))
            for number, person in enumerate(content.PEOPLE, start=1)
        ]
        uploads.append((content.SCANNED_CV, _blank_pdf()))
        for name, data in uploads:
            asset = files.begin_upload(
                self._owner,
                vacancy_id=vacancy_id,
                document_type=DocumentType.CV,
                original_name=name,
                declared_size=len(data),
            )
            receiver = pipeline.receiver(asset)
            receiver.write(data)
            receiver.close()
            outcome = pipeline.store(asset, receiver)
            files.finish_upload(self._owner, asset.id, outcome)
            if outcome.status is not FileStatus.CONFIRMADO:
                raise ConflictError(f"No se pudo guardar «{name}» en el almacenamiento.")

    def _evaluate(self, vacancy_id: uuid.UUID) -> None:
        """Lo mismo que el trabajo en segundo plano, pero dentro de esta transacción."""
        batches = self._context.cv_batches(self._repos)
        batch = batches.create(self._owner, vacancy_id)
        token = uuid.uuid4().hex
        if not batches.claim(batch.id, token):
            raise ConflictError("No se pudo iniciar la evaluación de los CV de prueba.")
        for _ in range(len(content.PEOPLE) * 4 + 8):
            outcome = batches.process_next(batch.id, token)
            if outcome is StepOutcome.NO_MORE:
                break
            if outcome is not StepOutcome.PROCESSED:
                raise ConflictError("La evaluación de los CV de prueba se detuvo.")
        else:
            raise ConflictError("La evaluación de los CV de prueba no terminó.")
        batches.finalize(batch.id, token)
        self._context.recruitment(self._repos).sync_evaluated(vacancy_id)

    # --- Personas ------------------------------------------------------------------------

    def _advance(self, vacancy_id: uuid.UUID) -> None:
        recruitment = self._context.recruitment(self._repos)
        board = recruitment.board(self._owner, vacancy_id)
        if board.pipeline is None:
            raise ConflictError("La vacante de prueba quedó sin proceso de etapas.")
        stages = sorted(board.pipeline.stages, key=lambda stage: stage.position)
        by_name = {view.candidate.full_name: view.application for view in board.applications}
        bank = self._context.phone_calls(self._repos).create_bank(
            self._owner,
            name=content.BANK_NAME,
            description="Banco ficticio de los datos de prueba.",
            shared=False,
            questions=[
                {"text": text, "competency": competency, "guidance": guidance}
                for text, competency, guidance, _ in content.BANK
            ],
        )
        assert self._summary is not None
        for number, person in enumerate(content.PEOPLE, start=1):
            application = by_name.get(person.name)
            if application is None:
                self._summary.warnings.append(f"{person.name}: su CV no quedó como postulación.")
                continue
            recruitment.update_candidate(
                self._owner,
                application.id,
                full_name=person.name,
                email=person.email,
                phone=person.phone(number),
            )
            current = next(stage for stage in stages if stage.id == application.stage_id)
            target = next((stage for stage in stages if stage.kind.value == person.stage), None)
            reached = current.name
            if target is not None:
                for stage in stages:
                    if not current.position < stage.position <= target.position:
                        continue
                    note = None
                    if person.level < 3 and stage.position == current.position + 1:
                        note = (
                            "La IA lo clasificó como rechazado por poca experiencia. Recursos "
                            "Humanos decide llamarlo: vive cerca y puede empezar de inmediato."
                        )
                    recruitment.move(self._owner, vacancy_id, [application.id], stage.id, note=note)
                    reached = stage.name
                    final = stage.id == target.id
                    self._guarded(
                        person.name,
                        lambda s=stage, f=final, p=person, a=application: self._records(
                            a.id, s.kind.value, p, bank.bank.id, last=f
                        ),
                    )
            if person.stage in ("PRUEBA_TECNICA", "ESTUDIO_SOCIOECONOMICO", "RESULTADO"):
                self._guarded(
                    person.name,
                    lambda a=application: self._context.assessments(self._repos).synthesize(
                        self._owner, a.id
                    ),
                )
            if person.outcome:
                kind, reason = person.outcome
                recruitment.record_outcome(
                    self._owner, application.id, OutcomeKind(kind), reason=reason or None
                )
                reached += f" · {kind.replace('_', ' ').capitalize()}"
            self._summary.people[person.name] = reached

    def _guarded(self, who: str, action: Any) -> None:
        """Un registro secundario que falla no detiene la carga: se avisa y se sigue."""
        try:
            action()
        except AppError as error:
            assert self._summary is not None
            self._summary.warnings.append(f"{who}: {error.detail}")

    def _records(
        self,
        application_id: uuid.UUID,
        stage: str,
        person: content.Person,
        bank_id: uuid.UUID,
        *,
        last: bool,
    ) -> None:
        """Lo que se registra al llegar a una etapa. Si la persona se queda en ella
        (``last``), el registro queda a medias, como en un proceso en curso."""
        assessments = self._context.assessments(self._repos)
        owner = self._owner
        pending = last and person.outcome is None
        if stage == "LLAMADA":
            self._call(application_id, bank_id, finished=not pending or person.level < 3)
        elif stage == "PSICOMETRIA":
            data = dict(content.PSYCHOMETRIC)
            assessments.create(
                owner,
                application_id,
                Kind.PSICOMETRIA,
                status="PENDIENTE" if pending else "VALIDADA",
                data={"instrument": data["instrument"]} if pending else data,
            )
        elif stage == "ENTREVISTA":
            if pending:
                data: dict[str, Any] = {"interviewer": content.INTERVIEW["interviewer"]}
                assessments.create(
                    owner, application_id, Kind.ENTREVISTA, status="PROGRAMADA", data=data
                )
            else:
                done = assessments.create(
                    owner,
                    application_id,
                    Kind.ENTREVISTA,
                    status="REALIZADA",
                    data=dict(content.INTERVIEW),
                )
                assessments.summarize(owner, done.id)
        elif stage == "PRUEBA_TECNICA":
            rubric = [
                {
                    "criterion": criterion,
                    "max_points": maximum,
                    "points": None if pending else points,
                }
                for criterion, maximum, points in content.TECHNICAL_RUBRIC
            ]
            if pending:
                assessments.create(
                    owner,
                    application_id,
                    Kind.PRUEBA_TECNICA,
                    status="PENDIENTE",
                    data={
                        "test_type": content.TECHNICAL["test_type"],
                        "competency": content.TECHNICAL["competency"],
                        "pass_mark": content.TECHNICAL["pass_mark"],
                        "rubric": rubric,
                    },
                )
            else:
                done = assessments.create(
                    owner,
                    application_id,
                    Kind.PRUEBA_TECNICA,
                    status="REALIZADA",
                    data={**content.TECHNICAL, "rubric": rubric},
                )
                assessments.summarize(owner, done.id)
        elif stage == "ESTUDIO_SOCIOECONOMICO":
            references = assessments.create(
                owner,
                application_id,
                Kind.REFERENCIAS,
                status="COMPLETADO",
                data={
                    "references": content.REFERENCES,
                    "notes": "Referencias inventadas de los datos de prueba.",
                },
            )
            assessments.summarize(owner, references.id)
            template = next(
                (item for item, _ in assessments.templates() if item.status == "ACTIVA"), None
            )
            if template is None:
                raise ValidationFailedError("No hay un formulario activo para el estudio.")
            version = next(v for item, v in assessments.templates() if item.id == template.id)
            answers = {
                item.id: {"value": content.STUDY_ANSWERS[item.label]}
                for item in version.fields
                if item.label in content.STUDY_ANSWERS
            }
            if "Nombre completo" in content.STUDY_ANSWERS:
                for item in version.fields:
                    if item.label == "Nombre completo":
                        answers[item.id] = {"value": person.name}
            assessments.create(
                owner,
                application_id,
                Kind.ESTUDIO_SOCIOECONOMICO,
                status="EN_PROCESO" if last else "COMPLETADO",
                data={
                    "performed_by": "Analista de estudios (datos de prueba)",
                    "notes": "Estudio inventado de los datos de prueba.",
                    "answers": answers,
                },
                template_id=template.id,
            )

    def _call(self, application_id: uuid.UUID, bank_id: uuid.UUID, *, finished: bool) -> None:
        calls = self._context.phone_calls(self._repos)
        view = calls.open_call(self._owner, application_id, bank_id)
        examples = {text: answer for text, _, _, answer in content.BANK}
        answers = []
        for position, question in enumerate(view.questions):
            example = examples.get(question.text)
            if example is None:
                # Una pregunta general de la empresa: aquí no hay respuesta inventada.
                if finished:
                    answers.append({"question_id": question.id, "not_asked": True})
            elif finished or position < len(view.questions) - 2:
                answers.append({"question_id": question.id, "answer": example})
        calls.save_call(
            self._owner,
            view.call.id,
            answers=answers,
            notes="Llamada inventada de los datos de prueba.",
            called_at=None,
            close=finished,
        )
        if finished:
            calls.analyze_call(self._owner, view.call.id)
