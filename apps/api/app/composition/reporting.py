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
