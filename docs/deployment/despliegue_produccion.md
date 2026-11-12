# Guía de despliegue para Sistemas

Cómo instalar, operar y mantener el sistema en un servidor de la empresa.

> **Nada de esta guía se ha ejecutado todavía en un servidor real.** Las imágenes de contenedor no se han construido, los scripts T-SQL no se han ejecutado en SQL Server y el proxy no se ha probado con un certificado. Es la propuesta de partida: Sistemas la revisa, la adapta y decide. El equipo de desarrollo no despliega ni se conecta a servidores de la empresa.

## 1. Qué se instala

```
Usuarios ──HTTPS──► proxy (nginx) ──► web  (pantallas, Next.js)
                         │
                         └──────────► api  (FastAPI) ──► SQL Server 2022 (de la empresa)
                                       │   ▲
                                       │   └── worker (Celery): evalúa los lotes de CV
                                       ├──► redis  (cola de tareas; no guarda datos)
                                       ├──► clamav (antivirus local)
                                       ├──► carpeta de documentos del servidor
                                       └──► proveedores de IA (Anthropic, OpenAI, Gemini), por HTTPS
```

Seis contenedores (`proxy`, `web`, `api`, `worker`, `redis`, `clamav`) definidos en `infrastructure/docker/docker-compose.prod.yml`. SQL Server, la carpeta de documentos, la clave maestra y el certificado quedan **fuera** de los contenedores, bajo control de Sistemas.

## 2. Requisitos del servidor

| Elemento | Requisito | Notas |
| --- | --- | --- |
| Sistema operativo | Linux de 64 bits con Docker Engine y Docker Compose v2 | Decidido el 10 nov 2026: Linux con contenedores. No se ha probado en ninguna distribución concreta |
| CPU y memoria | Punto de partida: 4 núcleos y 8 GB | ClamAV usa cerca de 2 GB; el resto es holgura. Sin medir con carga real |
| Disco de documentos | Volumen propio, con respaldo. Estimar unos 2 MB por CV | La aplicación rechaza cargas si queda menos de 1 GB libre |
| SQL Server | 2022, accesible desde el servidor por el puerto 1433 con cifrado | No se asume edición ni intercalación: decisión pendiente de Sistemas |
| Red de salida | HTTPS hacia los proveedores de IA habilitados y hacia la actualización de firmas de ClamAV | Si no hay salida, la IA y la actualización de firmas no funcionan; lo demás sí |
| Certificado | TLS para el nombre con el que se publicará | Lo emite Sistemas |
| Fuera de contenedores | Solo si se quiere ejecutar sin Docker: Python 3.12, Node.js 22, ODBC Driver 18, Tesseract con español | Ver `instalacion_local.md` |

Dependencias del sistema operativo que la imagen ya incluye: ODBC Driver 18 para SQL Server (implica aceptar la licencia de Microsoft) y Tesseract OCR con el idioma español.

## 3. Instalación, paso a paso

### 3.1 Base de datos

1. Crear la base vacía y un **usuario de aplicación** sin permisos de administración.
2. Ejecutar `database/sqlserver/instalacion_completa.sql` con un usuario que pueda crear esquemas y tablas (`sqlcmd -b` o SSMS en modo SQLCMD).
3. Ejecutar `database/sqlserver/permisos_usuario_aplicacion.sql`, sustituyendo `<USUARIO_APP>`. Da los permisos mínimos y hace inalterable la auditoría.
4. Ejecutar `database/sqlserver/validaciones_integridad.sql`: todas las filas deben mostrar 0 (la primera, «debe existir un administrador», mostrará 1 hasta completar el paso 3.4).

Recomendaciones a revisar en `docs/database/revision_sql_server.md`: aislamiento por instantáneas, intercalación, modelo de recuperación y mantenimiento de índices.

### 3.2 Carpetas y secretos en el servidor

```bash
# Documentos: propiedad del usuario 10001 (el de la aplicación dentro del contenedor).
sudo mkdir -p /srv/reclutamiento/storage && sudo chown 10001:10001 /srv/reclutamiento/storage
sudo chmod 750 /srv/reclutamiento/storage

# Clave maestra y certificado: fuera del disco de documentos.
sudo mkdir -p /etc/reclutamiento/tls && sudo chmod 750 /etc/reclutamiento
```

La **clave maestra** se crea una sola vez (paso 3.4) y cifra las claves de IA y los documentos sensibles. Si se pierde, esos datos no se recuperan. Si se filtra, hay que rotarla. Debe:

- tener permisos de solo lectura para el usuario 10001 y para nadie más;
- respaldarse **aparte** de la base y de los documentos, bajo custodia;
- ser distinta en pruebas y en producción.

