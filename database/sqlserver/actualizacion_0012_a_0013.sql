/* ============================================================================
   Sistema Integral de Reclutamiento e IA - Actualización 0012 -> 0013
   Versión del esquema: 0012 -> 0013
   Generado: 2026-11-12 19:37 (UTC) con scripts/generate_sql.py

   Aplica solo los cambios de la versión 0013 sobre una base que ya
   está en la versión 0012. Si está en otra versión, no hace nada.

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
IF OBJECT_ID(N'dbo.alembic_version') IS NULL OR NOT EXISTS (SELECT 1 FROM dbo.alembic_version WHERE version_num = N'0012')
BEGIN
    RAISERROR(N'La base no esta en la version 0012. No se aplico ningun cambio.', 16, 1);
    SET NOEXEC ON;
END
GO

BEGIN TRANSACTION;

-- Running upgrade 0012 -> 0013

ALTER TABLE ai.providers DROP CONSTRAINT ck_providers_code;

GO

ALTER TABLE ai.providers ADD CONSTRAINT ck_providers_code CHECK (code IN ('ANTHROPIC', 'OPENAI', 'GEMINI'));

GO

ALTER TABLE vacancy.job_profile_versions DROP CONSTRAINT ck_job_profile_versions_origin;

GO

ALTER TABLE vacancy.job_profile_versions ADD CONSTRAINT ck_job_profile_versions_origin CHECK (origin IN ('MANUAL', 'IA', 'FORMATO'));

GO

UPDATE alembic_version SET version_num='0013' WHERE alembic_version.version_num = '0012';

GO

COMMIT;

GO


GO
SET NOEXEC OFF;
GO
