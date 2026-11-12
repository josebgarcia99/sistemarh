# Variables por entorno

Los tres entornos se mantienen separados: cada uno con su base de datos, su carpeta de documentos y su clave maestra.

| Entorno | Archivo de ejemplo | Cómo se levanta |
| --- | --- | --- |
| Desarrollo | `.env.example` (raíz del repositorio) | En el equipo de quien desarrolla, o con `infrastructure/docker/docker-compose.dev.yml` |
| Pruebas | `infrastructure/env/pruebas.env.example` | `docker-compose.prod.yml` con `pruebas.env` |
| Producción | `infrastructure/env/produccion.env.example` | `docker-compose.prod.yml` con `produccion.env` |

Reglas:

- Los archivos con valores reales (`.env`, `pruebas.env`, `produccion.env`) se crean en el servidor y **no se suben al repositorio**.
- Las API keys de IA van en esos archivos del servidor, en `RECLU_ANTHROPIC_API_KEY`, `RECLU_OPENAI_API_KEY` y `RECLU_GEMINI_API_KEY`. En los `.env.example` esas variables van siempre vacías. Como contienen secretos, el archivo real debe quedar con permisos `600`.
- En desarrollo y pruebas, `RECLU_AI_ALLOW_REAL_DOCUMENTS` va en `false`: solo datos sintéticos.
- Una clave maestra de pruebas nunca se usa en producción, ni al revés.
- Nada de esto se ha ejecutado todavía en un servidor: es la propuesta para Sistemas.
