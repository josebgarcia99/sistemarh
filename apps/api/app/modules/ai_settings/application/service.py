"""Reglas de la configuración de IA. Solo administradores."""

from __future__ import annotations

import time
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
    PROVIDER_NAMES,
    AiRepository,
    Assignment,
    Credential,
    Execution,
    ExecutionStatus,
    KeySource,
    Model,
    Operation,
    Provider,
    ProviderClient,
    ProviderCode,
    ProviderError,
    TextCipher,
    UsageRow,
)
from app.modules.audit.application.service import AuditLog
from app.modules.audit.domain.models import AuditAction, AuditResult

RESOURCE = "proveedor_ia"
TEST_OPERATION = "PRUEBA"
# Fallos que pueden ser pasajeros: red, límite de solicitudes o error del proveedor.
_RETRYABLE = frozenset({"red", "limite", "proveedor"})
_BACKOFF_SECONDS = (2.0, 6.0)
_MILLION = Decimal(1_000_000)
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


@dataclass(frozen=True)
class GenerationResult:
    """Resultado de una llamada a un proveedor. Un fallo del proveedor no es una
    excepción: queda registrado y quien llama decide qué hacer."""

    ok: bool
    text: str
    complete: bool
    error: str | None
    input_tokens: int | None
    output_tokens: int | None
    estimated_cost_usd: Decimal | None
    attempts: int
    execution_id: uuid.UUID


@dataclass(frozen=True)
class ProviderSpend:
    code: ProviderCode
    spent_usd: Decimal
    limit_usd: Decimal | None


