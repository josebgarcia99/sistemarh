"""Tableros, históricos y reportes.

Permisos: un administrador ve todas las vacantes; cualquier otra persona, solo
las suyas y las que tiene compartidas **hoy**. Esa regla se aplica al leer los
datos, así que vale igual para un tablero, para un histórico de hace dos años
y para un Excel. El uso de IA, los errores técnicos y el reparto por persona
solo se entregan a administradores.

Un Excel ya generado se puede volver a descargar mientras quien lo pidió siga
viendo todas las vacantes que contiene; si perdió alguna, debe generarlo de
nuevo.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, tzinfo
from typing import BinaryIO

from app.core.exceptions.errors import (
    NotFoundError,
    PermissionDeniedError,
    ServiceUnavailableError,
    ValidationFailedError,
)
from app.core.ids import new_sequential_uuid
from app.modules.audit.application.service import AuditLog
from app.modules.audit.domain.models import AuditAction
from app.modules.reporting.application import workbooks
from app.modules.reporting.domain import metrics
from app.modules.reporting.domain.models import (
    IN_PROCESS,
    OUTCOMES,
    DateKind,
    ExportKind,
    Facts,
    FilterOptions,
    Option,
    ReportExport,
    ReportFilter,
    ReportingSource,
    ReportStore,
    VacancySelection,
    Viewer,
)

MAX_PAGE = 200
MAX_EXPORT_ROWS = 50_000
RECENT_EXPORTS = 30
_CLASSIFICATIONS = ("ACEPTADO_IA", "RECHAZADO_IA", "NO_EVALUABLE")
_DATE_KIND_LABELS = {
    DateKind.CARGA: "Carga del CV",
    DateKind.EVALUACION: "Evaluación del CV",
    DateKind.MOVIMIENTO: "Movimiento",
    DateKind.CIERRE: "Cierre",
}


@dataclass(frozen=True)
class HistoryPage:
    rows: list[metrics.HistoryRow]
    total: int


class ReportingService:
    def __init__(
        self,
        source: ReportingSource,
        store: ReportStore | None,
        audit: AuditLog,
        clock: Callable[[], datetime],
        zone: tzinfo,
    ) -> None:
        self._source = source
        self._store = store
        self._audit = audit
        self._clock = clock
        self._zone = zone

    # --- Filtros y permisos --------------------------------------------------------------

    @staticmethod
    def _selection(viewer: Viewer, flt: ReportFilter) -> VacancySelection:
        return VacancySelection(
            visible_to=None if viewer.is_admin else viewer.user_id,
            vacancy_id=flt.vacancy_id,
            owner_id=flt.owner_id,
            collaborator_id=flt.collaborator_id,
            department=(flt.department or "").strip() or None,
            status=flt.vacancy_status,
        )

    def _period(self, flt: ReportFilter) -> metrics.Period:
        if flt.date_from and flt.date_to and flt.date_from > flt.date_to:
            raise ValidationFailedError("La fecha inicial no puede ser posterior a la final.")
        return metrics.period_of(flt.date_from, flt.date_to, self._zone)

    @staticmethod
    def _check(flt: ReportFilter) -> None:
        if flt.ai_classification and flt.ai_classification not in _CLASSIFICATIONS:
            raise ValidationFailedError("La clasificación de la IA no es válida.")
        if flt.outcome and flt.outcome not in (IN_PROCESS, *OUTCOMES):
            raise ValidationFailedError("El resultado final no es válido.")
        if (
            flt.score_min is not None
            and flt.score_max is not None
            and flt.score_min > flt.score_max
        ):
            raise ValidationFailedError("La calificación mínima no puede superar a la máxima.")

    def _facts(
        self, viewer: Viewer, selection: VacancySelection, period: metrics.Period, *, ai: bool
    ) -> Facts:
        return Facts(
            vacancies=self._source.vacancies(selection),
            stages=self._source.stages(),
            applications=self._source.applications(selection),
            movements=self._source.movements(selection),
            outcomes=self._source.outcomes(selection),
            cvs=self._source.cvs(selection),
            ai=self._source.ai_executions(period.start, period.end, selection)
            if ai and viewer.is_admin
            else [],
        )

    # --- Consultas -----------------------------------------------------------------------

    def overview(self, viewer: Viewer, flt: ReportFilter) -> metrics.Overview:
        period = self._period(flt)
        facts = self._facts(viewer, self._selection(viewer, flt), period, ai=True)
        return metrics.overview(facts, period, viewer, zone=self._zone)

    def _history(self, viewer: Viewer, flt: ReportFilter) -> tuple[list[metrics.HistoryRow], Facts]:
        self._check(flt)
        period = self._period(flt)
        selection = self._selection(viewer, flt)
        facts = self._facts(viewer, selection, period, ai=False)
        with_bank = (
            self._source.applications_with_bank(selection, flt.bank_id)
            if flt.bank_id is not None
            else None
        )
        return metrics.history(facts, flt, period, with_bank=with_bank), facts

    def history(
        self, viewer: Viewer, flt: ReportFilter, *, limit: int = 50, offset: int = 0
    ) -> HistoryPage:
        rows, _ = self._history(viewer, flt)
        limit = max(1, min(limit, MAX_PAGE))
        offset = max(0, offset)
        return HistoryPage(rows[offset : offset + limit], len(rows))

    def options(self, viewer: Viewer) -> FilterOptions:
        return self._source.options(self._selection(viewer, ReportFilter()))

    # --- Reportes en Excel ---------------------------------------------------------------

    def _labels(self, viewer: Viewer, flt: ReportFilter, kind: ExportKind) -> dict[str, str]:
        """Los filtros pedidos, con nombres legibles, para dejarlos en el Excel."""
        options = None
        labels: dict[str, str] = {}

        def named(items: list[Option], value: uuid.UUID) -> str:
            # Solo se nombran cosas que quien consulta puede ver.
            return next((item.name for item in items if item.id == str(value)), str(value))

        if flt.date_from:
            labels["Desde"] = flt.date_from.isoformat()
        if flt.date_to:
            labels["Hasta"] = flt.date_to.isoformat()
        if any(
            (flt.vacancy_id, flt.owner_id, flt.collaborator_id, flt.prompt_version_id, flt.bank_id)
        ):
            options = self.options(viewer)
        if flt.vacancy_id and options:
            labels["Vacante"] = named(options.vacancies, flt.vacancy_id)
        if flt.owner_id and options:
            labels["Responsable"] = named(options.owners, flt.owner_id)
        if flt.collaborator_id and options:
            labels["Colaborador"] = named(options.collaborators, flt.collaborator_id)
        if flt.department:
            labels["Departamento"] = flt.department
        if flt.vacancy_status:
            labels["Estado de la vacante"] = workbooks.VACANCY_STATUS_LABELS.get(
                flt.vacancy_status, flt.vacancy_status
            )
        if kind is ExportKind.POSTULACIONES:
            if flt.date_from or flt.date_to:
                labels["Fecha que se compara"] = _DATE_KIND_LABELS[flt.date_kind]
            if flt.stage:
                labels["Etapa"] = flt.stage
            if flt.candidate:
                labels["Candidato"] = flt.candidate
            if flt.ai_classification:
                labels["Clasificación de la IA"] = workbooks.CLASSIFICATION_LABELS[
                    flt.ai_classification
                ]
            if flt.score_min is not None:
                labels["Calificación mínima"] = str(flt.score_min)
            if flt.score_max is not None:
                labels["Calificación máxima"] = str(flt.score_max)
            if flt.model:
                labels["Modelo"] = flt.model
            if flt.prompt_version_id and options:
                labels["Versión del prompt"] = named(options.prompt_versions, flt.prompt_version_id)
            if flt.bank_id and options:
                labels["Banco de preguntas"] = named(options.banks, flt.bank_id)
            if flt.outcome:
                labels["Resultado final"] = workbooks.OUTCOME_LABELS[flt.outcome]
        return labels

    def create_export(
        self,
        viewer: Viewer,
        viewer_name: str,
        kind: ExportKind,
        flt: ReportFilter,
        *,
        ip: str | None = None,
    ) -> ReportExport:
        if self._store is None:
            raise ServiceUnavailableError(
                "El almacenamiento documental no está configurado. Define RECLU_STORAGE_ROOT."
            )
        now = self._clock()
        labels = self._labels(viewer, flt, kind)
        common = {
            "generated_at": now,
            "generated_by": viewer_name,
            "filters": labels,
            "zone": self._zone,
        }
        if kind is ExportKind.INDICADORES:
            data = self.overview(viewer, flt)
            vacancy_ids = [row.id for row in data.vacancies]
            row_count = len(vacancy_ids)

            def write(target: BinaryIO) -> None:
                workbooks.build_overview(target, data, **common)

            prefix = "Indicadores"
        else:
            rows, facts = self._history(viewer, flt)
            if len(rows) > MAX_EXPORT_ROWS:
                raise ValidationFailedError(
                    f"El reporte tendría más de {MAX_EXPORT_ROWS} postulaciones. "
                    "Acota el periodo o los filtros."
                )
            # Contiene datos de todas las vacantes consultadas, tengan o no filas.
            vacancy_ids = [vacancy.id for vacancy in facts.vacancies]
            row_count = len(rows)

            def write(target: BinaryIO) -> None:
                workbooks.build_history(target, rows, **common)

            prefix = "Postulaciones"
        export_id = new_sequential_uuid()
        stored = self._store.save(export_id, write)
        export = ReportExport(
            id=export_id,
            kind=kind,
            name=f"{prefix}_{now.astimezone(self._zone):%Y%m%d_%H%M}.xlsx",
            filters=labels,
            vacancy_ids=vacancy_ids,
            row_count=row_count,
            storage_key=stored.key,
            size_bytes=stored.size_bytes,
            sha256=stored.sha256,
            created_at=now,
            created_by=viewer.user_id,
        )
        self._source.add_export(export)
        self._audit.record(
            AuditAction.REPORTE_GENERADO,
            actor_user_id=viewer.user_id,
            resource_type="reporte",
            resource_id=export.id,
            ip=ip,
            details={
                "tipo": kind.value,
                "filas": row_count,
                "vacantes": len(vacancy_ids),
                "sha256": stored.sha256,
            },
        )
        return export

    def exports(self, viewer: Viewer) -> list[ReportExport]:
        return self._source.exports_of(viewer.user_id, RECENT_EXPORTS)

    def prepare_download(
        self, viewer: Viewer, export_id: uuid.UUID, *, ip: str | None = None
    ) -> ReportExport:
        """Comprueba que quien pide el archivo puede verlo hoy y deja constancia."""
        export = self._source.export(export_id)
        # De otra persona: se responde igual que si no existiera.
        if export is None or (export.created_by != viewer.user_id and not viewer.is_admin):
            raise NotFoundError("El reporte no existe.")
        if not viewer.is_admin:
            visible = {
                vacancy.id
                for vacancy in self._source.vacancies(VacancySelection(visible_to=viewer.user_id))
            }
            if not set(export.vacancy_ids) <= visible:
                raise PermissionDeniedError(
                    "Este reporte incluye vacantes a las que ya no tienes acceso. Genera uno nuevo."
                )
        if self._store is None or not self._store.exists(export.storage_key):
            raise ServiceUnavailableError(
                "El archivo del reporte no está disponible en el almacenamiento. "
                "Genera uno nuevo o avisa a Sistemas."
            )
        self._audit.record(
            AuditAction.REPORTE_DESCARGADO,
            actor_user_id=viewer.user_id,
            resource_type="reporte",
            resource_id=export.id,
            ip=ip,
            details={"tipo": export.kind.value},
        )
        return export
