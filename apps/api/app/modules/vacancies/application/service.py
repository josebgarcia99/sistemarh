"""Vacantes y compartición.

Una vacante nace privada, con quien la crea como responsable principal.
Compartir concede acceso sin cambiar al responsable.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass

from app.core.clock import Clock
from app.core.exceptions.errors import ConflictError, NotFoundError, ValidationFailedError
from app.core.ids import new_sequential_uuid
from app.modules.audit.application.service import AuditLog
from app.modules.audit.domain.models import AuditAction
from app.modules.vacancies.application.access import VacancyAccess, effective_access
from app.modules.vacancies.domain.models import (
    ALLOWED_TRANSITIONS,
    AccessLevel,
    AccessType,
    Member,
    Scope,
    SensitiveClass,
    SensitiveGrant,
    UserInfo,
    UserLookup,
    Vacancy,
    VacancyRepository,
    VacancyStatus,
    WorkMode,
)

MAX_PAGE_SIZE = 100


@dataclass(frozen=True)
class VacancyData:
    name: str
    department: str
    location: str
    work_mode: WorkMode
    contract_type: str
    description: str
    positions: int
    notes: str | None = None


@dataclass(frozen=True)
class VacancyView:
    vacancy: Vacancy
    access: AccessLevel
    owner: UserInfo | None


@dataclass(frozen=True)
class MemberView:
    member: Member
    user: UserInfo | None
    sensitive_classes: tuple[SensitiveClass, ...]


def _clean(value: str, field: str, maximum: int, *, required: bool = True) -> str:
    text = " ".join(value.split())
    if required and not text:
        raise ValidationFailedError(f"El campo «{field}» es obligatorio.")
    if len(text) > maximum:
        raise ValidationFailedError(f"El campo «{field}» no puede superar {maximum} caracteres.")
    return text


def _validated(data: VacancyData) -> VacancyData:
    if not 1 <= data.positions <= 9999:
        raise ValidationFailedError("El número de posiciones debe estar entre 1 y 9999.")
    return VacancyData(
        name=_clean(data.name, "Nombre", 200),
        department=_clean(data.department, "Departamento", 120),
        location=_clean(data.location, "Ubicación", 120),
        work_mode=data.work_mode,
        contract_type=_clean(data.contract_type, "Tipo de contratación", 80),
        description=data.description.strip(),
        positions=data.positions,
        notes=(data.notes or "").strip() or None,
    )


class VacancyService:
    def __init__(
        self,
        vacancies: VacancyRepository,
        users: UserLookup,
        audit: AuditLog,
        clock: Clock,
        on_created: Callable[[Vacancy], None] | None = None,
    ) -> None:
        self._vacancies = vacancies
        self._users = users
        self._audit = audit
        self._clock = clock
        # Permite que otro módulo reaccione al alta (historial de responsables)
        # sin que este módulo lo conozca.
        self._on_created = on_created
        self._access = VacancyAccess(vacancies)

    # --- Vacantes --------------------------------------------------------------

    def create(self, actor: UserInfo, data: VacancyData, *, ip: str | None = None) -> VacancyView:
        data = _validated(data)
        now = self._clock()
        vacancy = Vacancy(
            id=new_sequential_uuid(),
            status=VacancyStatus.BORRADOR,
            owner_user_id=actor.id,
            created_at=now,
            created_by=actor.id,
            updated_at=now,
            updated_by=actor.id,
            **vars(data),
        )
        self._vacancies.add(vacancy)
        if self._on_created is not None:
            self._on_created(vacancy)
        self._audit.record(
            AuditAction.VACANTE_CREADA,
            actor_user_id=actor.id,
            resource_type="vacante",
            resource_id=vacancy.id,
            ip=ip,
        )
        return VacancyView(vacancy, AccessLevel.RESPONSABLE, self._users.get(actor.id))

    def get(self, actor: UserInfo, vacancy_id: uuid.UUID) -> VacancyView:
        vacancy, level = self._access.require(actor, vacancy_id, AccessLevel.LECTURA)
        return VacancyView(vacancy, level, self._users.get(vacancy.owner_user_id))

    def list(
        self,
        actor: UserInfo,
        *,
        scope: Scope,
        status: VacancyStatus | None,
        search: str | None,
        page: int,
        page_size: int,
    ) -> tuple[list[VacancyView], int]:
        if page < 1 or not 1 <= page_size <= MAX_PAGE_SIZE:
            raise ValidationFailedError("Paginación no válida.")
        # Solo un administrador puede listar sin filtro de acceso.
        unrestricted = actor.is_admin and scope is Scope.ALL
        rows, total = self._vacancies.search(
            viewer_id=None if unrestricted else actor.id,
            scope=scope,
            status=status,
            text=(search or "").strip() or None,
            offset=(page - 1) * page_size,
            limit=page_size,
        )
        owners = self._users.get_many([vacancy.owner_user_id for vacancy, _ in rows])
        views = []
        for vacancy, member_access in rows:
            level = effective_access(actor, vacancy, member_access)
            if level is None:  # Defensa adicional: nunca devolver lo que no se puede ver.
                continue
            views.append(VacancyView(vacancy, level, owners.get(vacancy.owner_user_id)))
        return views, total

    def update(
        self,
        actor: UserInfo,
        vacancy_id: uuid.UUID,
        data: VacancyData,
        *,
        expected_version: int,
        ip: str | None = None,
    ) -> VacancyView:
        vacancy, level = self._access.require(actor, vacancy_id, AccessLevel.RESPONSABLE)
        self._check_version(vacancy, expected_version)
        if vacancy.status is VacancyStatus.ARCHIVADA:
            raise ConflictError("Una vacante archivada no se puede modificar.")
        for field, value in vars(_validated(data)).items():
            setattr(vacancy, field, value)
        self._touch(vacancy, actor)
        self._vacancies.save(vacancy)
        self._audit.record(
            AuditAction.VACANTE_ACTUALIZADA,
            actor_user_id=actor.id,
            resource_type="vacante",
            resource_id=vacancy.id,
            ip=ip,
        )
        return VacancyView(vacancy, level, self._users.get(vacancy.owner_user_id))

    def change_status(
        self,
        actor: UserInfo,
        vacancy_id: uuid.UUID,
        new_status: VacancyStatus,
        *,
        expected_version: int,
        ip: str | None = None,
    ) -> VacancyView:
        vacancy, level = self._access.require(actor, vacancy_id, AccessLevel.RESPONSABLE)
        self._check_version(vacancy, expected_version)
        previous = vacancy.status
        if new_status not in ALLOWED_TRANSITIONS[previous]:
            raise ConflictError(
                f"Una vacante en estado {previous.value} no puede pasar a {new_status.value}."
            )
        now = self._clock()
        vacancy.status = new_status
        if new_status is VacancyStatus.ABIERTA:
            vacancy.opened_at = vacancy.opened_at or now
            vacancy.closed_at = None
        elif new_status in (VacancyStatus.CERRADA, VacancyStatus.CANCELADA):
            vacancy.closed_at = now
        self._touch(vacancy, actor)
        self._vacancies.save(vacancy)
        self._audit.record(
            AuditAction.VACANTE_ESTADO_CAMBIADO,
            actor_user_id=actor.id,
            resource_type="vacante",
            resource_id=vacancy.id,
            ip=ip,
            details={"de": previous.value, "a": new_status.value},
        )
        return VacancyView(vacancy, level, self._users.get(vacancy.owner_user_id))

    # --- Compartición ------------------------------------------------------------

    def members(self, actor: UserInfo, vacancy_id: uuid.UUID) -> list[MemberView]:
        self._access.require(actor, vacancy_id, AccessLevel.LECTURA)
        members = self._vacancies.active_members(vacancy_id)
        users = self._users.get_many([m.user_id for m in members])
        grants = self._vacancies.active_grants(vacancy_id=vacancy_id)
        return [
            MemberView(
                member=member,
                user=users.get(member.user_id),
                sensitive_classes=tuple(
                    sorted(g.document_class for g in grants if g.user_id == member.user_id)
                ),
            )
            for member in members
        ]

    def set_member(
        self,
        actor: UserInfo,
        vacancy_id: uuid.UUID,
        user_id: uuid.UUID,
        access_type: AccessType,
        *,
        ip: str | None = None,
    ) -> Member:
        """Comparte la vacante con ``user_id`` o cambia su tipo de acceso."""
        vacancy, _ = self._access.require(actor, vacancy_id, AccessLevel.RESPONSABLE)
        target = self._users.get(user_id)
        if target is None or not target.is_active:
            raise NotFoundError("El usuario no existe o está dado de baja.")
        if target.id == vacancy.owner_user_id:
            raise ConflictError("Esa persona ya es la responsable de la vacante.")

        member = self._vacancies.active_member(vacancy_id, user_id)
        if member is None:
            member = Member(
                id=new_sequential_uuid(),
                vacancy_id=vacancy_id,
                user_id=user_id,
                access_type=access_type,
                granted_by=actor.id,
                granted_at=self._clock(),
            )
            self._vacancies.add_member(member)
            action = AuditAction.VACANTE_COMPARTIDA
        elif member.access_type is not access_type:
            member.access_type = access_type
            self._vacancies.save_member(member)
            action = AuditAction.VACANTE_ACCESO_MODIFICADO
        else:
            return member
        self._audit.record(
            action,
            actor_user_id=actor.id,
            resource_type="vacante",
            resource_id=vacancy_id,
            ip=ip,
            details={"usuario": str(user_id), "acceso": access_type.value},
        )
        return member

    def revoke_member(
        self, actor: UserInfo, vacancy_id: uuid.UUID, user_id: uuid.UUID, *, ip: str | None = None
    ) -> None:
        """Revoca el acceso. Surte efecto en la siguiente petición del usuario."""
        self._access.require(actor, vacancy_id, AccessLevel.RESPONSABLE)
        member = self._vacancies.active_member(vacancy_id, user_id)
        if member is None:
            raise NotFoundError("Esa persona no tiene acceso a la vacante.")
        now = self._clock()
        member.revoked_at, member.revoked_by = now, actor.id
        self._vacancies.save_member(member)
        for grant in self._vacancies.active_grants(vacancy_id=vacancy_id, user_id=user_id):
            grant.revoked_at, grant.revoked_by = now, actor.id
            self._vacancies.save_grant(grant)
        self._audit.record(
            AuditAction.VACANTE_ACCESO_REVOCADO,
            actor_user_id=actor.id,
            resource_type="vacante",
            resource_id=vacancy_id,
            ip=ip,
            details={"usuario": str(user_id)},
        )

    def set_sensitive_grants(
        self,
        actor: UserInfo,
        vacancy_id: uuid.UUID,
        user_id: uuid.UUID,
        classes: set[SensitiveClass],
        *,
        ip: str | None = None,
    ) -> list[SensitiveClass]:
        """Deja exactamente ``classes`` como permisos adicionales del colaborador.

        Compartir la vacante no concede acceso a psicometría ni a estudios
        socioeconómicos: hay que otorgarlo aquí, por persona y por clase.
        """
        self._access.require(actor, vacancy_id, AccessLevel.RESPONSABLE)
        if self._vacancies.active_member(vacancy_id, user_id) is None:
            raise NotFoundError("Esa persona no tiene acceso a la vacante.")
        now = self._clock()
        current = {
            g.document_class: g
            for g in self._vacancies.active_grants(vacancy_id=vacancy_id, user_id=user_id)
        }
        changed = False
        for document_class in classes - current.keys():
            self._vacancies.add_grant(
                SensitiveGrant(
                    id=new_sequential_uuid(),
                    vacancy_id=vacancy_id,
                    user_id=user_id,
                    document_class=document_class,
                    granted_by=actor.id,
                    granted_at=now,
                )
            )
            changed = True
        for document_class in current.keys() - classes:
            grant = current[document_class]
            grant.revoked_at, grant.revoked_by = now, actor.id
            self._vacancies.save_grant(grant)
            changed = True
        if changed:
            self._audit.record(
                AuditAction.VACANTE_PERMISO_SENSIBLE,
                actor_user_id=actor.id,
                resource_type="vacante",
                resource_id=vacancy_id,
                ip=ip,
                details={"usuario": str(user_id), "clases": sorted(c.value for c in classes)},
            )
        return sorted(classes)

    # --- Apoyo -------------------------------------------------------------------

    @staticmethod
    def _check_version(vacancy: Vacancy, expected_version: int) -> None:
        if vacancy.version != expected_version:
            raise ConflictError(
                "Otra persona modificó esta vacante. Vuelve a cargarla antes de guardar."
            )

    def _touch(self, vacancy: Vacancy, actor: UserInfo) -> None:
        vacancy.updated_at = self._clock()
        vacancy.updated_by = actor.id
