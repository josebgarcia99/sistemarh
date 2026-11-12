/* ============================================================================
   Sistema Integral de Reclutamiento e IA - Actualización 0001 -> 0002
   Versión del esquema: 0001 -> 0002
   Generado: 2026-11-12 15:47 (UTC) con scripts/generate_sql.py

   Aplica solo los cambios de la versión 0002 sobre una base que ya
   está en la versión 0001. Si está en otra versión, no hace nada.

   ANTES DE EJECUTAR
   1. Ejecutar primero en una base de PRUEBAS. Este script se generó sin
      conexión y todavía no se ha ejecutado contra un SQL Server real.
   2. La base de datos debe existir. Este script no la crea ni usa "USE":
      selecciónela en la conexión.
   3. Requiere permisos para crear esquemas y tablas (por ejemplo, db_owner).
   4. Ejecute con "sqlcmd -b" (se detiene al primer error) o en SSMS con el
      modo SQLCMD activado. Todo corre en una sola transacción y, si se detiene
      al primer error, no queda nada a medias. Sin esa opción, SSMS seguiría
      ejecutando los lotes posteriores al error fuera de la transacción.
   5. La tabla dbo.alembic_version registra la versión instalada. No la edite
      a mano: la aplicación y los scripts de actualización dependen de ella.
   ============================================================================ */

SET XACT_ABORT ON;
GO

-- Protección: si la base no está en la versión esperada, no se ejecuta nada.
IF OBJECT_ID(N'dbo.alembic_version') IS NULL OR NOT EXISTS (SELECT 1 FROM dbo.alembic_version WHERE version_num = N'0001')
BEGIN
    RAISERROR(N'La base no esta en la version 0001. No se aplico ningun cambio.', 16, 1);
    SET NOEXEC ON;
END
GO

BEGIN TRANSACTION;

-- Running upgrade 0001 -> 0002

IF NOT EXISTS (SELECT 1 FROM sys.schemas WHERE name = N'vacancy') EXEC(N'CREATE SCHEMA [vacancy]');

GO

CREATE TABLE vacancy.vacancies (
    id UNIQUEIDENTIFIER NOT NULL, 
    name NVARCHAR(200) NOT NULL, 
    department NVARCHAR(120) NOT NULL, 
    location NVARCHAR(120) NOT NULL, 
    work_mode VARCHAR(20) NOT NULL, 
    contract_type NVARCHAR(80) NOT NULL, 
    description NVARCHAR(max) NOT NULL, 
    positions INTEGER NOT NULL, 
    notes NVARCHAR(max) NULL, 
    status VARCHAR(20) NOT NULL, 
    owner_user_id UNIQUEIDENTIFIER NOT NULL, 
    opened_at DATETIME2(3) NULL, 
    closed_at DATETIME2(3) NULL, 
    created_at DATETIME2(3) NOT NULL, 
    created_by UNIQUEIDENTIFIER NOT NULL, 
    updated_at DATETIME2(3) NOT NULL, 
    updated_by UNIQUEIDENTIFIER NOT NULL, 
    version INTEGER NOT NULL, 
    CONSTRAINT pk_vacancies PRIMARY KEY (id), 
    CONSTRAINT fk_vacancies_owner FOREIGN KEY(owner_user_id) REFERENCES auth.users (id), 
    CONSTRAINT fk_vacancies_created_by FOREIGN KEY(created_by) REFERENCES auth.users (id), 
    CONSTRAINT fk_vacancies_updated_by FOREIGN KEY(updated_by) REFERENCES auth.users (id), 
    CONSTRAINT ck_vacancies_status CHECK (status IN ('BORRADOR', 'ABIERTA', 'PAUSADA', 'CERRADA', 'CANCELADA', 'ARCHIVADA')), 
    CONSTRAINT ck_vacancies_work_mode CHECK (work_mode IN ('PRESENCIAL', 'HIBRIDA', 'REMOTA')), 
    CONSTRAINT ck_vacancies_positions CHECK (positions BETWEEN 1 AND 9999), 
    CONSTRAINT ck_vacancies_version CHECK (version >= 1)
);

GO

CREATE INDEX ix_vacancies_owner ON vacancy.vacancies (owner_user_id, status);

GO

CREATE INDEX ix_vacancies_status ON vacancy.vacancies (status);

GO

CREATE TABLE vacancy.vacancy_members (
    id UNIQUEIDENTIFIER NOT NULL, 
    vacancy_id UNIQUEIDENTIFIER NOT NULL, 
    user_id UNIQUEIDENTIFIER NOT NULL, 
    access_type VARCHAR(20) NOT NULL, 
    granted_by UNIQUEIDENTIFIER NOT NULL, 
    granted_at DATETIME2(3) NOT NULL, 
    revoked_at DATETIME2(3) NULL, 
    revoked_by UNIQUEIDENTIFIER NULL, 
    CONSTRAINT pk_vacancy_members PRIMARY KEY (id), 
    CONSTRAINT fk_vacancy_members_vacancy FOREIGN KEY(vacancy_id) REFERENCES vacancy.vacancies (id), 
    CONSTRAINT fk_vacancy_members_user FOREIGN KEY(user_id) REFERENCES auth.users (id), 
    CONSTRAINT fk_vacancy_members_granted_by FOREIGN KEY(granted_by) REFERENCES auth.users (id), 
    CONSTRAINT fk_vacancy_members_revoked_by FOREIGN KEY(revoked_by) REFERENCES auth.users (id), 
    CONSTRAINT ck_vacancy_members_access_type CHECK (access_type IN ('LECTURA', 'COLABORACION'))
);

