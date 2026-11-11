# Diccionario de datos

Describe las tablas que existen hoy (versión de esquema `0011`). Se amplía con cada migración. Los scripts están en `database/sqlserver/`.

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
| `document_type` | `VARCHAR(40)` | Sí | `CV`, `PERFIL_PUESTO`, `PSICOMETRIA`, `PRUEBA_TECNICA`, `ESTUDIO_SOCIOECONOMICO` o `ADJUNTO`. Los generados por el sistema, que nadie carga, son `REPORTE_EVALUACION` (Excel de un lote) y `PAQUETE_CV` (ZIP de originales); se guardan en el área `generated/`. |
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

### `ai.cv_batches`

Un lote de evaluación de CV: qué vacante, con qué versión aprobada del prompt, en qué estado está y qué archivos generó.

| Columna | Tipo | Oblig. | Descripción |
| --- | --- | --- | --- |
| `id` | `UNIQUEIDENTIFIER` | Sí | Clave primaria. |
| `vacancy_id` | `UNIQUEIDENTIFIER` | Sí | Vacante (`vacancy.vacancies`). |
| `prompt_version_id` | `UNIQUEIDENTIFIER` | Sí | Versión del prompt con que se evalúa (`ai.prompt_versions`). No cambia aunque después se apruebe otra. |
| `status` | `VARCHAR(30)` | Sí | `PENDIENTE`, `EN_COLA`, `PROCESANDO`, `COMPLETADO`, `COMPLETADO_CON_INCIDENCIAS`, `FALLIDO` o `CANCELADO`. |
| `total` | `INT` | Sí | Número de CV del lote. |
| `error` | `NVARCHAR(500)` | No | Motivo por el que el lote se detuvo, en palabras para la persona. |
| `created_at`, `created_by` | `DATETIME2(3)`, `UNIQUEIDENTIFIER` | Sí | Cuándo y quién lo inició. |
| `started_at`, `finished_at` | `DATETIME2(3)` | No | Inicio y fin del procesamiento. |
| `report_file_id` | `UNIQUEIDENTIFIER` | No | `Reporte_Evaluacion.xlsx` más reciente (`files.file_assets`). |
| `accepted_zip_file_id`, `rejected_zip_file_id`, `unevaluable_zip_file_id` | `UNIQUEIDENTIFIER` | No | ZIP más recientes de cada clasificación (`files.file_assets`). |
| `runner_token` | `VARCHAR(40)` | No | Proceso que tiene reservado el lote. |
| `lease_until` | `DATETIME2(3)` | No | Hasta cuándo vale la reserva. Vencida, otro proceso puede tomar el lote. |

Índices: `ix_cv_batches_vacancy (vacancy_id, created_at)` e `ix_cv_batches_status (status)`.

### `ai.cv_batch_items`

Un CV dentro de un lote, con su resultado. La clasificación es la sugerencia inicial de la IA y no se modifica con decisiones posteriores.

| Columna | Tipo | Oblig. | Descripción |
| --- | --- | --- | --- |
| `id` | `UNIQUEIDENTIFIER` | Sí | Clave primaria. |
| `batch_id` | `UNIQUEIDENTIFIER` | Sí | Lote (`ai.cv_batches`). |
| `file_id` | `UNIQUEIDENTIFIER` | Sí | El CV (`files.file_assets`). Único por lote. |
| `position` | `INT` | Sí | Orden dentro del lote. Único por lote. |
| `status` | `VARCHAR(20)` | Sí | `PENDIENTE`, `EVALUADO` o `FALLIDO`. |
| `step` | `VARCHAR(20)` | Sí | Último paso completado: `RECIBIDO`, `TEXTO_EXTRAIDO`, `ANALIZADO` o `CALIFICADO`. |
| `attempts` | `INT` | Sí | Veces que se ha intentado evaluar. |
| `classification` | `VARCHAR(20)` | No | `ACEPTADO_IA`, `RECHAZADO_IA` o `NO_EVALUABLE`. |
| `score` | `NUMERIC(5,2)` | No | Puntuación de 0 a 100 calculada por el sistema. Vacía si no es evaluable. |
| `result` | `NVARCHAR(MAX)` | No | JSON con el nivel, la evidencia y la justificación de cada criterio, la calidad documental, las observaciones y el motivo si no es evaluable. Contiene fragmentos del CV. |
| `error_code`, `error_message` | `VARCHAR(40)`, `NVARCHAR(500)` | No | Por qué falló: `proveedor`, `respuesta_invalida`, `archivo_no_disponible` u `original_sin_evaluar`. |
| `extraction` | `NVARCHAR(MAX)` | No | JSON con los datos ordenados del CV: correo y teléfono (tomados del texto sin IA), nombre, experiencia con periodos, estudios, habilidades, certificaciones y proyectos, y el estado de la extracción (`SOLO_CONTACTO`, `COMPLETA` o `FALLIDA`). |
| `duplicate_of` | `UNIQUEIDENTIFIER` | No | Otro CV del mismo lote con el mismo contenido, del que se toma el resultado. |
| `execution_id` | `UNIQUEIDENTIFIER` | No | Llamada al proveedor (`ai.executions`). Sin clave foránea. |
| `updated_at` | `DATETIME2(3)` | Sí | Último cambio. |

