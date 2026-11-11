"""Identidad (usuarios, roles, sesiones) y auditoría.

Revisión: 0001
Anterior: ninguna
Fecha: 2026-11-10

Crea los esquemas ``auth`` y ``ops`` y las tablas ``auth.roles``, ``auth.users``,
``auth.user_roles``, ``auth.sessions`` y ``ops.audit_events``.

Reversión: ``downgrade`` elimina las cinco tablas y los dos esquemas. Se pierden
todos los usuarios, sesiones y eventos de auditoría: no ejecutar en producción
sin respaldo.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mssql

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

GUID = mssql.UNIQUEIDENTIFIER()
UTC = mssql.DATETIME2(precision=3)


def upgrade() -> None:
    # Sentencias literales: los nombres de esquema son fijos, no datos de entrada.
    op.execute(
        "IF NOT EXISTS (SELECT 1 FROM sys.schemas WHERE name = N'auth') "
        "EXEC(N'CREATE SCHEMA [auth]')"
    )
    op.execute(
        "IF NOT EXISTS (SELECT 1 FROM sys.schemas WHERE name = N'ops') EXEC(N'CREATE SCHEMA [ops]')"
    )

    op.create_table(
        "roles",
        sa.Column("code", sa.NVARCHAR(30), nullable=False),
        sa.Column("name", sa.NVARCHAR(100), nullable=False),
        sa.PrimaryKeyConstraint("code", name="pk_roles"),
        schema="auth",
    )
    # INSERT explícito: op.bulk_insert añade SET IDENTITY_INSERT al generar el
    # script, y esta tabla no tiene columna de identidad.
    op.execute(
        "INSERT INTO auth.roles (code, name) VALUES "
        "(N'ADMINISTRADOR', N'Administrador'), (N'RECLUTADOR', N'Reclutador')"
    )

    op.create_table(
        "users",
        sa.Column("id", GUID, nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_users"),
        sa.Column("email", sa.NVARCHAR(254), nullable=False),
        sa.Column("full_name", sa.NVARCHAR(200), nullable=False),
        sa.Column("password_hash", sa.NVARCHAR(255), nullable=False),
        sa.Column("is_active", mssql.BIT(), nullable=False),
        sa.Column("created_at", UTC, nullable=False),
        sa.Column("created_by", GUID, nullable=True),
        sa.Column("last_activity_at", UTC, nullable=True),
        sa.Column("deactivated_at", UTC, nullable=True),
        sa.Column("password_changed_at", UTC, nullable=True),
        sa.Column("failed_login_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("locked_until", UTC, nullable=True),
        # Lo mantiene SQL Server; queda listo para control de concurrencia optimista.
        sa.Column("row_version", mssql.ROWVERSION(), nullable=False),
        sa.UniqueConstraint("email", name="uq_users_email"),
        sa.ForeignKeyConstraint(["created_by"], ["auth.users.id"], name="fk_users_created_by"),
        sa.CheckConstraint("failed_login_count >= 0", name="ck_users_failed_login_count"),
        schema="auth",
    )

    op.create_table(
        "user_roles",
        sa.Column("user_id", GUID, nullable=False),
        sa.Column("role_code", sa.NVARCHAR(30), nullable=False),
        sa.PrimaryKeyConstraint("user_id", "role_code", name="pk_user_roles"),
        sa.ForeignKeyConstraint(["user_id"], ["auth.users.id"], name="fk_user_roles_user"),
        sa.ForeignKeyConstraint(["role_code"], ["auth.roles.code"], name="fk_user_roles_role"),
        schema="auth",
    )

    op.create_table(
        "sessions",
        sa.Column("id", GUID, nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_sessions"),
        sa.Column("user_id", GUID, nullable=False),
        sa.Column("token_hash", sa.VARCHAR(64), nullable=False),
        sa.Column("csrf_token", sa.VARCHAR(64), nullable=False),
        sa.Column("created_at", UTC, nullable=False),
        sa.Column("last_seen_at", UTC, nullable=False),
        sa.Column("expires_at", UTC, nullable=False),
        sa.Column("ip", sa.VARCHAR(45), nullable=True),
        sa.Column("user_agent", sa.NVARCHAR(300), nullable=True),
        sa.Column("revoked_at", UTC, nullable=True),
        sa.UniqueConstraint("token_hash", name="uq_sessions_token_hash"),
        sa.ForeignKeyConstraint(["user_id"], ["auth.users.id"], name="fk_sessions_user"),
        schema="auth",
    )
    op.create_index("ix_sessions_user_id", "sessions", ["user_id"], schema="auth")

    op.create_table(
        "audit_events",
        sa.Column("id", GUID, nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_audit_events"),
        sa.Column("occurred_at", UTC, nullable=False),
        sa.Column("actor_user_id", GUID, nullable=True),
        sa.Column("action", sa.VARCHAR(80), nullable=False),
        sa.Column("result", sa.VARCHAR(20), nullable=False),
        sa.Column("resource_type", sa.VARCHAR(60), nullable=True),
        sa.Column("resource_id", sa.VARCHAR(64), nullable=True),
        sa.Column("ip", sa.VARCHAR(45), nullable=True),
        sa.Column("correlation_id", sa.VARCHAR(64), nullable=True),
        sa.Column("details", sa.NVARCHAR(None), nullable=False),
        sa.CheckConstraint(
            "result IN ('PERMITIDO', 'DENEGADO', 'FALLIDO')", name="ck_audit_events_result"
        ),
        sa.CheckConstraint("ISJSON(details) = 1", name="ck_audit_events_details_json"),
        schema="ops",
    )
    op.create_index("ix_audit_events_occurred_at", "audit_events", ["occurred_at"], schema="ops")
    op.create_index(
        "ix_audit_events_actor", "audit_events", ["actor_user_id", "occurred_at"], schema="ops"
    )
    op.create_index(
        "ix_audit_events_action", "audit_events", ["action", "occurred_at"], schema="ops"
    )


def downgrade() -> None:
    op.drop_table("audit_events", schema="ops")
    op.drop_table("sessions", schema="auth")
    op.drop_table("user_roles", schema="auth")
    op.drop_table("users", schema="auth")
    op.drop_table("roles", schema="auth")
    op.execute("DROP SCHEMA [ops]")
    op.execute("DROP SCHEMA [auth]")
