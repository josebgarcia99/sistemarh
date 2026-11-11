# Estado del proyecto

Última actualización: 10 de noviembre de 2026.

## Fase actual

**Fase 2: Seguridad y usuarios, en curso.** Está construida la primera parte (identidad): usuario maestro, inicio de sesión, administración de usuarios y auditoría. Falta la segunda parte: vacantes, compartición y transferencias.

La Fase 1 (fundamentos) está terminada.

## Funcionalidades terminadas

| Elemento | Detalle |
| --- | --- |
| Estructura del monorepositorio | `apps/api`, `apps/worker`, `apps/web`, `database`, `infrastructure`, `docs` |
| API base | Configuración por entorno, rutas `/api/v1`, formato único de error, identificador de correlación, logs JSON con filtro de secretos, rutas de salud |
| Usuario maestro | Comando `python -m app.cli create-admin`; solo funciona si no hay ningún administrador |
| Inicio y cierre de sesión | Sesión en el servidor, cookie `HttpOnly`, token CSRF, caducidad a 30 minutos sin actividad y a 12 horas en total |
| Bloqueo por intentos | 5 intentos fallidos bloquean la cuenta 15 minutos; el mensaje no revela si el correo existe |
| Administración de usuarios | Alta con correo, nombre completo, contraseña y rol; edición; restablecer contraseña; baja y reactivación. Sin envío de correos |
| Reglas de protección | Nadie se da de baja ni se quita el rol a sí mismo; siempre queda un administrador activo; la baja y el restablecimiento cierran las sesiones del usuario |
| Auditoría | Inicios de sesión (correctos y fallidos), cierres, accesos denegados y todos los cambios de usuarios. Nunca guarda contraseñas |
| Denegación por omisión | Una prueba recorre todas las rutas de la API y verifica que solo tres responden sin sesión |
| Migración `0001` | Esquemas `auth` y `ops`: `roles`, `users`, `user_roles`, `sessions`, `audit_events` |
| Frontend | Inicio de sesión, marco de la aplicación con menú por rol, pantalla de Usuarios, pantalla de inicio con estado del sistema para administradores |
| Worker Celery | Configuración segura y tarea `system.ping` |
| Reglas entre módulos | 6 contratos de `import-linter`: capas por módulo y dominios independientes |

## Pruebas ejecutadas

Ejecutadas el 10 de noviembre de 2026 en el entorno de construcción (Linux, Python 3.13, Node.js 22):

| Prueba | Resultado |
| --- | --- |
| API: `pytest` | 76 pruebas, todas pasan |
| Worker: `pytest` | 4 pruebas, todas pasan |
| `ruff check` y `lint-imports` | Sin errores; 6 contratos cumplidos |
| Frontend: `tsc --noEmit`, `eslint` | Sin errores |
| Frontend: `vitest` | 18 pruebas, todas pasan |
| Frontend: `next build` | Compila |
| Recorrido en navegador real | 10 pasos: redirección sin sesión, credenciales erróneas, inicio de sesión, alta de usuario, restablecer contraseña, recarga, cierre de sesión, contraseña anterior rechazada, reclutador sin acceso a Usuarios y respuesta 403 de la API |
| Migración | Genera T-SQL válido en sintaxis para SQL Server sin conectarse; se comprueba que coincide con el modelo |

### Cómo se probó sin SQL Server

No hay todavía una instancia de SQL Server de pruebas. Por eso:

- Las reglas de negocio y las rutas se prueban con **repositorios de prueba en memoria** (`app/tests/support/memory_backend.py`).
- Los repositorios reales de SQLAlchemy se ejecutan en una **comprobación estructural** sobre un motor en memoria (`app/tests/test_sql_structure.py`). Detecta errores de mapeo y de consultas, pero no sustituye a SQL Server.
- El recorrido en navegador usó la API real con los repositorios en memoria.
- La aplicación sigue rechazando cualquier motor que no sea SQL Server.

## No verificado todavía

