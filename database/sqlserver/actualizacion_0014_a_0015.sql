/* ============================================================================
   Sistema Integral de Reclutamiento e IA - Actualización 0014 -> 0015
   Versión del esquema: 0014 -> 0015
   Generado: 2026-11-12 20:21 (UTC) con scripts/generate_sql.py

   Aplica solo los cambios de la versión 0015 sobre una base que ya
   está en la versión 0014. Si está en otra versión, no hace nada.

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
IF OBJECT_ID(N'dbo.alembic_version') IS NULL OR NOT EXISTS (SELECT 1 FROM dbo.alembic_version WHERE version_num = N'0014')
BEGIN
    RAISERROR(N'La base no esta en la version 0014. No se aplico ningun cambio.', 16, 1);
    SET NOEXEC ON;
END
GO

BEGIN TRANSACTION;

-- Running upgrade 0014 -> 0015

ALTER TABLE recruitment.application_syntheses ADD includes_study BIT NOT NULL DEFAULT 0;

GO

UPDATE alembic_version SET version_num='0015' WHERE alembic_version.version_num = '0014';

GO

COMMIT;

GO


GO
SET NOEXEC OFF;
GO
