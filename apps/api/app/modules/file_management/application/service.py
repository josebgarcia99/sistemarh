"""Carga, consulta, descarga y eliminación controlada de documentos.

Protocolo de escritura recuperable (el disco y SQL Server no comparten
transacción):

1. ``begin_upload`` crea el registro en estado RECIBIENDO.
2. El archivo se recibe en la zona temporal mientras se calculan tamaño y hash.
3. ``UploadPipeline.store`` valida el tipo real, lo analiza con el antivirus y
   lo mueve de forma atómica a su ubicación definitiva.
4. ``finish_upload`` deja el registro en CONFIRMADO, RECHAZADO o FALLIDO.

Solo se responde "guardado" después del paso 4. Si el proceso se interrumpe
en cualquier punto, la conciliación lo detecta y lo deja en un estado final.
"""

from __future__ import annotations

import hashlib
import logging
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from app.core.exceptions.errors import (
    NotFoundError,
    PermissionDeniedError,
    ServiceUnavailableError,
    ValidationFailedError,
)
from app.core.ids import new_sequential_uuid
from app.modules.audit.application.service import AuditLog
from app.modules.audit.domain.models import AuditAction, AuditResult
from app.modules.file_management.domain.filetypes import (
    CONTENT_TYPES,
    FileRejectedError,
    extension_of,
    inspect_file,
    require_allowed_extension,
    sanitize_filename,
)
from app.modules.file_management.domain.models import (
    SENSITIVE_CLASSES,
    STORAGE_FOLDERS,
    Actor,
    DocumentType,
    FileAccessPolicy,
    FileAsset,
    FileRepository,
    FileStatus,
    MalwareScan,
)
from app.modules.file_management.domain.ports import FileStorage, Scanner

logger = logging.getLogger(__name__)

RESOURCE = "documento"


@dataclass(frozen=True)
class StoreOutcome:
    """Resultado de validar y guardar físicamente un archivo recibido."""

    status: FileStatus
    size_bytes: int | None = None
    sha256: str | None = None
    content_type: str | None = None
    malware_scan: MalwareScan | None = None
    failure_code: str | None = None
    message: str | None = None


@dataclass(frozen=True)
class Download:
    asset: FileAsset
    # Falso si el registro existe pero el archivo no está en el disco (incidente).
    available: bool


class TempReceiver:
    """Escribe un archivo en la zona temporal calculando tamaño y SHA-256."""

    def __init__(self, storage: FileStorage, file_id: uuid.UUID, max_bytes: int) -> None:
        self._handle = storage.open_temp(file_id)
        self._digest = hashlib.sha256()
        self._max_bytes = max_bytes
        self.size = 0
        self.too_large = False

    def write(self, chunk: bytes) -> bool:
        """Devuelve falso cuando se supera el límite; ya no se escribe más."""
        if self.too_large:
            return False
        self.size += len(chunk)
        if self.size > self._max_bytes:
            self.too_large = True
            return False
        self._digest.update(chunk)
        self._handle.write(chunk)
        return True

    def close(self) -> None:
        self._handle.close()

    @property
    def sha256(self) -> str:
        return self._digest.hexdigest()


