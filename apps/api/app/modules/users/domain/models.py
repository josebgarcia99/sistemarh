"""Entidad Usuario y sus reglas."""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from app.core.exceptions.errors import ValidationFailedError

_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
MAX_EMAIL_LENGTH = 254
MAX_NAME_LENGTH = 200


class Role(StrEnum):
    ADMINISTRADOR = "ADMINISTRADOR"
    RECLUTADOR = "RECLUTADOR"


def normalize_email(email: str) -> str:
    value = email.strip().lower()
    if len(value) > MAX_EMAIL_LENGTH or not _EMAIL.match(value):
        raise ValidationFailedError("El correo no tiene un formato válido.")
    return value


def normalize_full_name(full_name: str) -> str:
    value = " ".join(full_name.split())
    if not value:
        raise ValidationFailedError("El nombre completo es obligatorio.")
    if len(value) > MAX_NAME_LENGTH:
        raise ValidationFailedError(f"El nombre no puede superar {MAX_NAME_LENGTH} caracteres.")
    return value


@dataclass
class User:
    id: uuid.UUID
    email: str
    full_name: str
    role: Role
    password_hash: str
    is_active: bool
    created_at: datetime
    created_by: uuid.UUID | None = None
    last_activity_at: datetime | None = None
    deactivated_at: datetime | None = None
    password_changed_at: datetime | None = None
    failed_login_count: int = 0
    locked_until: datetime | None = None

    @property
    def is_admin(self) -> bool:
        return self.role is Role.ADMINISTRADOR

    def is_locked(self, now: datetime) -> bool:
        return self.locked_until is not None and self.locked_until > now
