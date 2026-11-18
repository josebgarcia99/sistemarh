/* ============================================================================
   Sistema Integral de Reclutamiento e IA - Permiso para eliminar vacantes

   PLANTILLA para Sistemas. Solo hace falta en una base instalada ANTES del 18 de
   noviembre de 2026; en una instalación nueva, permisos_usuario_aplicacion.sql
   ya lo incluye.

   Para qué sirve: la aplicación tiene ahora un botón «Eliminar vacante», solo
   para administradores, que borra de forma definitiva una vacante con todo su
   contenido. Hasta ahora el usuario de la aplicación no podía borrar filas de
   reclutamiento, de documentos ni de IA. Este script le da el permiso de
   borrado únicamente en las tablas que esa operación toca.

   Qué NO cambia:
   - La auditoría (ops.audit_events) sigue siendo inalterable.
   - El historial de movimientos (recruitment.application_movements) sigue sin
     poder MODIFICARSE; solo se permite borrarlo, junto con su postulación.
   - No cambia la estructura ni la versión del esquema (sigue en 0018).

   Cómo ejecutarlo:
   1. Sustituya <USUARIO_APP> por el usuario de base de datos de la aplicación.
   2. Ejecútelo con un usuario que pueda dar permisos (por ejemplo, db_owner),
      con la base seleccionada en la conexión.
   3. No hace falta detener ni reiniciar la aplicación.

   Mientras no se ejecute, el botón responde que la base todavía no permite
   eliminar y no borra nada.

   Este script no se ha ejecutado contra un SQL Server real.
   ============================================================================ */

-- Tablas de las que la aplicación borra filas al eliminar una vacante. En todas
-- las demás sigue sin poder borrar.
GRANT DELETE ON recruitment.call_session_banks TO [<USUARIO_APP>];
GRANT DELETE ON recruitment.call_sessions TO [<USUARIO_APP>];
GRANT DELETE ON recruitment.assessments TO [<USUARIO_APP>];
GRANT DELETE ON recruitment.application_syntheses TO [<USUARIO_APP>];
GRANT DELETE ON recruitment.application_outcomes TO [<USUARIO_APP>];
GRANT DELETE ON recruitment.applications TO [<USUARIO_APP>];
GRANT DELETE ON recruitment.candidates TO [<USUARIO_APP>];
GRANT DELETE ON recruitment.campaigns TO [<USUARIO_APP>];
GRANT DELETE ON ai.cv_batch_items TO [<USUARIO_APP>];
GRANT DELETE ON ai.cv_batches TO [<USUARIO_APP>];
GRANT DELETE ON ai.rubric_criteria TO [<USUARIO_APP>];
GRANT DELETE ON ai.prompt_versions TO [<USUARIO_APP>];
GRANT DELETE ON files.file_assets TO [<USUARIO_APP>];
GO

-- Historial de movimientos: estaba negado modificar y borrar. Se retira solo la
-- negación de borrado y se concede; modificar sigue negado.
REVOKE DELETE ON recruitment.application_movements FROM [<USUARIO_APP>];
GRANT DELETE ON recruitment.application_movements TO [<USUARIO_APP>];
GO

-- Comprobación (solo lectura): permisos de borrado del usuario de la aplicación.
SELECT s.name + '.' + o.name AS tabla, p.state_desc AS estado, p.permission_name AS permiso
FROM sys.database_permissions AS p
JOIN sys.objects AS o ON o.object_id = p.major_id
JOIN sys.schemas AS s ON s.schema_id = o.schema_id
JOIN sys.database_principals AS u ON u.principal_id = p.grantee_principal_id
WHERE p.class = 1 AND p.permission_name IN ('DELETE', 'UPDATE')
  AND u.name = '<USUARIO_APP>'
ORDER BY tabla, permiso;
GO
