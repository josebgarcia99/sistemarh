/* ============================================================================
   Sistema Integral de Reclutamiento e IA - Actualización 0007 -> 0008
   Versión del esquema: 0007 -> 0008
   Generado: 2026-11-12 15:47 (UTC) con scripts/generate_sql.py

   Aplica solo los cambios de la versión 0008 sobre una base que ya
   está en la versión 0007. Si está en otra versión, no hace nada.

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
IF OBJECT_ID(N'dbo.alembic_version') IS NULL OR NOT EXISTS (SELECT 1 FROM dbo.alembic_version WHERE version_num = N'0007')
BEGIN
    RAISERROR(N'La base no esta en la version 0007. No se aplico ningun cambio.', 16, 1);
    SET NOEXEC ON;
END
GO

BEGIN TRANSACTION;

-- Running upgrade 0007 -> 0008

ALTER TABLE files.file_assets DROP CONSTRAINT ck_file_assets_document_type;

GO

ALTER TABLE files.file_assets ADD CONSTRAINT ck_file_assets_document_type CHECK (document_type IN ('CV', 'PERFIL_PUESTO', 'PSICOMETRIA', 'PRUEBA_TECNICA', 'ESTUDIO_SOCIOECONOMICO', 'ADJUNTO', 'REPORTE_EVALUACION', 'PAQUETE_CV'));

GO

CREATE TABLE ai.cv_batches (
    id UNIQUEIDENTIFIER NOT NULL, 
    vacancy_id UNIQUEIDENTIFIER NOT NULL, 
    prompt_version_id UNIQUEIDENTIFIER NOT NULL, 
    status VARCHAR(30) NOT NULL, 
    total INTEGER NOT NULL, 
    error NVARCHAR(500) NULL, 
    created_at DATETIME2(3) NOT NULL, 
    created_by UNIQUEIDENTIFIER NOT NULL, 
    started_at DATETIME2(3) NULL, 
    finished_at DATETIME2(3) NULL, 
    report_file_id UNIQUEIDENTIFIER NULL, 
    accepted_zip_file_id UNIQUEIDENTIFIER NULL, 
    rejected_zip_file_id UNIQUEIDENTIFIER NULL, 
    unevaluable_zip_file_id UNIQUEIDENTIFIER NULL, 
    runner_token VARCHAR(40) NULL, 
    lease_until DATETIME2(3) NULL, 
    CONSTRAINT pk_cv_batches PRIMARY KEY (id), 
    CONSTRAINT fk_cv_batches_vacancy FOREIGN KEY(vacancy_id) REFERENCES vacancy.vacancies (id), 
    CONSTRAINT fk_cv_batches_prompt FOREIGN KEY(prompt_version_id) REFERENCES ai.prompt_versions (id), 
    CONSTRAINT fk_cv_batches_creator FOREIGN KEY(created_by) REFERENCES auth.users (id), 
    CONSTRAINT fk_cv_batches_report FOREIGN KEY(report_file_id) REFERENCES files.file_assets (id), 
    CONSTRAINT fk_cv_batches_accepted FOREIGN KEY(accepted_zip_file_id) REFERENCES files.file_assets (id), 
    CONSTRAINT fk_cv_batches_rejected FOREIGN KEY(rejected_zip_file_id) REFERENCES files.file_assets (id), 
    CONSTRAINT fk_cv_batches_unevaluable FOREIGN KEY(unevaluable_zip_file_id) REFERENCES files.file_assets (id), 
    CONSTRAINT ck_cv_batches_status CHECK (status IN ('PENDIENTE', 'EN_COLA', 'PROCESANDO', 'COMPLETADO', 'COMPLETADO_CON_INCIDENCIAS', 'FALLIDO', 'CANCELADO')), 
    CONSTRAINT ck_cv_batches_total CHECK (total >= 1)
);

GO

CREATE INDEX ix_cv_batches_vacancy ON ai.cv_batches (vacancy_id, created_at);

GO

CREATE INDEX ix_cv_batches_status ON ai.cv_batches (status);

GO

CREATE TABLE ai.cv_batch_items (
    id UNIQUEIDENTIFIER NOT NULL, 
    batch_id UNIQUEIDENTIFIER NOT NULL, 
    file_id UNIQUEIDENTIFIER NOT NULL, 
    position INTEGER NOT NULL, 
    status VARCHAR(20) NOT NULL, 
    step VARCHAR(20) NOT NULL, 
    attempts INTEGER NOT NULL, 
    classification VARCHAR(20) NULL, 
    score NUMERIC(5, 2) NULL, 
    result NVARCHAR(max) NULL, 
    error_code VARCHAR(40) NULL, 
    error_message NVARCHAR(500) NULL, 
    duplicate_of UNIQUEIDENTIFIER NULL, 
    execution_id UNIQUEIDENTIFIER NULL, 
    updated_at DATETIME2(3) NOT NULL, 
    CONSTRAINT pk_cv_batch_items PRIMARY KEY (id), 
    CONSTRAINT fk_cv_batch_items_batch FOREIGN KEY(batch_id) REFERENCES ai.cv_batches (id), 
    CONSTRAINT fk_cv_batch_items_file FOREIGN KEY(file_id) REFERENCES files.file_assets (id), 
    CONSTRAINT fk_cv_batch_items_duplicate FOREIGN KEY(duplicate_of) REFERENCES ai.cv_batch_items (id), 
    CONSTRAINT uq_cv_batch_items_position UNIQUE (batch_id, position), 
    CONSTRAINT uq_cv_batch_items_file UNIQUE (batch_id, file_id), 
    CONSTRAINT ck_cv_batch_items_status CHECK (status IN ('PENDIENTE', 'EVALUADO', 'FALLIDO')), 
    CONSTRAINT ck_cv_batch_items_step CHECK (step IN ('RECIBIDO', 'TEXTO_EXTRAIDO', 'ANALIZADO', 'CALIFICADO')), 
    CONSTRAINT ck_cv_batch_items_classification CHECK (classification IS NULL OR classification IN ('ACEPTADO_IA', 'RECHAZADO_IA', 'NO_EVALUABLE')), 
    CONSTRAINT ck_cv_batch_items_score CHECK (score IS NULL OR (score >= 0 AND score <= 100))
);

GO

CREATE INDEX ix_cv_batch_items_status ON ai.cv_batch_items (batch_id, status);

GO

CREATE INDEX ix_cv_batch_items_file ON ai.cv_batch_items (file_id);

GO

UPDATE alembic_version SET version_num='0008' WHERE alembic_version.version_num = '0007';

GO

COMMIT;

GO


GO
SET NOEXEC OFF;
GO
