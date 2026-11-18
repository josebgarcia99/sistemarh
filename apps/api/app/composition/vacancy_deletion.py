"""Eliminación definitiva de una vacante, con todo lo que contiene.

Es la única operación del sistema que borra datos de reclutamiento. La pidió el
responsable el 18 de noviembre de 2026, para poder quitar vacantes de prueba, y
la limitó a los administradores. Es irreversible: no hay papelera.

Qué se borra: la vacante, su perfil y sus prompts, los lotes de CV con sus
evaluaciones, las postulaciones con su historial, las llamadas, las evaluaciones
posteriores, las síntesis, los resultados finales, los documentos (registro y
archivo en el servidor), los permisos sobre la vacante y los candidatos que no
tengan postulación en otra vacante.

Qué se conserva: la auditoría (incluido el registro de la propia eliminación),
el consumo y costo de IA, que es historial contable y no guarda contenido, y los
reportes que ya se hubieran exportado.

Cruza todos los módulos, por eso vive en la composición y trabaja con las tablas
por su nombre.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

import sqlalchemy as sa
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.orm import Session

from app.core.exceptions.errors import (
    ConflictError,
    NotFoundError,
    PermissionDeniedError,
    ValidationFailedError,
)
from app.infrastructure.database.base import Base
from app.modules.audit.application.service import AuditLog
from app.modules.audit.domain.models import AuditAction
from app.modules.vacancies.domain.models import UserInfo

# Lotes de CV que todavía se están procesando.
_ACTIVE_BATCHES = ("PENDIENTE", "EN_COLA", "PROCESANDO")
# SQL Server admite 2100 parámetros por consulta.
_CHUNK = 500

_NO_PERMISSION = (
    "La base de datos todavía no permite eliminar vacantes. Sistemas debe ejecutar el "
    "script «permisos_eliminar_vacantes.sql» y después se puede volver a intentar. No se "
    "eliminó nada."
)


@dataclass(frozen=True)
class DeletionSummary:
    """Lo que contiene una vacante y se borraría con ella."""

    vacancy_id: uuid.UUID
    name: str
    status: str
    applications: int
    candidates: int  # los que no tienen postulación en otra vacante
    cv_files: int
    calls: int
    assessments: int
    syntheses: int
    documents: int
    # Lotes de CV en proceso: mientras haya, no se puede eliminar.
    active_batches: int

    def counts(self) -> dict[str, int]:
        return {
            "postulaciones": self.applications,
            "candidatos": self.candidates,
            "cv_evaluados": self.cv_files,
            "llamadas": self.calls,
            "evaluaciones": self.assessments,
            "sintesis": self.syntheses,
            "documentos": self.documents,
        }


def _table(name: str) -> sa.Table:
    return Base.metadata.tables[name]


def _chunks(values: Sequence[uuid.UUID]) -> Iterable[Sequence[uuid.UUID]]:
    for start in range(0, len(values), _CHUNK):
        yield values[start : start + _CHUNK]


class SqlVacancyPurge:
    """Las consultas: qué hay en una vacante y su borrado, en orden de dependencias."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def _count(self, table: str, condition: sa.ColumnElement[bool]) -> int:
        query = sa.select(sa.func.count()).select_from(_table(table)).where(condition)
        return int(self._session.execute(query).scalar_one())

    def _orphan_candidates(self, vacancy_id: uuid.UUID) -> list[uuid.UUID]:
        """Candidatos de la vacante que no tienen postulación en ninguna otra."""
        applications = _table("recruitment.applications")
        mine = sa.select(applications.c.candidate_id).where(applications.c.vacancy_id == vacancy_id)
        elsewhere = sa.select(applications.c.candidate_id).where(
            applications.c.vacancy_id != vacancy_id
        )
        query = mine.where(applications.c.candidate_id.not_in(elsewhere)).distinct()
        return list(self._session.execute(query).scalars())

    def summary(self, vacancy_id: uuid.UUID) -> DeletionSummary | None:
        vacancies = _table("vacancy.vacancies")
        row = self._session.execute(
            sa.select(vacancies.c.name, vacancies.c.status).where(vacancies.c.id == vacancy_id)
        ).first()
        if row is None:
            return None
        batches = _table("ai.cv_batches")
        items = _table("ai.cv_batch_items")
        own_batches = sa.select(batches.c.id).where(batches.c.vacancy_id == vacancy_id)

        def of_vacancy(table: str) -> int:
            return self._count(table, _table(table).c.vacancy_id == vacancy_id)

        return DeletionSummary(
            vacancy_id=vacancy_id,
            name=row.name,
            status=row.status,
            applications=of_vacancy("recruitment.applications"),
            candidates=len(self._orphan_candidates(vacancy_id)),
            cv_files=self._count("ai.cv_batch_items", items.c.batch_id.in_(own_batches)),
            calls=of_vacancy("recruitment.call_sessions"),
            assessments=of_vacancy("recruitment.assessments"),
            syntheses=of_vacancy("recruitment.application_syntheses"),
            documents=of_vacancy("files.file_assets"),
            active_batches=self._count(
                "ai.cv_batches",
                sa.and_(batches.c.vacancy_id == vacancy_id, batches.c.status.in_(_ACTIVE_BATCHES)),
            ),
        )

    def purge(self, vacancy_id: uuid.UUID) -> list[str]:
        """Borra la vacante y todo lo suyo. Devuelve las claves de los archivos que
        hay que quitar del almacenamiento cuando la transacción se confirme."""
        run = self._session.execute
        applications = _table("recruitment.applications")
        calls = _table("recruitment.call_sessions")
        batches = _table("ai.cv_batches")
        items = _table("ai.cv_batch_items")
        prompts = _table("ai.prompt_versions")
        files = _table("files.file_assets")
        candidates = _table("recruitment.candidates")

        own_applications = sa.select(applications.c.id).where(
            applications.c.vacancy_id == vacancy_id
        )
        own_calls = sa.select(calls.c.id).where(calls.c.vacancy_id == vacancy_id)
        own_batches = sa.select(batches.c.id).where(batches.c.vacancy_id == vacancy_id)
        own_items = sa.select(items.c.id).where(items.c.batch_id.in_(own_batches))
        own_prompts = sa.select(prompts.c.id).where(prompts.c.vacancy_id == vacancy_id)

        def drop(table: str, condition: sa.ColumnElement[bool] | None = None) -> None:
            target = _table(table)
            run(
                sa.delete(target).where(
                    target.c.vacancy_id == vacancy_id if condition is None else condition
                )
            )

        # Antes de borrar las postulaciones: a quién dejarán sin ninguna.
        orphans = self._orphan_candidates(vacancy_id)
        keys = list(
            run(sa.select(files.c.storage_key).where(files.c.vacancy_id == vacancy_id)).scalars()
        )

        # 1. Lo que cuelga de las postulaciones.
        bank_links = _table("recruitment.call_session_banks")
        drop("recruitment.call_session_banks", bank_links.c.call_id.in_(own_calls))
        drop("recruitment.call_sessions")
        drop("recruitment.assessments")
        drop("recruitment.application_syntheses")
        drop("recruitment.application_outcomes")
        movements = _table("recruitment.application_movements")
        drop("recruitment.application_movements", movements.c.application_id.in_(own_applications))
        # 2. Las postulaciones, los candidatos que quedan sin ninguna y las campañas.
        drop("recruitment.applications")
        for chunk in _chunks(orphans):
            run(sa.delete(candidates).where(candidates.c.id.in_(chunk)))
        drop("recruitment.campaigns")
        # 3. Los lotes de CV. Un CV repetido apunta a otro: se suelta ese vínculo antes.
        run(sa.update(items).where(items.c.duplicate_of.in_(own_items)).values(duplicate_of=None))
        drop("ai.cv_batch_items", items.c.batch_id.in_(own_batches))
        drop("ai.cv_batches")
        # 4. Los prompts (otros pueden haberse copiado de estos) y el perfil.
        run(
            sa.update(prompts)
            .where(prompts.c.duplicated_from.in_(own_prompts))
            .values(duplicated_from=None)
        )
        criteria = _table("ai.rubric_criteria")
        drop("ai.rubric_criteria", criteria.c.prompt_version_id.in_(own_prompts))
        drop("ai.prompt_versions")
        drop("vacancy.job_profile_versions")
        # 5. Los documentos, los permisos, el historial de responsables y la vacante.
        drop("files.file_assets")
        drop("vacancy.vacancy_ownership_history")
        drop("vacancy.vacancy_sensitive_grants")
        drop("vacancy.vacancy_members")
        vacancies = _table("vacancy.vacancies")
        drop("vacancy.vacancies", vacancies.c.id == vacancy_id)
        self._session.flush()
        self._session.expire_all()
        return keys


