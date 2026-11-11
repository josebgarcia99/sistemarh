# Estado del proyecto

Última actualización: 11 de noviembre de 2026.

## Fase actual

**Fases 2 (Seguridad y usuarios) y 3 (Almacenamiento documental): construidas y probadas sin SQL Server; pendientes de validar contra SQL Server 2022, Docker y ClamAV reales.**

Ninguna de las dos se declara cerrada hasta ejecutar los scripts y las pruebas en un entorno real (ver "No verificado todavía"). La Fase 1 (fundamentos) está terminada.

**Fase 4 (Inteligencia documental): en curso.** Se construye en tres partes: (1) clave maestra, cifrado de documentos sensibles y configuración de IA; (2) perfiles de puesto y prompts; (3) procesamiento de CV con Excel y ZIP. La primera parte está construida.

## Funcionalidades terminadas

| Elemento | Detalle |
| --- | --- |
| Estructura del monorepositorio | `apps/api`, `apps/worker`, `apps/web`, `database`, `infrastructure`, `docs`, `scripts` |
| API base | Configuración por entorno, rutas `/api/v1`, formato único de error, identificador de correlación, logs JSON con filtro de secretos, rutas de salud |
| Usuario maestro | Comando `python -m app.cli create-admin`; solo funciona si no hay ningún administrador |
| Inicio y cierre de sesión | Sesión en el servidor, cookie `HttpOnly`, token CSRF, caducidad a 30 minutos sin actividad y a 12 horas en total |
| Bloqueo por intentos | 5 intentos fallidos bloquean la cuenta 15 minutos; el mensaje no revela si el correo existe |
| Administración de usuarios | Alta con correo, nombre completo, contraseña y rol; edición; restablecer contraseña; baja y reactivación. Sin envío de correos |
| Reglas de protección | Nadie se da de baja ni se quita el rol a sí mismo; siempre queda un administrador activo; la baja y el restablecimiento cierran las sesiones del usuario |
| Vacantes | Alta, edición y estados (borrador, abierta, pausada, cerrada, cancelada, archivada) con transiciones validadas. Nacen privadas y con su creador como responsable |
| Edición simultánea | Cada vacante lleva un número de versión; si dos personas la editan a la vez, la segunda recibe un aviso de conflicto y no pisa el cambio |
| Compartición | Acceso de lectura o de colaboración por persona; cambiar el tipo de acceso; revocar. Compartir no cambia al responsable |
| Documentos sensibles | Permiso adicional, por persona y vacante, para psicometría y estudios socioeconómicos. Se revoca junto con el acceso. Todavía no hay documentos: el permiso queda listo para la Fase 3 |
| Transferencia individual | Solo el administrador; con motivo; opción de dejar al responsable anterior como colaborador; queda en el historial de responsables |
| Baja con transferencia | El administrador da de baja a un reclutador y pasa todas sus vacantes a otra persona. Vista previa obligatoria, una sola transacción, y repetir la confirmación no duplica la operación |
| Auditoría | Sesiones, cambios de usuarios, vacantes, accesos y transferencias. También **todo acceso denegado**, incluso cuando la respuesta es "no encontrado" para no revelar que la vacante existe. Nunca guarda contraseñas |
| Denegación por omisión | Una prueba recorre todas las rutas de la API y verifica que solo tres responden sin sesión |
| Almacenamiento de documentos | Cada documento se guarda en el disco privado del servidor con nombre UUID; SQL Server registra qué es, de qué vacante, su tamaño, su SHA-256 y su estado. Ninguna respuesta ni error muestra rutas físicas |
| Validación de archivos | PDF, DOCX, DOC, JPG y PNG hasta 20 MB. Se comprueba el tipo real por contenido; se rechazan archivos disfrazados, vacíos, dañados y documentos de Word con macros |
| Antivirus local | Cliente de ClamAV (`clamd`). Si está activado y no responde, la carga se rechaza. Los documentos nunca se envían a servicios externos |
| Escritura recuperable | Estados `RECIBIENDO`, `CONFIRMADO`, `RECHAZADO`, `FALLIDO` y `ELIMINADO`. Solo se responde "guardado" después de sincronizar a disco, mover el archivo y confirmar el registro |
| Descarga autorizada | Solo por la API; el permiso se evalúa en cada descarga, así que revocar un acceso o transferir la vacante bloquea lo ya cargado. Cada descarga queda auditada |
| Clave maestra | Clave AES-256 en un archivo del servidor, fuera de SQL Server y del repositorio; comando para crearla. Obligatoria en producción |
| Documentos sensibles | Psicometría y estudios socioeconómicos se guardan cifrados archivo por archivo y se descifran al descargarlos. El permiso adicional por persona se aplica al cargar, listar y descargar. Sin clave maestra no se aceptan |
| Duplicados | Se detectan por SHA-256 dentro de la vacante y se avisa; cada documento conserva su propio archivo |
| Eliminación controlada | Solo el administrador y con motivo. Borra el archivo, conserva los metadatos y queda auditada |
| Conciliación | Comando y ruta de administrador que cierran cargas interrumpidas, mandan a cuarentena archivos sin registro, reportan registros sin archivo y verifican hashes |
| Respaldos | Comandos para generar el manifiesto de documentos y para verificar una copia o una restauración contra él |
| Configuración de IA | Pantalla de administrador para registrar, sustituir y revocar las API keys de Anthropic y OpenAI (cifradas con la clave maestra y nunca devueltas), probar la conexión, habilitar proveedores, fijar un límite mensual y asignar un modelo a cada una de las ocho operaciones. También admite claves inyectadas por Sistemas como variables de entorno |
| Registro de modelos | La lista de modelos sale de lo que informa cada proveedor al probar la conexión; no hay identificadores de modelos en el código |
| Base de datos | Migraciones `0001` (identidad y auditoría), `0002` (vacantes y transferencias), `0003` (documentos), `0004` (cifrado de documentos) y `0005` (configuración de IA): 15 tablas en los esquemas `auth`, `vacancy`, `files`, `ai` y `ops` |
| Scripts para Sistemas | `database/sqlserver/`: instalación completa, actualizaciones entre versiones consecutivas (de `0001` a `0005`), reversión y plantilla de permisos del usuario de la aplicación |
| Pantallas | Inicio de sesión, Inicio, Vacantes (lista, alta, detalle, compartir, documentos, historial, transferir), Usuarios, Bajas (baja con transferencia), Configuración de IA y Auditoría. El menú cambia según el rol |
| Worker Celery | Configuración segura y tarea `system.ping` |
| Reglas entre módulos | 7 contratos de `import-linter`: capas por módulo y dominios independientes |

