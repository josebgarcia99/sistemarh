# Estado del proyecto

Última actualización: 10 de noviembre de 2026.

## Fase actual

**Fase 1: Fundamentos.** Código escrito y probado en el entorno de construcción. Pendiente de tu revisión para darla por cerrada.

## Funcionalidades terminadas

| Elemento | Detalle |
| --- | --- |
| Estructura del monorepositorio | `apps/api`, `apps/worker`, `apps/web`, `database`, `infrastructure`, `docs` |
| API FastAPI | Configuración por variables de entorno, rutas bajo `/api/v1`, formato único de error, identificador de correlación, logs en JSON con filtro de secretos |
| Salud | `/api/v1/health/live` y `/api/v1/health/ready` (SQL Server, Redis y escritura real en el almacenamiento) |
| Conexión a SQL Server | Fábrica de conexión con `mssql+pyodbc`; cualquier otro motor se rechaza |
| Worker Celery | Configuración segura (solo JSON, sin backend de resultados, confirmación al terminar) y tarea `system.ping` |
| Frontend Next.js | TypeScript estricto, Tailwind con los colores del diseño aprobado, cliente de API con validación, pantalla de estado del sistema |
| Reglas entre módulos | `import-linter` impide que `core` e `infrastructure` dependan de los módulos y fija las capas |
| Migraciones | Alembic configurado para SQL Server; aún sin migraciones |
| Infraestructura local | Dockerfiles y Docker Compose de desarrollo |
| Documentación | Arquitectura aprobada repartida en `docs/`, instalación local, este archivo |

## Pruebas ejecutadas

Ejecutadas el 10 de noviembre de 2026 en el entorno de construcción (Linux, Python 3.13, Node.js 22):

| Prueba | Resultado |
| --- | --- |
| API: `pytest` | 34 pruebas, todas pasan |
| Worker: `pytest` | 4 pruebas, todas pasan |
| `ruff check` y `lint-imports` | Sin errores; 3 contratos de importación cumplidos |
| Frontend: `tsc --noEmit`, `eslint` | Sin errores |
| Frontend: `vitest` | 9 pruebas, todas pasan |
| Frontend: `next build` | Compila |
| Recorrido manual | API y frontend levantados juntos; `/api/v1/health/ready` responde a través del frontend |
| Docker Compose | Solo validación de sintaxis (`docker compose config`) |

## No verificado todavía

- **Conexión real a SQL Server.** No hay instancia de pruebas; el código de conexión no se ha ejecutado contra un servidor.
- **Redis y worker en ejecución.** La configuración está probada; el worker no se ha ejecutado contra un Redis real.
- **Imágenes Docker.** No se han construido. Falta comprobar la instalación de ODBC Driver 18 dentro de la imagen.
- **Python 3.12.** Las pruebas corrieron en 3.13; la imagen Docker usa 3.12.
- **Windows.** Nada se ha probado en Windows.

## Funcionalidades pendientes

Todo lo de las Fases 2 a 8 (ver [`roadmap.md`](roadmap.md)). Lo inmediato, Fase 2:

- Usuario maestro creado por comando de instalación.
- Alta de usuarios por el administrador con correo, nombre completo y contraseña inicial; sin envío de correos.
- Restablecimiento de contraseñas desde la pantalla de Usuarios.
- Inicio de sesión, sesiones en SQL Server, cierre de sesión y bloqueo por intentos.
- Vacantes, compartición, transferencias y auditoría.
- Primeras tablas y migraciones.

## Documentos de `docs/` aún no creados

Se escriben cuando exista su contenido: `database/diccionario_datos.md` (con las primeras tablas, Fase 2), `security/modelo_amenazas.md` (Fase 2), `api/contratos_api.md` (Fase 2, generado desde OpenAPI), `manuals/manual_administrador.md` y `manuals/manual_reclutador.md` (Fases 2 a 7).

## Problemas conocidos

- Los logs de acceso de Uvicorn no salen en JSON; solo los de la aplicación. Se unifica en la Fase 2.
- `starlette` avisa de que `httpx` quedará obsoleto para pruebas en favor de `httpx2`. No afecta hoy.
- `npm audit` reporta 8 avisos de severidad moderada en dependencias de desarrollo del frontend. Pendiente de revisar uno por uno.
- `apps/api/requirements.lock` incluye las dependencias de desarrollo. Se separa en dos archivos antes de producción.

## Cambios recientes

- 10 nov 2026: arquitectura aprobada con dos cambios: usuarios sin correo electrónico (los crea y restablece el administrador) y entrega del código en GitHub.
- 10 nov 2026: Fase 1 construida.

## Decisiones tomadas

- Decisiones 1 a 14 de la propuesta aprobadas con la opción recomendada, salvo la 1 (entrega por GitHub) y la 9 (sin correo).
- Al crear un usuario, el sistema pedirá cambiar la contraseña inicial en el primer ingreso. Pendiente de tu confirmación.

## Decisiones pendientes

- Sistema operativo del servidor y disponibilidad de Docker (Sistemas).
- Instancia de SQL Server 2022 para desarrollo y pruebas (Sistemas).
- Edición e intercalación de SQL Server.
- Política de retención de documentos y aviso de privacidad (área legal).

## Próximos pasos

1. Tu revisión de la Fase 1.
2. Diseño de las pantallas de la Fase 2: inicio de sesión, usuarios, administración de vacantes y transferencia.
3. Construcción de la Fase 2.
