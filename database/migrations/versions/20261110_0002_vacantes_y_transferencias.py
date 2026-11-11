"""Vacantes, acceso compartido y transferencias.

Revisión: 0002
Anterior: 0001
Fecha: 2026-11-10

Crea el esquema ``vacancy`` y las tablas ``vacancies``, ``vacancy_members``,
``vacancy_sensitive_grants``, ``vacancy_transfers`` y
``vacancy_ownership_history``.

Reversión: ``downgrade`` elimina las cinco tablas y el esquema. Se pierden todas
las vacantes, sus accesos y su historial de responsables: no ejecutar en
producción sin respaldo.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mssql

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

GUID = mssql.UNIQUEIDENTIFIER()
UTC = mssql.DATETIME2(precision=3)
ACTIVE = sa.text("revoked_at IS NULL")


def _user_fk(column: str, name: str) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint([column], ["auth.users.id"], name=name)


def upgrade() -> None:
    # Sentencia literal: el nombre del esquema es fijo, no un dato de entrada.
    op.execute(
        "IF NOT EXISTS (SELECT 1 FROM sys.schemas WHERE name = N'vacancy') "
        "EXEC(N'CREATE SCHEMA [vacancy]')"
    )

    op.create_table(
        "vacancies",
        sa.Column("id", GUID, nullable=False),
        sa.Column("name", sa.NVARCHAR(200), nullable=False),
        sa.Column("department", sa.NVARCHAR(120), nullable=False),
        sa.Column("location", sa.NVARCHAR(120), nullable=False),
        sa.Column("work_mode", sa.VARCHAR(20), nullable=False),
        sa.Column("contract_type", sa.NVARCHAR(80), nullable=False),
        sa.Column("description", sa.NVARCHAR(None), nullable=False),
        sa.Column("positions", sa.Integer(), nullable=False),
        sa.Column("notes", sa.NVARCHAR(None), nullable=True),
        sa.Column("status", sa.VARCHAR(20), nullable=False),
        # Obligatorio: ninguna vacante puede quedar sin responsable.
        sa.Column("owner_user_id", GUID, nullable=False),
        sa.Column("opened_at", UTC, nullable=True),
        sa.Column("closed_at", UTC, nullable=True),
        sa.Column("created_at", UTC, nullable=False),
        sa.Column("created_by", GUID, nullable=False),
        sa.Column("updated_at", UTC, nullable=False),
        sa.Column("updated_by", GUID, nullable=False),
        # Control de concurrencia optimista administrado por la aplicación.
        sa.Column("version", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_vacancies"),
        _user_fk("owner_user_id", "fk_vacancies_owner"),
        _user_fk("created_by", "fk_vacancies_created_by"),
        _user_fk("updated_by", "fk_vacancies_updated_by"),
        sa.CheckConstraint(
            "status IN ('BORRADOR', 'ABIERTA', 'PAUSADA', 'CERRADA', 'CANCELADA', 'ARCHIVADA')",
            name="ck_vacancies_status",
        ),
        sa.CheckConstraint(
            "work_mode IN ('PRESENCIAL', 'HIBRIDA', 'REMOTA')", name="ck_vacancies_work_mode"
        ),
        sa.CheckConstraint("positions BETWEEN 1 AND 9999", name="ck_vacancies_positions"),
        sa.CheckConstraint("version >= 1", name="ck_vacancies_version"),
        schema="vacancy",
    )
    op.create_index(
        "ix_vacancies_owner", "vacancies", ["owner_user_id", "status"], schema="vacancy"
    )
    op.create_index("ix_vacancies_status", "vacancies", ["status"], schema="vacancy")

    op.create_table(
        "vacancy_members",
        sa.Column("id", GUID, nullable=False),
        sa.Column("vacancy_id", GUID, nullable=False),
        sa.Column("user_id", GUID, nullable=False),
        sa.Column("access_type", sa.VARCHAR(20), nullable=False),
        sa.Column("granted_by", GUID, nullable=False),
        sa.Column("granted_at", UTC, nullable=False),
        sa.Column("revoked_at", UTC, nullable=True),
        sa.Column("revoked_by", GUID, nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_vacancy_members"),
        sa.ForeignKeyConstraint(
            ["vacancy_id"], ["vacancy.vacancies.id"], name="fk_vacancy_members_vacancy"
        ),
        _user_fk("user_id", "fk_vacancy_members_user"),
        _user_fk("granted_by", "fk_vacancy_members_granted_by"),
        _user_fk("revoked_by", "fk_vacancy_members_revoked_by"),
        sa.CheckConstraint(
            "access_type IN ('LECTURA', 'COLABORACION')", name="ck_vacancy_members_access_type"
        ),
        schema="vacancy",
    )
    # Un solo acceso vigente por usuario y vacante; los revocados se conservan.
    op.create_index(
        "uq_vacancy_members_active",
        "vacancy_members",
        ["vacancy_id", "user_id"],
        unique=True,
        schema="vacancy",
        mssql_where=ACTIVE,
    )
    op.create_index("ix_vacancy_members_user", "vacancy_members", ["user_id"], schema="vacancy")

    op.create_table(
        "vacancy_sensitive_grants",
        sa.Column("id", GUID, nullable=False),
        sa.Column("vacancy_id", GUID, nullable=False),
        sa.Column("user_id", GUID, nullable=False),
        sa.Column("document_class", sa.VARCHAR(40), nullable=False),
        sa.Column("granted_by", GUID, nullable=False),
        sa.Column("granted_at", UTC, nullable=False),
        sa.Column("revoked_at", UTC, nullable=True),
        sa.Column("revoked_by", GUID, nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_vacancy_sensitive_grants"),
        sa.ForeignKeyConstraint(
            ["vacancy_id"], ["vacancy.vacancies.id"], name="fk_vacancy_sensitive_grants_vacancy"
        ),
        _user_fk("user_id", "fk_vacancy_sensitive_grants_user"),
        _user_fk("granted_by", "fk_vacancy_sensitive_grants_granted_by"),
        _user_fk("revoked_by", "fk_vacancy_sensitive_grants_revoked_by"),
        sa.CheckConstraint(
            "document_class IN ('PSICOMETRIA', 'ESTUDIO_SOCIOECONOMICO')",
            name="ck_vacancy_sensitive_grants_class",
        ),
        schema="vacancy",
    )
    op.create_index(
        "uq_vacancy_sensitive_grants_active",
        "vacancy_sensitive_grants",
        ["vacancy_id", "user_id", "document_class"],
        unique=True,
        schema="vacancy",
        mssql_where=ACTIVE,
    )
    op.create_index(
        "ix_vacancy_sensitive_grants_user",
        "vacancy_sensitive_grants",
        ["user_id"],
        schema="vacancy",
    )

    op.create_table(
        "vacancy_transfers",
        sa.Column("id", GUID, nullable=False),
        sa.Column("kind", sa.VARCHAR(20), nullable=False),
        sa.Column("from_user_id", GUID, nullable=False),
        sa.Column("to_user_id", GUID, nullable=False),
        sa.Column("reason", sa.NVARCHAR(500), nullable=False),
        sa.Column("requested_by", GUID, nullable=False),
        sa.Column("completed_at", UTC, nullable=False),
        sa.Column("vacancies_transferred", sa.Integer(), nullable=False),
        sa.Column("memberships_revoked", sa.Integer(), nullable=False),
        sa.Column("grants_revoked", sa.Integer(), nullable=False),
        sa.Column("user_deactivated", mssql.BIT(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_vacancy_transfers"),
        _user_fk("from_user_id", "fk_vacancy_transfers_from_user"),
        _user_fk("to_user_id", "fk_vacancy_transfers_to_user"),
        _user_fk("requested_by", "fk_vacancy_transfers_requested_by"),
        sa.CheckConstraint("kind IN ('INDIVIDUAL', 'MASIVA')", name="ck_vacancy_transfers_kind"),
        sa.CheckConstraint(
            "from_user_id <> to_user_id", name="ck_vacancy_transfers_distinct_users"
        ),
        schema="vacancy",
    )

    op.create_table(
        "vacancy_ownership_history",
        sa.Column("id", GUID, nullable=False),
        sa.Column("vacancy_id", GUID, nullable=False),
        sa.Column("previous_owner_id", GUID, nullable=True),
        sa.Column("new_owner_id", GUID, nullable=False),
        sa.Column("changed_at", UTC, nullable=False),
        sa.Column("reason", sa.NVARCHAR(500), nullable=False),
        sa.Column("authorized_by", GUID, nullable=False),
        sa.Column("transfer_id", GUID, nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_vacancy_ownership_history"),
        sa.ForeignKeyConstraint(
            ["vacancy_id"], ["vacancy.vacancies.id"], name="fk_vacancy_ownership_history_vacancy"
        ),
        _user_fk("previous_owner_id", "fk_vacancy_ownership_history_previous"),
        _user_fk("new_owner_id", "fk_vacancy_ownership_history_new"),
        _user_fk("authorized_by", "fk_vacancy_ownership_history_authorized_by"),
        sa.ForeignKeyConstraint(
            ["transfer_id"],
            ["vacancy.vacancy_transfers.id"],
            name="fk_vacancy_ownership_history_transfer",
        ),
        schema="vacancy",
    )
    op.create_index(
        "ix_vacancy_ownership_history_vacancy",
        "vacancy_ownership_history",
        ["vacancy_id", "changed_at"],
        schema="vacancy",
    )


def downgrade() -> None:
    op.drop_table("vacancy_ownership_history", schema="vacancy")
    op.drop_table("vacancy_transfers", schema="vacancy")
    op.drop_table("vacancy_sensitive_grants", schema="vacancy")
    op.drop_table("vacancy_members", schema="vacancy")
    op.drop_table("vacancies", schema="vacancy")
    op.execute("DROP SCHEMA [vacancy]")
