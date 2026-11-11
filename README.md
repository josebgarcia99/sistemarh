# Sistema Integral de Reclutamiento e Inteligencia Artificial

Plataforma web para gestionar el proceso completo de reclutamiento: vacantes, análisis de CV con IA, etapas, llamadas, pruebas, estudios, expedientes y contratación. La IA clasifica y resume; las decisiones las registra una persona.

**Estado actual: Fase 1 (fundamentos).** Lo que existe y lo que falta está en [`docs/estado_proyecto.md`](docs/estado_proyecto.md).

## Arquitectura en una línea

Monorepositorio con un backend monolítico modular (FastAPI), un frontend (Next.js), workers (Celery con Redis como cola) y SQL Server 2022 como fuente de verdad. Los documentos se guardan en el disco privado del servidor. Detalle en [`docs/architecture/arquitectura_general.md`](docs/architecture/arquitectura_general.md).

## Estructura

```
apps/
  api/        API FastAPI: app/core, app/modules/<dominio>, app/infrastructure
  worker/     Tareas Celery; importa los casos de uso de la API
  web/        Interfaz Next.js (TypeScript estricto, Tailwind)
database/     Migraciones Alembic para SQL Server
infrastructure/
  docker/     Imágenes y Docker Compose de desarrollo
docs/         Arquitectura, permisos, base de datos, seguridad, pruebas, despliegue
```

## Puesta en marcha local

Requisitos: Python 3.12 o posterior, Node.js 22 o posterior. SQL Server y Redis son opcionales en esta fase: sin ellos el sistema arranca y los reporta como "sin configurar".

```bash
# 1. Configuración
cp .env.example .env            # completa solo lo que tengas

# 2. API
python -m venv .venv
source .venv/bin/activate       # En Windows: .venv\Scripts\activate
pip install -r apps/api/requirements.lock
pip install -e apps/api --no-deps
cd apps/api && uvicorn app.main:app --reload --port 8000

# 3. Frontend (otra terminal)
cd apps/web && npm ci && npm run dev
```

Abre http://localhost:3000. La pantalla muestra si la API, SQL Server, Redis y el almacenamiento responden.

Guía completa, incluido Docker Compose y el worker: [`docs/deployment/instalacion_local.md`](docs/deployment/instalacion_local.md).

## Pruebas

```bash
cd apps/api    && pytest          # API
cd apps/worker && pytest          # Worker
cd apps/api    && ruff check . ../worker && lint-imports   # Estilo y reglas entre módulos
cd apps/web    && npm run typecheck && npm run lint && npm test && npm run build
```

## Reglas del proyecto

- Ningún secreto, documento real ni dato personal entra al repositorio. Revisa `.gitignore` antes de añadir archivos.
- Las API keys de IA se registran desde la aplicación, nunca en el código ni en `.env.example`.
- Solo SQL Server: no se usa SQLite ni PostgreSQL como sustituto.
- Las pruebas usan datos sintéticos.
- Una funcionalidad no está terminada sin pruebas.
