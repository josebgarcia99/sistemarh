/* ============================================================================
   Sistema Integral de Reclutamiento e IA - Actualización 0005 -> 0006
   Versión del esquema: 0005 -> 0006
   Generado: 2026-11-12 15:47 (UTC) con scripts/generate_sql.py

   Aplica solo los cambios de la versión 0006 sobre una base que ya
   está en la versión 0005. Si está en otra versión, no hace nada.

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
IF OBJECT_ID(N'dbo.alembic_version') IS NULL OR NOT EXISTS (SELECT 1 FROM dbo.alembic_version WHERE version_num = N'0005')
BEGIN
    RAISERROR(N'La base no esta en la version 0005. No se aplico ningun cambio.', 16, 1);
    SET NOEXEC ON;
END
GO

BEGIN TRANSACTION;

-- Running upgrade 0005 -> 0006

CREATE TABLE vacancy.job_profile_versions (
    id UNIQUEIDENTIFIER NOT NULL, 
    vacancy_id UNIQUEIDENTIFIER NOT NULL, 
    version_number INTEGER NOT NULL, 
    origin VARCHAR(20) NOT NULL, 
    content NVARCHAR(max) NOT NULL, 
    change_note NVARCHAR(300) NULL, 
    source_file_id UNIQUEIDENTIFIER NULL, 
    created_at DATETIME2(3) NOT NULL, 
    created_by UNIQUEIDENTIFIER NOT NULL, 
    CONSTRAINT pk_job_profile_versions PRIMARY KEY (id), 
    CONSTRAINT uq_job_profile_versions_number UNIQUE (vacancy_id, version_number), 
    CONSTRAINT fk_job_profile_versions_vacancy FOREIGN KEY(vacancy_id) REFERENCES vacancy.vacancies (id), 
    CONSTRAINT fk_job_profile_versions_file FOREIGN KEY(source_file_id) REFERENCES files.file_assets (id), 
    CONSTRAINT fk_job_profile_versions_created_by FOREIGN KEY(created_by) REFERENCES auth.users (id), 
    CONSTRAINT ck_job_profile_versions_origin CHECK (origin IN ('MANUAL', 'IA')), 
    CONSTRAINT ck_job_profile_versions_number CHECK (version_number >= 1), 
    CONSTRAINT ck_job_profile_versions_json CHECK (ISJSON(content) = 1)
);

GO

CREATE TABLE ai.prompt_versions (
    id UNIQUEIDENTIFIER NOT NULL, 
    vacancy_id UNIQUEIDENTIFIER NOT NULL, 
    version_number INTEGER NOT NULL, 
    status VARCHAR(20) NOT NULL, 
    profile_version_id UNIQUEIDENTIFIER NOT NULL, 
    pass_threshold NUMERIC(5, 2) NOT NULL, 
    layers NVARCHAR(max) NOT NULL, 
    revision INTEGER NOT NULL, 
    duplicated_from UNIQUEIDENTIFIER NULL, 
    created_at DATETIME2(3) NOT NULL, 
    created_by UNIQUEIDENTIFIER NOT NULL, 
    updated_at DATETIME2(3) NOT NULL, 
    updated_by UNIQUEIDENTIFIER NOT NULL, 
    submitted_at DATETIME2(3) NULL, 
    submitted_by UNIQUEIDENTIFIER NULL, 
    approved_at DATETIME2(3) NULL, 
    approved_by UNIQUEIDENTIFIER NULL, 
    archived_at DATETIME2(3) NULL, 
    archived_by UNIQUEIDENTIFIER NULL, 
    CONSTRAINT pk_prompt_versions PRIMARY KEY (id), 
    CONSTRAINT uq_prompt_versions_number UNIQUE (vacancy_id, version_number), 
    CONSTRAINT fk_prompt_versions_vacancy FOREIGN KEY(vacancy_id) REFERENCES vacancy.vacancies (id), 
    CONSTRAINT fk_prompt_versions_profile FOREIGN KEY(profile_version_id) REFERENCES vacancy.job_profile_versions (id), 
    CONSTRAINT fk_prompt_versions_duplicated FOREIGN KEY(duplicated_from) REFERENCES ai.prompt_versions (id), 
    CONSTRAINT fk_prompt_versions_created_by FOREIGN KEY(created_by) REFERENCES auth.users (id), 
    CONSTRAINT fk_prompt_versions_updated_by FOREIGN KEY(updated_by) REFERENCES auth.users (id), 
    CONSTRAINT fk_prompt_versions_submitted_by FOREIGN KEY(submitted_by) REFERENCES auth.users (id), 
    CONSTRAINT fk_prompt_versions_approved_by FOREIGN KEY(approved_by) REFERENCES auth.users (id), 
    CONSTRAINT fk_prompt_versions_archived_by FOREIGN KEY(archived_by) REFERENCES auth.users (id), 
    CONSTRAINT ck_prompt_versions_status CHECK (status IN ('BORRADOR', 'EN_REVISION', 'APROBADO', 'ARCHIVADO')), 
    CONSTRAINT ck_prompt_versions_threshold CHECK (pass_threshold > 0 AND pass_threshold <= 100), 
    CONSTRAINT ck_prompt_versions_approved CHECK (status <> 'APROBADO' OR (approved_at IS NOT NULL AND approved_by IS NOT NULL)), 
    CONSTRAINT ck_prompt_versions_layers_json CHECK (ISJSON(layers) = 1)
);

GO

CREATE INDEX ix_prompt_versions_vacancy_status ON ai.prompt_versions (vacancy_id, status);

GO

CREATE TABLE ai.rubric_criteria (
    id UNIQUEIDENTIFIER NOT NULL, 
    prompt_version_id UNIQUEIDENTIFIER NOT NULL, 
    position INTEGER NOT NULL, 
    name NVARCHAR(200) NOT NULL, 
    description NVARCHAR(1000) NOT NULL, 
    kind VARCHAR(20) NOT NULL, 
    weight NUMERIC(6, 2) NOT NULL, 
    levels NVARCHAR(max) NOT NULL, 
    origin VARCHAR(20) NOT NULL, 
    CONSTRAINT pk_rubric_criteria PRIMARY KEY (id), 
    CONSTRAINT uq_rubric_criteria_position UNIQUE (prompt_version_id, position), 
    CONSTRAINT fk_rubric_criteria_prompt FOREIGN KEY(prompt_version_id) REFERENCES ai.prompt_versions (id), 
    CONSTRAINT ck_rubric_criteria_kind CHECK (kind IN ('INDISPENSABLE', 'DESEABLE')), 
    CONSTRAINT ck_rubric_criteria_origin CHECK (origin IN ('PERFIL', 'MANUAL')), 
    CONSTRAINT ck_rubric_criteria_weight CHECK (weight >= 0 AND weight <= 100), 
    CONSTRAINT ck_rubric_criteria_levels_json CHECK (ISJSON(levels) = 1)
);

GO

UPDATE alembic_version SET version_num='0006' WHERE alembic_version.version_num = '0005';

GO

COMMIT;

GO


GO
SET NOEXEC OFF;
GO
