# Diccionario de datos

Describe las tablas que existen hoy (versión de esquema `0003`). Se amplía con cada migración. Los scripts están en `database/sqlserver/`.

Convenciones: las claves `UNIQUEIDENTIFIER` las genera la aplicación en orden creciente; las fechas son `DATETIME2(3)` en UTC; nada se borra en cascada. "Sí" en la columna Oblig. significa `NOT NULL`.

## Esquema `auth`: identidad

### `auth.roles`

Catálogo de roles. Se carga al instalar con `ADMINISTRADOR` y `RECLUTADOR`.

| Columna | Tipo | Oblig. | Descripción |
| --- | --- | --- | --- |
| `code` | `NVARCHAR(30)` | Sí | Clave primaria. Código del rol. |
| `name` | `NVARCHAR(100)` | Sí | Nombre para mostrar. |

### `auth.users`

Personas que pueden iniciar sesión. Nunca se borran: se dan de baja.

| Columna | Tipo | Oblig. | Descripción |
| --- | --- | --- | --- |
| `id` | `UNIQUEIDENTIFIER` | Sí | Clave primaria. |
| `email` | `NVARCHAR(254)` | Sí | Correo en minúsculas; es el nombre de usuario. Único (`uq_users_email`). |
| `full_name` | `NVARCHAR(200)` | Sí | Nombre completo. |
| `password_hash` | `NVARCHAR(255)` | Sí | Huella Argon2id de la contraseña. La contraseña nunca se guarda. |
| `is_active` | `BIT` | Sí | 0 cuando el usuario está dado de baja. |
| `created_at` | `DATETIME2(3)` | Sí | Fecha de alta. |
| `created_by` | `UNIQUEIDENTIFIER` | No | Quién lo dio de alta (`auth.users`). Vacío en el usuario maestro. |
| `last_activity_at` | `DATETIME2(3)` | No | Última actividad con sesión. |
| `deactivated_at` | `DATETIME2(3)` | No | Fecha de la baja. |
| `password_changed_at` | `DATETIME2(3)` | No | Último cambio o restablecimiento de contraseña. |
| `failed_login_count` | `INT` | Sí | Intentos fallidos seguidos. No negativo. |
| `locked_until` | `DATETIME2(3)` | No | Fin del bloqueo por intentos fallidos. |
| `row_version` | `ROWVERSION` | Sí | Marca que SQL Server cambia sola en cada modificación. La aplicación no la lee todavía. |

### `auth.user_roles`

Rol de cada usuario. Hoy cada usuario tiene exactamente uno.

| Columna | Tipo | Oblig. | Descripción |
| --- | --- | --- | --- |
| `user_id` | `UNIQUEIDENTIFIER` | Sí | Parte de la clave primaria. Usuario (`auth.users`). |
| `role_code` | `NVARCHAR(30)` | Sí | Parte de la clave primaria. Rol (`auth.roles`). |

### `auth.sessions`

Sesiones iniciadas. El navegador guarda un token; aquí solo está su huella.

| Columna | Tipo | Oblig. | Descripción |
| --- | --- | --- | --- |
| `id` | `UNIQUEIDENTIFIER` | Sí | Clave primaria. |
| `user_id` | `UNIQUEIDENTIFIER` | Sí | Usuario (`auth.users`). Índice `ix_sessions_user_id`. |
| `token_hash` | `VARCHAR(64)` | Sí | SHA-256 del token de sesión. Único. |
| `csrf_token` | `VARCHAR(64)` | Sí | Token que la pantalla envía en cada operación que modifica datos. |
| `created_at` | `DATETIME2(3)` | Sí | Inicio de la sesión. |
| `last_seen_at` | `DATETIME2(3)` | Sí | Última petición; determina la caducidad por inactividad. |
| `expires_at` | `DATETIME2(3)` | Sí | Caducidad absoluta. |
| `ip` | `VARCHAR(45)` | No | Dirección IP de origen. |
| `user_agent` | `NVARCHAR(300)` | No | Navegador declarado. |
| `revoked_at` | `DATETIME2(3)` | No | Cierre de sesión, baja o restablecimiento de contraseña. |

## Esquema `vacancy`: vacantes y acceso

### `vacancy.vacancies`

