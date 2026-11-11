/* ============================================================================
   Sistema Integral de Reclutamiento e IA - Actualización 0009 -> 0010
   Versión del esquema: 0009 -> 0010
   Generado: 2026-11-11 19:31 (UTC) con scripts/generate_sql.py

   Aplica solo los cambios de la versión 0010 sobre una base que ya
   está en la versión 0009. Si está en otra versión, no hace nada.

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
IF OBJECT_ID(N'dbo.alembic_version') IS NULL OR NOT EXISTS (SELECT 1 FROM dbo.alembic_version WHERE version_num = N'0009')
BEGIN
    RAISERROR(N'La base no esta en la version 0009. No se aplico ningun cambio.', 16, 1);
    SET NOEXEC ON;
END
GO

BEGIN TRANSACTION;

-- Running upgrade 0009 -> 0010

CREATE TABLE recruitment.form_templates (
    id UNIQUEIDENTIFIER NOT NULL, 
    name NVARCHAR(150) NOT NULL, 
    description NVARCHAR(500) NULL, 
    status VARCHAR(20) NOT NULL, 
    created_at DATETIME2(3) NOT NULL, 
    updated_at DATETIME2(3) NOT NULL, 
    CONSTRAINT pk_form_templates PRIMARY KEY (id), 
    CONSTRAINT ck_form_templates_status CHECK (status IN ('ACTIVA', 'ARCHIVADA'))
);

GO

CREATE TABLE recruitment.form_template_versions (
    id UNIQUEIDENTIFIER NOT NULL, 
    template_id UNIQUEIDENTIFIER NOT NULL, 
    version_number INTEGER NOT NULL, 
    sections NVARCHAR(max) NOT NULL, 
    created_at DATETIME2(3) NOT NULL, 
    created_by UNIQUEIDENTIFIER NULL, 
    CONSTRAINT pk_form_template_versions PRIMARY KEY (id), 
    CONSTRAINT uq_form_template_versions_number UNIQUE (template_id, version_number), 
    CONSTRAINT fk_form_template_versions_template FOREIGN KEY(template_id) REFERENCES recruitment.form_templates (id), 
    CONSTRAINT fk_form_template_versions_creator FOREIGN KEY(created_by) REFERENCES auth.users (id), 
    CONSTRAINT ck_form_template_versions_json CHECK (ISJSON(sections) = 1)
);

GO

CREATE TABLE recruitment.assessments (
    id UNIQUEIDENTIFIER NOT NULL, 
    application_id UNIQUEIDENTIFIER NOT NULL, 
    vacancy_id UNIQUEIDENTIFIER NOT NULL, 
    kind VARCHAR(30) NOT NULL, 
    status VARCHAR(20) NOT NULL, 
    event_date DATETIME2(3) NULL, 
    file_id UNIQUEIDENTIFIER NULL, 
    template_version_id UNIQUEIDENTIFIER NULL, 
    data NVARCHAR(max) NOT NULL, 
    score NUMERIC(5, 2) NULL, 
    ai_summary NVARCHAR(max) NULL, 
    ai_summary_at DATETIME2(3) NULL, 
    ai_summary_by UNIQUEIDENTIFIER NULL, 
    version INTEGER NOT NULL, 
    created_at DATETIME2(3) NOT NULL, 
    created_by UNIQUEIDENTIFIER NOT NULL, 
    updated_at DATETIME2(3) NOT NULL, 
    updated_by UNIQUEIDENTIFIER NOT NULL, 
    CONSTRAINT pk_assessments PRIMARY KEY (id), 
    CONSTRAINT fk_assessments_application FOREIGN KEY(application_id) REFERENCES recruitment.applications (id), 
    CONSTRAINT fk_assessments_vacancy FOREIGN KEY(vacancy_id) REFERENCES vacancy.vacancies (id), 
    CONSTRAINT fk_assessments_file FOREIGN KEY(file_id) REFERENCES files.file_assets (id), 
    CONSTRAINT fk_assessments_template FOREIGN KEY(template_version_id) REFERENCES recruitment.form_template_versions (id), 
    CONSTRAINT fk_assessments_summary_author FOREIGN KEY(ai_summary_by) REFERENCES auth.users (id), 
    CONSTRAINT fk_assessments_creator FOREIGN KEY(created_by) REFERENCES auth.users (id), 
    CONSTRAINT fk_assessments_editor FOREIGN KEY(updated_by) REFERENCES auth.users (id), 
    CONSTRAINT ck_assessments_kind CHECK (kind IN ('PSICOMETRIA', 'ENTREVISTA', 'PRUEBA_TECNICA', 'ESTUDIO_SOCIOECONOMICO')), 
    CONSTRAINT ck_assessments_status CHECK (status IN ('PENDIENTE', 'PRESENTADA', 'NO_PRESENTADA', 'INCOMPLETA', 'NO_APLICA', 'ANULADA', 'VALIDADA', 'PROGRAMADA', 'REALIZADA', 'NO_REALIZADA', 'CANCELADA', 'EN_PROCESO', 'COMPLETADO', 'ANULADO')), 
    CONSTRAINT ck_assessments_data_json CHECK (ISJSON(data) = 1), 
    CONSTRAINT ck_assessments_score CHECK (score IS NULL OR (score >= 0 AND score <= 100)), 
    CONSTRAINT ck_assessments_template CHECK ((kind = 'ESTUDIO_SOCIOECONOMICO' AND template_version_id IS NOT NULL) OR (kind <> 'ESTUDIO_SOCIOECONOMICO' AND template_version_id IS NULL))
);

GO

CREATE INDEX ix_assessments_application ON recruitment.assessments (application_id, kind);

GO

CREATE TABLE recruitment.application_syntheses (
    id UNIQUEIDENTIFIER NOT NULL, 
    application_id UNIQUEIDENTIFIER NOT NULL, 
    vacancy_id UNIQUEIDENTIFIER NOT NULL, 
    result NVARCHAR(max) NOT NULL, 
    sources NVARCHAR(max) NOT NULL, 
    includes_psychometrics BIT NOT NULL, 
    created_at DATETIME2(3) NOT NULL, 
    created_by UNIQUEIDENTIFIER NOT NULL, 
    CONSTRAINT pk_application_syntheses PRIMARY KEY (id), 
    CONSTRAINT fk_application_syntheses_application FOREIGN KEY(application_id) REFERENCES recruitment.applications (id), 
    CONSTRAINT fk_application_syntheses_vacancy FOREIGN KEY(vacancy_id) REFERENCES vacancy.vacancies (id), 
    CONSTRAINT fk_application_syntheses_creator FOREIGN KEY(created_by) REFERENCES auth.users (id), 
    CONSTRAINT ck_application_syntheses_json CHECK (ISJSON(result) = 1)
);

GO

CREATE INDEX ix_application_syntheses_application ON recruitment.application_syntheses (application_id, created_at);

GO

UPDATE alembic_version SET version_num='0010' WHERE alembic_version.version_num = '0009';

GO

COMMIT;

GO


GO
SET NOEXEC OFF;
GO
