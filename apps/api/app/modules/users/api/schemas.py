from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.modules.users.domain.models import Role, User


class UserOut(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str
    role: Role
    is_active: bool
    created_at: datetime
    last_activity_at: datetime | None
    deactivated_at: datetime | None

    @classmethod
    def from_domain(cls, user: User) -> UserOut:
        # El hash de la contraseña nunca sale de la API.
        return cls(
            id=user.id,
            email=user.email,
            full_name=user.full_name,
            role=user.role,
            is_active=user.is_active,
            created_at=user.created_at,
            last_activity_at=user.last_activity_at,
            deactivated_at=user.deactivated_at,
        )


class UserCreateIn(BaseModel):
    email: str = Field(max_length=254)
    full_name: str = Field(max_length=200)
    password: str = Field(max_length=128)
    role: Role = Role.RECLUTADOR


class UserUpdateIn(BaseModel):
    full_name: str | None = Field(default=None, max_length=200)
    role: Role | None = None


class PasswordResetIn(BaseModel):
    new_password: str = Field(max_length=128)


class PasswordResetOut(BaseModel):
    sessions_closed: int


class UserPage(BaseModel):
    items: list[UserOut]
    total: int
    page: int
    page_size: int


class DirectoryEntry(BaseModel):
    id: uuid.UUID
    full_name: str
    email: str