### 3.3 Variables de entorno

Copiar `infrastructure/env/produccion.env.example` como `infrastructure/env/produccion.env` **en el servidor** y completar los valores. Ese archivo no se sube al repositorio.

| Variable | Para qué |
| --- | --- |
| `RECLU_ENVIRONMENT` | `production`. Desactiva la documentación interactiva de la API y exige HTTPS |
| `RECLU_DATABASE_URL` | Conexión a SQL Server con el usuario de aplicación y `Encrypt=yes` |
| `RECLU_STORAGE_HOST_PATH` | Carpeta de documentos en el servidor |
| `RECLU_MASTER_KEY_HOST_FILE` | Archivo de la clave maestra en el servidor |
| `RECLU_TLS_CERT_HOST_FILE`, `RECLU_TLS_KEY_HOST_FILE` | Certificado y clave privada para el proxy |
| `RECLU_ANTIVIRUS_MODE` | `clamd` (recomendado) o `disabled`, que en producción exige una decisión expresa |
| `RECLU_AI_ALLOW_REAL_DOCUMENTS` | `false` por omisión. Ponerlo en `true` autoriza enviar documentos reales a los proveedores de IA: es una decisión del responsable del sistema |
| `RECLU_DISPLAY_TIMEZONE` | Zona horaria de fechas y reportes |
| `RECLU_LOG_LEVEL` | `INFO` |
| `FORWARDED_ALLOW_IPS` | Desde qué direcciones se acepta la IP real del usuario que informa el proxy |

Las claves de Anthropic, OpenAI y Google Gemini **no van en este archivo**: el administrador las registra en la pantalla «IA», donde quedan cifradas.

### 3.4 Arranque y primer administrador

```bash
COMPOSE="docker compose --env-file infrastructure/env/produccion.env -f infrastructure/docker/docker-compose.prod.yml"

# 1. Construir las imágenes.
$COMPOSE build

# 2. Clave maestra (una sola vez). Se genera con un contenedor de un solo uso que
#    escribe en /etc/reclutamiento; el comando se niega a sobrescribir una existente.
docker run --rm --user root -v /etc/reclutamiento:/salida reclutamiento-api \
  python -m app.cli generate-master-key --output /salida/clave_maestra
sudo chown 10001:10001 /etc/reclutamiento/clave_maestra && sudo chmod 400 /etc/reclutamiento/clave_maestra

# 3. Levantar.
$COMPOSE up -d

# 4. Primer administrador. La contraseña se pide por teclado y no queda en el historial.
$COMPOSE exec api python -m app.cli create-admin --email <correo> --name "<Nombre completo>"
```

El nombre de la imagen (`reclutamiento-api`) es el que asigna Compose al construir; confírmalo con `docker images`.

Los demás usuarios se crean desde la pantalla «Usuarios».

### 3.5 Comprobaciones tras instalar

| Comprobación | Resultado esperado |
| --- | --- |
| `curl -k https://<servidor>/api/v1/health/live` | `{"status":"ok"}` |
| `curl -k https://<servidor>/api/v1/health/ready` | `ready: true` con SQL Server, versión del esquema, cola y almacenamiento en `ok` |
| `curl -I http://<servidor>/` | Redirección 301 a HTTPS |
| `curl -kI https://<servidor>/api/v1/docs` | 404: la documentación no se publica en producción |
| Iniciar sesión como administrador | Entra y ve «Estado del sistema» en verde |
| Cargar un PDF de prueba en una vacante de prueba | Aparece como analizado por el antivirus; el archivo existe bajo la carpeta de documentos |
| Reiniciar los contenedores y descargar ese PDF | Se descarga íntegro |
| `docker compose ... exec api python -m app.cli storage-check --verify-hashes all` | «Resultado: coherente» |
| `validaciones_integridad.sql` | Todas las filas en 0 |

Si alguna falla, no dar servicio.

## 4. Operación

### 4.1 Respaldos y restauración

Procedimiento completo en [`respaldos_y_restauracion.md`](respaldos_y_restauracion.md). En resumen: base de datos y carpeta de documentos se respaldan como un conjunto, con el manifiesto que genera la aplicación; la clave maestra, aparte. Una restauración se da por buena cuando pasan `storage-verify --full`, `storage-check --verify-hashes all` y `validaciones_integridad.sql`. Se recomienda probarla cada trimestre en el entorno de pruebas.

### 4.2 Monitoreo

