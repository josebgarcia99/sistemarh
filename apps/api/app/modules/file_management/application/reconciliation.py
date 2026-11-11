"""Conciliación entre SQL Server y el disco de documentos.

Detecta y deja en un estado final lo que una interrupción pudo dejar a medias:

- Cargas atascadas en RECIBIENDO: pasan a FALLIDO y su temporal se limpia. Si
  el archivo ya había llegado a su ubicación definitiva, va a cuarentena.
- Archivos sin registro (huérfanos): van a cuarentena y al reporte. Nunca se
  borran solos.
- Registros CONFIRMADO sin archivo: incidente crítico; solo se reporta.
- Registros ELIMINADO cuyo archivo sigue en el disco: se termina el borrado.
- Verificación de SHA-256, completa o por muestreo.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from app.modules.audit.application.service import AuditLog
from app.modules.audit.domain.models import AuditAction, AuditResult
from app.modules.file_management.domain.models import FileRepository, FileStatus
from app.modules.file_management.domain.ports import FileStorage


@dataclass
class ReconciliationReport:
    stale_uploads_failed: int = 0
    temp_files_removed: int = 0
    orphans_quarantined: list[str] = field(default_factory=list)
    missing_files: list[uuid.UUID] = field(default_factory=list)
    size_mismatches: list[uuid.UUID] = field(default_factory=list)
    hash_mismatches: list[uuid.UUID] = field(default_factory=list)
    deleted_files_removed: int = 0
    confirmed_checked: int = 0
    hashes_verified: int = 0

    @property
    def consistent(self) -> bool:
        return not (
            self.orphans_quarantined
            or self.missing_files
            or self.size_mismatches
            or self.hash_mismatches
        )


class StorageReconciler:
    def __init__(
        self,
        files: FileRepository,
        storage: FileStorage,
        audit: AuditLog,
        clock: Callable[[], datetime],
        extra_known_keys: Callable[[], set[str]] | None = None,
    ) -> None:
        self._files = files
        self._storage = storage
        self._audit = audit
        self._clock = clock
        # Archivos del almacenamiento que lleva otro registro (los reportes).
        self._extra_known_keys = extra_known_keys

    def run(
        self,
        *,
        stale_after: timedelta = timedelta(hours=1),
        verify_hashes: int | None = 0,
        actor_user_id: uuid.UUID | None = None,
    ) -> ReconciliationReport:
        """``verify_hashes``: cuántos archivos confirmados recalcular (``None`` = todos)."""
        report = ReconciliationReport()
        now = self._clock()
        known_keys: set[str] = set(self._extra_known_keys() if self._extra_known_keys else ())
        in_progress: set[str] = set()

        for asset in self._files.list_by_status(FileStatus.RECIBIENDO):
            if now - asset.created_at < stale_after:
                known_keys.add(asset.storage_key)
                in_progress.add(f"{asset.id}.part")
                continue
            self._storage.discard_temp(asset.id)
            if self._storage.exists(asset.storage_key):
                report.orphans_quarantined.append(self._storage.quarantine(asset.storage_key))
            asset.status = FileStatus.FALLIDO
            asset.failure_code = "carga_interrumpida"
            self._files.save(asset)
            report.stale_uploads_failed += 1

        for name, modified_at in self._storage.iter_temp():
            if name not in in_progress and now - modified_at >= stale_after:
                self._storage.discard_temp_by_name(name)
                report.temp_files_removed += 1

        for asset in self._files.list_by_status(FileStatus.ELIMINADO):
            if self._storage.delete(asset.storage_key):
                report.deleted_files_removed += 1

        confirmed = self._files.list_by_status(FileStatus.CONFIRMADO)
        to_hash = len(confirmed) if verify_hashes is None else verify_hashes
        # Los más antiguos primero: así el muestreo recorre todo con el tiempo.
        for asset in confirmed:
            known_keys.add(asset.storage_key)
            report.confirmed_checked += 1
            size = self._storage.size(asset.storage_key)
            if size is None:
                report.missing_files.append(asset.id)
            elif size != asset.stored_size_bytes:
                report.size_mismatches.append(asset.id)
            elif report.hashes_verified < to_hash:
                report.hashes_verified += 1
                # Se compara lo que hay en el disco: no hace falta la clave maestra.
                if self._storage.sha256(asset.storage_key) != asset.stored_sha256:
                    report.hash_mismatches.append(asset.id)

        for key in list(self._storage.iter_keys()):
            if key not in known_keys:
                report.orphans_quarantined.append(self._storage.quarantine_unknown(key))

        self._audit.record(
            AuditAction.ALMACENAMIENTO_CONCILIADO,
            result=AuditResult.PERMITIDO if report.consistent else AuditResult.FALLIDO,
            actor_user_id=actor_user_id,
            resource_type="almacenamiento",
            details={
                "cargas_interrumpidas": report.stale_uploads_failed,
                "temporales_limpiados": report.temp_files_removed,
                "huerfanos_en_cuarentena": len(report.orphans_quarantined),
                "archivos_faltantes": len(report.missing_files),
                "tamanos_distintos": len(report.size_mismatches),
                "hashes_distintos": len(report.hash_mismatches),
                "borrados_terminados": report.deleted_files_removed,
                "confirmados_revisados": report.confirmed_checked,
                "hashes_verificados": report.hashes_verified,
            },
        )
        return report