- **Todo lo que toca SQL Server de verdad:** aplicar la migración, crear el usuario maestro con el comando, iniciar sesión contra la base, la paginación `OFFSET/FETCH`, la intercalación en las búsquedas y el comportamiento de `ROWVERSION`.
- **Redis y worker en ejecución.**
- **Imágenes Docker.** No se han construido. Falta comprobar la instalación de ODBC Driver 18 dentro de la imagen.
- **Python 3.12.** Las pruebas corrieron en 3.13; la imagen Docker usa 3.12.
- **Windows.** Nada se ha probado en Windows.
- **Proxy inverso.** La IP que se audita es la de la conexión directa; detrás del proxy habrá que tomarla de la cabecera que este envíe.

## Funcionalidades pendientes

Resto de la Fase 2:

- Vacantes, estados y convocatorias.
- Compartición con acceso de lectura o colaboración, y permiso adicional para documentos sensibles.
- Transferencia individual y transferencia masiva por baja de un reclutador.
- Pantallas: administración de vacantes, compartir, transferir y auditoría.
- Pruebas de seguridad 1 a 4, 6 y 7 de la sección 32.3 (dependen de vacantes).
- Row-Level Security como segunda barrera.

Después, Fases 3 a 8 (ver [`roadmap.md`](roadmap.md)).

## Documentos de `docs/` aún no creados

`database/diccionario_datos.md`, `security/modelo_amenazas.md`, `api/contratos_api.md` (se genera desde OpenAPI), `manuals/manual_administrador.md` y `manuals/manual_reclutador.md`. Se escriben al cerrar la Fase 2.

## Problemas conocidos

- Los logs de acceso de Uvicorn no salen en JSON; solo los de la aplicación.
- `starlette` avisa de que `httpx` quedará obsoleto para pruebas en favor de `httpx2`. No afecta hoy.
- `npm audit` reporta avisos de severidad moderada en dependencias de desarrollo del frontend. Pendiente de revisar uno por uno.
- `apps/api/requirements.lock` incluye las dependencias de desarrollo. Se separa en dos archivos antes de producción.
- La tabla de auditoría depende de que Sistemas niegue `UPDATE` y `DELETE` al usuario de la aplicación; la migración no lo hace porque no conoce ese usuario.
- No hay pruebas Playwright dentro del repositorio todavía; el recorrido en navegador se hizo con un script externo. Se incorporan al cerrar la Fase 2.
- Las pantallas de inicio de sesión y de Usuarios se construyeron directamente con el sistema visual aprobado, sin maqueta previa en el lienzo.

## Cambios recientes

- 10 nov 2026: arquitectura aprobada con dos cambios: usuarios sin correo electrónico y entrega del código en GitHub.
- 10 nov 2026: Fase 1 construida y subida.
- 10 nov 2026: primera parte de la Fase 2 (identidad) construida.
- 10 nov 2026: el cierre de sesión hace una recarga completa de la página, porque el enrutador conservaba en memoria las pantallas visitadas.

## Decisiones tomadas

- Decisiones 1 a 14 de la propuesta aprobadas con la opción recomendada, salvo la 1 (entrega por GitHub) y la 9 (sin correo).
- El usuario conserva la contraseña que le asigna el administrador; no hay cambio obligatorio en el primer ingreso.
- El servidor será Linux con contenedores.
- Se avanza de fase sin esperar revisión; los cambios se piden sobre la marcha.
- Los identificadores secuenciales se generan en la aplicación en lugar de usar `NEWSEQUENTIALID()`.
- La tabla `user_tokens` de la propuesta no se crea (no hay invitaciones ni recuperación por correo).

## Decisiones pendientes

- Instancia de SQL Server 2022 para desarrollo y pruebas (Sistemas).
- Edición e intercalación de SQL Server.
- Política de retención de documentos y aviso de privacidad (área legal).

## Próximos pasos

1. Segunda parte de la Fase 2: vacantes, compartición, transferencias y auditoría en pantalla.
2. Validar contra SQL Server en cuanto exista una instancia.
3. Fase 3: almacenamiento documental.
