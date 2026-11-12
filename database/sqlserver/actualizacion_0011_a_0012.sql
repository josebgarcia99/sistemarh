/* ============================================================================
   Sistema Integral de Reclutamiento e IA - Actualización 0011 -> 0012
   Versión del esquema: 0011 -> 0012
   Generado: 2026-11-12 20:21 (UTC) con scripts/generate_sql.py

   Aplica solo los cambios de la versión 0012 sobre una base que ya
   está en la versión 0011. Si está en otra versión, no hace nada.

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
IF OBJECT_ID(N'dbo.alembic_version') IS NULL OR NOT EXISTS (SELECT 1 FROM dbo.alembic_version WHERE version_num = N'0011')
BEGIN
    RAISERROR(N'La base no esta en la version 0011. No se aplico ningun cambio.', 16, 1);
    SET NOEXEC ON;
END
GO

BEGIN TRANSACTION;

-- Running upgrade 0011 -> 0012

CREATE INDEX ix_call_sessions_vacancy ON recruitment.call_sessions (vacancy_id);

GO

CREATE INDEX ix_call_sessions_bank_version ON recruitment.call_sessions (bank_version_id);

GO

CREATE INDEX ix_cv_batches_prompt_version ON ai.cv_batches (prompt_version_id);

GO

CREATE INDEX ix_applications_evaluation_item ON recruitment.applications (evaluation_item_id);

GO

CREATE INDEX ix_executions_vacancy ON ai.executions (vacancy_id, occurred_at);

GO

UPDATE alembic_version SET version_num='0012' WHERE alembic_version.version_num = '0011';

GO

COMMIT;

GO


GO
SET NOEXEC OFF;
GO
