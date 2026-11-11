"""Repositorio de bancos de preguntas y llamadas sobre SQL Server (SQLAlchemy)."""

from __future__ import annotations

import json
import uuid

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.modules.phone_calls.domain.models import (
    Answer,
    Bank,
    BankScope,
    BankStatus,
    BankVersion,
    CallSession,
    CallStatus,
    Question,
)
from app.modules.phone_calls.infrastructure.orm import (
    CallSessionRow,
    QuestionBankRow,
    QuestionBankVersionRow,
)

_BANK = ("name", "description", "owner_user_id", "duplicated_from", "created_at", "updated_at")
_CALL = (
    "application_id",
    "vacancy_id",
    "bank_version_id",
    "called_at",
    "notes",
    "analysis_at",
    "analysis_by",
    "created_at",
    "created_by",
    "updated_at",
    "closed_at",
)


def _bank_values(bank: Bank) -> dict[str, object]:
    values = {name: getattr(bank, name) for name in _BANK}
    return {**values, "scope": bank.scope.value, "status": bank.status.value}


def _to_bank(row: QuestionBankRow) -> Bank:
    values = {name: getattr(row, name) for name in _BANK}
    return Bank(id=row.id, scope=BankScope(row.scope), status=BankStatus(row.status), **values)


def _to_version(row: QuestionBankVersionRow) -> BankVersion:
    return BankVersion(
        id=row.id,
        bank_id=row.bank_id,
        version_number=row.version_number,
        questions=tuple(
            Question(
                id=uuid.UUID(item["id"]),
                text=item["text"],
                competency=item.get("competency", ""),
                guidance=item.get("guidance", ""),
                origin=item.get("origin", "MANUAL"),
            )
            for item in json.loads(row.questions)
        ),
        created_at=row.created_at,
        created_by=row.created_by,
        change_note=row.change_note,
    )


def _call_values(call: CallSession) -> dict[str, object]:
    values = {name: getattr(call, name) for name in _CALL}
    values["status"] = call.status.value
    values["answers"] = json.dumps(
        [
            {
                "question_id": str(answer.question_id),
                "answer": answer.answer,
                "notes": answer.notes,
                "not_asked": answer.not_asked,
            }
            for answer in call.answers
        ],
        ensure_ascii=False,
    )
    values["analysis"] = (
        json.dumps(call.analysis, ensure_ascii=False) if call.analysis is not None else None
    )
    return values


def _to_call(row: CallSessionRow) -> CallSession:
    values = {name: getattr(row, name) for name in _CALL}
    return CallSession(
        id=row.id,
        status=CallStatus(row.status),
        answers=tuple(
            Answer(
                question_id=uuid.UUID(item["question_id"]),
                answer=item.get("answer", ""),
                notes=item.get("notes", ""),
                not_asked=bool(item.get("not_asked")),
            )
            for item in json.loads(row.answers)
        ),
        analysis=json.loads(row.analysis) if row.analysis else None,
        **values,
    )


class SqlPhoneCallRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    # --- Bancos --------------------------------------------------------------------------

    def banks(self) -> list[Bank]:
        rows = self._session.execute(
            sa.select(QuestionBankRow).order_by(QuestionBankRow.name, QuestionBankRow.id)
        ).scalars()
        return [_to_bank(row) for row in rows]

    def bank(self, bank_id: uuid.UUID) -> Bank | None:
        row = self._session.get(QuestionBankRow, bank_id)
        return _to_bank(row) if row is not None else None

    def add_bank(self, bank: Bank) -> None:
        self._session.add(QuestionBankRow(id=bank.id, **_bank_values(bank)))
        self._session.flush()

    def save_bank(self, bank: Bank) -> None:
        row = self._session.get(QuestionBankRow, bank.id)
        if row is None:
            raise LookupError("El banco no existe.")
        for name, value in _bank_values(bank).items():
            setattr(row, name, value)
        self._session.flush()

    def versions(self, bank_id: uuid.UUID) -> list[BankVersion]:
        rows = self._session.execute(
            sa.select(QuestionBankVersionRow)
            .where(QuestionBankVersionRow.bank_id == bank_id)
            .order_by(QuestionBankVersionRow.version_number.desc())
        ).scalars()
        return [_to_version(row) for row in rows]

    def version(self, version_id: uuid.UUID) -> BankVersion | None:
        row = self._session.get(QuestionBankVersionRow, version_id)
        return _to_version(row) if row is not None else None

    def add_version(self, version: BankVersion) -> None:
        self._session.add(
            QuestionBankVersionRow(
                id=version.id,
                bank_id=version.bank_id,
                version_number=version.version_number,
                questions=json.dumps(
                    [
                        {
                            "id": str(q.id),
                            "text": q.text,
                            "competency": q.competency,
                            "guidance": q.guidance,
                            "origin": q.origin,
                        }
                        for q in version.questions
                    ],
                    ensure_ascii=False,
                ),
                change_note=version.change_note,
                created_at=version.created_at,
                created_by=version.created_by,
            )
        )
        self._session.flush()

    def latest_versions(self, bank_ids: list[uuid.UUID]) -> dict[uuid.UUID, BankVersion]:
        if not bank_ids:
            return {}
        rows = self._session.execute(
            sa.select(QuestionBankVersionRow)
            .where(QuestionBankVersionRow.bank_id.in_(bank_ids))
            .order_by(QuestionBankVersionRow.version_number)
        ).scalars()
        return {row.bank_id: _to_version(row) for row in rows}

    # --- Llamadas ------------------------------------------------------------------------

    def call(self, call_id: uuid.UUID) -> CallSession | None:
        row = self._session.get(CallSessionRow, call_id)
        return _to_call(row) if row is not None else None

    def calls(self, application_id: uuid.UUID) -> list[CallSession]:
        rows = self._session.execute(
            sa.select(CallSessionRow)
            .where(CallSessionRow.application_id == application_id)
            .order_by(CallSessionRow.called_at.desc(), CallSessionRow.created_at.desc())
        ).scalars()
        return [_to_call(row) for row in rows]

    def add_call(self, call: CallSession) -> None:
        self._session.add(CallSessionRow(id=call.id, **_call_values(call)))
        self._session.flush()

    def save_call(self, call: CallSession) -> None:
        row = self._session.get(CallSessionRow, call.id)
        if row is None:
            raise LookupError("La llamada no existe.")
        for name, value in _call_values(call).items():
            setattr(row, name, value)
        self._session.flush()
