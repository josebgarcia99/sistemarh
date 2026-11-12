/* ============================================================================
   Sistema Integral de Reclutamiento e IA - Actualización 0006 -> 0007
   Versión del esquema: 0006 -> 0007
   Generado: 2026-11-12 19:37 (UTC) con scripts/generate_sql.py

   Aplica solo los cambios de la versión 0007 sobre una base que ya
   está en la versión 0006. Si está en otra versión, no hace nada.

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
IF OBJECT_ID(N'dbo.alembic_version') IS NULL OR NOT EXISTS (SELECT 1 FROM dbo.alembic_version WHERE version_num = N'0006')
BEGIN
    RAISERROR(N'La base no esta en la version 0006. No se aplico ningun cambio.', 16, 1);
    SET NOEXEC ON;
END
GO

BEGIN TRANSACTION;

-- Running upgrade 0006 -> 0007

ALTER TABLE ai.models ADD input_price NUMERIC(12, 4) NULL;

GO

ALTER TABLE ai.models ADD output_price NUMERIC(12, 4) NULL;

GO

CREATE TABLE ai.executions (
    id UNIQUEIDENTIFIER NOT NULL, 
    occurred_at DATETIME2(3) NOT NULL, 
    operation VARCHAR(40) NOT NULL, 
    provider_code VARCHAR(20) NOT NULL, 
    model_id NVARCHAR(200) NOT NULL, 
    status VARCHAR(20) NOT NULL, 
    attempts INTEGER NOT NULL, 
    duration_ms INTEGER NOT NULL, 
    input_tokens INTEGER NULL, 
    output_tokens INTEGER NULL, 
    estimated_cost_usd NUMERIC(12, 6) NULL, 
    confirmed_cost_usd NUMERIC(12, 6) NULL, 
    error_kind VARCHAR(20) NULL, 
    actor_user_id UNIQUEIDENTIFIER NULL, 
    vacancy_id UNIQUEIDENTIFIER NULL, 
    CONSTRAINT pk_executions PRIMARY KEY (id), 
    CONSTRAINT ck_executions_status CHECK (status IN ('CORRECTA', 'FALLIDA')), 
    CONSTRAINT ck_executions_attempts CHECK (attempts >= 1)
);

GO

CREATE INDEX ix_executions_provider_date ON ai.executions (provider_code, occurred_at);

GO

CREATE INDEX ix_executions_date ON ai.executions (occurred_at);

GO

UPDATE alembic_version SET version_num='0007' WHERE alembic_version.version_num = '0006';

GO

COMMIT;

GO


GO
SET NOEXEC OFF;
GO
