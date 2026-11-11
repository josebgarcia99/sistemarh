"""Transferencia individual y transferencia masiva por baja de un reclutador.

Transferir cambia al responsable; no mueve ni borra ningún dato de la vacante.
La autoría de las acciones pasadas no cambia y el usuario saliente no se borra.
Solo un administrador transfiere.
"""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass

from app.core.clock import Clock
from app.core.exceptions.errors import (
    ConflictError,
    NotFoundError,
    PermissionDeniedError,
    ValidationFailedError,
)
from app.core.ids import new_sequential_uuid
from app.modules.audit.application.service import AuditLog
from app.modules.audit.domain.models import AuditAction
from app.modules.users.application.service import UserService
from app.modules.users.domain.models import User
from app.modules.users.domain.repository import UserRepository
from app.modules.vacancies.application.access import VacancyAccess
from app.modules.vacancies.domain.models import (
    AccessLevel,
    AccessType,
    Member,
    Vacancy,
    VacancyRepository,
)
from app.modules.vacancy_transfers.domain.models import (
    OwnershipChange,
    Transfer,
    TransferKind,
    TransferRepository,
)

MAX_REASON_LENGTH = 500


@dataclass(frozen=True)
class MassPreview:
    from_user: User
    to_user: User
    vacancies: list[Vacancy]
    memberships_to_revoke: int
    grants_to_revoke: int
    # Huella del estado mostrado. La confirmación debe devolverla: si los datos
    # cambiaron entre la vista previa y la confirmación, se exige repetirla.
    token: str


def _reason(text: str) -> str:
    reason = " ".join(text.split())
    if not reason:
        raise ValidationFailedError("El motivo de la transferencia es obligatorio.")
    if len(reason) > MAX_REASON_LENGTH:
        raise ValidationFailedError(f"El motivo no puede superar {MAX_REASON_LENGTH} caracteres.")
    return reason


