/* ============================================================================
   Sistema Integral de Reclutamiento e IA - Actualización 0002 -> 0003
   Versión del esquema: 0002 -> 0003
   Generado: 2026-11-11 19:31 (UTC) con scripts/generate_sql.py

   Aplica solo los cambios de la versión 0003 sobre una base que ya
   está en la versión 0002. Si está en otra versión, no hace nada.

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
IF OBJECT_ID(N'dbo.alembic_version') IS NULL OR NOT EXISTS (SELECT 1 FROM dbo.alembic_version WHERE version_num = N'0002')
BEGIN
    RAISERROR(N'La base no esta en la version 0002. No se aplico ningun cambio.', 16, 1);
    SET NOEXEC ON;
END
GO

BEGIN TRANSACTION;

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

COMMIT;

GO


GO
SET NOEXEC OFF;
GO
