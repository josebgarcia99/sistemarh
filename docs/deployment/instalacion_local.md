# Instalación local

Hay dos formas de ejecutar el proyecto en desarrollo. Ninguna toca servidores ni bases de datos de producción.

## Opción A: procesos locales

Requisitos: Python 3.12 o posterior y Node.js 22 o posterior.

### 1. Variables de entorno

```bash
cp .env.example .env
```

| Variable | Para qué sirve | ¿Obligatoria en desarrollo? |
| --- | --- | --- |
| `RECLU_ENVIRONMENT` | `development`, `test` o `production` | No (por omisión `development`) |
| `RECLU_DATABASE_URL` | Conexión a SQL Server con `mssql+pyodbc` | Sí para iniciar sesión y usar la aplicación |
| `RECLU_REDIS_URL` | Cola de tareas | Solo para ejecutar el worker |
| `RECLU_STORAGE_ROOT` | Ruta absoluta del almacenamiento documental | No hasta la Fase 3 |
| `RECLU_AI_ALLOW_REAL_DOCUMENTS` | Permite enviar documentos reales a la IA | Mantener en `false` |
| `API_INTERNAL_URL` | Dirección de la API para el frontend | No (por omisión `http://localhost:8000`) |

En producción, `RECLU_DATABASE_URL`, `RECLU_REDIS_URL` y `RECLU_STORAGE_ROOT` son obligatorias: la API no arranca sin ellas.

### 2. API

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r apps/api/requirements.lock
pip install -e apps/api --no-deps
cd apps/api
uvicorn app.main:app --reload --port 8000
```

- Salud: http://localhost:8000/api/v1/health/live y `/api/v1/health/ready`
- Documentación interactiva (no disponible en producción): http://localhost:8000/api/v1/docs

Para conectarse a SQL Server hace falta instalar **Microsoft ODBC Driver 18 for SQL Server** en el equipo.

### 3. Worker

Necesita Redis y `RECLU_REDIS_URL`.

```bash
cd apps/worker
celery -A worker.celery_app worker --loglevel=INFO
```

En Windows, Celery no tiene soporte oficial: usa Docker (opción B) o WSL2.

### 4. Frontend

```bash
cd apps/web
npm ci
npm run dev
```

Abre http://localhost:3000. Las llamadas a `/api/...` se reenvían a la API.

## Opción B: Docker Compose

> Las imágenes y este archivo de Compose están escritos y su sintaxis está validada, pero **todavía no se han construido ni ejecutado**. Ver `docs/estado_proyecto.md`.

```bash
cp .env.example .env
# Define RECLU_STORAGE_HOST_PATH con una carpeta de tu equipo para los documentos
docker compose --env-file .env -f infrastructure/docker/docker-compose.dev.yml up --build
```

Para añadir un SQL Server 2022 local de desarrollo define `MSSQL_SA_PASSWORD` en `.env` y agrega `--profile sqlserver-local`. Usar esa imagen implica aceptar la licencia de Microsoft.

## Base de datos y usuario maestro

El inicio de sesión y los usuarios necesitan SQL Server. Sin `RECLU_DATABASE_URL`, la API arranca pero responde "servicio no disponible" en esas rutas.

1. **Ten un SQL Server 2022 a mano.** Puede ser la base de pruebas que habilite Sistemas o el contenedor local de la opción B (`--profile sqlserver-local`). Crea en él una base vacía, por ejemplo `reclutamiento`.
2. **Instala Microsoft ODBC Driver 18 for SQL Server** en tu equipo (no hace falta si usas Docker para la API).
3. **Define la conexión** en `.env`:
   ```
   RECLU_DATABASE_URL=mssql+pyodbc://<USUARIO>:<CONTRASENA>@<SERVIDOR>:1433/reclutamiento?driver=ODBC+Driver+18+for+SQL+Server&Encrypt=yes&TrustServerCertificate=yes
   ```
   `TrustServerCertificate=yes` solo es aceptable en desarrollo local.
4. **Crea las tablas:**
   ```bash
   cd database
   alembic upgrade head
   ```
5. **Crea tu usuario maestro** (una sola vez):
   ```bash
   cd apps/api
   python -m app.cli create-admin
   ```
   El comando pregunta tu correo, tu nombre completo y la contraseña que tú elijas (mínimo 12 caracteres). La contraseña no se muestra, no se guarda en ningún archivo y nadie más la conoce. Si ya existe un administrador, el comando se niega: los demás usuarios se crean desde la pantalla **Usuarios**.

> Estos cinco pasos están escritos pero **no se han ejecutado contra un SQL Server real**. Si alguno falla, el mensaje de error indica el motivo; repórtalo para corregirlo.

## Migraciones de base de datos

```bash
cd database
alembic upgrade head            # requiere RECLU_DATABASE_URL
alembic upgrade head --sql      # genera el T-SQL sin conectarse, para revisión
```

La migración `0001` crea los esquemas `auth` y `ops` con usuarios, roles, sesiones y auditoría. La `0002` crea el esquema `vacancy` con vacantes, accesos, permisos de documentos sensibles, transferencias e historial de responsables.

### Scripts para Sistemas

Si Sistemas prefiere ejecutar T-SQL en lugar de Alembic, los scripts equivalentes están en `database/sqlserver/`:

| Archivo | Uso |
| --- | --- |
| `instalacion_completa.sql` | Base vacía: crea todo hasta la versión actual |
| `actualizacion_0001_a_0002.sql` | Base que ya tiene la versión `0001` |
| `permisos_usuario_aplicacion.sql` | Plantilla de permisos mínimos para el usuario de la aplicación |
| `reversion_completa.sql` | Elimina todo. Solo para bases de prueba |

Se ejecutan con `sqlcmd -b` o en SSMS con el modo SQLCMD. Se regeneran con `python scripts/generate_sql.py`. **Ninguno se ha ejecutado todavía contra un SQL Server real.**

Para que la auditoría sea inalterable, Sistemas debe aplicar `permisos_usuario_aplicacion.sql`, que niega `UPDATE` y `DELETE` sobre `ops.audit_events` al usuario de base de datos de la aplicación.

## Depuración en Visual Studio Code

`.vscode/launch.json` trae cuatro configuraciones: API, Worker, pruebas de la API y Frontend. Requieren el entorno virtual de Python seleccionado y el archivo `.env`.
