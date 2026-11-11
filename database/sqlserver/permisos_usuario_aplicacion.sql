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
GRANT SELECT, INSERT ON SCHEMA::ops TO [<USUARIO_APP>];
GRANT SELECT ON dbo.alembic_version TO [<USUARIO_APP>];
GO

-- Auditoría inalterable: la aplicación puede insertar y leer eventos, pero no
-- modificarlos ni borrarlos.
DENY UPDATE, DELETE ON ops.audit_events TO [<USUARIO_APP>];
GO
