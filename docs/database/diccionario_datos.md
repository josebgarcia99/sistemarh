# Diccionario de datos

Describe las tablas que existen hoy (versión de esquema `0007`). Se amplía con cada migración. Los scripts están en `database/sqlserver/`.

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

### `vacancy.job_profile_versions`

Versiones del perfil de puesto de cada vacante. Cada corrección crea una fila nueva; las anteriores no cambian. La vigente es la de mayor `version_number`.

| Columna | Tipo | Oblig. | Descripción |
| --- | --- | --- | --- |
| `id` | `UNIQUEIDENTIFIER` | Sí | Clave primaria. |
| `vacancy_id` | `UNIQUEIDENTIFIER` | Sí | Vacante. |
| `version_number` | `INT` | Sí | 1, 2, 3… Único por vacante. |
| `origin` | `VARCHAR(20)` | Sí | `MANUAL` (capturado por una persona) o `IA` (extraído de un archivo; aún no se usa). |
| `content` | `NVARCHAR(MAX)` | Sí | Perfil estructurado en JSON: objetivo, experiencia, formación, funciones, responsabilidades, conocimientos, habilidades, certificaciones, requisitos indispensables, requisitos deseables y requisitos que no están claros. |
| `change_note` | `NVARCHAR(300)` | No | Qué cambió respecto a la versión anterior. |
| `source_file_id` | `UNIQUEIDENTIFIER` | No | Documento del que se extrajo (`files.file_assets`). Aún no se usa. |
| `created_at`, `created_by` | `DATETIME2(3)`, `UNIQUEIDENTIFIER` | Sí | Cuándo se guardó y quién lo hizo. |

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
| `size_bytes` | `BIGINT` | No | Tamaño del contenido original, en bytes. Obligatorio si el estado es `CONFIRMADO` o `ELIMINADO`. |
| `sha256` | `VARCHAR(64)` | No | Huella SHA-256 del contenido original (sirve para detectar duplicados). Obligatoria si el estado es `CONFIRMADO` o `ELIMINADO`. |
| `stored_size_bytes` | `BIGINT` | No | Tamaño de lo que hay en el disco. Igual a `size_bytes` salvo en archivos cifrados. Obligatorio si el estado es `CONFIRMADO` o `ELIMINADO`. |
| `stored_sha256` | `VARCHAR(64)` | No | SHA-256 de lo que hay en el disco. Es el que usan la conciliación y los respaldos, que así no necesitan la clave maestra. |
| `encryption_key_id` | `VARCHAR(32)` | No | Identificador de la clave maestra con que se cifró el archivo. Vacío si no está cifrado. No es la clave. |
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

## Esquema `ai`: configuración de inteligencia artificial

### `ai.providers`

Un proveedor por fila (`ANTHROPIC`, `OPENAI`). La fila se crea la primera vez que se configura.

| Columna | Tipo | Oblig. | Descripción |
| --- | --- | --- | --- |
| `code` | `VARCHAR(20)` | Sí | Clave primaria. |
| `enabled` | `BIT` | Sí | Si sus modelos pueden usarse. |
| `monthly_limit_usd` | `NUMERIC(12,2)` | No | Límite de gasto mensual en dólares. Vacío: sin límite. |
| `last_test_at`, `last_test_ok`, `last_test_error` | `DATETIME2(3)`, `BIT`, `NVARCHAR(300)` | No | Resultado de la última prueba de conexión. El error es un mensaje redactado por la aplicación, no la respuesta del proveedor. |
| `updated_at`, `updated_by` | `DATETIME2(3)`, `UNIQUEIDENTIFIER` | No | Último cambio y quién lo hizo. |

### `ai.provider_credentials`

API keys de los proveedores, **cifradas con la clave maestra** (que no está en la base). Sustituir una clave crea una fila nueva y revoca la anterior.