Índices: `ix_cv_batch_items_status (batch_id, status)` e `ix_cv_batch_items_file (file_id)`.

## Esquema `recruitment`: reclutamiento operativo

La aplicación nunca borra filas de este esquema.

### `recruitment.pipeline_versions` y `recruitment.pipeline_stages`

Las etapas del proceso, por versiones. Una versión no cambia; modificar las etapas crea otra.

| Tabla | Columna | Tipo | Descripción |
| --- | --- | --- | --- |
| `pipeline_versions` | `id`, `version_number` | `UNIQUEIDENTIFIER`, `INT` | Versión; el número es único. |
| `pipeline_versions` | `created_at`, `created_by` | `DATETIME2(3)`, `UNIQUEIDENTIFIER` | Cuándo y quién. `created_by` vacío en la versión inicial, que crea el sistema. |
| `pipeline_stages` | `id`, `pipeline_version_id`, `position` | | Etapa y su orden dentro de la versión (único). |
| `pipeline_stages` | `name` | `NVARCHAR(100)` | Nombre visible. |
| `pipeline_stages` | `kind` | `VARCHAR(30)` | `EVALUACION_CV`, `REVISION_RH`, `LLAMADA`, `PSICOMETRIA`, `ENTREVISTA`, `PRUEBA_TECNICA`, `ESTUDIO_SOCIOECONOMICO`, `RESULTADO` u `OTRA`. |
| `pipeline_stages` | `is_optional` | `BIT` | Si puede omitirse sin motivo. |

### `recruitment.campaigns`

Convocatoria: un periodo de reclutamiento de una vacante.

| Columna | Tipo | Oblig. | Descripción |
| --- | --- | --- | --- |
| `id` | `UNIQUEIDENTIFIER` | Sí | Clave primaria. |
| `vacancy_id`, `number` | `UNIQUEIDENTIFIER`, `INT` | Sí | Vacante y número consecutivo dentro de ella (único). |
| `name` | `NVARCHAR(100)` | Sí | Nombre visible. |
| `status` | `VARCHAR(20)` | Sí | `ABIERTA` o `CERRADA`. La aplicación mantiene una sola abierta por vacante. |
| `pipeline_version_id` | `UNIQUEIDENTIFIER` | Sí | Versión de etapas con la que trabaja. No cambia. |
| `opened_at`, `opened_by` | | | Apertura. `opened_by` vacío si la abrió el sistema al registrar el primer candidato. |
| `closed_at`, `closed_by` | | No | Cierre. |

### `recruitment.candidates`

Una persona, con identificador global. Sus datos se comparten entre todas sus postulaciones.

| Columna | Tipo | Oblig. | Descripción |
| --- | --- | --- | --- |
| `id` | `UNIQUEIDENTIFIER` | Sí | Clave primaria. |
| `full_name` | `NVARCHAR(200)` | Sí | Nombre completo. |
| `email` | `NVARCHAR(254)` | No | En minúsculas. Único cuando existe (`uq_candidates_email`, índice filtrado). |
| `phone` | `NVARCHAR(40)` | No | Teléfono. |
| `created_at`, `created_by`, `updated_at` | | | `created_by` vacío si la creó el sistema desde un lote de CV. |

### `recruitment.applications`

Postulación: la participación de una persona en una convocatoria.