| Columna | Tipo | Oblig. | Descripción |
| --- | --- | --- | --- |
| `id` | `UNIQUEIDENTIFIER` | Sí | Clave primaria. |
| `name` | `NVARCHAR(200)` | Sí | Nombre de la vacante. |
| `department` | `NVARCHAR(120)` | Sí | Departamento. |
| `location` | `NVARCHAR(120)` | Sí | Ubicación. |
| `work_mode` | `VARCHAR(20)` | Sí | `PRESENCIAL`, `HIBRIDA` o `REMOTA`. |
| `contract_type` | `NVARCHAR(80)` | Sí | Tipo de contratación. |
| `description` | `NVARCHAR(MAX)` | Sí | Descripción. |
| `positions` | `INT` | Sí | Número de posiciones, de 1 a 9999. |
| `notes` | `NVARCHAR(MAX)` | No | Observaciones. |
| `status` | `VARCHAR(20)` | Sí | `BORRADOR`, `ABIERTA`, `PAUSADA`, `CERRADA`, `CANCELADA` o `ARCHIVADA`. |
| `owner_user_id` | `UNIQUEIDENTIFIER` | Sí | Responsable principal (`auth.users`). Toda vacante tiene uno. |
| `opened_at` | `DATETIME2(3)` | No | Primera vez que se abrió. |
| `closed_at` | `DATETIME2(3)` | No | Fecha de cierre o cancelación. |
| `created_at`, `created_by` | `DATETIME2(3)`, `UNIQUEIDENTIFIER` | Sí | Alta y quién la hizo. No se actualizan. |
| `updated_at`, `updated_by` | `DATETIME2(3)`, `UNIQUEIDENTIFIER` | Sí | Último cambio y quién lo hizo. |
| `version` | `INT` | Sí | Empieza en 1 y aumenta con cada cambio. Impide que dos ediciones simultáneas se pisen. |

Índices: `ix_vacancies_owner (owner_user_id, status)` e `ix_vacancies_status (status)`.

### `vacancy.vacancy_members`

Personas con las que se comparte una vacante. Revocar no borra la fila: llena `revoked_at`.

| Columna | Tipo | Oblig. | Descripción |
| --- | --- | --- | --- |
| `id` | `UNIQUEIDENTIFIER` | Sí | Clave primaria. |
| `vacancy_id` | `UNIQUEIDENTIFIER` | Sí | Vacante (`vacancy.vacancies`). |
| `user_id` | `UNIQUEIDENTIFIER` | Sí | Persona con acceso (`auth.users`). |
| `access_type` | `VARCHAR(20)` | Sí | `LECTURA` o `COLABORACION`. |
| `granted_by`, `granted_at` | `UNIQUEIDENTIFIER`, `DATETIME2(3)` | Sí | Quién compartió y cuándo. |
| `revoked_at`, `revoked_by` | `DATETIME2(3)`, `UNIQUEIDENTIFIER` | No | Cuándo se revocó y quién lo hizo. |

Índices: `uq_vacancy_members_active`, único sobre `(vacancy_id, user_id)` solo para filas sin revocar (un acceso vigente por persona y vacante); `ix_vacancy_members_user (user_id)`.

### `vacancy.vacancy_sensitive_grants`

Permiso adicional para documentos sensibles. Tener acceso a la vacante no basta.

| Columna | Tipo | Oblig. | Descripción |
| --- | --- | --- | --- |
| `id` | `UNIQUEIDENTIFIER` | Sí | Clave primaria. |
| `vacancy_id` | `UNIQUEIDENTIFIER` | Sí | Vacante. |
| `user_id` | `UNIQUEIDENTIFIER` | Sí | Persona que recibe el permiso. |
| `document_class` | `VARCHAR(40)` | Sí | `PSICOMETRIA` o `ESTUDIO_SOCIOECONOMICO`. |
| `granted_by`, `granted_at` | `UNIQUEIDENTIFIER`, `DATETIME2(3)` | Sí | Quién lo otorgó y cuándo. |
| `revoked_at`, `revoked_by` | `DATETIME2(3)`, `UNIQUEIDENTIFIER` | No | Cuándo se revocó y quién lo hizo. |

