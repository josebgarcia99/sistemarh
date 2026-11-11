"""Reglas de la configuración de IA. Solo administradores."""

from __future__ import annotations

import uuid
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from app.core.exceptions.errors import (
    ConflictError,
    NotFoundError,
    PermissionDeniedError,
    ServiceUnavailableError,
    ValidationFailedError,
)
from app.core.ids import new_sequential_uuid
from app.modules.ai_settings.domain.models import (
    AiRepository,
    Assignment,
    Credential,
    KeySource,
    Model,
    Operation,
    Provider,
    ProviderClient,
    ProviderCode,
    ProviderError,
    TextCipher,
)
from app.modules.audit.application.service import AuditLog
from app.modules.audit.domain.models import AuditAction, AuditResult

RESOURCE = "proveedor_ia"
_MIN_KEY_LENGTH = 20
_MAX_KEY_LENGTH = 500


class Actor:
    id: uuid.UUID
    is_admin: bool


@dataclass(frozen=True)
class ProviderView:
    provider: Provider
    key_source: KeySource | None
    key_mask: str | None
    key_updated_at: datetime | None
    key_updated_by: uuid.UUID | None
    models_available: int


@dataclass(frozen=True)
class TestResult:
    __test__ = False  # no es una clase de pruebas

    ok: bool
    error: str | None
    models_found: int


@dataclass(frozen=True)
class ResolvedModel:
    """Lo necesario para ejecutar una operación. La clave no se guarda ni se registra."""

    provider_code: ProviderCode
    model_id: str
    api_key: str


def _mask(last4: str) -> str:
    return f"••••{last4}"


def _context(code: ProviderCode) -> str:
    # Liga el texto cifrado a su proveedor.
    return f"ai-provider:{code.value}"