| Columna | Tipo | Oblig. | Descripción |
| --- | --- | --- | --- |
| `id` | `UNIQUEIDENTIFIER` | Sí | Clave primaria. |
| `candidate_id`, `campaign_id` | `UNIQUEIDENTIFIER` | Sí | Persona y convocatoria. Una postulación por persona y convocatoria. |
| `vacancy_id` | `UNIQUEIDENTIFIER` | Sí | Vacante de la convocatoria, repetida aquí para autorizar y consultar. |
| `stage_id` | `UNIQUEIDENTIFIER` | Sí | Etapa actual (`pipeline_stages`). |
| `status` | `VARCHAR(20)` | Sí | `ACTIVA` (en proceso) o el estado en que la dejó su resultado final: `CONTRATADA`, `DESCARTADA` (no contratada), `DESISTIO`, `NO_LOCALIZADA`, `CANCELADA` (vacante cancelada) u `OTRO_CIERRE`. |
| `cv_file_id` | `UNIQUEIDENTIFIER` | No | Su CV (`files.file_assets`). |
| `evaluation_item_id` | `UNIQUEIDENTIFIER` | No | Evaluación inicial de la IA (`ai.cv_batch_items`). |
| `ai_classification`, `ai_score` | `VARCHAR(20)`, `NUMERIC(5,2)` | No | Copia de la clasificación y puntuación iniciales. No cambian aunque el CV se vuelva a evaluar ni cuando RH mueve a la persona. |
| `due_at` | `DATETIME2(3)` | No | Fecha acordada para la etapa actual. |
| `created_at`, `created_by`, `updated_at` | | | `created_by` vacío si la creó el sistema. |

Índices: `ix_applications_campaign (campaign_id, stage_id, status)`, `ix_applications_vacancy` e `ix_applications_file`.

### `recruitment.application_movements`

Historial de una postulación. Solo recibe altas; la plantilla de permisos niega `UPDATE` y `DELETE`.

| Columna | Tipo | Oblig. | Descripción |
| --- | --- | --- | --- |
| `id` | `UNIQUEIDENTIFIER` | Sí | Clave primaria. |
| `application_id`, `sequence` | `UNIQUEIDENTIFIER`, `INT` | Sí | Postulación y número de orden dentro de su historial (único). |
| `kind` | `VARCHAR(20)` | Sí | `ALTA`, `AVANCE`, `RETROCESO`, `OMISION`, `DESISTIMIENTO`, `DESCARTE`, `CANCELACION`, `REACTIVACION`, `REPROGRAMACION`, `INCIDENCIA`, `CONTRATACION`, `NO_LOCALIZADO` o `CIERRE`. |
| `from_stage_id`, `to_stage_id` | `UNIQUEIDENTIFIER` | No | Etapa de origen y de destino. En una omisión, `from_stage_id` es la etapa omitida. |
| `note` | `NVARCHAR(500)` | No | Motivo o descripción. |
| `due_at` | `DATETIME2(3)` | No | Nueva fecha, en una reprogramación. |
| `group_id` | `UNIQUEIDENTIFIER` | No | Agrupa los movimientos de una misma operación masiva. |
| `occurred_at`, `actor_user_id` | | | Cuándo y quién. `actor_user_id` vacío si lo hizo el sistema. |

### `recruitment.application_outcomes`

Resultado final de una postulación (sección 23). Lo registra siempre una persona. Al reabrir la postulación el registro se anula, no se borra; por eso una postulación puede tener varios, pero solo uno vigente.

| Columna | Tipo | Oblig. | Descripción |
| --- | --- | --- | --- |
| `id` | `UNIQUEIDENTIFIER` | Sí | Clave primaria. |
| `application_id`, `vacancy_id` | `UNIQUEIDENTIFIER` | Sí | Postulación y su vacante. |
| `outcome` | `VARCHAR(20)` | Sí | `CONTRATADO`, `NO_CONTRATADO`, `DESISTIO`, `NO_LOCALIZADO`, `VACANTE_CANCELADA` u `OTRO_CIERRE`. «En proceso» es no tener ninguno vigente. |
| `reason` | `NVARCHAR(500)` | No | Motivo. Obligatorio en la aplicación salvo en una contratación. |
| `notes` | `NVARCHAR(MAX)` | No | Observaciones. |
| `start_date` | `DATE` | No | Fecha de incorporación. Solo en una contratación (restricción `CHECK`). |
| `recorded_at`, `recorded_by` | `DATETIME2(3)`, `UNIQUEIDENTIFIER` | Sí | Cuándo y quién lo registró. `recorded_by` nunca va vacío: el sistema y la IA no registran resultados. |
| `voided_at`, `voided_by`, `void_reason` | | No | Cuándo, quién y por qué lo anuló al reabrir la postulación. |

Índices: `uq_application_outcomes_current`, único y filtrado (`voided_at IS NULL`) sobre `application_id`: un solo resultado vigente por postulación; e `ix_application_outcomes_vacancy (vacancy_id, outcome, recorded_at)`.

