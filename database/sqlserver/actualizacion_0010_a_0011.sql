/* ============================================================================
   Sistema Integral de Reclutamiento e IA - Actualización 0010 -> 0011
   Versión del esquema: 0010 -> 0011
   Generado: 2026-11-12 20:41 (UTC) con scripts/generate_sql.py

   Aplica solo los cambios de la versión 0011 sobre una base que ya
   está en la versión 0010. Si está en otra versión, no hace nada.

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
IF OBJECT_ID(N'dbo.alembic_version') IS NULL OR NOT EXISTS (SELECT 1 FROM dbo.alembic_version WHERE version_num = N'0010')
BEGIN
    RAISERROR(N'La base no esta en la version 0010. No se aplico ningun cambio.', 16, 1);
    SET NOEXEC ON;
END
GO

BEGIN TRANSACTION;

-- Running upgrade 0010 -> 0011

ALTER TABLE recruitment.applications DROP CONSTRAINT ck_applications_status;

GO

ALTER TABLE recruitment.applications ADD CONSTRAINT ck_applications_status CHECK (status IN ('ACTIVA', 'DESISTIO', 'DESCARTADA', 'CANCELADA', 'CONTRATADA', 'NO_LOCALIZADA', 'OTRO_CIERRE'));

GO

ALTER TABLE recruitment.application_movements DROP CONSTRAINT ck_application_movements_kind;

GO

ALTER TABLE recruitment.application_movements ADD CONSTRAINT ck_application_movements_kind CHECK (kind IN ('ALTA', 'AVANCE', 'RETROCESO', 'OMISION', 'DESISTIMIENTO', 'DESCARTE', 'CANCELACION', 'REACTIVACION', 'REPROGRAMACION', 'INCIDENCIA', 'CONTRATACION', 'NO_LOCALIZADO', 'CIERRE'));

GO

CREATE TABLE recruitment.application_outcomes (
    id UNIQUEIDENTIFIER NOT NULL, 
    application_id UNIQUEIDENTIFIER NOT NULL, 
    vacancy_id UNIQUEIDENTIFIER NOT NULL, 
    outcome VARCHAR(20) NOT NULL, 
    reason NVARCHAR(500) NULL, 
    notes NVARCHAR(max) NULL, 
    start_date DATE NULL, 
    recorded_at DATETIME2(3) NOT NULL, 
    recorded_by UNIQUEIDENTIFIER NOT NULL, 
    voided_at DATETIME2(3) NULL, 
    voided_by UNIQUEIDENTIFIER NULL, 
    void_reason NVARCHAR(500) NULL, 
    CONSTRAINT pk_application_outcomes PRIMARY KEY (id), 
    CONSTRAINT fk_application_outcomes_application FOREIGN KEY(application_id) REFERENCES recruitment.applications (id), 
    CONSTRAINT fk_application_outcomes_vacancy FOREIGN KEY(vacancy_id) REFERENCES vacancy.vacancies (id), 
    CONSTRAINT fk_application_outcomes_recorded_by FOREIGN KEY(recorded_by) REFERENCES auth.users (id), 
    CONSTRAINT fk_application_outcomes_voided_by FOREIGN KEY(voided_by) REFERENCES auth.users (id), 
    CONSTRAINT ck_application_outcomes_outcome CHECK (outcome IN ('CONTRATADO', 'NO_CONTRATADO', 'DESISTIO', 'NO_LOCALIZADO', 'VACANTE_CANCELADA', 'OTRO_CIERRE')), 
    CONSTRAINT ck_application_outcomes_start_date CHECK (start_date IS NULL OR outcome = 'CONTRATADO')
);

GO

CREATE UNIQUE INDEX uq_application_outcomes_current ON recruitment.application_outcomes (application_id) WHERE voided_at IS NULL;

GO

CREATE INDEX ix_application_outcomes_vacancy ON recruitment.application_outcomes (vacancy_id, outcome, recorded_at);

GO

INSERT INTO recruitment.application_outcomes
    (id, application_id, vacancy_id, outcome, reason, recorded_at, recorded_by)
SELECT NEWID(), a.id, a.vacancy_id,
       CASE a.status
            WHEN 'DESISTIO' THEN 'DESISTIO'
            WHEN 'DESCARTADA' THEN 'NO_CONTRATADO'
            ELSE 'VACANTE_CANCELADA'
       END,
       m.note, m.occurred_at, m.actor_user_id
FROM recruitment.applications AS a
JOIN recruitment.application_movements AS m ON m.application_id = a.id
WHERE a.status <> 'ACTIVA'
  AND m.actor_user_id IS NOT NULL
  AND m.sequence = (
        SELECT MAX(x.sequence)
        FROM recruitment.application_movements AS x
        WHERE x.application_id = a.id
          AND x.kind IN ('DESISTIMIENTO', 'DESCARTE', 'CANCELACION')
      );

GO

CREATE TABLE ops.report_exports (
    id UNIQUEIDENTIFIER NOT NULL, 
    kind VARCHAR(20) NOT NULL, 
    name NVARCHAR(200) NOT NULL, 
    filters NVARCHAR(max) NOT NULL, 
    vacancy_ids NVARCHAR(max) NOT NULL, 
    row_count INTEGER NOT NULL, 
    storage_key VARCHAR(200) NOT NULL, 
    size_bytes BIGINT NOT NULL, 
    sha256 VARCHAR(64) NOT NULL, 
    created_at DATETIME2(3) NOT NULL, 
    created_by UNIQUEIDENTIFIER NOT NULL, 
    CONSTRAINT pk_report_exports PRIMARY KEY (id), 
    CONSTRAINT uq_report_exports_storage_key UNIQUE (storage_key), 
    CONSTRAINT fk_report_exports_created_by FOREIGN KEY(created_by) REFERENCES auth.users (id), 
    CONSTRAINT ck_report_exports_kind CHECK (kind IN ('INDICADORES', 'POSTULACIONES')), 
    CONSTRAINT ck_report_exports_filters_json CHECK (ISJSON(filters) = 1), 
    CONSTRAINT ck_report_exports_vacancies_json CHECK (ISJSON(vacancy_ids) = 1)
);

GO

CREATE INDEX ix_report_exports_user ON ops.report_exports (created_by, created_at);

GO

UPDATE alembic_version SET version_num='0011' WHERE alembic_version.version_num = '0010';

GO

COMMIT;

GO


GO
SET NOEXEC OFF;
GO
