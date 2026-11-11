"""Análisis antivirus local.

Los documentos nunca se envían a servicios externos de análisis: el único
analizador real es ClamAV (``clamd``) dentro de la infraestructura propia.
"""

from __future__ import annotations

import socket
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


class ScannerUnavailableError(Exception):
    """El antivirus no respondió. La carga se rechaza: no se guarda sin analizar."""


@dataclass(frozen=True)
class ScanResult:
    clean: bool
    analyzed: bool
    signature: str | None = None


class MalwareScanner(Protocol):
    def scan(self, path: Path) -> ScanResult: ...


class DisabledScanner:
    """Sin antivirus. Solo para desarrollo o por decisión expresa de Sistemas."""

    def scan(self, path: Path) -> ScanResult:
        return ScanResult(clean=True, analyzed=False)


class ClamdScanner:
    """Cliente mínimo del protocolo INSTREAM de clamd."""

    _CHUNK = 64 * 1024

    def __init__(self, host: str, port: int, timeout_seconds: float = 60.0) -> None:
        self._address = (host, port)
        self._timeout = timeout_seconds

    def scan(self, path: Path) -> ScanResult:
        try:
            with socket.create_connection(self._address, timeout=self._timeout) as connection:
                connection.sendall(b"zINSTREAM\0")
                with open(path, "rb") as handle:
                    while chunk := handle.read(self._CHUNK):
                        connection.sendall(struct.pack("!L", len(chunk)) + chunk)
                connection.sendall(struct.pack("!L", 0))
                reply = b""
                while not reply.endswith(b"\0"):
                    part = connection.recv(4096)
                    if not part:
                        break
                    reply += part
        except OSError as error:
            raise ScannerUnavailableError("El antivirus no está disponible.") from error

        text = reply.rstrip(b"\0").decode("utf-8", "replace").strip()
        if text.endswith("OK"):
            return ScanResult(clean=True, analyzed=True)
        if text.endswith("FOUND"):
            signature = text.removeprefix("stream:").removesuffix("FOUND").strip()
            return ScanResult(clean=False, analyzed=True, signature=signature[:200])
        raise ScannerUnavailableError("El antivirus devolvió una respuesta inesperada.")