class UploadPipeline:
    """Pasos que no tocan SQL Server: validar, analizar y confirmar en disco."""

    def __init__(self, storage: FileStorage, scanner: Scanner, max_bytes: int) -> None:
        self._storage = storage
        self._scanner = scanner
        self._max_bytes = max_bytes

    def receiver(self, asset: FileAsset) -> TempReceiver:
        return TempReceiver(self._storage, asset.id, self._max_bytes)

    def abort(self, asset: FileAsset, code: str, message: str) -> StoreOutcome:
        self._storage.discard_temp(asset.id)
        return StoreOutcome(status=FileStatus.FALLIDO, failure_code=code, message=message)

    def store(self, asset: FileAsset, received: TempReceiver) -> StoreOutcome:
        storage = self._storage
        if received.too_large:
            storage.discard_temp(asset.id)
            megabytes = self._max_bytes // (1024 * 1024)
            return StoreOutcome(
                status=FileStatus.RECHAZADO,
                failure_code="tamano_excedido",
                message=f"El archivo supera el límite de {megabytes} MB.",
            )
        temp = storage.temp_path(asset.id)
        try:
            kind = inspect_file(temp, asset.original_name)
        except FileRejectedError as rejected:
            storage.discard_temp(asset.id)
            return StoreOutcome(
                status=FileStatus.RECHAZADO, failure_code=rejected.code, message=rejected.message
            )

        try:
            scan = self._scanner.scan(temp)
        except Exception:
            # Sin antivirus disponible no se guarda nada: se falla de forma segura.
            logger.exception("El antivirus no respondió al analizar una carga")
            return self.abort(
                asset,
                "antivirus_no_disponible",
                "No se pudo analizar el archivo. Inténtalo de nuevo más tarde.",
            )
        if not scan.clean:
            storage.discard_temp(asset.id)
            return StoreOutcome(
                status=FileStatus.RECHAZADO,
                failure_code="archivo_malicioso",
                message="El antivirus detectó una amenaza en el archivo y no se guardó.",
            )

        try:
            storage.commit(asset.id, asset.storage_key)
            stored_size = storage.size(asset.storage_key)
        except Exception:
            logger.exception("No se pudo confirmar un archivo en el almacenamiento")
            return self.abort(
                asset, "escritura_fallida", "No se pudo guardar el documento. Inténtalo de nuevo."
            )
        if stored_size != received.size:
            # No se declara guardado algo cuya persistencia no se confirmó.
            logger.error("El tamaño del archivo guardado no coincide con el recibido")
            return StoreOutcome(
                status=FileStatus.FALLIDO,
                failure_code="escritura_no_confirmada",
                message="No se pudo guardar el documento. Inténtalo de nuevo.",
            )
        return StoreOutcome(
            status=FileStatus.CONFIRMADO,
            size_bytes=received.size,
            sha256=received.sha256,
            content_type=CONTENT_TYPES[kind],
            malware_scan=MalwareScan.LIMPIO if scan.analyzed else MalwareScan.NO_ANALIZADO,
        )