## Pruebas ejecutadas

Ejecutadas el 11 de noviembre de 2026 en el entorno de construcción (Linux, Python 3.13, Node.js 22):

| Prueba | Resultado |
| --- | --- |
| API: `pytest` | 207 pruebas, todas pasan |
| Worker: `pytest` | 4 pruebas, todas pasan |
| `ruff check` y `lint-imports` | Sin errores; 9 contratos cumplidos |
| Frontend: `tsc --noEmit`, `eslint` | Sin errores |
| Frontend: `vitest` | 50 pruebas, todas pasan |
| Frontend: `next build` | Compila |
| Recorrido en navegador real, identidad | 10 pasos: redirección sin sesión, credenciales erróneas, inicio de sesión, alta de usuario, restablecer contraseña, recarga, cierre de sesión, contraseña anterior rechazada, reclutador sin acceso a Usuarios y respuesta 403 de la API |
| Recorrido en navegador real, vacantes | 11 pasos: alta de dos reclutadores, alta de dos vacantes, cambio de estado, compartir en lectura, la otra persona solo ve la compartida y no puede editarla, la API le niega cambiar el estado, transferencia individual, baja con transferencia, auditoría con el acceso denegado, la persona dada de baja ya no entra y el receptor queda como responsable |
| Recorrido en navegador real, configuración de IA | 8 pasos con proveedores simulados: registrar una clave, clave rechazada, sustituirla, conexión correcta, habilitar con límite, asignar un modelo, comprobar que la clave no aparece en la página ni en ninguna respuesta, revocar, y auditoría con solo la terminación |
| Recorrido en navegador real, documento sensible | 3 pasos: carga de un archivo de psicometría sintético de 12 MB, comprobación de que en el disco está cifrado y descarga idéntica al original |
| Recorrido en navegador real, documentos | 11 pasos: carga de un PDF, aviso de duplicado, rechazo de un ejecutable disfrazado y de un Word con macros, carga de 12 MB a través del frontend, descarga idéntica al original (SHA-256), descarga negada a otra persona (404) y sin sesión (401), eliminación con motivo y auditoría de todo lo anterior |
| Migraciones | Generan T-SQL sin conectarse; una prueba comprueba que definen las mismas columnas que el modelo, que no usan `IDENTITY_INSERT` y que ninguna columna usa tipos obsoletos |

