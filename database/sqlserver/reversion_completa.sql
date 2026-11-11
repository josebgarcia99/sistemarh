/* ============================================================================
   Sistema Integral de Reclutamiento e IA - Reversión completa (DESTRUCTIVO)
   Versión del esquema: 0008 -> (vacía)
   Generado: 2026-11-11 17:28 (UTC) con scripts/generate_sql.py

   ELIMINA todas las tablas y esquemas del sistema, con todos sus datos.
   Solo para entornos de prueba. Nunca ejecutar en producción sin respaldo.

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
IF OBJECT_ID(N'dbo.alembic_version') IS NULL OR NOT EXISTS (SELECT 1 FROM dbo.alembic_version WHERE version_num = N'0008')
BEGIN
    RAISERROR(N'La base no esta en la version 0008. No se aplico ningun cambio.', 16, 1);
    SET NOEXEC ON;
END
GO

BEGIN TRANSACTION;

-- Running downgrade 0008 -> 0007

DROP TABLE ai.cv_batch_items;

GO

DROP TABLE ai.cv_batches;

GO

ALTER TABLE files.file_assets DROP CONSTRAINT ck_file_assets_document_type;

GO

ALTER TABLE files.file_assets ADD CONSTRAINT ck_file_assets_document_type CHECK (document_type IN ('CV', 'PERFIL_PUESTO', 'PSICOMETRIA', 'PRUEBA_TECNICA', 'ESTUDIO_SOCIOECONOMICO', 'ADJUNTO'));

GO

UPDATE alembic_version SET version_num='0007' WHERE alembic_version.version_num = '0008';

GO

-- Running downgrade 0007 -> 0006

DROP TABLE ai.executions;

GO

ALTER TABLE ai.models DROP COLUMN output_price;

GO

ALTER TABLE ai.models DROP COLUMN input_price;

GO

UPDATE alembic_version SET version_num='0006' WHERE alembic_version.version_num = '0007';

GO

-- Running downgrade 0006 -> 0005

DROP TABLE ai.rubric_criteria;

GO

DROP TABLE ai.prompt_versions;

GO

DROP TABLE vacancy.job_profile_versions;

GO

UPDATE alembic_version SET version_num='0005' WHERE alembic_version.version_num = '0006';

GO

-- Running downgrade 0005 -> 0004

DROP TABLE ai.operation_assignments;

GO

DROP TABLE ai.models;

GO

DROP TABLE ai.provider_credentials;

GO

DROP TABLE ai.providers;

GO

DROP SCHEMA [ai];

GO

UPDATE alembic_version SET version_num='0004' WHERE alembic_version.version_num = '0005';

GO

-- Running downgrade 0004 -> 0003

ALTER TABLE files.file_assets DROP CONSTRAINT ck_file_assets_stored_complete;

GO

ALTER TABLE files.file_assets DROP COLUMN encryption_key_id;

GO

ALTER TABLE files.file_assets DROP COLUMN stored_sha256;

GO

ALTER TABLE files.file_assets DROP COLUMN stored_size_bytes;

GO

UPDATE alembic_version SET version_num='0003' WHERE alembic_version.version_num = '0004';

GO

-- Running downgrade 0003 -> 0002

DROP TABLE files.file_assets;

GO

DROP SCHEMA [files];

GO

UPDATE alembic_version SET version_num='0002' WHERE alembic_version.version_num = '0003';

GO

-- Running downgrade 0002 -> 0001

DROP TABLE vacancy.vacancy_ownership_history;

GO

DROP TABLE vacancy.vacancy_transfers;

GO

DROP TABLE vacancy.vacancy_sensitive_grants;

GO

DROP TABLE vacancy.vacancy_members;

GO

DROP TABLE vacancy.vacancies;

GO

DROP SCHEMA [vacancy];

GO

UPDATE alembic_version SET version_num='0001' WHERE alembic_version.version_num = '0002';

GO

-- Running downgrade 0001 -> 

DROP TABLE ops.audit_events;

GO

DROP TABLE auth.sessions;

GO

DROP TABLE auth.user_roles;

GO

DROP TABLE auth.users;

GO

DROP TABLE auth.roles;

GO

DROP SCHEMA [ops];

GO

DROP SCHEMA [auth];

GO

DELETE FROM alembic_version WHERE alembic_version.version_num = '0001';

GO

COMMIT;

GO


GO
SET NOEXEC OFF;
GO