| Columna | Tipo | Oblig. | Descripción |
| --- | --- | --- | --- |
| `id` | `UNIQUEIDENTIFIER` | Sí | Clave primaria. |
| `provider_code` | `VARCHAR(20)` | Sí | Proveedor (`ai.providers`). |
| `ciphertext` | `NVARCHAR(MAX)` | No | Texto cifrado (AES-256-GCM). Se borra al revocar o sustituir: una fila revocada no conserva el secreto. |
| `last4` | `VARCHAR(4)` | Sí | Últimos cuatro caracteres, para el identificador enmascarado. |
| `master_key_id` | `VARCHAR(32)` | Sí | Identificador de la clave maestra con que se cifró. No es la clave. |
| `created_at`, `created_by` | `DATETIME2(3)`, `UNIQUEIDENTIFIER` | Sí | Cuándo se registró y quién lo hizo. |
| `revoked_at`, `revoked_by` | `DATETIME2(3)`, `UNIQUEIDENTIFIER` | No | Cuándo se revocó o sustituyó y quién lo hizo. |

Índice: `uq_provider_credentials_active`, único sobre `provider_code` para filas sin revocar (una clave vigente por proveedor).

### `ai.models`

Modelos que cada proveedor informa. Se llena al probar la conexión; no hay identificadores de modelos escritos en el código.

| Columna | Tipo | Oblig. | Descripción |
| --- | --- | --- | --- |
| `id` | `UNIQUEIDENTIFIER` | Sí | Clave primaria. |
| `provider_code` | `VARCHAR(20)` | Sí | Proveedor. |
| `model_id` | `NVARCHAR(200)` | Sí | Identificador del modelo en el proveedor. Único por proveedor. |
| `display_name` | `NVARCHAR(200)` | Sí | Nombre para mostrar. |
| `capabilities` | `NVARCHAR(MAX)` | No | Capacidades que declara el proveedor, en JSON. Vacío si no las informa. |
| `is_available` | `BIT` | Sí | 0 si el proveedor dejó de listarlo en la última comprobación. |
| `first_seen_at`, `last_seen_at` | `DATETIME2(3)` | Sí | Primera y última vez que el proveedor lo listó. |
| `input_price`, `output_price` | `NUMERIC(12,4)` | No | Precio en dólares por millón de tokens de entrada y de salida. Lo captura el administrador; sin él no se estima el costo. |

### `ai.operation_assignments`

Modelo asignado a cada operación (extracción de CV, evaluación, generación de prompts, etc.).

| Columna | Tipo | Oblig. | Descripción |
| --- | --- | --- | --- |
| `operation` | `VARCHAR(40)` | Sí | Clave primaria. Una de las ocho operaciones. |
| `model_ref` | `UNIQUEIDENTIFIER` | No | Modelo asignado (`ai.models`). Vacío: sin asignar. |
| `updated_at`, `updated_by` | `DATETIME2(3)`, `UNIQUEIDENTIFIER` | No | Último cambio y quién lo hizo. |

### `ai.executions`

Una fila por cada llamada a un proveedor de IA. Guarda el consumo, **nunca** el contenido enviado ni la respuesta. Solo recibe inserciones.

| Columna | Tipo | Oblig. | Descripción |
| --- | --- | --- | --- |
| `id` | `UNIQUEIDENTIFIER` | Sí | Clave primaria. |
| `occurred_at` | `DATETIME2(3)` | Sí | Fecha de la llamada. |
| `operation` | `VARCHAR(40)` | Sí | Operación (por ejemplo `EVALUACION_DOCUMENTAL`) o `PRUEBA`. |
| `provider_code` | `VARCHAR(20)` | Sí | Proveedor. |
| `model_id` | `NVARCHAR(200)` | Sí | Modelo usado. |
| `status` | `VARCHAR(20)` | Sí | `CORRECTA` o `FALLIDA`. |
| `attempts` | `INT` | Sí | Intentos realizados (1 si no hubo reintentos). |
| `duration_ms` | `INT` | Sí | Duración total, en milisegundos. |
| `input_tokens`, `output_tokens` | `INT` | No | Tokens que informó el proveedor. Vacíos si la llamada falló. |
| `estimated_cost_usd` | `NUMERIC(12,6)` | No | Costo estimado con el precio capturado. Vacío si el modelo no tiene precio. |
| `confirmed_cost_usd` | `NUMERIC(12,6)` | No | Costo real, si algún día se concilia con la factura del proveedor. Aún no se usa. |
| `error_kind` | `VARCHAR(20)` | No | Tipo de fallo: `red`, `clave`, `limite` o `proveedor`. |
| `actor_user_id`, `vacancy_id` | `UNIQUEIDENTIFIER` | No | Quién la originó y para qué vacante. Sin clave foránea a propósito: el registro se conserva. |