Comprobaciones de almacenamiento de la sección 32.4, con su estado:

| Comprobación | Estado |
| --- | --- |
| Carga de CV | Probada |
| Reinicio de aplicación | Probada: una instancia nueva sobre la misma carpeta encuentra los archivos |
| Persistencia tras reinicio de Docker | **No probada**: no hay Docker en el entorno de construcción |
| Recuperación de documento, descarga autorizada y denegada | Probadas |
| Documento duplicado | Probada |
| Fallo durante escritura y recuperación | Probadas simulando el fallo del disco y una carga a medias |
| Respaldo y restauración | Probados con una copia local de los archivos y el manifiesto. **No probados** con respaldos reales de SQL Server |
| Verificación SHA-256 | Probada: detecta un archivo alterado con el mismo tamaño |
| Consistencia entre SQL Server y archivos | Probada sobre el motor de pruebas |
| Eliminación autorizada y controlada | Probada |

Pruebas de seguridad de la sección 32.3 que ya existen con nombre propio: 1 (vacantes privadas), 2 (compartir permite solo lo autorizado), 3 (revocar bloquea), 4 (cambiar el UUID no da acceso), 5 (un usuario desactivado pierde sus sesiones), 6 (el administrador transfiere), 7 (la transferencia no pierde nada, ahora también con documentos), 8 (permiso adicional para sensibles, con documentos sintéticos) y 9 (las API keys no aparecen en respuestas, logs ni auditoría). La 10 depende de fases posteriores.

### Cómo se probó sin SQL Server

No hay todavía una instancia de SQL Server de pruebas. Por eso:

- Todas las pruebas de la API ejecutan **los repositorios reales de SQLAlchemy**, los mismos que usará producción, sobre un **motor SQLite en memoria que solo existe dentro de las pruebas** (`app/tests/support/sql_memory.py`). Esto detecta errores de reglas, de mapeo y de consultas.
- Ese motor **no sustituye a SQL Server** y no valida nada propio de él: tipos, intercalación, bloqueos, paginación, índices filtrados ni concurrencia real.
- La aplicación en ejecución sigue rechazando cualquier motor que no sea SQL Server (`validate_database_url`). SQLite no puede usarse fuera de las pruebas.
- Los recorridos en navegador usaron la API real con ese mismo motor en memoria, atendiendo una petición a la vez.
- Antes se usaban repositorios de prueba escritos a mano; se retiraron porque duplicaban la lógica y podían comportarse distinto que los reales.

## No verificado todavía

- **Todo lo que toca SQL Server de verdad:** ejecutar `instalacion_completa.sql` y `actualizacion_0001_a_0002.sql`, la plantilla de permisos, crear el usuario maestro con el comando, iniciar sesión contra la base, la paginación `OFFSET/FETCH`, la intercalación en las búsquedas, los índices únicos filtrados, la restricción `ISJSON` y dos ediciones simultáneas reales de una vacante.
- **La atomicidad de la baja con transferencia en SQL Server.** La prueba de "si falla a la mitad no cambia nada" pasa sobre el motor en memoria; falta repetirla en SQL Server.
- **Anthropic y OpenAI reales.** La aplicación nunca se ha conectado a ningún proveedor de IA: todas las pruebas usan proveedores simulados y claves ficticias. La forma de la llamada se tomó de la documentación pública de cada proveedor.
- **ClamAV real.** El cliente del antivirus se probó contra un `clamd` simulado que habla el mismo protocolo; no contra ClamAV.
- **Almacenamiento en Docker.** No se ha comprobado el montaje de la carpeta del servidor ni que los documentos sobrevivan a recrear los contenedores.
- **Carga interrumpida por el navegador.** El caso está programado (la carga queda como fallida), pero no tiene prueba automática; sí la tienen el fallo del disco y la recuperación por conciliación.
- **Cargas grandes detrás del proxy de producción.** Se probó una carga de 12 MB a través del servidor de desarrollo de Next.js; el proxy inverso real debe permitir al menos 20 MB.
- **Las restricciones `CHECK` de `files.file_assets`** solo existen en SQL Server; el motor de pruebas no las aplica.
- **Redis y worker en ejecución.**
- **Imágenes Docker.** No se han construido. Falta comprobar la instalación de ODBC Driver 18 dentro de la imagen.
- **Python 3.12.** Las pruebas corrieron en 3.13; la imagen Docker usa 3.12.
- **Windows.** Nada se ha probado en Windows.
- **Proxy inverso.** La IP que se audita es la de la conexión directa; detrás del proxy habrá que tomarla de la cabecera que este envíe.

