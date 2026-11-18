/* ============================================================================
   Sistema Integral de Reclutamiento e IA - Permisos del usuario de la aplicación

   PLANTILLA para Sistemas. Ejecutar DESPUÉS de instalacion_completa.sql.

   La aplicación debe conectarse con un usuario propio y con el mínimo
   privilegio: no debe ser db_owner ni poder cambiar el esquema.

   1. Sustituya <USUARIO_APP> por el usuario de base de datos de la aplicación
      (créelo antes con el inicio de sesión y la contraseña que defina Sistemas;
      esa contraseña no debe escribirse en este archivo ni en el repositorio).
   2. Las migraciones (crear o cambiar tablas) se ejecutan con OTRO usuario,
      con permisos de administración del esquema.

   Este script no se ha ejecutado contra un SQL Server real.
   ============================================================================ */

-- Lectura y escritura de datos en los esquemas de la aplicación.
GRANT SELECT, INSERT, UPDATE, DELETE ON SCHEMA::auth TO [<USUARIO_APP>];
GRANT SELECT, INSERT, UPDATE, DELETE ON SCHEMA::vacancy TO [<USUARIO_APP>];
-- Auditoría y registro de reportes generados: solo altas y lectura.
GRANT SELECT, INSERT ON SCHEMA::ops TO [<USUARIO_APP>];
-- Documentos: la aplicación registra y actualiza metadatos. Solo borra filas al
-- eliminar una vacante (permiso por tabla, más abajo).
GRANT SELECT, INSERT, UPDATE ON SCHEMA::files TO [<USUARIO_APP>];
-- Configuración de IA: las API keys se guardan cifradas; la clave maestra no está en la base.
GRANT SELECT, INSERT, UPDATE ON SCHEMA::ai TO [<USUARIO_APP>];
-- Reclutamiento: candidatos, postulaciones, historial, resultados finales, bancos y
-- llamadas. En el uso normal no borra filas (un resultado final se anula, no se
-- elimina); la excepción es eliminar una vacante (permiso por tabla, más abajo).
GRANT SELECT, INSERT, UPDATE ON SCHEMA::recruitment TO [<USUARIO_APP>];
GRANT SELECT ON dbo.alembic_version TO [<USUARIO_APP>];
GO

-- Auditoría inalterable: la aplicación puede insertar y leer eventos, pero no
-- modificarlos ni borrarlos.
DENY UPDATE, DELETE ON ops.audit_events TO [<USUARIO_APP>];
GO

-- Historial de movimientos de las postulaciones: no se modifica. Solo se borra
-- junto con su postulación, al eliminar una vacante.
DENY UPDATE ON recruitment.application_movements TO [<USUARIO_APP>];
GO

-- Eliminar una vacante (solo administradores, desde la aplicación): es la única
-- operación que borra datos de reclutamiento.
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
GRANT DELETE ON recruitment.application_movements TO [<USUARIO_APP>];
GO
