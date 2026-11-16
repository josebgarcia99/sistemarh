/* ============================================================================
   Sistema Integral de Reclutamiento e IA - Actualización 0016 -> 0017
   Versión del esquema: 0016 -> 0017
   Generado: 2026-11-16 04:00 (UTC) con scripts/generate_sql.py

   Aplica solo los cambios de la versión 0017 sobre una base que ya
   está en la versión 0016. Si está en otra versión, no hace nada.

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
IF OBJECT_ID(N'dbo.alembic_version') IS NULL OR NOT EXISTS (SELECT 1 FROM dbo.alembic_version WHERE version_num = N'0016')
BEGIN
    RAISERROR(N'La base no esta en la version 0016. No se aplico ningun cambio.', 16, 1);
    SET NOEXEC ON;
END
GO

BEGIN TRANSACTION;

-- Running upgrade 0016 -> 0017

ALTER TABLE recruitment.assessments DROP CONSTRAINT ck_assessments_kind;

GO

ALTER TABLE recruitment.assessments ADD CONSTRAINT ck_assessments_kind CHECK (kind IN ('PSICOMETRIA', 'ENTREVISTA', 'PRUEBA_TECNICA', 'ESTUDIO_SOCIOECONOMICO', 'REFERENCIAS'));

GO

ALTER TABLE recruitment.question_banks DROP CONSTRAINT ck_question_banks_scope;

GO

ALTER TABLE recruitment.question_banks ADD CONSTRAINT ck_question_banks_scope CHECK (scope IN ('PRIVADO', 'COMPARTIDO', 'GENERAL'));

GO

ALTER TABLE recruitment.call_sessions ADD general_version_ids VARCHAR(800) NOT NULL DEFAULT '[]';

GO

UPDATE alembic_version SET version_num='0017' WHERE alembic_version.version_num = '0016';

GO

COMMIT;

GO


GO
SET NOEXEC OFF;
GO