## Diferencias frente a la arquitectura aprobada

| Aprobado | Construido | Motivo |
| --- | --- | --- |
| Módulo `vacancy_sharing` separado | La compartición vive dentro del módulo `vacancies` | El acceso a una vacante y sus miembros se deciden juntos; separarlos obligaba a dependencias cruzadas |
| Tabla `vacancy_transfer_items` | No existe. Cada vacante movida queda en `vacancy_ownership_history`; en una baja con transferencia lleva el `transfer_id` de la operación, y `vacancy_transfers` guarda los totales. Las transferencias individuales no crean fila en `vacancy_transfers` | Evita guardar dos veces el mismo dato |
| `ROWVERSION` para la edición simultánea | Columna entera `version` que la aplicación compara y aumenta | Se puede probar sin SQL Server y viaja sin conversión hasta la pantalla |
| Convocatorias (`recruitment_campaigns`) en la Fase 2 | Se construyen en la Fase 5, junto con las postulaciones | No tienen uso hasta que existan candidatos |
| Pruebas con repositorios de prueba | Pruebas con los repositorios reales sobre un motor en memoria | Ver "Cómo se probó sin SQL Server" |
| Tipos de texto largo | `NVARCHAR(MAX)` en todas las columnas largas | `NTEXT` está obsoleto en SQL Server |
| Cifrado por archivo de documentos sensibles en la Fase 3 (decisión 8) | Se construyó al inicio de la Fase 4. Con clave maestra, psicometría y estudios socioeconómicos ya se pueden cargar | Necesitaba la clave maestra |
| Tabla `file_versions` | No se crea todavía | No hay documentos versionados hasta los perfiles de puesto (Fase 4) |
| Conciliación nocturna automática | Existe como comando y como ruta de administrador; no se ejecuta sola | Falta decidir con Sistemas si se programa con `cron` o con el worker |
| Tablas `ai_budgets` y `ai_executions` en la primera parte de la Fase 4 | El límite mensual vive en `ai.providers`; el registro de consumo se crea con el procesamiento de CV | No hay consumo que registrar hasta que se procesen documentos |
| Carga de archivos como formulario | El archivo viaja como cuerpo de la petición | Permite escribirlo directo a la zona temporal y cortar al superar el límite, sin copias intermedias |

## Funcionalidades pendientes

De la Fase 2, para después de tener SQL Server:

- Validación completa contra SQL Server 2022.
- Row-Level Security como segunda barrera (decisión 11).
- Pruebas Playwright dentro del repositorio (hoy el recorrido se hace con un script externo).

De la Fase 3:

- Validación con SQL Server, Docker y ClamAV reales.
- Rotación de la clave maestra (cambiarla y volver a cifrar lo existente).
- Programar la conciliación nocturna.
- Pantalla de administración del almacenamiento y vista previa de PDF.

Después, Fases 4 a 8 (ver [`roadmap.md`](roadmap.md)).

## Documentos de `docs/` aún no creados

`security/modelo_amenazas.md`, `api/contratos_api.md` (se genera desde OpenAPI), `manuals/manual_administrador.md` y `manuals/manual_reclutador.md`.

## Problemas conocidos

