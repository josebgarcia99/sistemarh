/* ============================================================================
   Sistema Integral de Reclutamiento e IA - Actualización 0008 -> 0009
   Versión del esquema: 0008 -> 0009
   Generado: 2026-11-12 20:00 (UTC) con scripts/generate_sql.py

   Aplica solo los cambios de la versión 0009 sobre una base que ya
   está en la versión 0008. Si está en otra versión, no hace nada.

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

-- Running upgrade 0008 -> 0009

IF NOT EXISTS (SELECT 1 FROM sys.schemas WHERE name = N'recruitment') EXEC(N'CREATE SCHEMA [recruitment]');

GO

ALTER TABLE ai.cv_batch_items ADD extraction NVARCHAR(max) NULL;

GO

CREATE TABLE recruitment.pipeline_versions (
    id UNIQUEIDENTIFIER NOT NULL, 
    version_number INTEGER NOT NULL, 
    created_at DATETIME2(3) NOT NULL, 
    created_by UNIQUEIDENTIFIER NULL, 
    CONSTRAINT pk_pipeline_versions PRIMARY KEY (id), 
    CONSTRAINT uq_pipeline_versions_number UNIQUE (version_number), 
    CONSTRAINT fk_pipeline_versions_creator FOREIGN KEY(created_by) REFERENCES auth.users (id)
);

GO

CREATE TABLE recruitment.pipeline_stages (
    id UNIQUEIDENTIFIER NOT NULL, 
    pipeline_version_id UNIQUEIDENTIFIER NOT NULL, 
    position INTEGER NOT NULL, 
    name NVARCHAR(100) NOT NULL, 
    kind VARCHAR(30) NOT NULL, 
    is_optional BIT NOT NULL, 
    CONSTRAINT pk_pipeline_stages PRIMARY KEY (id), 
    CONSTRAINT uq_pipeline_stages_position UNIQUE (pipeline_version_id, position), 
    CONSTRAINT fk_pipeline_stages_version FOREIGN KEY(pipeline_version_id) REFERENCES recruitment.pipeline_versions (id), 
    CONSTRAINT ck_pipeline_stages_kind CHECK (kind IN ('EVALUACION_CV', 'REVISION_RH', 'LLAMADA', 'PSICOMETRIA', 'ENTREVISTA', 'PRUEBA_TECNICA', 'ESTUDIO_SOCIOECONOMICO', 'RESULTADO', 'OTRA'))
);

GO

CREATE TABLE recruitment.campaigns (
    id UNIQUEIDENTIFIER NOT NULL, 
    vacancy_id UNIQUEIDENTIFIER NOT NULL, 
    number INTEGER NOT NULL, 
    name NVARCHAR(100) NOT NULL, 
    status VARCHAR(20) NOT NULL, 
    pipeline_version_id UNIQUEIDENTIFIER NOT NULL, 
    opened_at DATETIME2(3) NOT NULL, 
    opened_by UNIQUEIDENTIFIER NULL, 
    closed_at DATETIME2(3) NULL, 
    closed_by UNIQUEIDENTIFIER NULL, 
    CONSTRAINT pk_campaigns PRIMARY KEY (id), 
    CONSTRAINT uq_campaigns_number UNIQUE (vacancy_id, number), 
    CONSTRAINT fk_campaigns_vacancy FOREIGN KEY(vacancy_id) REFERENCES vacancy.vacancies (id), 
    CONSTRAINT fk_campaigns_pipeline FOREIGN KEY(pipeline_version_id) REFERENCES recruitment.pipeline_versions (id), 
    CONSTRAINT fk_campaigns_opener FOREIGN KEY(opened_by) REFERENCES auth.users (id), 
    CONSTRAINT fk_campaigns_closer FOREIGN KEY(closed_by) REFERENCES auth.users (id), 
    CONSTRAINT ck_campaigns_status CHECK (status IN ('ABIERTA', 'CERRADA'))
);

GO

CREATE TABLE recruitment.candidates (
    id UNIQUEIDENTIFIER NOT NULL, 
    full_name NVARCHAR(200) NOT NULL, 
    email NVARCHAR(254) NULL, 
    phone NVARCHAR(40) NULL, 
    created_at DATETIME2(3) NOT NULL, 
    created_by UNIQUEIDENTIFIER NULL, 
    updated_at DATETIME2(3) NOT NULL, 
    CONSTRAINT pk_candidates PRIMARY KEY (id), 
    CONSTRAINT fk_candidates_creator FOREIGN KEY(created_by) REFERENCES auth.users (id)
);

GO

CREATE UNIQUE INDEX uq_candidates_email ON recruitment.candidates (email) WHERE email IS NOT NULL;

GO

CREATE TABLE recruitment.applications (
    id UNIQUEIDENTIFIER NOT NULL, 
    candidate_id UNIQUEIDENTIFIER NOT NULL, 
    campaign_id UNIQUEIDENTIFIER NOT NULL, 
    vacancy_id UNIQUEIDENTIFIER NOT NULL, 
    stage_id UNIQUEIDENTIFIER NOT NULL, 
    status VARCHAR(20) NOT NULL, 
    cv_file_id UNIQUEIDENTIFIER NULL, 
    evaluation_item_id UNIQUEIDENTIFIER NULL, 
    ai_classification VARCHAR(20) NULL, 
    ai_score NUMERIC(5, 2) NULL, 
    due_at DATETIME2(3) NULL, 
    created_at DATETIME2(3) NOT NULL, 
    created_by UNIQUEIDENTIFIER NULL, 
    updated_at DATETIME2(3) NOT NULL, 
    CONSTRAINT pk_applications PRIMARY KEY (id), 
    CONSTRAINT uq_applications_candidate UNIQUE (candidate_id, campaign_id), 
    CONSTRAINT fk_applications_candidate FOREIGN KEY(candidate_id) REFERENCES recruitment.candidates (id), 
    CONSTRAINT fk_applications_campaign FOREIGN KEY(campaign_id) REFERENCES recruitment.campaigns (id), 
    CONSTRAINT fk_applications_vacancy FOREIGN KEY(vacancy_id) REFERENCES vacancy.vacancies (id), 
    CONSTRAINT fk_applications_stage FOREIGN KEY(stage_id) REFERENCES recruitment.pipeline_stages (id), 
    CONSTRAINT fk_applications_cv FOREIGN KEY(cv_file_id) REFERENCES files.file_assets (id), 
    CONSTRAINT fk_applications_evaluation FOREIGN KEY(evaluation_item_id) REFERENCES ai.cv_batch_items (id), 
    CONSTRAINT fk_applications_creator FOREIGN KEY(created_by) REFERENCES auth.users (id), 
    CONSTRAINT ck_applications_status CHECK (status IN ('ACTIVA', 'DESISTIO', 'DESCARTADA', 'CANCELADA'))
);

GO

CREATE INDEX ix_applications_campaign ON recruitment.applications (campaign_id, stage_id, status);

GO

CREATE INDEX ix_applications_vacancy ON recruitment.applications (vacancy_id);

GO

CREATE INDEX ix_applications_file ON recruitment.applications (cv_file_id);

GO

CREATE TABLE recruitment.application_movements (
    id UNIQUEIDENTIFIER NOT NULL, 
    application_id UNIQUEIDENTIFIER NOT NULL, 
    sequence INTEGER NOT NULL, 
    kind VARCHAR(20) NOT NULL, 
    from_stage_id UNIQUEIDENTIFIER NULL, 
    to_stage_id UNIQUEIDENTIFIER NULL, 
    note NVARCHAR(500) NULL, 
    due_at DATETIME2(3) NULL, 
    group_id UNIQUEIDENTIFIER NULL, 
    occurred_at DATETIME2(3) NOT NULL, 
    actor_user_id UNIQUEIDENTIFIER NULL, 
    CONSTRAINT pk_application_movements PRIMARY KEY (id), 
    CONSTRAINT uq_application_movements_sequence UNIQUE (application_id, sequence), 
    CONSTRAINT fk_application_movements_application FOREIGN KEY(application_id) REFERENCES recruitment.applications (id), 
    CONSTRAINT fk_application_movements_from FOREIGN KEY(from_stage_id) REFERENCES recruitment.pipeline_stages (id), 
    CONSTRAINT fk_application_movements_to FOREIGN KEY(to_stage_id) REFERENCES recruitment.pipeline_stages (id), 
    CONSTRAINT fk_application_movements_actor FOREIGN KEY(actor_user_id) REFERENCES auth.users (id), 
    CONSTRAINT ck_application_movements_kind CHECK (kind IN ('ALTA', 'AVANCE', 'RETROCESO', 'OMISION', 'DESISTIMIENTO', 'DESCARTE', 'CANCELACION', 'REACTIVACION', 'REPROGRAMACION', 'INCIDENCIA'))
);

GO

CREATE TABLE recruitment.question_banks (
    id UNIQUEIDENTIFIER NOT NULL, 
    name NVARCHAR(150) NOT NULL, 
    description NVARCHAR(500) NULL, 
    owner_user_id UNIQUEIDENTIFIER NOT NULL, 
    scope VARCHAR(20) NOT NULL, 
    status VARCHAR(20) NOT NULL, 
    duplicated_from UNIQUEIDENTIFIER NULL, 
    created_at DATETIME2(3) NOT NULL, 
    updated_at DATETIME2(3) NOT NULL, 
    CONSTRAINT pk_question_banks PRIMARY KEY (id), 
    CONSTRAINT fk_question_banks_owner FOREIGN KEY(owner_user_id) REFERENCES auth.users (id), 
    CONSTRAINT fk_question_banks_source FOREIGN KEY(duplicated_from) REFERENCES recruitment.question_banks (id), 
    CONSTRAINT ck_question_banks_scope CHECK (scope IN ('PRIVADO', 'COMPARTIDO')), 
    CONSTRAINT ck_question_banks_status CHECK (status IN ('ACTIVO', 'ARCHIVADO'))
);

GO

CREATE INDEX ix_question_banks_owner ON recruitment.question_banks (owner_user_id, status);

GO

CREATE TABLE recruitment.question_bank_versions (
    id UNIQUEIDENTIFIER NOT NULL, 
    bank_id UNIQUEIDENTIFIER NOT NULL, 
    version_number INTEGER NOT NULL, 
    questions NVARCHAR(max) NOT NULL, 
    change_note NVARCHAR(300) NULL, 
    created_at DATETIME2(3) NOT NULL, 
    created_by UNIQUEIDENTIFIER NOT NULL, 
    CONSTRAINT pk_question_bank_versions PRIMARY KEY (id), 
    CONSTRAINT uq_question_bank_versions_number UNIQUE (bank_id, version_number), 
    CONSTRAINT fk_question_bank_versions_bank FOREIGN KEY(bank_id) REFERENCES recruitment.question_banks (id), 
    CONSTRAINT fk_question_bank_versions_creator FOREIGN KEY(created_by) REFERENCES auth.users (id), 
    CONSTRAINT ck_question_bank_versions_json CHECK (ISJSON(questions) = 1)
);

GO

CREATE TABLE recruitment.call_sessions (
    id UNIQUEIDENTIFIER NOT NULL, 
    application_id UNIQUEIDENTIFIER NOT NULL, 
    vacancy_id UNIQUEIDENTIFIER NOT NULL, 
    bank_version_id UNIQUEIDENTIFIER NOT NULL, 
    status VARCHAR(20) NOT NULL, 
    called_at DATETIME2(3) NOT NULL, 
    notes NVARCHAR(max) NOT NULL, 
    answers NVARCHAR(max) NOT NULL, 
    analysis NVARCHAR(max) NULL, 
    analysis_at DATETIME2(3) NULL, 
    analysis_by UNIQUEIDENTIFIER NULL, 
    created_at DATETIME2(3) NOT NULL, 
    created_by UNIQUEIDENTIFIER NOT NULL, 
    updated_at DATETIME2(3) NOT NULL, 
    closed_at DATETIME2(3) NULL, 
    CONSTRAINT pk_call_sessions PRIMARY KEY (id), 
    CONSTRAINT fk_call_sessions_application FOREIGN KEY(application_id) REFERENCES recruitment.applications (id), 
    CONSTRAINT fk_call_sessions_vacancy FOREIGN KEY(vacancy_id) REFERENCES vacancy.vacancies (id), 
    CONSTRAINT fk_call_sessions_bank_version FOREIGN KEY(bank_version_id) REFERENCES recruitment.question_bank_versions (id), 
    CONSTRAINT fk_call_sessions_analyst FOREIGN KEY(analysis_by) REFERENCES auth.users (id), 
    CONSTRAINT fk_call_sessions_creator FOREIGN KEY(created_by) REFERENCES auth.users (id), 
    CONSTRAINT ck_call_sessions_status CHECK (status IN ('BORRADOR', 'CERRADA')), 
    CONSTRAINT ck_call_sessions_answers_json CHECK (ISJSON(answers) = 1)
);

GO

CREATE INDEX ix_call_sessions_application ON recruitment.call_sessions (application_id, called_at);

GO

UPDATE alembic_version SET version_num='0009' WHERE alembic_version.version_num = '0008';

GO

COMMIT;

GO


GO
SET NOEXEC OFF;
GO
