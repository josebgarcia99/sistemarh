/* ============================================================================
   Sistema Integral de Reclutamiento e IA - Instalación completa
   Versión del esquema: (vacía) -> 0006
   Generado: 2026-11-11 15:40 (UTC) con scripts/generate_sql.py

   Crea todos los esquemas y tablas en una base de datos VACÍA.

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
IF OBJECT_ID(N'dbo.alembic_version') IS NOT NULL
BEGIN
    RAISERROR(N'Esta base ya tiene el sistema instalado. Use un script de actualizacion.', 16, 1);
    SET NOEXEC ON;
END
GO

BEGIN TRANSACTION;

CREATE TABLE alembic_version (
    version_num VARCHAR(32) NOT NULL, 
    CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
);

GO

-- Running upgrade  -> 0001

IF NOT EXISTS (SELECT 1 FROM sys.schemas WHERE name = N'auth') EXEC(N'CREATE SCHEMA [auth]');

GO

IF NOT EXISTS (SELECT 1 FROM sys.schemas WHERE name = N'ops') EXEC(N'CREATE SCHEMA [ops]');

GO

CREATE TABLE auth.roles (
    code NVARCHAR(30) NOT NULL, 
    name NVARCHAR(100) NOT NULL, 
    CONSTRAINT pk_roles PRIMARY KEY (code)
);

GO

INSERT INTO auth.roles (code, name) VALUES (N'ADMINISTRADOR', N'Administrador'), (N'RECLUTADOR', N'Reclutador');

GO

CREATE TABLE auth.users (
    id UNIQUEIDENTIFIER NOT NULL, 
    email NVARCHAR(254) NOT NULL, 
    full_name NVARCHAR(200) NOT NULL, 
    password_hash NVARCHAR(255) NOT NULL, 
    is_active BIT NOT NULL, 
    created_at DATETIME2(3) NOT NULL, 
    created_by UNIQUEIDENTIFIER NULL, 
    last_activity_at DATETIME2(3) NULL, 
    deactivated_at DATETIME2(3) NULL, 
    password_changed_at DATETIME2(3) NULL, 
    failed_login_count INTEGER NOT NULL DEFAULT 0, 
    locked_until DATETIME2(3) NULL, 
    row_version ROWVERSION NOT NULL, 
    CONSTRAINT pk_users PRIMARY KEY (id), 
    CONSTRAINT uq_users_email UNIQUE (email), 
    CONSTRAINT fk_users_created_by FOREIGN KEY(created_by) REFERENCES auth.users (id), 
    CONSTRAINT ck_users_failed_login_count CHECK (failed_login_count >= 0)
);

GO

CREATE TABLE auth.user_roles (
    user_id UNIQUEIDENTIFIER NOT NULL, 
    role_code NVARCHAR(30) NOT NULL, 
    CONSTRAINT pk_user_roles PRIMARY KEY (user_id, role_code), 
    CONSTRAINT fk_user_roles_user FOREIGN KEY(user_id) REFERENCES auth.users (id), 
    CONSTRAINT fk_user_roles_role FOREIGN KEY(role_code) REFERENCES auth.roles (code)
);

GO

CREATE TABLE auth.sessions (
    id UNIQUEIDENTIFIER NOT NULL, 
    user_id UNIQUEIDENTIFIER NOT NULL, 
    token_hash VARCHAR(64) NOT NULL, 
    csrf_token VARCHAR(64) NOT NULL, 
    created_at DATETIME2(3) NOT NULL, 
    last_seen_at DATETIME2(3) NOT NULL, 
    expires_at DATETIME2(3) NOT NULL, 
    ip VARCHAR(45) NULL, 
    user_agent NVARCHAR(300) NULL, 
    revoked_at DATETIME2(3) NULL, 
    CONSTRAINT pk_sessions PRIMARY KEY (id), 
    CONSTRAINT uq_sessions_token_hash UNIQUE (token_hash), 
    CONSTRAINT fk_sessions_user FOREIGN KEY(user_id) REFERENCES auth.users (id)
);

GO

CREATE INDEX ix_sessions_user_id ON auth.sessions (user_id);

GO

CREATE TABLE ops.audit_events (
    id UNIQUEIDENTIFIER NOT NULL, 
    occurred_at DATETIME2(3) NOT NULL, 
    actor_user_id UNIQUEIDENTIFIER NULL, 
    action VARCHAR(80) NOT NULL, 
    result VARCHAR(20) NOT NULL, 
    resource_type VARCHAR(60) NULL, 
    resource_id VARCHAR(64) NULL, 
    ip VARCHAR(45) NULL, 
    correlation_id VARCHAR(64) NULL, 
    details NVARCHAR(max) NOT NULL, 
    CONSTRAINT pk_audit_events PRIMARY KEY (id), 
    CONSTRAINT ck_audit_events_result CHECK (result IN ('PERMITIDO', 'DENEGADO', 'FALLIDO')), 
    CONSTRAINT ck_audit_events_details_json CHECK (ISJSON(details) = 1)
);

GO

CREATE INDEX ix_audit_events_occurred_at ON ops.audit_events (occurred_at);

GO

CREATE INDEX ix_audit_events_actor ON ops.audit_events (actor_user_id, occurred_at);

GO

CREATE INDEX ix_audit_events_action ON ops.audit_events (action, occurred_at);

GO

INSERT INTO alembic_version (version_num) OUTPUT inserted.version_num VALUES ('0001');

GO

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

-- Running upgrade 0002 -> 0003

IF NOT EXISTS (SELECT 1 FROM sys.schemas WHERE name = N'files') EXEC(N'CREATE SCHEMA [files]');

GO

CREATE TABLE files.file_assets (
    id UNIQUEIDENTIFIER NOT NULL, 
    vacancy_id UNIQUEIDENTIFIER NOT NULL, 
    document_type VARCHAR(40) NOT NULL, 
    sensitive_class VARCHAR(40) NULL, 
    original_name NVARCHAR(200) NOT NULL, 
    extension VARCHAR(10) NOT NULL, 
    content_type VARCHAR(100) NULL, 
    size_bytes BIGINT NULL, 
    sha256 VARCHAR(64) NULL, 
    storage_backend VARCHAR(20) NOT NULL, 
    storage_key VARCHAR(200) NOT NULL, 
    status VARCHAR(20) NOT NULL, 
    malware_scan VARCHAR(20) NULL, 
    failure_code VARCHAR(40) NULL, 
    uploaded_by UNIQUEIDENTIFIER NOT NULL, 
    created_at DATETIME2(3) NOT NULL, 
    confirmed_at DATETIME2(3) NULL, 
    retention_until DATETIME2(3) NULL, 
    deleted_at DATETIME2(3) NULL, 
    deleted_by UNIQUEIDENTIFIER NULL, 
    deletion_reason NVARCHAR(500) NULL, 
    CONSTRAINT pk_file_assets PRIMARY KEY (id), 
    CONSTRAINT uq_file_assets_storage_key UNIQUE (storage_key), 
    CONSTRAINT fk_file_assets_vacancy FOREIGN KEY(vacancy_id) REFERENCES vacancy.vacancies (id), 
    CONSTRAINT fk_file_assets_uploaded_by FOREIGN KEY(uploaded_by) REFERENCES auth.users (id), 
    CONSTRAINT fk_file_assets_deleted_by FOREIGN KEY(deleted_by) REFERENCES auth.users (id), 
    CONSTRAINT ck_file_assets_status CHECK (status IN ('RECIBIENDO', 'CONFIRMADO', 'RECHAZADO', 'FALLIDO', 'ELIMINADO')), 
    CONSTRAINT ck_file_assets_document_type CHECK (document_type IN ('CV', 'PERFIL_PUESTO', 'PSICOMETRIA', 'PRUEBA_TECNICA', 'ESTUDIO_SOCIOECONOMICO', 'ADJUNTO')), 
    CONSTRAINT ck_file_assets_sensitive_class CHECK (sensitive_class IS NULL OR sensitive_class IN ('PSICOMETRIA', 'ESTUDIO_SOCIOECONOMICO')), 
    CONSTRAINT ck_file_assets_malware_scan CHECK (malware_scan IS NULL OR malware_scan IN ('LIMPIO', 'NO_ANALIZADO')), 
    CONSTRAINT ck_file_assets_confirmed_complete CHECK (status NOT IN ('CONFIRMADO', 'ELIMINADO') OR (size_bytes IS NOT NULL AND sha256 IS NOT NULL AND confirmed_at IS NOT NULL)), 
    CONSTRAINT ck_file_assets_deleted_complete CHECK (status <> 'ELIMINADO' OR (deleted_at IS NOT NULL AND deleted_by IS NOT NULL AND deletion_reason IS NOT NULL)), 
    CONSTRAINT ck_file_assets_size CHECK (size_bytes IS NULL OR size_bytes >= 0)
);

GO

CREATE INDEX ix_file_assets_vacancy ON files.file_assets (vacancy_id, status);

GO

CREATE INDEX ix_file_assets_hash ON files.file_assets (vacancy_id, sha256);

GO

CREATE INDEX ix_file_assets_status ON files.file_assets (status, created_at);

GO

UPDATE alembic_version SET version_num='0003' WHERE alembic_version.version_num = '0002';

GO

-- Running upgrade 0003 -> 0004

ALTER TABLE files.file_assets ADD stored_size_bytes BIGINT NULL;

GO

ALTER TABLE files.file_assets ADD stored_sha256 VARCHAR(64) NULL;

GO

ALTER TABLE files.file_assets ADD encryption_key_id VARCHAR(32) NULL;

GO

UPDATE files.file_assets SET stored_size_bytes = size_bytes, stored_sha256 = sha256 WHERE status IN ('CONFIRMADO', 'ELIMINADO');

GO

ALTER TABLE files.file_assets ADD CONSTRAINT ck_file_assets_stored_complete CHECK (status NOT IN ('CONFIRMADO', 'ELIMINADO') OR (stored_size_bytes IS NOT NULL AND stored_sha256 IS NOT NULL));

GO

UPDATE alembic_version SET version_num='0004' WHERE alembic_version.version_num = '0003';

GO

-- Running upgrade 0004 -> 0005

IF NOT EXISTS (SELECT 1 FROM sys.schemas WHERE name = N'ai') EXEC(N'CREATE SCHEMA [ai]');

GO

CREATE TABLE ai.providers (
    code VARCHAR(20) NOT NULL, 
    enabled BIT NOT NULL, 
    monthly_limit_usd NUMERIC(12, 2) NULL, 
    last_test_at DATETIME2(3) NULL, 
    last_test_ok BIT NULL, 
    last_test_error NVARCHAR(300) NULL, 
    updated_at DATETIME2(3) NULL, 
    updated_by UNIQUEIDENTIFIER NULL, 
    CONSTRAINT pk_providers PRIMARY KEY (code), 
    CONSTRAINT fk_providers_updated_by FOREIGN KEY(updated_by) REFERENCES auth.users (id), 
    CONSTRAINT ck_providers_code CHECK (code IN ('ANTHROPIC', 'OPENAI')), 
    CONSTRAINT ck_providers_limit CHECK (monthly_limit_usd IS NULL OR monthly_limit_usd >= 0)
);

GO

CREATE TABLE ai.provider_credentials (
    id UNIQUEIDENTIFIER NOT NULL, 
    provider_code VARCHAR(20) NOT NULL, 
    ciphertext NVARCHAR(max) NULL, 
    last4 VARCHAR(4) NOT NULL, 
    master_key_id VARCHAR(32) NOT NULL, 
    created_at DATETIME2(3) NOT NULL, 
    created_by UNIQUEIDENTIFIER NOT NULL, 
    revoked_at DATETIME2(3) NULL, 
    revoked_by UNIQUEIDENTIFIER NULL, 
    CONSTRAINT pk_provider_credentials PRIMARY KEY (id), 
    CONSTRAINT fk_provider_credentials_provider FOREIGN KEY(provider_code) REFERENCES ai.providers (code), 
    CONSTRAINT fk_provider_credentials_created_by FOREIGN KEY(created_by) REFERENCES auth.users (id), 
    CONSTRAINT fk_provider_credentials_revoked_by FOREIGN KEY(revoked_by) REFERENCES auth.users (id), 
    CONSTRAINT ck_provider_credentials_secret CHECK ((revoked_at IS NULL AND ciphertext IS NOT NULL) OR (revoked_at IS NOT NULL AND ciphertext IS NULL))
);

GO

CREATE UNIQUE INDEX uq_provider_credentials_active ON ai.provider_credentials (provider_code) WHERE revoked_at IS NULL;

GO

CREATE TABLE ai.models (
    id UNIQUEIDENTIFIER NOT NULL, 
    provider_code VARCHAR(20) NOT NULL, 
    model_id NVARCHAR(200) NOT NULL, 
    display_name NVARCHAR(200) NOT NULL, 
    capabilities NVARCHAR(max) NULL, 
    is_available BIT NOT NULL, 
    first_seen_at DATETIME2(3) NOT NULL, 
    last_seen_at DATETIME2(3) NOT NULL, 
    CONSTRAINT pk_models PRIMARY KEY (id), 
    CONSTRAINT uq_models_provider_model UNIQUE (provider_code, model_id), 
    CONSTRAINT fk_models_provider FOREIGN KEY(provider_code) REFERENCES ai.providers (code), 
    CONSTRAINT ck_models_capabilities_json CHECK (capabilities IS NULL OR ISJSON(capabilities) = 1)
);

GO

CREATE TABLE ai.operation_assignments (
    operation VARCHAR(40) NOT NULL, 
    model_ref UNIQUEIDENTIFIER NULL, 
    updated_at DATETIME2(3) NULL, 
    updated_by UNIQUEIDENTIFIER NULL, 
    CONSTRAINT pk_operation_assignments PRIMARY KEY (operation), 
    CONSTRAINT fk_operation_assignments_model FOREIGN KEY(model_ref) REFERENCES ai.models (id), 
    CONSTRAINT fk_operation_assignments_updated_by FOREIGN KEY(updated_by) REFERENCES auth.users (id), 
    CONSTRAINT ck_operation_assignments_operation CHECK (operation IN ('ANALISIS_PERFILES', 'GENERACION_PROMPTS', 'EXTRACCION_CV', 'EVALUACION_DOCUMENTAL', 'ANALISIS_LLAMADAS', 'LECTURA_DOCUMENTOS', 'RESUMEN_PRUEBAS', 'SINTESIS_EXPEDIENTES'))
);

GO

UPDATE alembic_version SET version_num='0005' WHERE alembic_version.version_num = '0004';

GO

-- Running upgrade 0005 -> 0006

CREATE TABLE vacancy.job_profile_versions (
    id UNIQUEIDENTIFIER NOT NULL, 
    vacancy_id UNIQUEIDENTIFIER NOT NULL, 
    version_number INTEGER NOT NULL, 
    origin VARCHAR(20) NOT NULL, 
    content NVARCHAR(max) NOT NULL, 
    change_note NVARCHAR(300) NULL, 
    source_file_id UNIQUEIDENTIFIER NULL, 
    created_at DATETIME2(3) NOT NULL, 
    created_by UNIQUEIDENTIFIER NOT NULL, 
    CONSTRAINT pk_job_profile_versions PRIMARY KEY (id), 
    CONSTRAINT uq_job_profile_versions_number UNIQUE (vacancy_id, version_number), 
    CONSTRAINT fk_job_profile_versions_vacancy FOREIGN KEY(vacancy_id) REFERENCES vacancy.vacancies (id), 
    CONSTRAINT fk_job_profile_versions_file FOREIGN KEY(source_file_id) REFERENCES files.file_assets (id), 
    CONSTRAINT fk_job_profile_versions_created_by FOREIGN KEY(created_by) REFERENCES auth.users (id), 
    CONSTRAINT ck_job_profile_versions_origin CHECK (origin IN ('MANUAL', 'IA')), 
    CONSTRAINT ck_job_profile_versions_number CHECK (version_number >= 1), 
    CONSTRAINT ck_job_profile_versions_json CHECK (ISJSON(content) = 1)
);

GO

CREATE TABLE ai.prompt_versions (
    id UNIQUEIDENTIFIER NOT NULL, 
    vacancy_id UNIQUEIDENTIFIER NOT NULL, 
    version_number INTEGER NOT NULL, 
    status VARCHAR(20) NOT NULL, 
    profile_version_id UNIQUEIDENTIFIER NOT NULL, 
    pass_threshold NUMERIC(5, 2) NOT NULL, 
    layers NVARCHAR(max) NOT NULL, 
    revision INTEGER NOT NULL, 
    duplicated_from UNIQUEIDENTIFIER NULL, 
    created_at DATETIME2(3) NOT NULL, 
    created_by UNIQUEIDENTIFIER NOT NULL, 
    updated_at DATETIME2(3) NOT NULL, 
    updated_by UNIQUEIDENTIFIER NOT NULL, 
    submitted_at DATETIME2(3) NULL, 
    submitted_by UNIQUEIDENTIFIER NULL, 
    approved_at DATETIME2(3) NULL, 
    approved_by UNIQUEIDENTIFIER NULL, 
    archived_at DATETIME2(3) NULL, 
    archived_by UNIQUEIDENTIFIER NULL, 
    CONSTRAINT pk_prompt_versions PRIMARY KEY (id), 
    CONSTRAINT uq_prompt_versions_number UNIQUE (vacancy_id, version_number), 
    CONSTRAINT fk_prompt_versions_vacancy FOREIGN KEY(vacancy_id) REFERENCES vacancy.vacancies (id), 
    CONSTRAINT fk_prompt_versions_profile FOREIGN KEY(profile_version_id) REFERENCES vacancy.job_profile_versions (id), 
    CONSTRAINT fk_prompt_versions_duplicated FOREIGN KEY(duplicated_from) REFERENCES ai.prompt_versions (id), 
    CONSTRAINT fk_prompt_versions_created_by FOREIGN KEY(created_by) REFERENCES auth.users (id), 
    CONSTRAINT fk_prompt_versions_updated_by FOREIGN KEY(updated_by) REFERENCES auth.users (id), 
    CONSTRAINT fk_prompt_versions_submitted_by FOREIGN KEY(submitted_by) REFERENCES auth.users (id), 
    CONSTRAINT fk_prompt_versions_approved_by FOREIGN KEY(approved_by) REFERENCES auth.users (id), 
    CONSTRAINT fk_prompt_versions_archived_by FOREIGN KEY(archived_by) REFERENCES auth.users (id), 
    CONSTRAINT ck_prompt_versions_status CHECK (status IN ('BORRADOR', 'EN_REVISION', 'APROBADO', 'ARCHIVADO')), 
    CONSTRAINT ck_prompt_versions_threshold CHECK (pass_threshold > 0 AND pass_threshold <= 100), 
    CONSTRAINT ck_prompt_versions_approved CHECK (status <> 'APROBADO' OR (approved_at IS NOT NULL AND approved_by IS NOT NULL)), 
    CONSTRAINT ck_prompt_versions_layers_json CHECK (ISJSON(layers) = 1)
);

GO

CREATE INDEX ix_prompt_versions_vacancy_status ON ai.prompt_versions (vacancy_id, status);

GO

CREATE TABLE ai.rubric_criteria (
    id UNIQUEIDENTIFIER NOT NULL, 
    prompt_version_id UNIQUEIDENTIFIER NOT NULL, 
    position INTEGER NOT NULL, 
    name NVARCHAR(200) NOT NULL, 
    description NVARCHAR(1000) NOT NULL, 
    kind VARCHAR(20) NOT NULL, 
    weight NUMERIC(6, 2) NOT NULL, 
    levels NVARCHAR(max) NOT NULL, 
    origin VARCHAR(20) NOT NULL, 
    CONSTRAINT pk_rubric_criteria PRIMARY KEY (id), 
    CONSTRAINT uq_rubric_criteria_position UNIQUE (prompt_version_id, position), 
    CONSTRAINT fk_rubric_criteria_prompt FOREIGN KEY(prompt_version_id) REFERENCES ai.prompt_versions (id), 
    CONSTRAINT ck_rubric_criteria_kind CHECK (kind IN ('INDISPENSABLE', 'DESEABLE')), 
    CONSTRAINT ck_rubric_criteria_origin CHECK (origin IN ('PERFIL', 'MANUAL')), 
    CONSTRAINT ck_rubric_criteria_weight CHECK (weight >= 0 AND weight <= 100), 
    CONSTRAINT ck_rubric_criteria_levels_json CHECK (ISJSON(levels) = 1)
);

GO

UPDATE alembic_version SET version_num='0006' WHERE alembic_version.version_num = '0005';

GO

COMMIT;

GO


GO
SET NOEXEC OFF;
GO
