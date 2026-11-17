/* ============================================================================
   Sistema Integral de Reclutamiento e IA - Actualización 0017 -> 0018
   Versión del esquema: 0017 -> 0018
   Generado: 2026-11-17 18:26 (UTC) con scripts/generate_sql.py

   Aplica solo los cambios de la versión 0018 sobre una base que ya
   está en la versión 0017. Si está en otra versión, no hace nada.

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
IF OBJECT_ID(N'dbo.alembic_version') IS NULL OR NOT EXISTS (SELECT 1 FROM dbo.alembic_version WHERE version_num = N'0017')
BEGIN
    RAISERROR(N'La base no esta en la version 0017. No se aplico ningun cambio.', 16, 1);
    SET NOEXEC ON;
END
GO

BEGIN TRANSACTION;

-- Running upgrade 0017 -> 0018

ALTER TABLE recruitment.call_sessions ADD questions NVARCHAR(max) NULL;

GO

ALTER TABLE recruitment.call_sessions ADD CONSTRAINT ck_call_sessions_questions_json CHECK (questions IS NULL OR ISJSON(questions) = 1);

GO

DROP INDEX ix_call_sessions_bank_version ON recruitment.call_sessions;

GO

ALTER TABLE recruitment.call_sessions DROP CONSTRAINT fk_call_sessions_bank_version;

GO

ALTER TABLE recruitment.call_sessions ALTER COLUMN bank_version_id UNIQUEIDENTIFIER NULL;

GO

ALTER TABLE recruitment.call_sessions ADD CONSTRAINT fk_call_sessions_bank_version FOREIGN KEY(bank_version_id) REFERENCES recruitment.question_bank_versions (id);

GO

CREATE INDEX ix_call_sessions_bank_version ON recruitment.call_sessions (bank_version_id);

GO

CREATE TABLE recruitment.call_session_banks (
    call_id UNIQUEIDENTIFIER NOT NULL, 
    bank_id UNIQUEIDENTIFIER NOT NULL, 
    CONSTRAINT pk_call_session_banks PRIMARY KEY (call_id, bank_id), 
    CONSTRAINT fk_call_session_banks_call FOREIGN KEY(call_id) REFERENCES recruitment.call_sessions (id), 
    CONSTRAINT fk_call_session_banks_bank FOREIGN KEY(bank_id) REFERENCES recruitment.question_banks (id)
);

GO

CREATE INDEX ix_call_session_banks_bank ON recruitment.call_session_banks (bank_id);

GO

INSERT INTO recruitment.call_session_banks (call_id, bank_id)
SELECT c.id, v.bank_id
FROM recruitment.call_sessions AS c
JOIN recruitment.question_bank_versions AS v ON v.id = c.bank_version_id;

GO

UPDATE alembic_version SET version_num='0018' WHERE alembic_version.version_num = '0017';

GO

COMMIT;

GO


GO
SET NOEXEC OFF;
GO