Índices: `ix_executions_provider_date (provider_code, occurred_at)` para el límite mensual e `ix_executions_date (occurred_at)`.

### `ai.prompt_versions`

Versiones del prompt de evaluación de cada vacante. Solo una versión `APROBADO` puede usarse para evaluar CV, y una vez aprobada no se modifica.

| Columna | Tipo | Oblig. | Descripción |
| --- | --- | --- | --- |
| `id` | `UNIQUEIDENTIFIER` | Sí | Clave primaria. |
| `vacancy_id` | `UNIQUEIDENTIFIER` | Sí | Vacante. |
| `version_number` | `INT` | Sí | Único por vacante. |
| `status` | `VARCHAR(20)` | Sí | `BORRADOR`, `EN_REVISION`, `APROBADO` o `ARCHIVADO`. |
| `profile_version_id` | `UNIQUEIDENTIFIER` | Sí | Versión del perfil de la que salió (`vacancy.job_profile_versions`). |
| `pass_threshold` | `NUMERIC(5,2)` | Sí | Puntuación mínima (mayor que 0, hasta 100) para clasificar un CV como aceptado. |
| `layers` | `NVARCHAR(MAX)` | Sí | Las diez capas del prompt, en JSON. |
| `revision` | `INT` | Sí | Aumenta con cada cambio; impide que dos personas se pisen. |
| `duplicated_from` | `UNIQUEIDENTIFIER` | No | Versión de la que se copió. |
| `created_at`, `created_by`, `updated_at`, `updated_by` | `DATETIME2(3)`, `UNIQUEIDENTIFIER` | Sí | Alta y último cambio. |
| `submitted_at`, `submitted_by` | `DATETIME2(3)`, `UNIQUEIDENTIFIER` | No | Envío a revisión. |
| `approved_at`, `approved_by` | `DATETIME2(3)`, `UNIQUEIDENTIFIER` | No | Aprobación. Obligatorios si el estado es `APROBADO`. |
| `archived_at`, `archived_by` | `DATETIME2(3)`, `UNIQUEIDENTIFIER` | No | Archivo. |

Índice: `ix_prompt_versions_vacancy_status (vacancy_id, status)`.

### `ai.rubric_criteria`

Criterios de la rúbrica de cada versión del prompt.

| Columna | Tipo | Oblig. | Descripción |
| --- | --- | --- | --- |
| `id` | `UNIQUEIDENTIFIER` | Sí | Clave primaria. |
| `prompt_version_id` | `UNIQUEIDENTIFIER` | Sí | Versión del prompt. |
| `position` | `INT` | Sí | Orden; el criterio se identifica como C1, C2… Único por versión. |
| `name` | `NVARCHAR(200)` | Sí | Requisito que se evalúa. |
| `description` | `NVARCHAR(1000)` | Sí | Aclaración opcional (puede ir vacía). |
| `kind` | `VARCHAR(20)` | Sí | `INDISPENSABLE` o `DESEABLE`. |
| `weight` | `NUMERIC(6,2)` | Sí | Peso en la puntuación, de 0 a 100. |
| `levels` | `NVARCHAR(MAX)` | Sí | Descripción de los niveles 0 a 4, en JSON. |
| `origin` | `VARCHAR(20)` | Sí | `PERFIL` (sale de un requisito del perfil) o `MANUAL` (añadido por una persona). |

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
