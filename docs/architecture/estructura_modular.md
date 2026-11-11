# Estructura modular

> Origen: propuesta de arquitectura aprobada el 10 de noviembre de 2026.
> Este archivo es la copia de trabajo del repositorio y se actualiza en cada fase.

## 5. Estructura detallada de carpetas

Se conserva la estructura del documento maestro con tres ajustes, explicados debajo del árbol.

```
reclutamiento-ia/
  apps/
    web/                        Next.js
      src/app/                  una ruta por pantalla
      src/features/             una carpeta por dominio (vacancies, cv-analysis, ...)
      src/components/           componentes compartidos (ui, layout)
      src/lib/api/              cliente HTTP y tipos generados desde OpenAPI
      src/hooks/  src/styles/
      tests/                    componentes y recorridos Playwright
    api/
      app/
        main.py
        core/                   config, security, permissions, exceptions, logging, events
        modules/
          <dominio>/
            api/                rutas y esquemas Pydantic
            application/        casos de uso
            domain/             entidades, reglas y puertos
            infrastructure/     repositorios SQLAlchemy del dominio
            tests/
        infrastructure/         database, storage, ai_providers, ocr, queues, secrets
    worker/
      celery_app.py
      jobs/                     tareas Celery, delgadas
      pipelines/                cv, exportaciones, digitalización de estudios
      tests/
  database/
    design/  migrations/  sqlserver/  documentation/
  infrastructure/
    docker/  deployment/  backup/  monitoring/
  docs/                         architecture, requirements, permissions, database, api,
                                security, testing, deployment, manuals
  tests/                        integration, e2e, performance, security, fixtures
  .env.example  .gitignore  README.md
```

| Ajuste | Razón |
| --- | --- |
| Los repositorios viven dentro de cada módulo, no en una carpeta global | Cada dominio es dueño de su persistencia; así la independencia entre módulos es real. |
| El worker importa los casos de uso del paquete de la API | Las reglas de negocio existen una sola vez. El worker solo orquesta tareas. |
| Los tipos del frontend se generan desde OpenAPI | El contrato se escribe una vez en el backend y el frontend no puede desviarse. |

La carpeta `scripts/` se crea hasta que exista el primer script. Los documentos reales de los usuarios nunca están dentro del repositorio.

## 6. Responsabilidades de cada módulo

Son los 24 módulos del documento maestro más uno propuesto, `privacy`, porque las solicitudes de eliminación y las políticas de retención no tenían dueño.

| Módulo | Responsabilidad |
| --- | --- |
| `authentication` | Inicio y cierre de sesión, sesiones, recuperación de contraseña, bloqueo por intentos. |
| `users` | Alta por el administrador, invitaciones, roles, activación y baja. |
| `vacancies` | Vacantes, estados y convocatorias. |
| `vacancy_sharing` | Colaboradores, tipo de acceso y permisos adicionales para documentos sensibles. |
| `vacancy_transfers` | Transferencia individual y masiva; historial de responsables. |
| `candidates` | Identidad global del candidato, duplicados y búsqueda restringida por permisos. |
| `applications` | Postulación por convocatoria; agrupa todo el expediente. |
| `job_profiles` | Carga y análisis de perfiles, correcciones humanas, versiones. |
| `prompts` | Capas del prompt, generación con IA, estados y versiones inmutables. |
| `rubrics` | Criterios, pesos, escala 0 a 4 y umbral, por versión. |
| `cv_analysis` | Lotes, extracción, evaluación, puntuación en Python, clasificación y permanencia laboral. |
| `recruitment_workflows` | Plantillas de etapas versionadas, movimientos, historial y tareas pendientes. |
| `question_banks` | Bancos, versiones, preguntas, rúbricas opcionales y alcance. |
| `phone_interviews` | Sesiones, respuestas y análisis de contenido con IA. |
| `psychometrics` | Instrumentos, aplicaciones, resultados y validación profesional. |
| `manager_interviews` | Entrevistas, retroalimentación y conclusión humana. |
| `technical_tests` | Pruebas opcionales, resultados y cálculo objetivo cuando hay reglas. |
| `socioeconomic_studies` | Plantillas de formularios, digitalización y verificación documental. |
| `hiring` | Resultado final y registro de contratación. |
| `dashboard` | Indicadores del reclutador y globales. |
| `reporting` | Reportes, Excel histórico, exportaciones y vistas SQL. |
| `file_management` | `FileStorageService`, metadatos, descargas, integridad y huérfanos. |
| `ai_configuration` | Proveedores, claves, registro de modelos, presupuestos y consumo. |
| `audit` | Registro y consulta de eventos de auditoría. |
| `privacy` (propuesto) | Políticas de retención, solicitudes de eliminación y borrado seguro. |
