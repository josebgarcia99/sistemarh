"""Contraseñas: hash Argon2id y política mínima.

La contraseña nunca se guarda ni se registra en claro. Nadie, tampoco el
administrador, puede leerla: solo se puede restablecer.
"""

from __future__ import annotations

from typing import Protocol

from argon2 import PasswordHasher as _Argon2
from argon2.exceptions import InvalidHashError, VerificationError

from app.core.exceptions.errors import ValidationFailedError

MIN_PASSWORD_LENGTH = 12
MAX_PASSWORD_LENGTH = 128


class PasswordHasher(Protocol):
    def hash(self, password: str) -> str: ...

    def verify(self, password_hash: str, password: str) -> bool: ...

    def needs_rehash(self, password_hash: str) -> bool: ...

    def verify_dummy(self, password: str) -> None: ...


class Argon2Hasher:
    """Argon2id con los parámetros por omisión de argon2-cffi, o los que se indiquen."""

    def __init__(self, **parameters: int) -> None:
        self._hasher = _Argon2(**parameters)
        # Hash de relleno: se verifica cuando el usuario no existe, para que la
        # respuesta tarde lo mismo y no revele qué correos están registrados.
        self._dummy_hash = self._hasher.hash("contraseña-de-relleno")

    def hash(self, password: str) -> str:
        return self._hasher.hash(password)

    def verify(self, password_hash: str, password: str) -> bool:
        try:
            return self._hasher.verify(password_hash, password)
        except (VerificationError, InvalidHashError):
            return False

    def needs_rehash(self, password_hash: str) -> bool:
        return self._hasher.check_needs_rehash(password_hash)

    def verify_dummy(self, password: str) -> None:
        self.verify(self._dummy_hash, password)


def validate_password(password: str, *, email: str | None = None) -> None:
    """Política mínima. Lanza ``ValidationFailedError`` si no se cumple."""
    if len(password) < MIN_PASSWORD_LENGTH:
        raise ValidationFailedError(
            f"La contraseña debe tener al menos {MIN_PASSWORD_LENGTH} caracteres."
        )
    if len(password) > MAX_PASSWORD_LENGTH:
        raise ValidationFailedError(
            f"La contraseña no puede superar {MAX_PASSWORD_LENGTH} caracteres."
        )
    if len(set(password)) < 4:
        raise ValidationFailedError("La contraseña es demasiado repetitiva.")
    if email and password.strip().lower() in {email.lower(), email.lower().split("@")[0]}:
        raise ValidationFailedError("La contraseña no puede ser el correo del usuario.")
