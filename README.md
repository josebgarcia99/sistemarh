# Sistema Integral de Reclutamiento e Inteligencia Artificial

Plataforma web para gestionar el proceso completo de reclutamiento: vacantes, análisis de CV con IA, etapas, llamadas, pruebas, estudios, expedientes y contratación. La IA clasifica y resume; las decisiones las registra una persona.

**Estado actual: Fases 2 a 8 construidas, pendientes de validar contra SQL Server y con proveedores de IA reales.** Funcionan el inicio de sesión, los usuarios, las vacantes, la compartición, las transferencias, la auditoría, el almacenamiento de documentos, la configuración de IA, los perfiles y prompts, la evaluación de CV por lotes (con lectura de escaneados por OCR), los candidatos con sus etapas e historial, los bancos de preguntas, las llamadas telefónicas con su análisis, y la psicometría, las entrevistas, las pruebas técnicas, los estudios socioeconómicos y la síntesis del expediente, y los resultados finales (contrataciones), el tablero de inicio, los indicadores con históricos y los reportes en Excel. Están también las pruebas de seguridad y del flujo completo, los manuales y el paquete de despliegue para Sistemas ([`docs/deployment/despliegue_produccion.md`](docs/deployment/despliegue_produccion.md)). Nada se ha ejecutado todavía contra un SQL Server real ni contra un proveedor de IA real. Lo que existe y lo que falta está en [`docs/estado_proyecto.md`](docs/estado_proyecto.md).

## Arquitectura en una línea

Monorepositorio con un backend monolítico modular (FastAPI), un frontend (Next.js), workers (Celery con Redis como cola) y SQL Server 2022 como fuente de verdad. Los documentos se guardan en el disco privado del servidor. Detalle en [`docs/architecture/arquitectura_general.md`](docs/architecture/arquitectura_general.md).

## Estructura

```
apps/
  api/        API FastAPI: app/core, app/modules/<dominio>, app/infrastructure
  worker/     Tareas Celery; importa los casos de uso de la API
  web/        Interfaz Next.js (TypeScript estricto, Tailwind)
database/     Migraciones Alembic y scripts T-SQL para Sistemas (database/sqlserver)
scripts/      Scripts T-SQL (generate_sql.py), documentación derivada (generate_docs.py),
              modo demostración (demo.py) y medición de rendimiento (medir_rendimiento.py)
tests/e2e/    Recorridos completos en navegador (Playwright) sobre el modo demostración
infrastructure/
  docker/     Imágenes y Docker Compose de desarrollo y de producción
  nginx/      Proxy inverso de ejemplo con HTTPS
  env/        Variables de ejemplo por entorno
docs/         Arquitectura, permisos, base de datos, seguridad, pruebas, despliegue y manuales
```

## Puesta en marcha local

Requisitos: Python 3.12 o posterior, Node.js 22 o posterior y un SQL Server 2022 con Microsoft ODBC Driver 18. Redis solo hace falta para el worker.

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

Abre http://localhost:3000. Para iniciar sesión necesitas SQL Server y haber creado tu usuario maestro; los pasos están en la guía de instalación.

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
- Solo SQL Server: la aplicación rechaza cualquier otro motor. Las pruebas automáticas usan un motor SQLite en memoria que solo existe dentro de las pruebas y que no sustituye la validación contra SQL Server.
- Las pruebas usan datos sintéticos.
- Una funcionalidad no está terminada sin pruebas.