class AiSettingsService:
    def __init__(
        self,
        repository: AiRepository,
        audit: AuditLog,
        clock: Callable[[], datetime],
        *,
        cipher: TextCipher | None,
        clients: Mapping[ProviderCode, ProviderClient],
        env_keys: Mapping[ProviderCode, str],
    ) -> None:
        self._repo = repository
        self._audit = audit
        self._clock = clock
        self._cipher = cipher
        self._clients = clients
        self._env_keys = env_keys

    @staticmethod
    def _require_admin(actor: Actor) -> None:
        if not actor.is_admin:
            raise PermissionDeniedError("La configuración de IA es solo para administradores.")

    # --- Consulta ------------------------------------------------------------------------

    def _view(self, code: ProviderCode) -> ProviderView:
        provider = self._repo.get_provider(code)
        available = sum(1 for model in self._repo.list_models(code) if model.is_available)
        env_key = self._env_keys.get(code)
        if env_key:
            return ProviderView(
                provider, KeySource.ENTORNO, _mask(env_key[-4:]), None, None, available
            )
        credential = self._repo.active_credential(code)
        if credential is None:
            return ProviderView(provider, None, None, None, None, available)
        return ProviderView(
            provider,
            KeySource.PANTALLA,
            _mask(credential.last4),
            credential.created_at,
            credential.created_by,
            available,
        )

    def overview(self, actor: Actor) -> list[ProviderView]:
        self._require_admin(actor)
        return [self._view(code) for code in ProviderCode]

    def models(self, actor: Actor, code: ProviderCode | None = None) -> list[Model]:
        self._require_admin(actor)
        return self._repo.list_models(code)

    def assignments(self, actor: Actor) -> list[tuple[Assignment, Model | None]]:
        self._require_admin(actor)
        result = []
        for operation in Operation:
            assignment = self._repo.get_assignment(operation)
            model = self._repo.get_model(assignment.model_ref) if assignment.model_ref else None
            result.append((assignment, model))
        return result

    # --- Claves --------------------------------------------------------------------------

    def set_key(
        self, actor: Actor, code: ProviderCode, api_key: str, *, ip: str | None = None
    ) -> ProviderView:
        self._require_admin(actor)
        if self._env_keys.get(code):
            raise ConflictError(
                "La clave de este proveedor la define Sistemas en el servidor; "
                "no se puede cambiar desde la pantalla."
            )
        if self._cipher is None:
            raise ServiceUnavailableError(
                "La clave maestra no está configurada, así que no se puede guardar "
                "una API key de forma segura. Avisa a Sistemas."
            )
        api_key = api_key.strip()
        if (
            not _MIN_KEY_LENGTH <= len(api_key) <= _MAX_KEY_LENGTH
            or any(ch.isspace() for ch in api_key)
            or not api_key.isprintable()
        ):
            # El mensaje no repite lo que se escribió.
            raise ValidationFailedError("La API key no tiene un formato válido.")

        now = self._clock()
        previous = self._repo.active_credential(code)
        if previous is not None:
            previous.ciphertext = None
            previous.revoked_at = now
            previous.revoked_by = actor.id
            self._repo.save_credential(previous)
        self._repo.add_credential(
            Credential(
                id=new_sequential_uuid(),
                provider_code=code,
                ciphertext=self._cipher.encrypt_text(api_key, context=_context(code)),
                last4=api_key[-4:],
                master_key_id=self._cipher.key_id,
                created_at=now,
                created_by=actor.id,
            )
        )
        provider = self._repo.get_provider(code)
        # Una clave nueva todavía no se ha probado.
        provider.last_test_at = provider.last_test_ok = provider.last_test_error = None
        self._touch(provider, actor, now)
        self._audit.record(
            AuditAction.IA_CLAVE_REGISTRADA,
            actor_user_id=actor.id,
            resource_type=RESOURCE,
            resource_id=code.value,
            ip=ip,
            details={"terminacion": api_key[-4:], "sustituye_a_otra": previous is not None},
        )
        return self._view(code)

    def revoke_key(
        self, actor: Actor, code: ProviderCode, *, ip: str | None = None
    ) -> ProviderView:
        self._require_admin(actor)
        if self._env_keys.get(code):
            raise ConflictError(
                "La clave de este proveedor la define Sistemas en el servidor; "
                "no se puede revocar desde la pantalla."
            )
        credential = self._repo.active_credential(code)
        if credential is None:
            raise NotFoundError("Este proveedor no tiene una API key registrada.")
        now = self._clock()
        credential.ciphertext = None
        credential.revoked_at = now
        credential.revoked_by = actor.id
        self._repo.save_credential(credential)
        provider = self._repo.get_provider(code)
        provider.enabled = False
        provider.last_test_at = provider.last_test_ok = provider.last_test_error = None
        self._touch(provider, actor, now)
        self._audit.record(
            AuditAction.IA_CLAVE_REVOCADA,
            actor_user_id=actor.id,
            resource_type=RESOURCE,
            resource_id=code.value,
            ip=ip,
            details={"terminacion": credential.last4},
        )
        return self._view(code)

    def _api_key(self, code: ProviderCode) -> str | None:
        env_key = self._env_keys.get(code)
        if env_key:
            return env_key
        credential = self._repo.active_credential(code)
        if credential is None or credential.ciphertext is None:
            return None
        if self._cipher is None or self._cipher.key_id != credential.master_key_id:
            raise ServiceUnavailableError(
                "La API key está cifrada con una clave maestra que no está disponible. "
                "Avisa a Sistemas."
            )
        return self._cipher.decrypt_text(credential.ciphertext, context=_context(code))

    # --- Conexión y modelos --------------------------------------------------------------

    def test_connection(
        self, actor: Actor, code: ProviderCode, *, ip: str | None = None
    ) -> TestResult:
        """Pide al proveedor su lista de modelos. No envía ningún documento."""
        self._require_admin(actor)
        api_key = self._api_key(code)
        if api_key is None:
            raise ValidationFailedError("Registra primero una API key para este proveedor.")
        now = self._clock()
        provider = self._repo.get_provider(code)
        try:
            discovered = self._clients[code].list_models(api_key)
        except ProviderError as error:
            provider.last_test_at, provider.last_test_ok = now, False
            provider.last_test_error = error.message[:300]
            self._touch(provider, actor, now)
            self._audit.record(
                AuditAction.IA_CONEXION_PROBADA,
                result=AuditResult.FALLIDO,
                actor_user_id=actor.id,
                resource_type=RESOURCE,
                resource_id=code.value,
                ip=ip,
                details={"motivo": error.kind},
            )
            return TestResult(ok=False, error=error.message, models_found=0)

        known = {model.model_id: model for model in self._repo.list_models(code)}
        seen = set()
        for item in discovered:
            seen.add(item.model_id)
            model = known.get(item.model_id)
            if model is None:
                self._repo.add_model(
                    Model(
                        id=new_sequential_uuid(),
                        provider_code=code,
                        model_id=item.model_id[:200],
                        display_name=(item.display_name or item.model_id)[:200],
                        capabilities=item.capabilities,
                        is_available=True,
                        first_seen_at=now,
                        last_seen_at=now,
                    )
                )
            else:
                model.display_name = (item.display_name or item.model_id)[:200]
                model.capabilities = item.capabilities
                model.is_available = True
                model.last_seen_at = now
                self._repo.save_model(model)
        for model_id, model in known.items():
            if model_id not in seen and model.is_available:
                model.is_available = False
                self._repo.save_model(model)

        provider.last_test_at, provider.last_test_ok, provider.last_test_error = now, True, None
        self._touch(provider, actor, now)
        self._audit.record(
            AuditAction.IA_CONEXION_PROBADA,
            actor_user_id=actor.id,
            resource_type=RESOURCE,
            resource_id=code.value,
            ip=ip,
            details={"modelos": len(seen)},
        )
        return TestResult(ok=True, error=None, models_found=len(seen))

    # --- Ajustes -------------------------------------------------------------------------

    def _touch(self, provider: Provider, actor: Actor, now: datetime) -> None:
        provider.updated_at = now
        provider.updated_by = actor.id
        self._repo.save_provider(provider)

    def update_provider(
        self,
        actor: Actor,
        code: ProviderCode,
        *,
        enabled: bool,
        monthly_limit_usd: Decimal | None,
        ip: str | None = None,
    ) -> ProviderView:
        self._require_admin(actor)
        provider = self._repo.get_provider(code)
        if enabled and self._view(code).key_source is None:
            raise ValidationFailedError("Para habilitar el proveedor, registra primero su API key.")
        if monthly_limit_usd is not None and not Decimal(0) <= monthly_limit_usd <= Decimal(
            "1000000"
        ):
            raise ValidationFailedError("El límite mensual debe estar entre 0 y 1,000,000 USD.")
        provider.enabled = enabled
        provider.monthly_limit_usd = monthly_limit_usd
        self._touch(provider, actor, self._clock())
        self._audit.record(
            AuditAction.IA_PROVEEDOR_ACTUALIZADO,
            actor_user_id=actor.id,
            resource_type=RESOURCE,
            resource_id=code.value,
            ip=ip,
            details={
                "habilitado": enabled,
                "limite_mensual_usd": str(monthly_limit_usd)
                if monthly_limit_usd is not None
                else None,
            },
        )
        return self._view(code)

    def assign(
        self,
        actor: Actor,
        operation: Operation,
        model_ref: uuid.UUID | None,
        *,
        ip: str | None = None,
    ) -> tuple[Assignment, Model | None]:
        self._require_admin(actor)
        model = None
        if model_ref is not None:
            model = self._repo.get_model(model_ref)
            if model is None:
                raise NotFoundError("El modelo no existe.")
            if not model.is_available:
                raise ValidationFailedError("El proveedor ya no ofrece ese modelo.")
            if not self._repo.get_provider(model.provider_code).enabled:
                raise ValidationFailedError("El proveedor de ese modelo no está habilitado.")
        assignment = self._repo.get_assignment(operation)
        assignment.model_ref = model_ref
        assignment.updated_at = self._clock()
        assignment.updated_by = actor.id
        self._repo.save_assignment(assignment)
        self._audit.record(
            AuditAction.IA_MODELO_ASIGNADO,
            actor_user_id=actor.id,
            resource_type="operacion_ia",
            resource_id=operation.value,
            ip=ip,
            details={
                "proveedor": model.provider_code.value if model else None,
                "modelo": model.model_id if model else None,
            },
        )
        return assignment, model

    # --- Uso por otras partes del sistema ------------------------------------------------

    def resolve(self, operation: Operation) -> ResolvedModel:
        """Modelo y clave para ejecutar una operación. Se valida en el momento de usarlo."""
        assignment = self._repo.get_assignment(operation)
        model = self._repo.get_model(assignment.model_ref) if assignment.model_ref else None
        if model is None:
            raise ValidationFailedError(
                "Esta operación no tiene un modelo asignado. Pídele al administrador "
                "que lo configure en Configuración de IA."
            )
        if not model.is_available or not self._repo.get_provider(model.provider_code).enabled:
            raise ValidationFailedError(
                "El modelo asignado a esta operación ya no está disponible o su "
                "proveedor está deshabilitado."
            )
        api_key = self._api_key(model.provider_code)
        if api_key is None:
            raise ValidationFailedError("El proveedor asignado no tiene una API key registrada.")
        return ResolvedModel(model.provider_code, model.model_id, api_key)
