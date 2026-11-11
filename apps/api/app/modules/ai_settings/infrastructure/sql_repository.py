"""Repositorio de la configuración de IA sobre SQL Server (SQLAlchemy)."""

from __future__ import annotations

import json
import uuid

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.modules.ai_settings.domain.models import (
    Assignment,
    Credential,
    Model,
    Operation,
    Provider,
    ProviderCode,
)
from app.modules.ai_settings.infrastructure.orm import (
    AiModelRow,
    AiOperationAssignmentRow,
    AiProviderCredentialRow,
    AiProviderRow,
)

_PROVIDER_FIELDS = (
    "enabled",
    "monthly_limit_usd",
    "last_test_at",
    "last_test_ok",
    "last_test_error",
    "updated_at",
    "updated_by",
)
_CREDENTIAL_FIELDS = (
    "ciphertext",
    "last4",
    "master_key_id",
    "created_at",
    "created_by",
    "revoked_at",
    "revoked_by",
)


def _to_model(row: AiModelRow) -> Model:
    return Model(
        id=row.id,
        provider_code=ProviderCode(row.provider_code),
        model_id=row.model_id,
        display_name=row.display_name,
        capabilities=json.loads(row.capabilities) if row.capabilities else None,
        is_available=row.is_available,
        first_seen_at=row.first_seen_at,
        last_seen_at=row.last_seen_at,
    )


def _to_credential(row: AiProviderCredentialRow) -> Credential:
    return Credential(
        id=row.id,
        provider_code=ProviderCode(row.provider_code),
        **{name: getattr(row, name) for name in _CREDENTIAL_FIELDS},
    )


class SqlAiRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    # Los proveedores y las asignaciones son un conjunto fijo: la fila se crea
    # la primera vez que se guarda.

    def get_provider(self, code: ProviderCode) -> Provider:
        row = self._session.get(AiProviderRow, code.value)
        if row is None:
            return Provider(code=code)
        return Provider(code=code, **{name: getattr(row, name) for name in _PROVIDER_FIELDS})

    def save_provider(self, provider: Provider) -> None:
        row = self._session.get(AiProviderRow, provider.code.value)
        values = {name: getattr(provider, name) for name in _PROVIDER_FIELDS}
        if row is None:
            self._session.add(AiProviderRow(code=provider.code.value, **values))
        else:
            for name, value in values.items():
                setattr(row, name, value)
        self._session.flush()

    def _ensure_provider(self, code: ProviderCode) -> None:
        if self._session.get(AiProviderRow, code.value) is None:
            self.save_provider(Provider(code=code))

    def active_credential(self, code: ProviderCode) -> Credential | None:
        row = self._session.execute(
            sa.select(AiProviderCredentialRow).where(
                AiProviderCredentialRow.provider_code == code.value,
                AiProviderCredentialRow.revoked_at.is_(None),
            )
        ).scalar_one_or_none()
        return _to_credential(row) if row is not None else None

    def add_credential(self, credential: Credential) -> None:
        self._ensure_provider(credential.provider_code)
        self._session.add(
            AiProviderCredentialRow(
                id=credential.id,
                provider_code=credential.provider_code.value,
                **{name: getattr(credential, name) for name in _CREDENTIAL_FIELDS},
            )
        )
        self._session.flush()

    def save_credential(self, credential: Credential) -> None:
        row = self._session.get(AiProviderCredentialRow, credential.id)
        if row is None:
            raise LookupError("La credencial no existe.")
        for name in _CREDENTIAL_FIELDS:
            setattr(row, name, getattr(credential, name))
        self._session.flush()

    def list_models(self, code: ProviderCode | None = None) -> list[Model]:
        query = sa.select(AiModelRow).order_by(AiModelRow.provider_code, AiModelRow.display_name)
        if code is not None:
            query = query.where(AiModelRow.provider_code == code.value)
        return [_to_model(row) for row in self._session.execute(query).scalars()]

    def get_model(self, model_ref: uuid.UUID) -> Model | None:
        row = self._session.get(AiModelRow, model_ref)
        return _to_model(row) if row is not None else None

    def add_model(self, model: Model) -> None:
        self._ensure_provider(model.provider_code)
        self._session.add(
            AiModelRow(
                id=model.id,
                provider_code=model.provider_code.value,
                model_id=model.model_id,
                display_name=model.display_name,
                capabilities=json.dumps(model.capabilities) if model.capabilities else None,
                is_available=model.is_available,
                first_seen_at=model.first_seen_at,
                last_seen_at=model.last_seen_at,
            )
        )
        self._session.flush()

    def save_model(self, model: Model) -> None:
        row = self._session.get(AiModelRow, model.id)
        if row is None:
            raise LookupError("El modelo no existe.")
        row.display_name = model.display_name
        row.capabilities = json.dumps(model.capabilities) if model.capabilities else None
        row.is_available = model.is_available
        row.last_seen_at = model.last_seen_at
        self._session.flush()

    def get_assignment(self, operation: Operation) -> Assignment:
        row = self._session.get(AiOperationAssignmentRow, operation.value)
        if row is None:
            return Assignment(operation=operation)
        return Assignment(operation, row.model_ref, row.updated_at, row.updated_by)

    def save_assignment(self, assignment: Assignment) -> None:
        row = self._session.get(AiOperationAssignmentRow, assignment.operation.value)
        if row is None:
            row = AiOperationAssignmentRow(operation=assignment.operation.value)
            self._session.add(row)
        row.model_ref = assignment.model_ref
        row.updated_at = assignment.updated_at
        row.updated_by = assignment.updated_by
        self._session.flush()