GO

CREATE UNIQUE INDEX uq_vacancy_members_active ON vacancy.vacancy_members (vacancy_id, user_id) WHERE revoked_at IS NULL;

GO

CREATE INDEX ix_vacancy_members_user ON vacancy.vacancy_members (user_id);

GO

CREATE TABLE vacancy.vacancy_sensitive_grants (
    id UNIQUEIDENTIFIER NOT NULL, 
    vacancy_id UNIQUEIDENTIFIER NOT NULL, 
    user_id UNIQUEIDENTIFIER NOT NULL, 
    document_class VARCHAR(40) NOT NULL, 
    granted_by UNIQUEIDENTIFIER NOT NULL, 
    granted_at DATETIME2(3) NOT NULL, 
    revoked_at DATETIME2(3) NULL, 
    revoked_by UNIQUEIDENTIFIER NULL, 
    CONSTRAINT pk_vacancy_sensitive_grants PRIMARY KEY (id), 
    CONSTRAINT fk_vacancy_sensitive_grants_vacancy FOREIGN KEY(vacancy_id) REFERENCES vacancy.vacancies (id), 
    CONSTRAINT fk_vacancy_sensitive_grants_user FOREIGN KEY(user_id) REFERENCES auth.users (id), 
    CONSTRAINT fk_vacancy_sensitive_grants_granted_by FOREIGN KEY(granted_by) REFERENCES auth.users (id), 
    CONSTRAINT fk_vacancy_sensitive_grants_revoked_by FOREIGN KEY(revoked_by) REFERENCES auth.users (id), 
    CONSTRAINT ck_vacancy_sensitive_grants_class CHECK (document_class IN ('PSICOMETRIA', 'ESTUDIO_SOCIOECONOMICO'))
);

GO

CREATE UNIQUE INDEX uq_vacancy_sensitive_grants_active ON vacancy.vacancy_sensitive_grants (vacancy_id, user_id, document_class) WHERE revoked_at IS NULL;

GO

CREATE INDEX ix_vacancy_sensitive_grants_user ON vacancy.vacancy_sensitive_grants (user_id);

GO

CREATE TABLE vacancy.vacancy_transfers (
    id UNIQUEIDENTIFIER NOT NULL, 
    kind VARCHAR(20) NOT NULL, 
    from_user_id UNIQUEIDENTIFIER NOT NULL, 
    to_user_id UNIQUEIDENTIFIER NOT NULL, 
    reason NVARCHAR(500) NOT NULL, 
    requested_by UNIQUEIDENTIFIER NOT NULL, 
    completed_at DATETIME2(3) NOT NULL, 
    vacancies_transferred INTEGER NOT NULL, 
    memberships_revoked INTEGER NOT NULL, 
    grants_revoked INTEGER NOT NULL, 
    user_deactivated BIT NOT NULL, 
    CONSTRAINT pk_vacancy_transfers PRIMARY KEY (id), 
    CONSTRAINT fk_vacancy_transfers_from_user FOREIGN KEY(from_user_id) REFERENCES auth.users (id), 
    CONSTRAINT fk_vacancy_transfers_to_user FOREIGN KEY(to_user_id) REFERENCES auth.users (id), 
    CONSTRAINT fk_vacancy_transfers_requested_by FOREIGN KEY(requested_by) REFERENCES auth.users (id), 
    CONSTRAINT ck_vacancy_transfers_kind CHECK (kind IN ('INDIVIDUAL', 'MASIVA')), 
    CONSTRAINT ck_vacancy_transfers_distinct_users CHECK (from_user_id <> to_user_id)
);

GO

CREATE TABLE vacancy.vacancy_ownership_history (
    id UNIQUEIDENTIFIER NOT NULL, 
    vacancy_id UNIQUEIDENTIFIER NOT NULL, 
    previous_owner_id UNIQUEIDENTIFIER NULL, 
    new_owner_id UNIQUEIDENTIFIER NOT NULL, 
    changed_at DATETIME2(3) NOT NULL, 
    reason NVARCHAR(500) NOT NULL, 
    authorized_by UNIQUEIDENTIFIER NOT NULL, 
    transfer_id UNIQUEIDENTIFIER NULL, 
    CONSTRAINT pk_vacancy_ownership_history PRIMARY KEY (id), 
    CONSTRAINT fk_vacancy_ownership_history_vacancy FOREIGN KEY(vacancy_id) REFERENCES vacancy.vacancies (id), 
    CONSTRAINT fk_vacancy_ownership_history_previous FOREIGN KEY(previous_owner_id) REFERENCES auth.users (id), 
    CONSTRAINT fk_vacancy_ownership_history_new FOREIGN KEY(new_owner_id) REFERENCES auth.users (id), 
    CONSTRAINT fk_vacancy_ownership_history_authorized_by FOREIGN KEY(authorized_by) REFERENCES auth.users (id), 
    CONSTRAINT fk_vacancy_ownership_history_transfer FOREIGN KEY(transfer_id) REFERENCES vacancy.vacancy_transfers (id)
);

GO

CREATE INDEX ix_vacancy_ownership_history_vacancy ON vacancy.vacancy_ownership_history (vacancy_id, changed_at);

GO

UPDATE alembic_version SET version_num='0002' WHERE alembic_version.version_num = '0001';

GO

COMMIT;

GO


GO
SET NOEXEC OFF;
GO
