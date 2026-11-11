"""Puertos hacia el almacenamiento físico y el antivirus."""

from __future__ import annotations

import uuid
from collections.abc import Callable, Iterable, Iterator
from datetime import datetime
from pathlib import Path
from typing import BinaryIO, Protocol


class FileStorage(Protocol):
    backend_name: str

    def new_key(self, area: str, folder: str, file_id: uuid.UUID) -> str: ...

    def open_temp(self, file_id: uuid.UUID) -> BinaryIO: ...

    def temp_path(self, file_id: uuid.UUID) -> Path: ...

    def discard_temp(self, file_id: uuid.UUID) -> None: ...

    def transform_temp(
        self, file_id: uuid.UUID, transform: Callable[[BinaryIO, BinaryIO], None]
    ) -> tuple[int, str]:
        """Sustituye el temporal por su versión transformada. Devuelve tamaño y SHA-256."""
        ...

    def commit(self, file_id: uuid.UUID, key: str) -> None: ...

    def exists(self, key: str) -> bool: ...

    def size(self, key: str) -> int | None: ...

    def read_chunks(self, key: str) -> Iterator[bytes]: ...

    def sha256(self, key: str) -> str: ...

    def delete(self, key: str) -> bool: ...

    def quarantine(self, key: str) -> str: ...

    def quarantine_unknown(self, key: str) -> str: ...

    def iter_keys(self) -> Iterator[str]: ...

    def iter_temp(self) -> Iterator[tuple[str, datetime]]: ...

    def discard_temp_by_name(self, name: str) -> None: ...

    def free_bytes(self) -> int: ...


class FileCipher(Protocol):
    """Cifrado de archivos de clase sensible."""

    key_id: str

    def encrypt_stream(self, source: BinaryIO, target: BinaryIO) -> None: ...

    def decrypt_chunks(self, chunks: Iterable[bytes]) -> Iterator[bytes]: ...


class ScanOutcome(Protocol):
    clean: bool
    analyzed: bool
    signature: str | None


class Scanner(Protocol):
    def scan(self, path: Path) -> ScanOutcome: ...