def month_bounds(year: int, month: int) -> tuple[datetime, datetime]:
    from datetime import UTC

    start = datetime(year, month, 1, tzinfo=UTC)
    end = datetime(year + month // 12, month % 12 + 1, 1, tzinfo=UTC)
    return start, end


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
        documents_allowed: bool = False,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._repo = repository
        self._audit = audit
        self._clock = clock
        self._cipher = cipher
        self._clients = clients
        self._env_keys = env_keys
        self._documents_allowed = documents_allowed
        self._sleep = sleep

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

    def _assigned_model(self, operation: Operation) -> Model:
        assignment = self._repo.get_assignment(operation)
        model = self._repo.get_model(assignment.model_ref) if assignment.model_ref else None
        if model is None:
            raise ValidationFailedError(
                "Esta operación no tiene un modelo asignado. Pídele al administrador "
                "que lo configure en Configuración de IA."
            )
        return model

    def _usable_key(self, model: Model) -> str:
        if not model.is_available or not self._repo.get_provider(model.provider_code).enabled:
            raise ValidationFailedError(
                "El modelo asignado ya no está disponible o su proveedor está deshabilitado."
            )
        api_key = self._api_key(model.provider_code)
        if api_key is None:
            raise ValidationFailedError("El proveedor del modelo no tiene una API key registrada.")
        return api_key

    def resolve(self, operation: Operation) -> ResolvedModel:
        """Modelo y clave para ejecutar una operación. Se valida en el momento de usarlo."""
        model = self._assigned_model(operation)
        return ResolvedModel(model.provider_code, model.model_id, self._usable_key(model))

    # --- Precios y consumo ---------------------------------------------------------------

    def set_prices(
        self,
        actor: Actor,
        model_ref: uuid.UUID,
        *,
        input_price: Decimal | None,
        output_price: Decimal | None,
        ip: str | None = None,
    ) -> Model:
        """Precio por millón de tokens. Lo captura el administrador: no hay precios
        escritos en el código."""
        self._require_admin(actor)
        model = self._repo.get_model(model_ref)
        if model is None:
            raise NotFoundError("El modelo no existe.")
        if (input_price is None) != (output_price is None):
            raise ValidationFailedError(
                "Captura los dos precios, de entrada y de salida, o ninguno."
            )
        for price in (input_price, output_price):
            if price is not None and not Decimal(0) <= price <= Decimal(100000):
                raise ValidationFailedError("El precio debe estar entre 0 y 100,000 USD.")
        if input_price is not None and output_price is not None:
            input_price = input_price.quantize(Decimal("0.0001"))
            output_price = output_price.quantize(Decimal("0.0001"))
        model.input_price, model.output_price = input_price, output_price
        self._repo.save_model(model)
        self._audit.record(
            AuditAction.IA_PRECIO_ACTUALIZADO,
            actor_user_id=actor.id,
            resource_type="modelo_ia",
            resource_id=model.id,
            ip=ip,
            details={
                "modelo": model.model_id,
                "entrada_usd": str(input_price) if input_price is not None else None,
                "salida_usd": str(output_price) if output_price is not None else None,
            },
        )
        return model

    def usage(
        self, actor: Actor, year: int, month: int
    ) -> tuple[list[UsageRow], list[ProviderSpend]]:
        self._require_admin(actor)
        start, end = month_bounds(year, month)
        spend = [
            ProviderSpend(
                code,
                self._repo.provider_cost(code, start, end),
                self._repo.get_provider(code).monthly_limit_usd,
            )
            for code in ProviderCode
        ]
        return self._repo.usage(start, end), spend

    # --- Ejecución -----------------------------------------------------------------------

    def execute(
        self,
        operation: Operation | str,
        *,
        system: str,
        user: str,
        model: Model | None = None,
        actor_user_id: uuid.UUID | None = None,
        vacancy_id: uuid.UUID | None = None,
        max_output_tokens: int = 4000,
        carries_document: bool = False,
    ) -> GenerationResult:
        """Llama al proveedor del modelo asignado y registra el consumo.

        Antes de llamar comprueba el modelo, la clave, la autorización para
        enviar documentos y el límite de gasto mensual. Reintenta los fallos
        pasajeros. No guarda lo enviado ni lo recibido: solo tokens, costo
        estimado, duración y resultado.
        """
        if model is None:
            if not isinstance(operation, Operation):
                raise ValidationFailedError("La operación no existe.")
            model = self._assigned_model(operation)
        api_key = self._usable_key(model)
        code = model.provider_code
        if carries_document and not self._documents_allowed:
            raise ValidationFailedError(
                "En este entorno no está autorizado enviar documentos a proveedores de IA "
                "(RECLU_AI_ALLOW_REAL_DOCUMENTS)."
            )
        priced = model.input_price is not None and model.output_price is not None
        limit = self._repo.get_provider(code).monthly_limit_usd
        now = self._clock()
        if limit is not None:
            if not priced:
                raise ValidationFailedError(
                    "El proveedor tiene un límite de gasto mensual, pero el modelo no tiene "
                    "precio capturado. Captúralo en Configuración de IA para poder aplicarlo."
                )
            if self._repo.provider_cost(code, *month_bounds(now.year, now.month)) >= limit:
                raise ConflictError(
                    f"Se alcanzó el límite de gasto mensual de {PROVIDER_NAMES[code]}. "
                    "Un administrador puede ampliarlo en Configuración de IA."
                )

        started = time.monotonic()
        attempts = 0
        generation = None
        failure: ProviderError | None = None
        while generation is None:
            attempts += 1
            try:
                generation = self._clients[code].generate(
                    api_key,
                    model.model_id,
                    system=system,
                    user=user,
                    max_output_tokens=max_output_tokens,
                )
            except ProviderError as error:
                if error.kind in _RETRYABLE and attempts <= len(_BACKOFF_SECONDS):
                    self._sleep(_BACKOFF_SECONDS[attempts - 1])
                    continue
                failure = error
                break

        cost = None
        if generation is not None and priced:
            cost = (
                generation.input_tokens * model.input_price
                + generation.output_tokens * model.output_price
            ) / _MILLION
            cost = cost.quantize(Decimal("0.000001"))
        execution = Execution(
            id=new_sequential_uuid(),
            occurred_at=now,
            operation=str(operation.value if isinstance(operation, Operation) else operation),
            provider_code=code,
            model_id=model.model_id,
            status=ExecutionStatus.CORRECTA if generation else ExecutionStatus.FALLIDA,
            attempts=attempts,
            duration_ms=int((time.monotonic() - started) * 1000),
            input_tokens=generation.input_tokens if generation else None,
            output_tokens=generation.output_tokens if generation else None,
            estimated_cost_usd=cost,
            error_kind=failure.kind if failure else None,
            actor_user_id=actor_user_id,
            vacancy_id=vacancy_id,
        )
        self._repo.add_execution(execution)
        return GenerationResult(
            ok=generation is not None,
            text=generation.text if generation else "",
            complete=generation.complete if generation else False,
            error=failure.message if failure else None,
            input_tokens=execution.input_tokens,
            output_tokens=execution.output_tokens,
            estimated_cost_usd=cost,
            attempts=attempts,
            execution_id=execution.id,
        )

    def test_model(self, actor: Actor, model_ref: uuid.UUID) -> GenerationResult:
        """Pide al modelo una respuesta mínima. No envía ningún documento."""
        self._require_admin(actor)
        model = self._repo.get_model(model_ref)
        if model is None:
            raise NotFoundError("El modelo no existe.")
        return self.execute(
            TEST_OPERATION,
            model=model,
            system="Responde únicamente con la palabra OK.",
            user="Prueba de funcionamiento.",
            actor_user_id=actor.id,
            max_output_tokens=200,
        )
