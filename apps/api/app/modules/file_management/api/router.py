"""Documentos: carga, consulta, descarga y eliminación controlada.

Ningún archivo tiene URL pública ni se sirve desde una carpeta estática: toda
descarga pasa por aquí y evalúa el permiso en ese momento.
"""

from __future__ import annotations

import logging
import uuid
from urllib.parse import quote

from fastapi import APIRouter, Depends, Query, Request, status
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import StreamingResponse
from starlette.requests import ClientDisconnect

from app.composition.backend import Repositories
from app.composition.context import AppContext, client_ip, get_context
from app.core.exceptions.errors import ServiceUnavailableError, ValidationFailedError
from app.modules.authentication.api.dependencies import Principal, require_admin, require_user
from app.modules.file_management.api.schemas import (
    FileDeletionIn,
    FileOut,
    FileUploadOut,
    ReconciliationIn,
    ReconciliationOut,
    StorageStatusOut,
)
from app.modules.file_management.application.service import StoreOutcome
from app.modules.file_management.domain.models import DocumentType, FileAsset, FileStatus

logger = logging.getLogger(__name__)
router = APIRouter(tags=["documentos"])

_SAMPLE_SIZE = 200


def _names(repos: Repositories, assets: list[FileAsset]) -> dict[uuid.UUID, str]:
    users = repos.users.get_many(list({asset.uploaded_by for asset in assets}))
    return {user_id: user.full_name for user_id, user in users.items()}


@router.get(
    "/vacancies/{vacancy_id}/files",
    response_model=list[FileOut],
    summary="Documentos de una vacante que el usuario puede ver",
)
def list_files(
    vacancy_id: uuid.UUID,
    principal: Principal = Depends(require_user),  # noqa: B008
    context: AppContext = Depends(get_context),  # noqa: B008
) -> list[FileOut]:
    context.require_storage()
    with context.require_backend().transaction() as repos:
        assets = context.file_service(repos).list_for_vacancy(principal.user, vacancy_id)
        names = _names(repos, assets)
    return [FileOut.of(asset, names) for asset in assets]


@router.post(
    "/vacancies/{vacancy_id}/files",
    response_model=FileUploadOut,
    status_code=status.HTTP_201_CREATED,
    summary="Carga un documento (el cuerpo de la petición es el archivo)",
)
async def upload_file(
    vacancy_id: uuid.UUID,
    request: Request,
    document_type: DocumentType = Query(),  # noqa: B008
    filename: str = Query(min_length=1, max_length=400),
    principal: Principal = Depends(require_user),  # noqa: B008
    context: AppContext = Depends(get_context),  # noqa: B008
) -> FileUploadOut:
    context.require_storage()
    backend = context.require_backend()
    ip = client_ip(request)
    declared = request.headers.get("content-length")

    def begin() -> FileAsset:
        with backend.transaction() as repos:
            return context.file_service(repos).begin_upload(
                principal.user,
                vacancy_id=vacancy_id,
                document_type=document_type,
                original_name=filename,
                declared_size=int(declared) if declared and declared.isdigit() else None,
            )

    asset = await run_in_threadpool(begin)
    pipeline = context.upload_pipeline()

    # Desde aquí existe un registro RECIBIENDO: pase lo que pase debe quedar en
    # un estado final. Si el proceso muere, lo resuelve la conciliación.
    failure: tuple[str, str] | None = None
    receiver = None
    try:
        receiver = await run_in_threadpool(pipeline.receiver, asset)
        async for chunk in request.stream():
            if chunk and not await run_in_threadpool(receiver.write, chunk):
                break
    except ClientDisconnect:
        failure = ("carga_interrumpida", "La carga se interrumpió.")
    except Exception:
        logger.exception("Fallo al recibir un documento")
        failure = ("escritura_fallida", "No se pudo guardar el documento. Inténtalo de nuevo.")
    finally:
        if receiver is not None:
            await run_in_threadpool(receiver.close)

    def finish() -> tuple[StoreOutcome, FileUploadOut]:
        if failure is not None or receiver is None:
            code, message = failure or ("escritura_fallida", "No se pudo guardar el documento.")
            outcome = pipeline.abort(asset, code, message)
        else:
            outcome = pipeline.store(asset, receiver)
        with backend.transaction() as repos:
            stored, duplicates = context.file_service(repos).finish_upload(
                principal.user, asset.id, outcome, ip=ip
            )
            names = _names(repos, [stored, *duplicates])
        return outcome, FileUploadOut(
            file=FileOut.of(stored, names),
            duplicates=[FileOut.of(duplicate, names) for duplicate in duplicates],
        )

    outcome, body = await run_in_threadpool(finish)
    if outcome.status is FileStatus.RECHAZADO:
        raise ValidationFailedError(outcome.message or "El archivo no se aceptó.")
    if outcome.status is not FileStatus.CONFIRMADO:
        raise ServiceUnavailableError(outcome.message or "No se pudo guardar el documento.")
    return body


