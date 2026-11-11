"""Repositorio de auditoría sobre SQL Server (SQLAlchemy)."""

from __future__ import annotations

import json

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.modules.audit.domain.models import AuditEvent, AuditResult
from app.modules.audit.infrastructure.orm import AuditEventRow


class SqlAuditRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, event: AuditEvent) -> None:
        self._session.add(
            AuditEventRow(
                id=event.id,
                occurred_at=event.occurred_at,
                actor_user_id=event.actor_user_id,
                action=event.action,
                result=event.result.value,
                resource_type=event.resource_type,
                resource_id=event.resource_id,
                ip=event.ip,
                correlation_id=event.correlation_id,
                details=json.dumps(event.details, ensure_ascii=False),
            )
        )
        self._session.flush()

    def list(self, *, action: str | None, offset: int, limit: int) -> tuple[list[AuditEvent], int]:
        query = sa.select(AuditEventRow)
        count = sa.select(sa.func.count()).select_from(AuditEventRow)
        if action:
            query = query.where(AuditEventRow.action == action)
            count = count.where(AuditEventRow.action == action)
        total = self._session.execute(count).scalar_one()
        rows = (
            self._session.execute(
                query.order_by(AuditEventRow.occurred_at.desc(), AuditEventRow.id.desc())
                .offset(offset)
                .limit(limit)
            )
            .scalars()
            .all()
        )
        return [
            AuditEvent(
                id=row.id,
                occurred_at=row.occurred_at,
                actor_user_id=row.actor_user_id,
                action=row.action,
                result=AuditResult(row.result),
                resource_type=row.resource_type,
                resource_id=row.resource_id,
                ip=row.ip,
                correlation_id=row.correlation_id,
                details=json.loads(row.details),
            )
            for row in rows
        ], total