La migración `0011` crea el resultado final de las postulaciones que ya estaban cerradas, a partir del movimiento con el que se cerraron.

### `recruitment.question_banks` y `recruitment.question_bank_versions`

| Tabla | Columna | Tipo | Descripción |
| --- | --- | --- | --- |
| `question_banks` | `name`, `description` | `NVARCHAR(150)`, `NVARCHAR(500)` | Nombre y descripción. |
| `question_banks` | `owner_user_id` | `UNIQUEIDENTIFIER` | Propietario. |
| `question_banks` | `scope` | `VARCHAR(20)` | `PRIVADO` o `COMPARTIDO`. |
| `question_banks` | `status` | `VARCHAR(20)` | `ACTIVO` o `ARCHIVADO`. |
| `question_banks` | `duplicated_from` | `UNIQUEIDENTIFIER` | Banco del que se copió, si es una copia. |
| `question_bank_versions` | `bank_id`, `version_number` | | Versión del banco (única por banco). No cambia. |
| `question_bank_versions` | `questions` | `NVARCHAR(MAX)` | Preguntas en orden, en JSON (`ISJSON`): identificador, texto, competencia, guía y origen (`MANUAL` o `IA`). |
| `question_bank_versions` | `change_note`, `created_at`, `created_by` | | Qué cambió, cuándo y quién. |

### `recruitment.call_sessions`

Una llamada telefónica de una postulación.

| Columna | Tipo | Oblig. | Descripción |
| --- | --- | --- | --- |
| `id` | `UNIQUEIDENTIFIER` | Sí | Clave primaria. |
| `application_id`, `vacancy_id` | `UNIQUEIDENTIFIER` | Sí | Postulación y su vacante. |
| `bank_version_id` | `UNIQUEIDENTIFIER` | Sí | Versión exacta del banco con la que se hizo la llamada. |
| `status` | `VARCHAR(20)` | Sí | `BORRADOR` o `CERRADA`. Cerrada ya no se modifica. |
| `called_at` | `DATETIME2(3)` | Sí | Fecha de la llamada. |
| `notes` | `NVARCHAR(MAX)` | Sí | Observaciones generales. |
| `answers` | `NVARCHAR(MAX)` | Sí | Respuestas en JSON (`ISJSON`): pregunta, respuesta, observación y si no se realizó. |
| `analysis`, `analysis_at`, `analysis_by` | | No | Último análisis de IA, en JSON, con su fecha y quién lo pidió. |
| `created_at`, `created_by`, `updated_at`, `closed_at` | | | Registro y cierre. |

### `recruitment.form_templates` y `recruitment.form_template_versions`

Formularios configurables del estudio socioeconómico, por versiones.

| Tabla | Columna | Tipo | Descripción |
| --- | --- | --- | --- |
| `form_templates` | `name`, `description` | `NVARCHAR(150)`, `NVARCHAR(500)` | Nombre y descripción. |
| `form_templates` | `status` | `VARCHAR(20)` | `ACTIVA` o `ARCHIVADA`. |
| `form_template_versions` | `template_id`, `version_number` | | Versión del formulario (única por formulario). No cambia. |
| `form_template_versions` | `sections` | `NVARCHAR(MAX)` | Secciones y campos en JSON (`ISJSON`): identificador, nombre, tipo, obligatoriedad, opciones, mínimo y máximo. |
| `form_template_versions` | `created_at`, `created_by` | | `created_by` vacío en la plantilla inicial, que crea el sistema. |

### `recruitment.assessments`

Una evaluación de una postulación. Lo capturado va en JSON y se valida en la aplicación según el tipo.

