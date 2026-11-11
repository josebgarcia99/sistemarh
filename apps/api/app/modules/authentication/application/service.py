"""Inicio de sesión, validación de sesión y cierre."""

from __future__ import annotations

from dataclasses import dataclass

from app.core.clock import Clock
from app.core.exceptions.errors import NotAuthenticatedError
from app.core.ids import new_sequential_uuid
from app.core.security.passwords import PasswordHasher
from app.core.security.tokens import generate_token, hash_token
from app.modules.audit.application.service import AuditLog
from app.modules.audit.domain.models import AuditAction, AuditResult
from app.modules.authentication.domain.models import AuthPolicy, AuthSession, SessionRepository
from app.modules.users.domain.models import User
from app.modules.users.domain.repository import UserRepository

MAX_USER_AGENT_LENGTH = 300


@dataclass(frozen=True)
class LoginSuccess:
    token: str
    session: AuthSession
    user: User


class AuthService:
    def __init__(
        self,
        users: UserRepository,
        sessions: SessionRepository,
        audit: AuditLog,
        hasher: PasswordHasher,
        clock: Clock,
        policy: AuthPolicy,
    ) -> None:
        self._users = users
        self._sessions = sessions
        self._audit = audit
        self._hasher = hasher
        self._clock = clock
        self._policy = policy

    def login(
        self, email: str, password: str, *, ip: str | None, user_agent: str | None
    ) -> LoginSuccess | None:
        """Devuelve la sesión creada, o ``None`` si las credenciales no valen.

        No lanza excepción en el fallo para que el contador de intentos y el
        evento de auditoría se confirmen en la misma transacción.
        """
        now = self._clock()
        user = self._users.get_by_email(email.strip().lower())

        if user is None:
            self._hasher.verify_dummy(password)
            self._fail(None, "usuario_desconocido", ip)
            return None
        if user.is_locked(now):
            self._fail(user, "cuenta_bloqueada", ip)
            return None
        if not user.is_active:
            self._hasher.verify_dummy(password)
            self._fail(user, "cuenta_inactiva", ip)
            return None

        if not self._hasher.verify(user.password_hash, password):
            user.failed_login_count += 1
            reason = "contrasena_incorrecta"
            if user.failed_login_count >= self._policy.max_failed_attempts:
                user.locked_until = now + self._policy.lock_duration
                user.failed_login_count = 0
                reason = "bloqueo_por_intentos"
            self._users.save(user)
            self._fail(user, reason, ip)
            return None

        user.failed_login_count = 0
        user.locked_until = None
        user.last_activity_at = now
        if self._hasher.needs_rehash(user.password_hash):
            user.password_hash = self._hasher.hash(password)
        self._users.save(user)

        token = generate_token()
        session = AuthSession(
            id=new_sequential_uuid(),
            user_id=user.id,
            token_hash=hash_token(token),
            csrf_token=generate_token(),
            created_at=now,
            last_seen_at=now,
            expires_at=now + self._policy.absolute_timeout,
            ip=ip,
            user_agent=(user_agent or "")[:MAX_USER_AGENT_LENGTH] or None,
        )
        self._sessions.add(session)
        self._audit.record(
            AuditAction.SESION_INICIO,
            actor_user_id=user.id,
            resource_type="sesion",
            resource_id=session.id,
            ip=ip,
        )
        return LoginSuccess(token=token, session=session, user=user)

    def resolve(self, token: str | None) -> tuple[AuthSession, User]:
        """Valida el token de la cookie. Lanza ``NotAuthenticatedError`` si no vale."""
        if not token:
            raise NotAuthenticatedError()
        now = self._clock()
        session = self._sessions.get_by_token_hash(hash_token(token))
        if session is None or not session.is_valid(now, self._policy.idle_timeout):
            raise NotAuthenticatedError()
        user = self._users.get(session.user_id)
        if user is None or not user.is_active:
            raise NotAuthenticatedError()
        if now - session.last_seen_at >= self._policy.touch_interval:
            session.last_seen_at = now
            self._sessions.save(session)
            user.last_activity_at = now
            self._users.save(user)
        return session, user

    def logout(self, session: AuthSession, *, ip: str | None) -> None:
        session.revoked_at = self._clock()
        self._sessions.save(session)
        self._audit.record(
            AuditAction.SESION_CIERRE,
            actor_user_id=session.user_id,
            resource_type="sesion",
            resource_id=session.id,
            ip=ip,
        )

    def _fail(self, user: User | None, reason: str, ip: str | None) -> None:
        # No se guarda el correo tecleado: podría ser un dato de un tercero o
        # incluso una contraseña escrita en el campo equivocado.
        self._audit.record(
            AuditAction.SESION_INICIO_FALLIDO,
            result=AuditResult.FALLIDO,
            actor_user_id=user.id if user else None,
            resource_type="usuario" if user else None,
            resource_id=user.id if user else None,
            ip=ip,
            details={"motivo": reason},
        )
