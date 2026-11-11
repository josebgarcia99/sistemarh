"""Clave maestra y cifrado autenticado (AES-256-GCM).

La clave maestra vive en un archivo del servidor, fuera de SQL Server y del
repositorio, bajo custodia de Sistemas. Con ella se cifran las API keys de los
proveedores de IA y los documentos de clase sensible. Sin ella, lo cifrado no
se puede leer: debe respaldarse por separado.

La clave nunca se escribe en logs, errores ni auditoría; solo su identificador
(una huella corta que no permite deducirla).
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import os
import struct
from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import BinaryIO

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

KEY_BYTES = 32
_TEXT_NONCE_BYTES = 12
_FILE_MAGIC = b"RCLU1"
_FILE_PREFIX_BYTES = 8
_CHUNK_BYTES = 1024 * 1024
_TAG_BYTES = 16
_LAST = b"\x01"
_MORE = b"\x00"


class MasterKeyError(Exception):
    """La clave maestra falta o no es válida. El mensaje nunca incluye la clave."""


class DecryptionError(Exception):
    """El contenido cifrado está dañado, incompleto o se cifró con otra clave."""


def generate_key_text() -> str:
    """Clave nueva, lista para guardarse en el archivo de la clave maestra."""
    return base64.b64encode(os.urandom(KEY_BYTES)).decode("ascii")


class MasterKey:
    def __init__(self, key: bytes) -> None:
        if len(key) != KEY_BYTES:
            raise MasterKeyError("La clave maestra debe medir 32 bytes.")
        self._aead = AESGCM(key)
        # Huella corta para saber con qué clave se cifró algo, sin revelarla.
        self.key_id = hashlib.sha256(b"reclutamiento-clave-maestra:" + key).hexdigest()[:16]

    @classmethod
    def from_text(cls, text: str) -> MasterKey:
        try:
            return cls(base64.b64decode(text.strip(), validate=True))
        except (binascii.Error, ValueError) as error:
            raise MasterKeyError("La clave maestra no tiene el formato esperado.") from error

    @classmethod
    def load(cls, path: Path) -> MasterKey:
        try:
            return cls.from_text(path.read_text(encoding="ascii"))
        except OSError as error:
            raise MasterKeyError("No se pudo leer el archivo de la clave maestra.") from error

    def __repr__(self) -> str:
        return f"MasterKey(key_id={self.key_id!r})"

    # --- Textos cortos (API keys) --------------------------------------------------------

    def encrypt_text(self, plaintext: str, *, context: str) -> str:
        """Cifra un texto. ``context`` liga el resultado a su uso: un texto
        cifrado para un proveedor no se puede hacer pasar por el de otro."""
        nonce = os.urandom(_TEXT_NONCE_BYTES)
        sealed = self._aead.encrypt(nonce, plaintext.encode("utf-8"), context.encode("utf-8"))
        return base64.b64encode(nonce + sealed).decode("ascii")

    def decrypt_text(self, token: str, *, context: str) -> str:
        try:
            raw = base64.b64decode(token, validate=True)
            nonce, sealed = raw[:_TEXT_NONCE_BYTES], raw[_TEXT_NONCE_BYTES:]
            return self._aead.decrypt(nonce, sealed, context.encode("utf-8")).decode("utf-8")
        except (InvalidTag, binascii.Error, ValueError) as error:
            raise DecryptionError("No se pudo descifrar el valor.") from error

    # --- Archivos ------------------------------------------------------------------------
    #
    # Formato: "RCLU1" + prefijo aleatorio de 8 bytes + bloques. Cada bloque es
    # su longitud (4 bytes) y el texto cifrado de hasta 1 MiB. El número de
    # bloque forma parte del nonce y el último bloque va marcado: así se detecta
    # un archivo recortado, reordenado o alterado.

    def encrypt_stream(self, source: BinaryIO, target: BinaryIO) -> None:
        prefix = os.urandom(_FILE_PREFIX_BYTES)
        target.write(_FILE_MAGIC + prefix)
        counter = 0
        chunk = source.read(_CHUNK_BYTES)
        while True:
            following = source.read(_CHUNK_BYTES)
            last = not following
            sealed = self._aead.encrypt(
                prefix + struct.pack("!L", counter), chunk, _LAST if last else _MORE
            )
            target.write(struct.pack("!L", len(sealed)) + sealed)
            if last:
                return
            counter += 1
            chunk = following

    def decrypt_chunks(self, chunks: Iterable[bytes]) -> Iterator[bytes]:
        """Descifra un archivo recibido por partes de cualquier tamaño."""
        buffer = bytearray()
        source = iter(chunks)

        def take(count: int) -> bytes | None:
            while len(buffer) < count:
                more = next(source, None)
                if more is None:
                    return None
                buffer.extend(more)
            data = bytes(buffer[:count])
            del buffer[:count]
            return data

        header = take(len(_FILE_MAGIC) + _FILE_PREFIX_BYTES)
        if header is None or not header.startswith(_FILE_MAGIC):
            raise DecryptionError("El archivo no tiene el formato cifrado esperado.")
        prefix = header[len(_FILE_MAGIC) :]
        counter = 0
        finished = False
        while not finished:
            size_bytes = take(4)
            if size_bytes is None:
                raise DecryptionError("El archivo cifrado está incompleto.")
            (size,) = struct.unpack("!L", size_bytes)
            if size < _TAG_BYTES or size > _CHUNK_BYTES + _TAG_BYTES:
                raise DecryptionError("El archivo cifrado está dañado.")
            sealed = take(size)
            if sealed is None:
                raise DecryptionError("El archivo cifrado está incompleto.")
            nonce = prefix + struct.pack("!L", counter)
            try:
                plain = self._aead.decrypt(nonce, sealed, _LAST)
                finished = True
            except InvalidTag:
                try:
                    plain = self._aead.decrypt(nonce, sealed, _MORE)
                except InvalidTag as error:
                    raise DecryptionError(
                        "El archivo cifrado está dañado o se cifró con otra clave."
                    ) from error
            counter += 1
            yield plain
        if buffer or next(source, None):
            raise DecryptionError("El archivo cifrado tiene datos sobrantes.")