| Qué vigilar | Cómo |
| --- | --- |
| Que el servicio responde | `GET /api/v1/health/live` cada minuto |
| Que sus dependencias responden | `GET /api/v1/health/ready`; responde 503 si falla la base, la cola o el almacenamiento, o si la versión del esquema no coincide |
| Errores y lentitud | `GET /api/v1/system/metrics` (solo administradores y solo desde la red interna): solicitudes, errores y duración por ruta desde el último arranque |
| Registros | Salida estándar de `api` y `worker`, en JSON, una línea por evento. Cada solicitud deja método, ruta, estado, duración e identificador de correlación. Las solicitudes de más de 2 segundos salen como advertencia |
| Espacio en disco | Carpeta de documentos; la aplicación rechaza cargas con menos de 1 GB libre |
| Lotes de CV detenidos | Registros del `worker`; en pantalla, la pestaña «Evaluación de CV» de la vacante |
| Consumo de IA | Pantalla «IA» e «Indicadores» |

Los registros no contienen contraseñas, claves ni la consulta de las direcciones (que puede llevar nombres). Cuando un usuario reporta un error, la pantalla le muestra un identificador de correlación: con él se encuentra la solicitud en los registros.

Las métricas son por proceso y se pierden al reiniciar. Si Sistemas usa una herramienta de monitoreo, puede consultarlas periódicamente; no hay integración con ninguna en particular.

### 4.3 Actualizaciones

1. Respaldar base y documentos.
2. Obtener la versión nueva del repositorio y revisar `docs/estado_proyecto.md` («Cambios recientes»).
3. Si cambió la versión del esquema, ejecutar en orden los scripts `actualizacion_NNNN_a_MMMM.sql` que falten. La versión instalada está en `dbo.alembic_version`. Si se añadieron tablas, revisar `permisos_usuario_aplicacion.sql`.
4. Reconstruir y levantar: `docker compose ... up -d --build`. Si la versión del esquema de la base no es la que espera la aplicación, `/api/v1/health/ready` responde 503 con el componente «esquema» en fallo y lo deja escrito en los registros: no dar servicio hasta corregirlo.
5. Repetir las comprobaciones de la sección 3.5.

Para volver atrás: restaurar el respaldo del paso 1 y levantar la versión anterior. Los scripts de actualización no tienen reversión automática en producción.

### 4.4 Mantenimiento

| Tarea | Frecuencia sugerida |
| --- | --- |
| `storage-check --verify-hashes sample` (conciliación: cierra cargas interrumpidas, limpia temporales, detecta faltantes) | Cada noche. Hay que programarla: el sistema no la ejecuta solo |
| `storage-check --verify-hashes all` | Semanal |
| `validaciones_integridad.sql` | Mensual y tras cada restauración |
| Mantenimiento de índices y estadísticas de SQL Server | Según la política de Sistemas |
| Renovación del certificado | Antes de su vencimiento |
| Actualización de imágenes base y dependencias | Mensual, en el entorno de pruebas primero |
| Revisión de la carpeta `quarantine/` del almacenamiento | Mensual: archivos sin registro que la conciliación apartó |
| Rotación de la clave maestra | Si se sospecha que se filtró. **El procedimiento todavía no está construido** |

## 5. Entornos

Desarrollo, pruebas y producción se mantienen separados, cada uno con su base de datos, su carpeta de documentos y su clave maestra. Ver `infrastructure/env/README.md`. En desarrollo y pruebas solo se usan datos sintéticos y `RECLU_AI_ALLOW_REAL_DOCUMENTS=false`.

## 6. Qué contiene el paquete de despliegue

| Ruta | Contenido |
| --- | --- |
| `database/sqlserver/` | Instalación completa, actualizaciones entre versiones, permisos del usuario de aplicación, validaciones de integridad y reversión (solo para bases de prueba) |
| `infrastructure/docker/` | Imágenes de la API, el worker y las pantallas; Compose de desarrollo y de producción |
| `infrastructure/nginx/` | Configuración de ejemplo del proxy con HTTPS |
| `infrastructure/env/` | Variables de ejemplo por entorno |
| `docs/deployment/` | Esta guía, instalación local, almacenamiento documental, respaldos y restauración |
| `docs/database/` | Diccionario de datos, diagrama entidad-relación y revisión de SQL Server |
| `docs/security/` | Modelo de seguridad y modelo de amenazas |

## 7. Pendiente de decidir o validar con Sistemas

- Instancia, edición e intercalación de SQL Server.
- Construir las imágenes y ejecutar las comprobaciones de la sección 3.5.
- Antivirus definitivo (el ClamAV incluido u otra solución local).
- Dónde se guarda y cómo se respalda la clave maestra.
- Cómo se programa la conciliación nocturna.
- Política de retención de documentos y de reportes generados (con el área legal).
- Rangos de red desde los que se consultan las métricas (hoy, redes privadas habituales en `reclutamiento.conf`).