@router.get("/files/{file_id}", response_model=FileOut, summary="Metadatos de un documento")
def get_file(
    file_id: uuid.UUID,
    principal: Principal = Depends(require_user),  # noqa: B008
    context: AppContext = Depends(get_context),  # noqa: B008
) -> FileOut:
    context.require_storage()
    with context.require_backend().transaction() as repos:
        asset = context.file_service(repos).get(principal.user, file_id)
        names = _names(repos, [asset])
    return FileOut.of(asset, names)


def _content_disposition(name: str) -> str:
    fallback = name.encode("ascii", "replace").decode("ascii").replace("?", "_")
    fallback = fallback.replace("\\", "_").replace('"', "_")
    return f"attachment; filename=\"{fallback}\"; filename*=UTF-8''{quote(name, safe='')}"


@router.get("/files/{file_id}/download", summary="Descarga autorizada de un documento")
def download_file(
    file_id: uuid.UUID,
    request: Request,
    principal: Principal = Depends(require_user),  # noqa: B008
    context: AppContext = Depends(get_context),  # noqa: B008
) -> StreamingResponse:
    storage = context.require_storage()
    with context.require_backend().transaction() as repos:
        download = context.file_service(repos).prepare_download(
            principal.user, file_id, ip=client_ip(request)
        )
    asset = download.asset
    if not download.available:
        raise ServiceUnavailableError(
            "El documento no está disponible en el almacenamiento. "
            "El incidente quedó registrado; avisa a Sistemas."
        )
    return StreamingResponse(
        storage.read_chunks(asset.storage_key),
        media_type=asset.content_type or "application/octet-stream",
        headers={
            "Content-Disposition": _content_disposition(asset.original_name),
            "Content-Length": str(asset.size_bytes),
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "no-store",
            "Content-Security-Policy": "sandbox; default-src 'none'",
        },
    )


@router.post(
    "/files/{file_id}/deletion",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Eliminación controlada (solo administradores, con motivo)",
)
def delete_file(
    file_id: uuid.UUID,
    body: FileDeletionIn,
    request: Request,
    principal: Principal = Depends(require_admin),  # noqa: B008
    context: AppContext = Depends(get_context),  # noqa: B008
) -> None:
    storage = context.require_storage()
    with context.require_backend().transaction() as repos:
        asset = context.file_service(repos).delete(
            principal.user, file_id, reason=body.reason, ip=client_ip(request)
        )
    # La eliminación ya quedó registrada. Si el borrado físico falla, la
    # conciliación lo termina: el documento ya no es accesible en ningún caso.
    try:
        storage.delete(asset.storage_key)
    except Exception:
        logger.exception("No se pudo borrar el archivo de un documento eliminado")


@router.get("/storage/status", response_model=StorageStatusOut, summary="Estado del almacenamiento")
def storage_status(
    _: Principal = Depends(require_admin),  # noqa: B008
    context: AppContext = Depends(get_context),  # noqa: B008
) -> StorageStatusOut:
    storage = context.require_storage()
    with context.require_backend().transaction() as repos:
        counts = repos.files.count_by_status()
    mode = context.settings.antivirus_mode
    return StorageStatusOut(
        free_bytes=storage.free_bytes(),
        max_upload_bytes=context.settings.max_upload_bytes,
        antivirus=mode.value if mode else "disabled",
        files_by_status={state.value: counts.get(state, 0) for state in FileStatus},
    )


@router.post(
    "/storage/reconciliation",
    response_model=ReconciliationOut,
    summary="Concilia SQL Server con el disco de documentos",
)
def reconcile_storage(
    body: ReconciliationIn,
    principal: Principal = Depends(require_admin),  # noqa: B008
    context: AppContext = Depends(get_context),  # noqa: B008
) -> ReconciliationOut:
    context.require_storage()
    verify = {"none": 0, "sample": _SAMPLE_SIZE, "all": None}[body.verify_hashes]
    with context.require_backend().transaction() as repos:
        report = context.reconciler(repos).run(
            verify_hashes=verify, actor_user_id=principal.user.id
        )
    return ReconciliationOut.of(report)
