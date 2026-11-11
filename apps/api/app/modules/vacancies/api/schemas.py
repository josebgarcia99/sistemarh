from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.modules.vacancies.application.service import MemberView, VacancyData, VacancyView
from app.modules.vacancies.domain.models import (
    AccessType,
    SensitiveClass,
    UserInfo,
    VacancyStatus,
    WorkMode,
)


class PersonOut(BaseModel):
    id: uuid.UUID
    full_name: str
    email: str
    is_active: bool

    @classmethod
    def from_user(cls, user: UserInfo | None) -> PersonOut | None:
        if user is None:
            return None
        return cls(id=user.id, full_name=user.full_name, email=user.email, is_active=user.is_active)


class VacancyIn(BaseModel):
    name: str = Field(max_length=200)
    department: str = Field(max_length=120)
    location: str = Field(max_length=120)
    work_mode: WorkMode
    contract_type: str = Field(max_length=80)
    description: str = Field(default="", max_length=20000)
    positions: int = Field(default=1, ge=1, le=9999)
    notes: str | None = Field(default=None, max_length=20000)

    def to_data(self) -> VacancyData:
        return VacancyData(**self.model_dump())


class VacancyUpdateIn(VacancyIn):
    # Versión que el usuario tenía en pantalla; evita pisar cambios de otra persona.
    version: int


class StatusChangeIn(BaseModel):
    status: VacancyStatus
    version: int


class VacancyOut(BaseModel):
    id: uuid.UUID
    name: str
    department: str
    location: str
    work_mode: WorkMode
    contract_type: str
    description: str
    positions: int
    notes: str | None
    status: VacancyStatus
    owner: PersonOut | None
    # RESPONSABLE, COLABORACION, LECTURA o ADMINISTRADOR
    my_access: str
    opened_at: datetime | None
    closed_at: datetime | None
    created_at: datetime
    updated_at: datetime
    version: int

    @classmethod
    def from_view(cls, view: VacancyView) -> VacancyOut:
        v = view.vacancy
        return cls(
            id=v.id,
            name=v.name,
            department=v.department,
            location=v.location,
            work_mode=v.work_mode,
            contract_type=v.contract_type,
            description=v.description,
            positions=v.positions,
            notes=v.notes,
            status=v.status,
            owner=PersonOut.from_user(view.owner),
            my_access=view.access.name,
            opened_at=v.opened_at,
            closed_at=v.closed_at,
            created_at=v.created_at,
            updated_at=v.updated_at,
            version=v.version,
        )


class VacancyPage(BaseModel):
    items: list[VacancyOut]
    total: int
    page: int
    page_size: int


class MemberIn(BaseModel):
    access_type: AccessType


class MemberOut(BaseModel):
    user: PersonOut | None
    access_type: AccessType
    granted_at: datetime
    sensitive_classes: list[SensitiveClass]

    @classmethod
    def from_view(cls, view: MemberView) -> MemberOut:
        return cls(
            user=PersonOut.from_user(view.user),
            access_type=view.member.access_type,
            granted_at=view.member.granted_at,
            sensitive_classes=list(view.sensitive_classes),
        )


class SensitiveGrantsIn(BaseModel):
    document_classes: list[SensitiveClass]


class SensitiveGrantsOut(BaseModel):
    document_classes: list[SensitiveClass]
