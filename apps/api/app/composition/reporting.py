"""Conexiones del módulo de reportes con el almacenamiento del servidor."""

from __future__ import annotations

import hashlib
import uuid
from collections.abc import Callable
from typing import BinaryIO

from app.infrastructure.storage.local import LocalFileStorage
from app.modules.reporting.domain.models import StoredFile

_FOLDER = "reports"
_CHUNK = 1024 * 1024


class StoredReports:
    """Guarda cada Excel en ``generated/reports`` del almacenamiento documental.

    Primero se escribe y confirma el archivo y después se registra. Si la
    transacción no llega a confirmarse, queda un archivo sin registro que la
    conciliación lleva a cuarentena.
    """

    def __init__(self, storage: LocalFileStorage) -> None:
        self._storage = storage

    def save(self, file_id: uuid.UUID, write: Callable[[BinaryIO], None]) -> StoredFile:
        key = self._storage.new_key("generated", _FOLDER, file_id)
        try:
            with self._storage.open_temp(file_id) as handle:
                write(handle)
            digest = hashlib.sha256()
            size = 0
            with open(self._storage.temp_path(file_id), "rb") as handle:
                while chunk := handle.read(_CHUNK):
                    digest.update(chunk)
                    size += len(chunk)
            self._storage.commit(file_id, key)
        except BaseException:
            self._storage.discard_temp(file_id)
            raise
        return StoredFile(key=key, size_bytes=size, sha256=digest.hexdigest())

    def exists(self, key: str) -> bool:
        return self._storage.exists(key)


def check_report_files(
    storage: LocalFileStorage, files: list[tuple[uuid.UUID, StoredFile]], *, verify_hashes: bool
) -> list[str]:
    """Compara los reportes registrados con lo que hay en el disco.

    Devuelve una línea por cada problema: archivo que falta, tamaño distinto o,
    si se pide, huella distinta.
    """
    problems = []
    for export_id, expected in files:
        size = storage.size(expected.key)
        if size is None:
            problems.append(f"FALTANTE: reporte {export_id}")
        elif size != expected.size_bytes:
            problems.append(f"TAMAÑO DISTINTO: reporte {export_id}")
        elif verify_hashes and storage.sha256(expected.key) != expected.sha256:
            problems.append(f"HASH DISTINTO: reporte {export_id}")
    return problems
