"""Almacenamiento documental en el sistema de archivos privado del servidor.

Reglas que este módulo garantiza:

- Las claves las construye el servidor a partir de un UUID; nunca llegan del
  usuario. Toda ruta resuelta debe quedar dentro de la raíz.
- Un archivo definitivo no se sobrescribe ni se modifica.
- Un archivo solo pasa a su ubicación definitiva después de sincronizarse a
  disco, y el cambio de lugar es atómico.
- Ningún nombre de persona aparece en el disco.

No conoce vacantes, candidatos ni ninguna regla de negocio. Otro backend
(por ejemplo, uno compatible con S3) solo tendría que ofrecer estos métodos.
"""

from __future__ import annotations

import hashlib
import os
import re
import shutil
import uuid
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import BinaryIO

AREAS = ("private", "generated")
_TEMP_DIR = Path("processing") / "temporary"
_QUARANTINE_DIR = Path("quarantine")
_KEY_PATTERN = re.compile(
    r"^(private|generated)/[a-z_]{1,40}/[0-9a-f]{2}/[0-9a-f]{2}/"
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
)
_FOLDER_PATTERN = re.compile(r"^[a-z_]{1,40}$")
CHUNK_SIZE = 1024 * 1024


class StorageError(Exception):
    """Fallo del almacenamiento. El mensaje nunca incluye rutas físicas."""


class InvalidStorageKeyError(StorageError):
    pass


def build_key(area: str, folder: str, file_id: uuid.UUID) -> str:
    """Clave lógica relativa, por ejemplo ``private/cv/3f/a9/<uuid>``."""
    if area not in AREAS or not _FOLDER_PATTERN.match(folder):
        raise InvalidStorageKeyError("Área o carpeta de almacenamiento no válida.")
    name = str(file_id)
    return f"{area}/{folder}/{name[0:2]}/{name[2:4]}/{name}"


