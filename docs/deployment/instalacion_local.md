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

Los pasos 4 y 5 necesitan `RECLU_DATABASE_URL` definida en la terminal (no leen `.env`), o lanzarse desde el panel de Visual Studio Code (ver más abajo).

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

## Verlo en Visual Studio Code, paso a paso (Windows)

> Esta guía está escrita pero **no se ha probado en Windows ni contra un SQL Server real**. Si un paso falla, copia el mensaje de error.

Es Visual Studio Code (el editor gratuito), no Visual Studio. La aplicación necesita un SQL Server para funcionar: sin él las pantallas abren, pero no se puede iniciar sesión.

**Instalar una sola vez**

1. [Visual Studio Code](https://code.visualstudio.com/), [Git](https://git-scm.com/), [Python 3.12 o posterior](https://www.python.org/downloads/) (marca "Add python.exe to PATH") y [Node.js 22 LTS](https://nodejs.org/).
2. SQL Server 2022 Developer (gratuito para desarrollo) y SQL Server Management Studio.
3. Microsoft ODBC Driver 18 for SQL Server.
4. En Management Studio, crea una base de datos vacía llamada `reclutamiento`.

**Preparar el proyecto**

5. En VS Code: `Ctrl+Shift+P` → "Git: Clone" → la dirección del repositorio. Abre la carpeta y acepta instalar las extensiones recomendadas.
6. Abre una terminal (`Ctrl+ñ`) y ejecuta:
   ```powershell
   py -m venv .venv
   .venv\Scripts\activate
   pip install -r apps/api/requirements.lock
   pip install -e apps/api --no-deps
   cd apps/web
   npm ci
   cd ../..
   copy .env.example .env
   ```
   Si PowerShell no deja activar el entorno, ejecuta antes `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`.
7. `Ctrl+Shift+P` → "Python: Select Interpreter" → el que está en `.venv`.
8. En `.env`, completa la conexión. Con un SQL Server instalado en el mismo equipo y tu usuario de Windows:
   ```
   RECLU_DATABASE_URL=mssql+pyodbc://@localhost/reclutamiento?driver=ODBC+Driver+18+for+SQL+Server&Trusted_Connection=yes&Encrypt=yes&TrustServerCertificate=yes
   ```
   `.env` no se sube a GitHub. `TrustServerCertificate=yes` solo es aceptable en tu equipo.

**Ejecutar** (panel "Ejecutar y depurar", `Ctrl+Shift+D`; elige en la lista y pulsa el botón verde)

9. **1. Base de datos: crear o actualizar tablas.** Una vez, y de nuevo cuando haya migraciones nuevas.
10. **2. Crear usuario maestro (una sola vez).** Pregunta en la terminal tu correo, tu nombre y la contraseña que elijas (mínimo 12 caracteres; no se ve al escribirla).
11. **3. Sistema (API + Frontend).** Cuando la terminal muestre que está listo, abre http://localhost:3000 y entra con ese correo y esa contraseña.

Las demás configuraciones de `.vscode/launch.json` (API, Frontend, Worker y pruebas de la API) sirven para ejecutar cada parte por separado. El worker no hace falta todavía y en Windows requiere Docker o WSL2.

Los comandos escritos en una terminal no leen `.env`: por eso los pasos 9 y 10 se lanzan desde el panel. Para usarlos en una terminal, define antes la variable (`$env:RECLU_DATABASE_URL = "..."`).
