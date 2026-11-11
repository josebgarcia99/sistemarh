"""Tokens opacos de sesión.

El navegador recibe el token; la base de datos guarda solo su SHA-256. Así,
quien lea la tabla de sesiones no puede suplantar a nadie.
"""

from __future__ import annotations

import hashlib
import secrets


def generate_token() -> str:
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