class VacancyDeletion:
    """La regla: solo un administrador, confirmando el nombre y sin lotes en proceso."""

    def __init__(self, purge: SqlVacancyPurge, audit: AuditLog) -> None:
        self._purge = purge
        self._audit = audit

    def _summary(self, actor: UserInfo, vacancy_id: uuid.UUID) -> DeletionSummary:
        if not actor.is_admin:
            raise PermissionDeniedError("Solo un administrador puede eliminar una vacante.")
        summary = self._purge.summary(vacancy_id)
        if summary is None:
            raise NotFoundError("La vacante no existe.")
        return summary

    def preview(self, actor: UserInfo, vacancy_id: uuid.UUID) -> DeletionSummary:
        """Lo que se borraría. No cambia nada."""
        return self._summary(actor, vacancy_id)

    def delete(
        self,
        actor: UserInfo,
        vacancy_id: uuid.UUID,
        *,
        confirm_name: str,
        ip: str | None = None,
    ) -> tuple[DeletionSummary, list[str]]:
        """Elimina la vacante. Devuelve lo que se borró y las claves de los archivos
        que hay que quitar del almacenamiento una vez confirmada la transacción."""
        summary = self._summary(actor, vacancy_id)
        typed = " ".join(confirm_name.split()).casefold()
        if typed != " ".join(summary.name.split()).casefold():
            raise ValidationFailedError(
                "El nombre escrito no coincide con el de la vacante. No se eliminó nada."
            )
        if summary.active_batches:
            raise ConflictError(
                "La vacante tiene CV en proceso. Espera a que termine el lote o cancélalo, "
                "y vuelve a intentarlo. No se eliminó nada."
            )
        try:
            keys = self._purge.purge(vacancy_id)
        except ProgrammingError as error:
            # SQL Server rechazó el borrado: al usuario de la aplicación le falta el
            # permiso. Cualquier otro fallo sigue su curso como error del servidor.
            raise ConflictError(_NO_PERMISSION) from error
        self._audit.record(
            AuditAction.VACANTE_ELIMINADA,
            actor_user_id=actor.id,
            resource_type="vacante",
            resource_id=vacancy_id,
            ip=ip,
            details={"nombre": summary.name, "estado": summary.status, **summary.counts()},
        )
        return summary, keys