| Columna | Tipo | Oblig. | Descripción |
| --- | --- | --- | --- |
| `id` | `UNIQUEIDENTIFIER` | Sí | Clave primaria. |
| `application_id`, `vacancy_id` | `UNIQUEIDENTIFIER` | Sí | Postulación y su vacante. |
| `kind` | `VARCHAR(30)` | Sí | `PSICOMETRIA`, `ENTREVISTA`, `PRUEBA_TECNICA` o `ESTUDIO_SOCIOECONOMICO`. Los tipos `PSICOMETRIA` y `ESTUDIO_SOCIOECONOMICO` son datos sensibles: la aplicación exige el permiso adicional para leerlos. |
| `status` | `VARCHAR(20)` | Sí | Según el tipo. Psicometría: `PENDIENTE`, `PRESENTADA`, `NO_PRESENTADA`, `INCOMPLETA`, `NO_APLICA`, `ANULADA`, `VALIDADA`. Prueba técnica: `PENDIENTE`, `REALIZADA`, `NO_PRESENTADA`, `INCOMPLETA`, `NO_APLICA`, `ANULADA`. Entrevista: `PROGRAMADA`, `REALIZADA`, `NO_REALIZADA`, `CANCELADA`. Estudio: `PENDIENTE`, `EN_PROCESO`, `COMPLETADO`, `NO_APLICA`, `ANULADO`. |
| `event_date` | `DATETIME2(3)` | No | Fecha de la prueba, entrevista o visita. |
| `file_id` | `UNIQUEIDENTIFIER` | No | Documento de la vacante (`files.file_assets`). |
| `template_version_id` | `UNIQUEIDENTIFIER` | Solo estudios | Versión del formulario con la que se capturó. Obligatoria en un estudio y vacía en los demás tipos (`ck_assessments_template`). |
| `data` | `NVARCHAR(MAX)` | Sí | Lo capturado, en JSON (`ISJSON`). En un estudio, cada respuesta lleva su valor, si una persona la verificó y si la leyó la IA. Contiene datos personales y, según el tipo, sensibles. |
| `score` | `NUMERIC(5,2)` | No | Solo en pruebas técnicas con rúbrica completa: puntos obtenidos entre posibles, de 0 a 100. Nunca en psicometría ni en estudios. |
| `ai_summary`, `ai_summary_at`, `ai_summary_by` | | No | Último resumen de IA, en JSON, con su fecha y quién lo pidió. |
| `version` | `INT` | Sí | Aumenta con cada guardado; evita que dos personas se pisen. |
| `created_at`, `created_by`, `updated_at`, `updated_by` | | Sí | Registro. |

Índice: `ix_assessments_application (application_id, kind)`.

### `recruitment.application_syntheses`

Síntesis del expediente generadas por la IA. Se conservan todas.

| Columna | Tipo | Oblig. | Descripción |
| --- | --- | --- | --- |
| `id` | `UNIQUEIDENTIFIER` | Sí | Clave primaria. |
| `application_id`, `vacancy_id` | `UNIQUEIDENTIFIER` | Sí | Postulación y su vacante. |
| `result` | `NVARCHAR(MAX)` | Sí | JSON (`ISJSON`) con seis listas: hechos documentados, declaraciones, observaciones humanas, resultados técnicos, información pendiente y discrepancias verificables. Nunca una puntuación. |
| `sources` | `NVARCHAR(MAX)` | Sí | Fuentes usadas, en JSON (por ejemplo, «2 llamadas»). |
| `includes_psychometrics` | `BIT` | Sí | Si incluyó psicometría validada; en ese caso solo la ve quien tiene ese permiso. |
| `created_at`, `created_by` | | Sí | Cuándo y quién la pidió. |

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

### `ops.report_exports`

Un registro por cada Excel de reportes generado. El archivo está en el almacenamiento documental del servidor (`generated/reports`). Solo recibe altas.

| Columna | Tipo | Oblig. | Descripción |
| --- | --- | --- | --- |
| `id` | `UNIQUEIDENTIFIER` | Sí | Clave primaria; es también el nombre del archivo guardado. |
| `kind` | `VARCHAR(20)` | Sí | `INDICADORES` o `POSTULACIONES`. |
| `name` | `NVARCHAR(200)` | Sí | Nombre con el que se descarga. |
| `filters` | `NVARCHAR(MAX)` | Sí | JSON (`ISJSON`) con los filtros pedidos, con nombres legibles. |
| `vacancy_ids` | `NVARCHAR(MAX)` | Sí | JSON (`ISJSON`) con las vacantes cuyos datos contiene. Al descargar se comprueba que quien lo pide las siga viendo todas. |
| `row_count` | `INT` | Sí | Vacantes (indicadores) o postulaciones (postulaciones) incluidas. |
| `storage_key` | `VARCHAR(200)` | Sí | Ubicación lógica del archivo. Única. |
| `size_bytes`, `sha256` | `BIGINT`, `VARCHAR(64)` | Sí | Tamaño y huella del archivo. |
| `created_at`, `created_by` | | Sí | Cuándo y quién lo generó. |

Índice: `ix_report_exports_user (created_by, created_at)`.

Los tableros no tienen tablas propias: sus cifras se calculan en cada consulta a partir de las tablas anteriores.

## Esquema `dbo`

### `dbo.alembic_version`

Una sola fila con la versión del esquema instalada (`version_num`). La usan la aplicación y los scripts de actualización; no se edita a mano.