class TransferService:
    def __init__(
        self,
        vacancies: VacancyRepository,
        transfers: TransferRepository,
        users: UserRepository,
        user_service: UserService,
        audit: AuditLog,
        clock: Clock,
    ) -> None:
        self._vacancies = vacancies
        self._transfers = transfers
        self._users = users
        self._user_service = user_service
        self._audit = audit
        self._clock = clock

    # --- Historial ---------------------------------------------------------------

    def record_creation(self, vacancy: Vacancy) -> None:
        """Primer registro del historial: quién fue el responsable inicial."""
        self._transfers.add_change(
            OwnershipChange(
                id=new_sequential_uuid(),
                vacancy_id=vacancy.id,
                previous_owner_id=None,
                new_owner_id=vacancy.owner_user_id,
                changed_at=vacancy.created_at,
                reason="Creación de la vacante",
                authorized_by=vacancy.created_by,
            )
        )

    def history(self, actor: User, vacancy_id: uuid.UUID) -> list[OwnershipChange]:
        VacancyAccess(self._vacancies).require(actor, vacancy_id, AccessLevel.LECTURA)
        return self._transfers.changes_for(vacancy_id)

    # --- Transferencia individual --------------------------------------------------

    def transfer(
        self,
        actor: User,
        vacancy_id: uuid.UUID,
        *,
        to_user_id: uuid.UUID,
        reason: str,
        keep_previous_as_collaborator: bool = False,
        ip: str | None = None,
    ) -> Vacancy:
        self._require_admin(actor)
        reason = _reason(reason)
        vacancy = self._vacancies.get(vacancy_id)
        if vacancy is None:
            raise NotFoundError("La vacante no existe.")
        new_owner = self._active_target(to_user_id)
        if new_owner.id == vacancy.owner_user_id:
            raise ConflictError("Esa persona ya es la responsable de la vacante.")

        previous_owner_id = vacancy.owner_user_id
        now = self._clock()
        self._move(vacancy, new_owner, actor, reason, transfer_id=None)
        if keep_previous_as_collaborator:
            previous = self._users.get(previous_owner_id)
            if previous is not None and previous.is_active:
                self._vacancies.add_member(
                    Member(
                        id=new_sequential_uuid(),
                        vacancy_id=vacancy.id,
                        user_id=previous_owner_id,
                        access_type=AccessType.COLABORACION,
                        granted_by=actor.id,
                        granted_at=now,
                    )
                )
        self._audit.record(
            AuditAction.VACANTE_TRANSFERIDA,
            actor_user_id=actor.id,
            resource_type="vacante",
            resource_id=vacancy.id,
            ip=ip,
            details={
                "de": str(previous_owner_id),
                "a": str(new_owner.id),
                "anterior_queda_como_colaborador": keep_previous_as_collaborator,
            },
        )
        return vacancy

    # --- Transferencia masiva --------------------------------------------------------

    def preview_mass(
        self, actor: User, *, from_user_id: uuid.UUID, to_user_id: uuid.UUID
    ) -> MassPreview:
        self._require_admin(actor)
        if from_user_id == to_user_id:
            raise ValidationFailedError("El usuario saliente y el receptor deben ser distintos.")
        if from_user_id == actor.id:
            raise ConflictError("No puedes darte de baja a ti mismo.")
        from_user = self._users.get(from_user_id)
        if from_user is None:
            raise NotFoundError("El usuario saliente no existe.")
        to_user = self._active_target(to_user_id)

        vacancies = self._vacancies.owned_by(from_user_id)
        memberships = self._vacancies.memberships_of(from_user_id)
        grants = self._vacancies.active_grants(user_id=from_user_id)
        fingerprint = "|".join(
            [
                str(from_user_id),
                str(to_user_id),
                str(from_user.is_active),
                *sorted(f"v:{v.id}:{v.version}" for v in vacancies),
                *sorted(f"m:{m.id}" for m in memberships),
                *sorted(f"g:{g.id}" for g in grants),
            ]
        )
        return MassPreview(
            from_user=from_user,
            to_user=to_user,
            vacancies=vacancies,
            memberships_to_revoke=len(memberships),
            grants_to_revoke=len(grants),
            token=hashlib.sha256(fingerprint.encode("utf-8")).hexdigest(),
        )

    def execute_mass(
        self,
        actor: User,
        *,
        operation_id: uuid.UUID,
        from_user_id: uuid.UUID,
        to_user_id: uuid.UUID,
        reason: str,
        preview_token: str,
        ip: str | None = None,
    ) -> Transfer:
        """Transfiere todo lo del usuario saliente y lo da de baja.

        Corre dentro de una sola transacción: o se aplica completa o no cambia
        nada. Repetirla con el mismo ``operation_id`` devuelve el resultado ya
        registrado, sin duplicar nada.
        """
        self._require_admin(actor)
        existing = self._transfers.get_transfer(operation_id)
        if existing is not None:
            if (existing.from_user_id, existing.to_user_id) != (from_user_id, to_user_id):
                raise ConflictError("Ese identificador de operación ya se usó para otra baja.")
            return existing

        reason = _reason(reason)
        preview = self.preview_mass(actor, from_user_id=from_user_id, to_user_id=to_user_id)
        if preview.token != preview_token:
            raise ConflictError(
                "Los datos cambiaron desde la vista previa. Revísala de nuevo antes de confirmar."
            )

        now = self._clock()
        memberships = self._vacancies.memberships_of(from_user_id)
        grants = self._vacancies.active_grants(user_id=from_user_id)

        # La operación se registra primero: el historial de cada vacante la referencia.
        transfer = Transfer(
            id=operation_id,
            kind=TransferKind.MASIVA,
            from_user_id=from_user_id,
            to_user_id=to_user_id,
            reason=reason,
            requested_by=actor.id,
            completed_at=now,
            vacancies_transferred=len(preview.vacancies),
            memberships_revoked=len(memberships),
            grants_revoked=len(grants),
            user_deactivated=preview.from_user.is_active,
        )
        self._transfers.add_transfer(transfer)

        for vacancy in preview.vacancies:
            self._move(vacancy, preview.to_user, actor, reason, transfer_id=operation_id)
        for member in memberships:
            member.revoked_at, member.revoked_by = now, actor.id
            self._vacancies.save_member(member)
        for grant in grants:
            grant.revoked_at, grant.revoked_by = now, actor.id
            self._vacancies.save_grant(grant)

        # Aplica las reglas de baja: no a uno mismo y siempre queda un administrador.
        self._user_service.deactivate(actor, from_user_id, ip=ip)

        self._audit.record(
            AuditAction.TRANSFERENCIA_MASIVA,
            actor_user_id=actor.id,
            resource_type="usuario",
            resource_id=from_user_id,
            ip=ip,
            details={
                "operacion": str(operation_id),
                "receptor": str(to_user_id),
                "vacantes": len(preview.vacancies),
                "accesos_revocados": len(memberships),
                "permisos_sensibles_revocados": len(grants),
            },
        )
        return transfer

    # --- Apoyo -----------------------------------------------------------------------

    @staticmethod
    def _require_admin(actor: User) -> None:
        if not actor.is_admin:
            raise PermissionDeniedError("Solo un administrador puede transferir vacantes.")

    def _active_target(self, user_id: uuid.UUID) -> User:
        user = self._users.get(user_id)
        if user is None or not user.is_active:
            raise ConflictError("El usuario receptor no existe o está dado de baja.")
        return user

    def _move(
        self,
        vacancy: Vacancy,
        new_owner: User,
        actor: User,
        reason: str,
        *,
        transfer_id: uuid.UUID | None,
    ) -> None:
        now = self._clock()
        previous_owner_id = vacancy.owner_user_id
        # Si el nuevo responsable era colaborador, ese acceso ya no hace falta.
        membership = self._vacancies.active_member(vacancy.id, new_owner.id)
        if membership is not None:
            membership.revoked_at, membership.revoked_by = now, actor.id
            self._vacancies.save_member(membership)
        vacancy.owner_user_id = new_owner.id
        vacancy.updated_at, vacancy.updated_by = now, actor.id
        self._vacancies.save(vacancy)
        self._transfers.add_change(
            OwnershipChange(
                id=new_sequential_uuid(),
                vacancy_id=vacancy.id,
                previous_owner_id=previous_owner_id,
                new_owner_id=new_owner.id,
                changed_at=now,
                reason=reason,
                authorized_by=actor.id,
                transfer_id=transfer_id,
            )
        )
