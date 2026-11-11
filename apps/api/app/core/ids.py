"""Identificadores.

SQL Server ordena los ``UNIQUEIDENTIFIER`` empezando por sus últimos 6 bytes. Un
UUID aleatorio fragmenta los índices; uno con la marca de tiempo en esos bytes
se inserta casi en orden. Se genera en la aplicación (y no con
``NEWSEQUENTIALID()``) para conocer el identificador antes de insertar.
"""

from __future__ import annotations

import secrets
import time
import uuid


def new_sequential_uuid(now_ms: int | None = None) -> uuid.UUID:
    milliseconds = now_ms if now_ms is not None else time.time_ns() // 1_000_000
    return uuid.UUID(bytes=secrets.token_bytes(10) + milliseconds.to_bytes(6, "big"))