Índices: `uq_vacancy_sensitive_grants_active`, único sobre `(vacancy_id, user_id, document_class)` para filas sin revocar; `ix_vacancy_sensitive_grants_user (user_id)`.

### `vacancy.vacancy_transfers`

Una fila por cada baja con transferencia (`MASIVA`). Usa como `id` el identificador de operación que envía la pantalla: repetirla no la duplica. Las transferencias individuales no crean fila aquí hoy: quedan en `vacancy_ownership_history` y en la auditoría; el valor `INDIVIDUAL` está previsto en la restricción pero aún no se usa.

| Columna | Tipo | Oblig. | Descripción |
| --- | --- | --- | --- |
| `id` | `UNIQUEIDENTIFIER` | Sí | Clave primaria. |
| `kind` | `VARCHAR(20)` | Sí | `INDIVIDUAL` o `MASIVA`. |
| `from_user_id` | `UNIQUEIDENTIFIER` | Sí | Responsable anterior. Distinto de `to_user_id`. |
| `to_user_id` | `UNIQUEIDENTIFIER` | Sí | Nuevo responsable. |
| `reason` | `NVARCHAR(500)` | Sí | Motivo. |
| `requested_by` | `UNIQUEIDENTIFIER` | Sí | Administrador que la ejecutó. |
| `completed_at` | `DATETIME2(3)` | Sí | Fecha de la operación. |
| `vacancies_transferred` | `INT` | Sí | Vacantes que cambiaron de responsable. |
| `memberships_revoked` | `INT` | Sí | Accesos a vacantes de otros que se revocaron al usuario saliente. |
| `grants_revoked` | `INT` | Sí | Permisos de documentos sensibles revocados. |
| `user_deactivated` | `BIT` | Sí | 1 si la operación dio de baja al usuario saliente. |

### `vacancy.vacancy_ownership_history`

Historial de responsables de cada vacante. Solo recibe inserciones.

| Columna | Tipo | Oblig. | Descripción |
| --- | --- | --- | --- |
| `id` | `UNIQUEIDENTIFIER` | Sí | Clave primaria. |
| `vacancy_id` | `UNIQUEIDENTIFIER` | Sí | Vacante. |
| `previous_owner_id` | `UNIQUEIDENTIFIER` | No | Responsable anterior. Vacío en la fila de creación. |
| `new_owner_id` | `UNIQUEIDENTIFIER` | Sí | Nuevo responsable. |
| `changed_at` | `DATETIME2(3)` | Sí | Fecha del cambio. |
| `reason` | `NVARCHAR(500)` | Sí | Motivo. |
| `authorized_by` | `UNIQUEIDENTIFIER` | Sí | Quién lo autorizó. |
| `transfer_id` | `UNIQUEIDENTIFIER` | No | Baja con transferencia (`vacancy.vacancy_transfers`) a la que pertenece. Vacío en la fila de creación y en las transferencias individuales. |

Índice: `ix_vacancy_ownership_history_vacancy (vacancy_id, changed_at)`.

## Esquema `files`: documentos

### `files.file_assets`

Metadatos de cada documento guardado en el disco privado del servidor. El archivo está en el disco; aquí está qué es, de qué vacante, dónde está y en qué estado. Las filas nunca se borran: una eliminación autorizada cambia el estado y borra el archivo físico.