- Los logs de acceso de Uvicorn no salen en JSON; solo los de la aplicación.
- `starlette` avisa de que `httpx` quedará obsoleto para pruebas en favor de `httpx2`. No afecta hoy.
- `npm audit` reporta avisos de severidad moderada en dependencias de desarrollo del frontend. Pendiente de revisar uno por uno.
- `apps/api/requirements.lock` incluye las dependencias de desarrollo. Se separa en dos archivos antes de producción.
- La tabla de auditoría depende de que Sistemas aplique `permisos_usuario_aplicacion.sql`; la migración no lo hace porque no conoce el usuario de la aplicación.
- En la pantalla de Auditoría, el detalle muestra identificadores internos de usuarios y vacantes en lugar de nombres.
- La búsqueda de vacantes consulta la API con cada letra que se escribe.
- Las pantallas de inicio de sesión, Usuarios, Bajas y Auditoría se construyeron directamente con el sistema visual aprobado, sin maqueta previa en el lienzo.
- La lista de vacantes no muestra el número de posiciones; está en el detalle.
- Con seis secciones en el menú del administrador, el nombre del usuario y el botón de cerrar sesión bajan a una segunda línea.
- El límite de gasto mensual se guarda, pero todavía no se aplica: no hay consumo que medir.
- El botón para elegir archivo aparece en el idioma del navegador ("Choose File" si el navegador está en inglés).
- Si una descarga falla (por ejemplo, porque se revocó el acceso), el navegador muestra su propio aviso de descarga fallida en lugar de un mensaje de la aplicación.

## Cambios recientes

- 10 nov 2026: arquitectura aprobada con dos cambios: usuarios sin correo electrónico y entrega del código en GitHub.
- 10 nov 2026: Fase 1 construida y subida.
- 10 nov 2026: primera parte de la Fase 2 (identidad) construida.
- 10 nov 2026: el cierre de sesión hace una recarga completa de la página, porque el enrutador conservaba en memoria las pantallas visitadas.
- 11 nov 2026: segunda parte de la Fase 2: vacantes, compartición, transferencias, pantallas y scripts T-SQL.
- 11 nov 2026: los accesos denegados se auditan de forma central. Antes solo se registraban los de rutas de administrador; el recorrido en navegador mostró que los rechazos sobre vacantes no quedaban registrados.
- 11 nov 2026: las pruebas pasan a usar los repositorios reales sobre un motor en memoria.
- 11 nov 2026: guía y configuraciones para ejecutar en Visual Studio Code; `uvloop` solo fuera de Windows.
- 11 nov 2026: Fase 3 construida: almacenamiento, validación, antivirus, descarga autorizada, eliminación controlada, conciliación, manifiesto de respaldos y pantalla de documentos.
- 11 nov 2026: Fase 4, primera parte: clave maestra y cifrado por archivo de los documentos sensibles; su carga queda habilitada.
- 11 nov 2026: Fase 4, primera parte: configuración de IA (claves cifradas, prueba de conexión, registro de modelos y asignaciones).
- 11 nov 2026: el servidor de desarrollo de Next.js cortaba las cargas de más de 10 MB al reenviarlas a la API; se amplió el límite a 25 MB. Lo detectó el recorrido en navegador.

## Decisiones tomadas

- Decisiones 1 a 14 de la propuesta aprobadas con la opción recomendada, salvo la 1 (entrega por GitHub) y la 9 (sin correo).
- El usuario conserva la contraseña que le asigna el administrador; no hay cambio obligatorio en el primer ingreso.
- El servidor será Linux con contenedores; lo monta Sistemas.
- Se avanza de fase sin esperar revisión; los cambios se piden sobre la marcha.
- Los identificadores secuenciales se generan en la aplicación en lugar de usar `NEWSEQUENTIALID()`.
- La tabla `user_tokens` de la propuesta no se crea (no hay invitaciones ni recuperación por correo).

## Decisiones pendientes

- Instancia de SQL Server 2022 para desarrollo y pruebas (Sistemas).
- Edición e intercalación de SQL Server.
- Política de retención de documentos y aviso de privacidad (área legal).
- Antivirus en producción: ClamAV en el servidor u otra solución local (Sistemas).
- Dónde guardará y cómo respaldará Sistemas el archivo de la clave maestra (decisión 5).
- Cómo se programa la conciliación nocturna.

## Próximos pasos

1. Validar contra SQL Server en cuanto exista una instancia.
2. Fase 4, segunda parte: perfiles de puesto, generador de prompts y rúbricas.
3. Fase 4, tercera parte: procesamiento de CV, calificaciones, Excel y ZIP.
