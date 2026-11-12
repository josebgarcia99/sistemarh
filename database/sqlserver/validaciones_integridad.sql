/*
  Validaciones de integridad del Sistema Integral de Reclutamiento e IA.

  SOLO LECTURA: este script no modifica nada. Devuelve una tabla con una fila
  por validación y el número de registros con problema. En una base sana todas
  las filas muestran 0.

  Cuándo ejecutarlo:
    - Después de instalar o actualizar la base.
    - Después de restaurar un respaldo, antes de dar servicio.
    - Como revisión periódica (por ejemplo, mensual).

  Qué NO comprueba: que cada documento exista en el disco con su huella. Eso lo
  hace la aplicación con:  python -m app.cli storage-check --verify-hashes all

  Escrito a mano. No se ha ejecutado todavía contra un SQL Server real.
*/

SET NOCOUNT ON;

SELECT v.validacion, v.problemas
FROM (
    -- Identidad -------------------------------------------------------------
    SELECT '01. Debe existir al menos un administrador activo' AS validacion,
           CASE WHEN EXISTS (
                SELECT 1
                FROM auth.users AS u
                JOIN auth.user_roles AS r ON r.user_id = u.id
                WHERE u.is_active = 1 AND r.role_code = 'ADMINISTRADOR'
           ) THEN 0 ELSE 1 END AS problemas
    UNION ALL
    SELECT '02. Usuarios activos sin ningun rol', COUNT(*)
    FROM auth.users AS u
    WHERE u.is_active = 1
      AND NOT EXISTS (SELECT 1 FROM auth.user_roles AS r WHERE r.user_id = u.id)
    UNION ALL
    SELECT '03. Sesiones abiertas de usuarios desactivados', COUNT(*)
    FROM auth.sessions AS s
    JOIN auth.users AS u ON u.id = s.user_id
    WHERE u.is_active = 0 AND s.revoked_at IS NULL

    -- Vacantes ----------------------------------------------------------------
    UNION ALL
    SELECT '04. Vacantes en curso cuyo responsable esta desactivado', COUNT(*)
    FROM vacancy.vacancies AS v
    JOIN auth.users AS u ON u.id = v.owner_user_id
    WHERE u.is_active = 0 AND v.status IN ('BORRADOR', 'ABIERTA', 'PAUSADA')
    UNION ALL
    SELECT '05. Accesos compartidos vigentes de usuarios desactivados', COUNT(*)
    FROM vacancy.vacancy_members AS m
    JOIN auth.users AS u ON u.id = m.user_id
    WHERE u.is_active = 0 AND m.revoked_at IS NULL
    UNION ALL
    SELECT '06. Vacantes con mas contrataciones vigentes que plazas', COUNT(*)
    FROM vacancy.vacancies AS v
    WHERE v.positions < (
        SELECT COUNT(*)
        FROM recruitment.application_outcomes AS o
        WHERE o.vacancy_id = v.id AND o.outcome = 'CONTRATADO' AND o.voided_at IS NULL
    )

    -- Postulaciones y resultados finales -------------------------------------
    UNION ALL
    SELECT '07. Postulaciones cuya vacante no es la de su convocatoria', COUNT(*)
    FROM recruitment.applications AS a
    JOIN recruitment.campaigns AS c ON c.id = a.campaign_id
    WHERE c.vacancy_id <> a.vacancy_id
    UNION ALL
    SELECT '08. Postulaciones en una etapa que no es del proceso de su convocatoria', COUNT(*)
    FROM recruitment.applications AS a
    JOIN recruitment.campaigns AS c ON c.id = a.campaign_id
    JOIN recruitment.pipeline_stages AS s ON s.id = a.stage_id
    WHERE s.pipeline_version_id <> c.pipeline_version_id
    UNION ALL
    SELECT '09. Postulaciones cerradas sin resultado final vigente', COUNT(*)
    FROM recruitment.applications AS a
    WHERE a.status <> 'ACTIVA'
      AND NOT EXISTS (
          SELECT 1 FROM recruitment.application_outcomes AS o
          WHERE o.application_id = a.id AND o.voided_at IS NULL
      )
    UNION ALL
    SELECT '10. Postulaciones activas con un resultado final vigente', COUNT(*)
    FROM recruitment.applications AS a
    WHERE a.status = 'ACTIVA'
      AND EXISTS (
          SELECT 1 FROM recruitment.application_outcomes AS o
          WHERE o.application_id = a.id AND o.voided_at IS NULL
      )
    UNION ALL
    SELECT '11. Resultado final vigente que no corresponde al estado de la postulacion', COUNT(*)
    FROM recruitment.application_outcomes AS o
    JOIN recruitment.applications AS a ON a.id = o.application_id
    WHERE o.voided_at IS NULL
      AND a.status <> CASE o.outcome
                          WHEN 'CONTRATADO' THEN 'CONTRATADA'
                          WHEN 'NO_CONTRATADO' THEN 'DESCARTADA'
                          WHEN 'DESISTIO' THEN 'DESISTIO'
                          WHEN 'NO_LOCALIZADO' THEN 'NO_LOCALIZADA'
                          WHEN 'VACANTE_CANCELADA' THEN 'CANCELADA'
                          ELSE 'OTRO_CIERRE'
                      END
    UNION ALL
    SELECT '12. Postulaciones sin ningun movimiento en su historial', COUNT(*)
    FROM recruitment.applications AS a
    WHERE NOT EXISTS (
        SELECT 1 FROM recruitment.application_movements AS m WHERE m.application_id = a.id
    )

    -- Documentos ---------------------------------------------------------------
    UNION ALL
    SELECT '13. Documentos confirmados sin huella o sin tamano', COUNT(*)
    FROM files.file_assets AS f
    WHERE f.status = 'CONFIRMADO'
      AND (f.sha256 IS NULL OR f.stored_sha256 IS NULL OR f.stored_size_bytes IS NULL)
    UNION ALL
    SELECT '14. Documentos sensibles confirmados sin cifrar', COUNT(*)
    FROM files.file_assets AS f
    WHERE f.status = 'CONFIRMADO'
      AND f.sensitive_class IS NOT NULL
      AND f.encryption_key_id IS NULL
    UNION ALL
    SELECT '15. Documentos eliminados sin motivo o sin responsable', COUNT(*)
    FROM files.file_assets AS f
    WHERE f.status = 'ELIMINADO'
      AND (f.deleted_by IS NULL OR f.deleted_at IS NULL OR f.deletion_reason IS NULL)
    UNION ALL
    SELECT '16. CV evaluados en un lote de otra vacante', COUNT(*)
    FROM ai.cv_batch_items AS i
    JOIN ai.cv_batches AS b ON b.id = i.batch_id
    JOIN files.file_assets AS f ON f.id = i.file_id
    WHERE f.vacancy_id <> b.vacancy_id
    UNION ALL
    SELECT '17. Postulaciones con el CV de otra vacante', COUNT(*)
    FROM recruitment.applications AS a
    JOIN files.file_assets AS f ON f.id = a.cv_file_id
    WHERE f.vacancy_id <> a.vacancy_id

    -- Version del esquema ------------------------------------------------------
    UNION ALL
    SELECT '18. La version del esquema debe ser 0016',
           CASE WHEN EXISTS (
                SELECT 1 FROM dbo.alembic_version AS x WHERE x.version_num = '0016'
           ) THEN 0 ELSE 1 END
) AS v
ORDER BY v.validacion;