| Columna | Tipo | Oblig. | Descripción |
| --- | --- | --- | --- |
| `id` | `UNIQUEIDENTIFIER` | Sí | Clave primaria. También es el nombre del archivo en el disco. |
| `vacancy_id` | `UNIQUEIDENTIFIER` | Sí | Vacante a la que pertenece (`vacancy.vacancies`). Determina quién puede verlo. |
| `document_type` | `VARCHAR(40)` | Sí | `CV`, `PERFIL_PUESTO`, `PSICOMETRIA`, `PRUEBA_TECNICA`, `ESTUDIO_SOCIOECONOMICO` o `ADJUNTO`. |
| `sensitive_class` | `VARCHAR(40)` | No | `PSICOMETRIA` o `ESTUDIO_SOCIOECONOMICO` si exige el permiso adicional; vacío en documentos ordinarios. |
| `original_name` | `NVARCHAR(200)` | Sí | Nombre original, saneado. Solo se usa para mostrarlo y al descargar; nunca para ubicar el archivo. |
| `extension` | `VARCHAR(10)` | Sí | Extensión en minúsculas. |
| `content_type` | `VARCHAR(100)` | No | Tipo real detectado por contenido. |
| `size_bytes` | `BIGINT` | No | Tamaño en bytes. Obligatorio si el estado es `CONFIRMADO` o `ELIMINADO`. |
| `sha256` | `VARCHAR(64)` | No | Huella SHA-256 del contenido. Obligatoria si el estado es `CONFIRMADO` o `ELIMINADO`. |
| `storage_backend` | `VARCHAR(20)` | Sí | Dónde está guardado. Hoy siempre `local` (disco del servidor). |
| `storage_key` | `VARCHAR(200)` | Sí | Referencia lógica relativa, por ejemplo `private/cv/3f/a9/<uuid>`. Única. Nunca una ruta absoluta. |
| `status` | `VARCHAR(20)` | Sí | `RECIBIENDO`, `CONFIRMADO`, `RECHAZADO`, `FALLIDO` o `ELIMINADO`. |
| `malware_scan` | `VARCHAR(20)` | No | `LIMPIO` si el antivirus lo analizó; `NO_ANALIZADO` si el antivirus está desactivado. |
| `failure_code` | `VARCHAR(40)` | No | Motivo del rechazo o del fallo, por ejemplo `contiene_macros` o `carga_interrumpida`. |
| `uploaded_by` | `UNIQUEIDENTIFIER` | Sí | Quién lo cargó (`auth.users`). |
| `created_at` | `DATETIME2(3)` | Sí | Inicio de la carga. |
| `confirmed_at` | `DATETIME2(3)` | No | Momento en que quedó guardado y verificado. |
| `retention_until` | `DATETIME2(3)` | No | Fecha de retención. Vacía hasta que exista la política aprobada. |
| `deleted_at`, `deleted_by`, `deletion_reason` | `DATETIME2(3)`, `UNIQUEIDENTIFIER`, `NVARCHAR(500)` | No | Cuándo, quién y por qué se eliminó. Obligatorios si el estado es `ELIMINADO`. |

Índices: `ix_file_assets_vacancy (vacancy_id, status)`, `ix_file_assets_hash (vacancy_id, sha256)` para detectar duplicados e `ix_file_assets_status (status, created_at)` para la conciliación.

## Esquema `ops`: operación

### `ops.audit_events`

Registro de auditoría. Solo recibe inserciones; la plantilla de permisos niega `UPDATE` y `DELETE` al usuario de la aplicación.

| Columna | Tipo | Oblig. | Descripción |
| --- | --- | --- | --- |
| `id` | `UNIQUEIDENTIFIER` | Sí | Clave primaria. |
| `occurred_at` | `DATETIME2(3)` | Sí | Fecha del evento. |
| `actor_user_id` | `UNIQUEIDENTIFIER` | No | Quién lo hizo. Sin clave foránea a propósito: el evento se conserva pase lo que pase con el usuario. Vacío en intentos de inicio de sesión con un correo desconocido. |
| `action` | `VARCHAR(80)` | Sí | Código del evento, por ejemplo `vacante.compartida` o `acceso.denegado`. |
| `result` | `VARCHAR(20)` | Sí | `PERMITIDO`, `DENEGADO` o `FALLIDO`. |
| `resource_type` | `VARCHAR(60)` | No | Tipo de recurso afectado. |
| `resource_id` | `VARCHAR(64)` | No | Identificador del recurso. |
| `ip` | `VARCHAR(45)` | No | Dirección IP de origen. |
| `correlation_id` | `VARCHAR(64)` | No | Identificador de la petición, para cruzar con los logs. |
| `details` | `NVARCHAR(MAX)` | Sí | Detalle en JSON (`ISJSON`). Nunca contiene contraseñas, tokens ni claves. |

Índices: `ix_audit_events_occurred_at`, `ix_audit_events_actor (actor_user_id, occurred_at)` e `ix_audit_events_action (action, occurred_at)`.

## Esquema `dbo`

### `dbo.alembic_version`

Una sola fila con la versión del esquema instalada (`version_num`). La usan la aplicación y los scripts de actualización; no se edita a mano.
