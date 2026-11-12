# Imagen compartida por la API y el worker: el mismo código de dominio, dos procesos.
# Construir desde la raíz del repositorio:
#   docker build -f infrastructure/docker/python.Dockerfile --target api -t reclutamiento-api .
#
# NO VERIFICADO: esta imagen todavía no se ha construido (ver docs/estado_proyecto.md).
# Instalar msodbcsql18 implica aceptar la licencia de Microsoft (ACCEPT_EULA=Y).

FROM python:3.12-slim-bookworm AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/srv/app/apps/api:/srv/app/apps/worker

# Microsoft ODBC Driver 18 para SQL Server (Debian 12).
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl gnupg ca-certificates \
    && curl -fsSL https://packages.microsoft.com/keys/microsoft.asc \
        | gpg --dearmor -o /usr/share/keyrings/microsoft-prod.gpg \
    && echo "deb [arch=amd64,arm64 signed-by=/usr/share/keyrings/microsoft-prod.gpg] https://packages.microsoft.com/debian/12/prod bookworm main" \
        > /etc/apt/sources.list.d/mssql-release.list \
    && apt-get update \
    && ACCEPT_EULA=Y apt-get install -y --no-install-recommends msodbcsql18 unixodbc \
    # Lectura de CV escaneados (OCR) dentro del servidor, en español e inglés.
    && apt-get install -y --no-install-recommends tesseract-ocr tesseract-ocr-spa \
    && apt-get purge -y gnupg \
    && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/*

RUN useradd --create-home --uid 10001 reclutamiento
WORKDIR /srv/app

# Solo las dependencias de ejecución; las de desarrollo y pruebas no entran en la imagen.
COPY apps/api/requirements-prod.lock apps/api/requirements-prod.lock
RUN pip install -r apps/api/requirements-prod.lock

COPY apps/api apps/api
COPY apps/worker apps/worker
COPY database database

USER reclutamiento

FROM base AS api
WORKDIR /srv/app/apps/api
EXPOSE 8000
# La aplicación escribe su propia línea de acceso en JSON, por eso se apaga la de
# Uvicorn. La IP real del usuario se toma de la cabecera del proxy inverso solo si
# la conexión viene de una dirección listada en FORWARDED_ALLOW_IPS.
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD ["python", "-c", "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health/live', timeout=3).status == 200 else 1)"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log", "--proxy-headers"]

FROM base AS worker
WORKDIR /srv/app/apps/worker
CMD ["celery", "-A", "worker.celery_app", "worker", "--loglevel=INFO"]