def _fsync_directory(directory: Path) -> None:
    if os.name == "nt":  # Windows no permite sincronizar directorios.
        return
    descriptor = os.open(directory, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


class LocalFileStorage:
    backend_name = "local"

    def __init__(self, root: Path) -> None:
        if not root.is_absolute():
            raise StorageError("La raíz del almacenamiento debe ser una ruta absoluta.")
        self._root = root.resolve()

    def prepare(self) -> None:
        """Crea las carpetas internas. La raíz debe existir ya.

        No se crea la raíz a propósito: si el volumen del servidor no está
        montado, es mejor fallar al arrancar que guardar documentos dentro de
        un contenedor que se pierde al recrearlo.
        """
        if not self._root.is_dir():
            raise StorageError(
                "La carpeta de almacenamiento documental no existe o no está montada."
            )
        for relative in (*(Path(area) for area in AREAS), _TEMP_DIR, _QUARANTINE_DIR):
            (self._root / relative).mkdir(parents=True, exist_ok=True)

    # --- Rutas ---------------------------------------------------------------------------

    def new_key(self, area: str, folder: str, file_id: uuid.UUID) -> str:
        return build_key(area, folder, file_id)

    def _resolve(self, key: str) -> Path:
        if not _KEY_PATTERN.match(key):
            raise InvalidStorageKeyError("Referencia de almacenamiento no válida.")
        path = (self._root / key).resolve()
        if not path.is_relative_to(self._root):
            raise InvalidStorageKeyError("Referencia de almacenamiento no válida.")
        return path

    def _temp_path(self, file_id: uuid.UUID) -> Path:
        return self._root / _TEMP_DIR / f"{uuid.UUID(str(file_id))}.part"

    # --- Recepción temporal --------------------------------------------------------------

    def open_temp(self, file_id: uuid.UUID) -> BinaryIO:
        """Abre el archivo temporal de una recepción. Falla si ya existe."""
        return open(self._temp_path(file_id), "xb")  # noqa: SIM115

    def temp_path(self, file_id: uuid.UUID) -> Path:
        """Ruta del temporal, solo para validarlo y analizarlo dentro del servidor."""
        return self._temp_path(file_id)

    def discard_temp(self, file_id: uuid.UUID) -> None:
        self._temp_path(file_id).unlink(missing_ok=True)

    def commit(self, file_id: uuid.UUID, key: str) -> None:
        """Mueve el temporal a su ubicación definitiva sin sobrescribir nada."""
        final = self._resolve(key)
        temp = self._temp_path(file_id)
        if final.exists():
            raise StorageError("Ya existe un archivo con esa referencia; no se sobrescribe.")
        try:
            with open(temp, "rb") as handle:
                os.fsync(handle.fileno())
            final.parent.mkdir(parents=True, exist_ok=True)
            os.replace(temp, final)
            _fsync_directory(final.parent)
        except OSError as error:
            raise StorageError("No se pudo guardar el archivo en el almacenamiento.") from error

    # --- Archivos definitivos ------------------------------------------------------------

    def exists(self, key: str) -> bool:
        return self._resolve(key).is_file()

    def size(self, key: str) -> int | None:
        try:
            return self._resolve(key).stat().st_size
        except FileNotFoundError:
            return None

    def open(self, key: str) -> BinaryIO:
        try:
            return open(self._resolve(key), "rb")  # noqa: SIM115
        except FileNotFoundError as error:
            raise StorageError("El archivo no está en el almacenamiento.") from error

    def read_chunks(self, key: str) -> Iterator[bytes]:
        with self.open(key) as handle:
            while chunk := handle.read(CHUNK_SIZE):
                yield chunk

    def sha256(self, key: str) -> str:
        digest = hashlib.sha256()
        for chunk in self.read_chunks(key):
            digest.update(chunk)
        return digest.hexdigest()

    def delete(self, key: str) -> bool:
        """Elimina un archivo definitivo. Devuelve si existía."""
        path = self._resolve(key)
        try:
            path.unlink()
        except FileNotFoundError:
            return False
        except OSError as error:
            raise StorageError("No se pudo eliminar el archivo del almacenamiento.") from error
        _fsync_directory(path.parent)
        return True

    def quarantine(self, key: str) -> str:
        """Aparta un archivo sin borrarlo. Devuelve su nombre en cuarentena."""
        source = self._resolve(key)
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        name = f"{stamp}__{key.replace('/', '__')}"
        try:
            os.replace(source, self._root / _QUARANTINE_DIR / name)
        except OSError as error:
            raise StorageError("No se pudo mover el archivo a cuarentena.") from error
        return name

    # --- Inventario ----------------------------------------------------------------------

    def iter_keys(self) -> Iterator[str]:
        """Claves de todos los archivos definitivos presentes en el disco."""
        for area in AREAS:
            base = self._root / area
            if not base.is_dir():
                continue
            for path in sorted(base.rglob("*")):
                if path.is_file():
                    yield path.relative_to(self._root).as_posix()

    def iter_temp(self) -> Iterator[tuple[str, datetime]]:
        """Nombre y fecha de modificación de cada temporal presente."""
        base = self._root / _TEMP_DIR
        if not base.is_dir():
            return
        for path in sorted(base.iterdir()):
            if path.is_file():
                yield path.name, datetime.fromtimestamp(path.stat().st_mtime, UTC)

    def discard_temp_by_name(self, name: str) -> None:
        if "/" in name or "\\" in name or name in {".", ".."}:
            raise InvalidStorageKeyError("Nombre de temporal no válido.")
        (self._root / _TEMP_DIR / name).unlink(missing_ok=True)

    def quarantine_unknown(self, key: str) -> str:
        """Aparta un archivo presente en el disco cuya clave no es reconocible."""
        path = (self._root / key).resolve()
        if not path.is_relative_to(self._root) or not path.is_file():
            raise InvalidStorageKeyError("Referencia de almacenamiento no válida.")
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        name = f"{stamp}__{key.replace('/', '__')}"
        os.replace(path, self._root / _QUARANTINE_DIR / name)
        return name

    def free_bytes(self) -> int:
        return shutil.disk_usage(self._root).free
