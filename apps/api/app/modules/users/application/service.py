"""Administración de usuarios.

Solo el administrador crea usuarios y restablece contraseñas. El sistema no
envía correos: la contraseña la define el administrador y el usuario la
conserva hasta que el administrador la cambie.
"""

from __future__ import annotations

import uuid

from app.core.clock import Clock
from app.core.exceptions.errors import ConflictError, NotFoundError, ValidationFailedError
from app.core.ids import new_sequential_uuid
from app.core.security.passwords import PasswordHasher, validate_password
from app.modules.audit.application.service import AuditLog
from app.modules.audit.domain.models import AuditAction
from app.modules.users.domain.models import Role, User, normalize_email, normalize_full_name
from app.modules.users.domain.repository import SessionRevoker, UserRepository

MAX_PAGE_SIZE = 100


class UserService:
    def __init__(
        self,
        users: UserRepository,
        sessions: SessionRevoker,
        audit: AuditLog,
        hasher: PasswordHasher,
        clock: Clock,
    ) -> None:
        self._users = users
        self._sessions = sessions
        self._audit = audit
        self._hasher = hasher
        self._clock = clock

    # --- Altas -----------------------------------------------------------------

    def create_master_user(self, *, email: str, full_name: str, password: str) -> User:
        """Crea el primer administrador. Solo funciona si no existe ninguno activo."""
        if self._users.count_active_admins() > 0:
            raise ConflictError(
                "Ya existe un administrador. Los demás usuarios se crean desde la aplicación."
            )
        return self._create(
            email=email,
            full_name=full_name,
            password=password,
            role=Role.ADMINISTRADOR,
            actor=None,
            ip=None,
            details={"origen": "comando_de_instalacion"},
        )

    def create_user(
        self,
        actor: User,
        *,
        email: str,
        full_name: str,
        password: str,
        role: Role,
        ip: str | None = None,
    ) -> User:
        return self._create(
            email=email,
            full_name=full_name,
            password=password,
            role=role,
            actor=actor,
            ip=ip,
            details={},
        )

    def _create(
        self,
        *,
        email: str,
        full_name: str,
        password: str,
        role: Role,
        actor: User | None,
        ip: str | None,
        details: dict[str, str],
    ) -> User:
        email = normalize_email(email)
        full_name = normalize_full_name(full_name)
        validate_password(password, email=email)
        if self._users.get_by_email(email) is not None:
            raise ConflictError("Ya existe un usuario con ese correo.")
        now = self._clock()
        user = User(
            id=new_sequential_uuid(),
            email=email,
            full_name=full_name,
            role=role,
            password_hash=self._hasher.hash(password),
            is_active=True,
            created_at=now,
            created_by=actor.id if actor else None,
            password_changed_at=now,
        )
        self._users.add(user)
        self._audit.record(
            AuditAction.USUARIO_CREADO,
            actor_user_id=actor.id if actor else None,
            resource_type="usuario",
            resource_id=user.id,
            ip=ip,
            details={"rol": role.value, **details},
        )
        return user

    # --- Consultas -------------------------------------------------------------

    def get(self, user_id: uuid.UUID) -> User:
        user = self._users.get(user_id)
        if user is None:
            raise NotFoundError("El usuario no existe.")
        return user

    def list(self, *, search: str | None, page: int, page_size: int) -> tuple[list[User], int]:
        if page < 1 or not 1 <= page_size <= MAX_PAGE_SIZE:
            raise ValidationFailedError("Paginación no válida.")
        search = search.strip() if search else None
        return self._users.list(
            search=search or None, offset=(page - 1) * page_size, limit=page_size
        )

    # --- Cambios ---------------------------------------------------------------

    def update(
        self,
        actor: User,
        user_id: uuid.UUID,
        *,
        full_name: str | None = None,
        role: Role | None = None,
        ip: str | None = None,
    ) -> User:
        user = self.get(user_id)
        changes: dict[str, str] = {}
        if full_name is not None:
            new_name = normalize_full_name(full_name)
            if new_name != user.full_name:
                user.full_name = new_name
                changes["nombre"] = "actualizado"
        if role is not None and role is not user.role:
            if user.id == actor.id:
                raise ConflictError("No puedes cambiar tu propio rol.")
            if user.is_admin and user.is_active:
                self._ensure_another_admin_remains()
            changes["rol"] = f"{user.role.value} -> {role.value}"
            user.role = role
        if changes:
            self._users.save(user)
            self._audit.record(
                AuditAction.USUARIO_ACTUALIZADO,
                actor_user_id=actor.id,
                resource_type="usuario",
                resource_id=user.id,
                ip=ip,
                details=changes,
            )
        return user

    def reset_password(
        self, actor: User, user_id: uuid.UUID, *, new_password: str, ip: str | None = None
    ) -> int:
        """Asigna una contraseña nueva y cierra las sesiones del usuario.

        Devuelve cuántas sesiones se cerraron.
        """
        user = self.get(user_id)
        validate_password(new_password, email=user.email)
        now = self._clock()
        user.password_hash = self._hasher.hash(new_password)
        user.password_changed_at = now
        user.failed_login_count = 0
        user.locked_until = None
        self._users.save(user)
        closed = self._sessions.revoke_all_for_user(user.id, now)
        self._audit.record(
            AuditAction.USUARIO_CONTRASENA_RESTABLECIDA,
            actor_user_id=actor.id,
            resource_type="usuario",
            resource_id=user.id,
            ip=ip,
            details={"sesiones_cerradas": closed},
        )
        return closed

    def deactivate(self, actor: User, user_id: uuid.UUID, *, ip: str | None = None) -> User:
        user = self.get(user_id)
        if user.id == actor.id:
            raise ConflictError("No puedes desactivar tu propia cuenta.")
        if not user.is_active:
            return user
        if user.is_admin:
            self._ensure_another_admin_remains()
        now = self._clock()
        user.is_active = False
        user.deactivated_at = now
        self._users.save(user)
        closed = self._sessions.revoke_all_for_user(user.id, now)
        self._audit.record(
            AuditAction.USUARIO_DESACTIVADO,
            actor_user_id=actor.id,
            resource_type="usuario",
            resource_id=user.id,
            ip=ip,
            details={"sesiones_cerradas": closed},
        )
        return user

    def activate(self, actor: User, user_id: uuid.UUID, *, ip: str | None = None) -> User:
        user = self.get(user_id)
        if user.is_active:
            return user
        user.is_active = True
        user.deactivated_at = None
        user.failed_login_count = 0
        user.locked_until = None
        self._users.save(user)
        self._audit.record(
            AuditAction.USUARIO_ACTIVADO,
            actor_user_id=actor.id,
            resource_type="usuario",
            resource_id=user.id,
            ip=ip,
        )
        return user

    def _ensure_another_admin_remains(self) -> None:
        if self._users.count_active_admins() <= 1:
            raise ConflictError("Debe quedar al menos un administrador activo.")
