/* ============================================================================
   Sistema Integral de Reclutamiento e IA - Actualización 0004 -> 0005
   Versión del esquema: 0004 -> 0005
   Generado: 2026-11-12 20:41 (UTC) con scripts/generate_sql.py

   Aplica solo los cambios de la versión 0005 sobre una base que ya
   está en la versión 0004. Si está en otra versión, no hace nada.

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
IF OBJECT_ID(N'dbo.alembic_version') IS NULL OR NOT EXISTS (SELECT 1 FROM dbo.alembic_version WHERE version_num = N'0004')
BEGIN
    RAISERROR(N'La base no esta en la version 0004. No se aplico ningun cambio.', 16, 1);
    SET NOEXEC ON;
END
GO

BEGIN TRANSACTION;

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

COMMIT;

GO


GO
SET NOEXEC OFF;
GO
