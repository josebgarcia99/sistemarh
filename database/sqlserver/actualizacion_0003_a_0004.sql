/* ============================================================================
   Sistema Integral de Reclutamiento e IA - Actualización 0003 -> 0004
   Versión del esquema: 0003 -> 0004
   Generado: 2026-11-12 20:41 (UTC) con scripts/generate_sql.py

   Aplica solo los cambios de la versión 0004 sobre una base que ya
   está en la versión 0003. Si está en otra versión, no hace nada.

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
IF OBJECT_ID(N'dbo.alembic_version') IS NULL OR NOT EXISTS (SELECT 1 FROM dbo.alembic_version WHERE version_num = N'0003')
BEGIN
    RAISERROR(N'La base no esta en la version 0003. No se aplico ningun cambio.', 16, 1);
    SET NOEXEC ON;
END
GO

BEGIN TRANSACTION;

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

COMMIT;

GO


GO
SET NOEXEC OFF;
GO