class FileService:
    def __init__(
        self,
        files: FileRepository,
        policy: FileAccessPolicy,
        audit: AuditLog,
        clock: Callable[[], datetime],
        storage: FileStorage,
        *,
        max_bytes: int,
        min_free_bytes: int,
        allow_sensitive: bool,
    ) -> None:
        self._files = files
        self._policy = policy
        self._audit = audit
        self._clock = clock
        self._storage = storage
        self._max_bytes = max_bytes
        self._min_free_bytes = min_free_bytes
        self._allow_sensitive = allow_sensitive

    # --- Carga ---------------------------------------------------------------------------

    def begin_upload(
        self,
        actor: Actor,
        *,
        vacancy_id: uuid.UUID,
        document_type: DocumentType,
        original_name: str,
        declared_size: int | None,
    ) -> FileAsset:
        sensitive_class = SENSITIVE_CLASSES.get(document_type)
        self._policy.require_write(actor, vacancy_id, sensitive_class)
        if sensitive_class is not None and not self._allow_sensitive:
            raise ValidationFailedError(
                "Los documentos de psicometría y estudios socioeconómicos aún no se "
                "aceptan: falta activar su cifrado."
            )
        name = sanitize_filename(original_name)
        try:
            require_allowed_extension(name)
        except FileRejectedError as rejected:
            raise ValidationFailedError(rejected.message) from rejected
        megabytes = self._max_bytes // (1024 * 1024)
        if declared_size is not None and declared_size > self._max_bytes:
            raise ValidationFailedError(f"El archivo supera el límite de {megabytes} MB.")
        if self._storage.free_bytes() < self._min_free_bytes + self._max_bytes:
            logger.error("Espacio insuficiente en el almacenamiento documental")
            raise ServiceUnavailableError(
                "No hay espacio suficiente para guardar documentos. Avisa a Sistemas."
            )

        file_id = new_sequential_uuid()
        asset = FileAsset(
            id=file_id,
            vacancy_id=vacancy_id,
            document_type=document_type,
            sensitive_class=sensitive_class,
            original_name=name,
            extension=extension_of(name),
            storage_backend=self._storage.backend_name,
            storage_key=self._storage.new_key("private", STORAGE_FOLDERS[document_type], file_id),
            status=FileStatus.RECIBIENDO,
            uploaded_by=actor.id,
            created_at=self._clock(),
        )
        self._files.add(asset)
        return asset

    def finish_upload(
        self, actor: Actor, file_id: uuid.UUID, outcome: StoreOutcome, *, ip: str | None = None
    ) -> tuple[FileAsset, list[FileAsset]]:
        """Registra el resultado. Devuelve el documento y sus duplicados en la vacante."""
        asset = self._files.get(file_id)
        if asset is None or asset.status is not FileStatus.RECIBIENDO:
            raise NotFoundError("La carga ya no está en curso.")
        asset.status = outcome.status
        asset.failure_code = outcome.failure_code
        duplicates: list[FileAsset] = []
        if outcome.status is FileStatus.CONFIRMADO:
            asset.size_bytes = outcome.size_bytes
            asset.sha256 = outcome.sha256
            asset.content_type = outcome.content_type
            asset.malware_scan = outcome.malware_scan
            asset.confirmed_at = self._clock()
            duplicates = self._files.find_by_hash(
                asset.vacancy_id, outcome.sha256 or "", exclude_id=asset.id
            )
        self._files.save(asset)
        self._audit.record(
            AuditAction.DOCUMENTO_CARGADO
            if outcome.status is FileStatus.CONFIRMADO
            else AuditAction.DOCUMENTO_RECHAZADO,
            result=AuditResult.PERMITIDO
            if outcome.status is FileStatus.CONFIRMADO
            else AuditResult.FALLIDO,
            actor_user_id=actor.id,
            resource_type=RESOURCE,
            resource_id=asset.id,
            ip=ip,
            details={
                "vacante": str(asset.vacancy_id),
                "tipo": asset.document_type.value,
                "tamano": outcome.size_bytes,
                "motivo": outcome.failure_code,
                "duplicados": len(duplicates),
            },
        )
        return asset, duplicates

    # --- Consulta ------------------------------------------------------------------------

    def list_for_vacancy(self, actor: Actor, vacancy_id: uuid.UUID) -> list[FileAsset]:
        self._policy.require_read(actor, vacancy_id, None)
        visible = self._policy.readable_sensitive_classes(actor, vacancy_id)
        return [
            asset
            for asset in self._files.list_for_vacancy(vacancy_id, FileStatus.CONFIRMADO)
            if asset.sensitive_class is None or asset.sensitive_class in visible
        ]

    def _authorized(self, actor: Actor, file_id: uuid.UUID) -> FileAsset:
        asset = self._files.get(file_id)
        if asset is None:
            raise NotFoundError("El documento no existe.")
        # El permiso se evalúa ahora, no cuando se cargó el archivo.
        self._policy.require_read(actor, asset.vacancy_id, asset.sensitive_class)
        if asset.status is not FileStatus.CONFIRMADO:
            raise NotFoundError("El documento no existe o ya no está disponible.")
        return asset

    def get(self, actor: Actor, file_id: uuid.UUID) -> FileAsset:
        return self._authorized(actor, file_id)

    def prepare_download(
        self, actor: Actor, file_id: uuid.UUID, *, ip: str | None = None
    ) -> Download:
        asset = self._authorized(actor, file_id)
        available = self._storage.size(asset.storage_key) == asset.size_bytes
        self._audit.record(
            AuditAction.DOCUMENTO_DESCARGADO if available else AuditAction.DOCUMENTO_NO_DISPONIBLE,
            result=AuditResult.PERMITIDO if available else AuditResult.FALLIDO,
            actor_user_id=actor.id,
            resource_type=RESOURCE,
            resource_id=asset.id,
            ip=ip,
            details={"vacante": str(asset.vacancy_id), "tipo": asset.document_type.value},
        )
        if not available:
            logger.error("Documento confirmado ausente o alterado en el almacenamiento")
        return Download(asset=asset, available=available)

    # --- Eliminación controlada ----------------------------------------------------------

    def delete(
        self, actor: Actor, file_id: uuid.UUID, *, reason: str, ip: str | None = None
    ) -> FileAsset:
        """Marca el documento como eliminado. El archivo físico se borra después
        de confirmar la transacción; si ese borrado falla, la conciliación lo termina."""
        if not actor.is_admin:
            raise PermissionDeniedError("Solo un administrador puede eliminar documentos.")
        reason = " ".join(reason.split())
        if len(reason) < 10:
            raise ValidationFailedError("Escribe el motivo de la eliminación (mínimo 10 letras).")
        asset = self._files.get(file_id)
        if asset is None or asset.status is not FileStatus.CONFIRMADO:
            raise NotFoundError("El documento no existe o ya no está disponible.")
        asset.status = FileStatus.ELIMINADO
        asset.deleted_at = self._clock()
        asset.deleted_by = actor.id
        asset.deletion_reason = reason[:500]
        self._files.save(asset)
        self._audit.record(
            AuditAction.DOCUMENTO_ELIMINADO,
            actor_user_id=actor.id,
            resource_type=RESOURCE,
            resource_id=asset.id,
            ip=ip,
            details={
                "vacante": str(asset.vacancy_id),
                "tipo": asset.document_type.value,
                "sha256": asset.sha256,
                "motivo": asset.deletion_reason,
            },
        )
        return asset
