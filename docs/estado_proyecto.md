# Estado del proyecto

Última actualización: 11 de noviembre de 2026.

## Fase actual

**Fases 2 (Seguridad y usuarios) y 3 (Almacenamiento documental): construidas y probadas sin SQL Server; pendientes de validar contra SQL Server 2022, Docker y ClamAV reales.**

Ninguna de las dos se declara cerrada hasta ejecutar los scripts y las pruebas en un entorno real (ver "No verificado todavía"). La Fase 1 (fundamentos) está terminada.

**Fase 4 (Inteligencia documental): construida y probada con proveedores de IA simulados; pendiente de validar con SQL Server, con el worker y Redis, y con un modelo real.** Incluye la clave maestra y el cifrado de documentos sensibles, la configuración de IA, los perfiles de puesto y prompts, la evaluación de CV por lotes con su Excel y sus ZIP, y las dos ayudas de IA: llenar el perfil desde un documento o texto y proponer una mejor redacción de los criterios. Quedó fuera de esta fase, y se indica más abajo: leer CV escaneados (OCR) y DOC antiguos, y la extracción estructurada del CV con el cálculo de permanencia laboral (secciones 12.2 y 12.3), que se construye con los expedientes de la Fase 5.

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
| Llamadas a los proveedores de IA | Una sola vía para llamar a Anthropic y a OpenAI: comprueba modelo, clave y autorización para enviar documentos, reintenta los fallos pasajeros y registra tokens, costo estimado, duración y resultado, sin guardar el contenido |
| Precios y límite mensual | El administrador captura el precio de cada modelo; con él se estima el costo y se detienen las llamadas al alcanzar el límite mensual del proveedor. Pantalla con el consumo del mes y botón para probar cada modelo |
| Perfil de puesto | Captura estructurada (objetivo, funciones, requisitos indispensables y deseables, etc.) por versiones: cada corrección crea una versión nueva y las anteriores no cambian |
| Prompt de evaluación | Diez capas y una rúbrica con escala 0 a 4, pesos y umbral. El borrador se genera del perfil con un criterio por requisito, sin inventar ninguno. Flujo borrador, en revisión, aprobado y archivado; una versión aprobada es inmutable y se duplica para cambiarla. Quien colabora edita y envía a revisión; solo el responsable o un administrador aprueba |
| Perfil desde un documento | En el perfil, «Llenar con IA desde un documento»: la IA lee un PDF o Word de tipo «Perfil de puesto» cargado en la vacante, o un texto pegado, y llena el formulario con lo que el documento dice, marcando los requisitos ambiguos. Es una propuesta: no se guarda hasta que la persona la revisa y pulsa guardar. La versión queda marcada como originada con IA y enlazada a su documento |
| Mejoras a la rúbrica con IA | En un borrador, «Proponer mejoras con IA» sugiere una redacción más clara de la descripción y los niveles 0 a 4 de cada criterio. El sistema descarta cualquier criterio que no exista ya en la rúbrica, así que la IA no puede añadir requisitos. Nada cambia hasta que la persona aplica la sugerencia y guarda |
| Lectura de CV | Se extrae el texto de PDF y de DOCX dentro del servidor. Un PDF escaneado, una imagen, un DOC antiguo, un PDF con contraseña o un archivo dañado quedan como «no evaluable» con su motivo; nunca como rechazo |
| Evaluación de CV por lotes | Desde la vacante, con el prompt aprobado vigente. Cada CV se guarda en cuanto se evalúa; si el proveedor falla, lo evaluado se conserva y el lote se reanuda. Antes de enviar el texto se ocultan correos y teléfonos. Un CV repetido dentro del lote no se evalúa dos veces |
| Puntuación y clasificación | La IA solo asigna un nivel de 0 a 4 por criterio; Python valida la respuesta contra la rúbrica y calcula el promedio ponderado (0 a 100). Con el umbral aprobado clasifica en `ACEPTADO_IA`, `RECHAZADO_IA` o `NO_EVALUABLE`. La calidad documental se informa aparte y no cambia la puntuación. Es una sugerencia inicial: no decide nada y no se sobrescribe |
| Excel y ZIP | Al terminar un lote se generan `Reporte_Evaluacion.xlsx`, `Aceptados.zip`, `Rechazados.zip` y, si los hay, `No_Evaluables.zip`, con los originales intactos, nombres numerados para que no choquen y un manifiesto con el SHA-256. Se guardan en el servidor, se descargan con el mismo permiso que los documentos y quedan auditados. El Excel neutraliza los textos que parecen fórmulas |
| Segundo plano | Estados `EN_COLA`, `PROCESANDO`, `COMPLETADO`, `COMPLETADO_CON_INCIDENCIAS`, `FALLIDO` y `CANCELADO`. El lote se detiene solo si se alcanza el límite de gasto, si falta el modelo o si el proveedor falla tres veces seguidas; se puede cancelar, reintentar y reanudar. Dos procesos no atienden el mismo lote |
| Base de datos | Migraciones `0001` (identidad y auditoría), `0002` (vacantes y transferencias), `0003` (documentos), `0004` (cifrado de documentos), `0005` (configuración de IA), `0006` (perfiles y prompts), `0007` (consumo de IA) y `0008` (lotes de CV): 21 tablas en los esquemas `auth`, `vacancy`, `files`, `ai` y `ops` |
| Scripts para Sistemas | `database/sqlserver/`: instalación completa, actualizaciones entre versiones consecutivas (de `0001` a `0008`), reversión y plantilla de permisos del usuario de la aplicación |
| Pantallas | Inicio de sesión, Inicio, Vacantes (lista, alta, detalle, compartir, documentos, perfil, prompt y evaluación de CV, historial, transferir), Usuarios, Bajas (baja con transferencia), Configuración de IA y Auditoría. El menú cambia según el rol |
| Worker Celery | Configuración segura, tarea `system.ping` y tarea `cv.process_batch`, que procesa un lote de CV y, al arrancar, vuelve a encolar los lotes que quedaron a medias |
| Reglas entre módulos | 10 contratos de `import-linter`: capas por módulo y dominios independientes |

## Pruebas ejecutadas

Ejecutadas el 11 de noviembre de 2026 en el entorno de construcción (Linux, Python 3.13, Node.js 22):

| Prueba | Resultado |
| --- | --- |
| API: `pytest` | 269 pruebas, todas pasan |
| Worker: `pytest` | 5 pruebas, todas pasan |
| `ruff check` y `lint-imports` | Sin errores; 10 contratos cumplidos |
| Frontend: `tsc --noEmit`, `eslint` | Sin errores |
| Frontend: `vitest` | 68 pruebas, todas pasan |
| Frontend: `next build` | Compila |
| Recorrido en navegador real, identidad | 10 pasos: redirección sin sesión, credenciales erróneas, inicio de sesión, alta de usuario, restablecer contraseña, recarga, cierre de sesión, contraseña anterior rechazada, reclutador sin acceso a Usuarios y respuesta 403 de la API |
| Recorrido en navegador real, vacantes | 11 pasos: alta de dos reclutadores, alta de dos vacantes, cambio de estado, compartir en lectura, la otra persona solo ve la compartida y no puede editarla, la API le niega cambiar el estado, transferencia individual, baja con transferencia, auditoría con el acceso denegado, la persona dada de baja ya no entra y el receptor queda como responsable |
| Recorrido en navegador real, evaluación de CV | 9 pasos sobre el modo demostración, con CV ficticios y un proveedor simulado: la pestaña muestra el prompt aprobado y los CV sin evaluar; el lote evalúa 4 CV y deja uno como no evaluable; el detalle muestra niveles, evidencia y motivo; se descargan el Excel y los ZIP, que suman los 4 originales con su manifiesto; se repite la evaluación y el lote anterior se conserva; los archivos generados no se mezclan con los documentos; con acceso de lectura se consulta y se descarga sin poder operar; auditoría y consumo lo registran; en móvil no hay desbordamiento |
| Recorrido en navegador real, ayudas de IA | 5 pasos sobre el modo demostración, con un proveedor simulado: la IA llena el formulario del perfil desde un Word y no guarda nada; la persona lo guarda como versión 1; la IA propone redacción para los tres criterios con sus avisos; al aplicar y guardar siguen siendo tres criterios; un texto demasiado corto se rechaza con su motivo |
| Recorrido en navegador real, consumo de IA | 4 pasos sobre el modo demostración: con límite y sin precio la llamada se rechaza; con precio el modelo responde y se estima el costo; el consumo aparece en la tabla del mes; al alcanzar el límite mensual las llamadas se detienen |
| Recorrido en navegador real, perfil y prompt | 7 pasos sobre el modo demostración: el perfil exige objetivo, se guarda como versión 1, el borrador sale con un criterio por requisito, editar actualiza la rúbrica, revisión y aprobación, duplicar crea la versión 2, y con acceso de lectura solo se consulta |
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
- **Las ayudas de IA con un modelo real.** La lectura del perfil y la propuesta de criterios se probaron con respuestas programadas. Falta ver qué tan fiel es un modelo real al documento y si respeta el formato.
- **La evaluación de CV con un modelo real.** Todo se probó con un proveedor simulado que devuelve respuestas programadas. No se sabe todavía qué tan bien sigue un modelo real el formato pedido ni qué calidad tienen sus niveles y evidencias; eso se mide cuando haya claves, con CV sintéticos primero.
- **El worker y la cola.** La tarea `cv.process_batch` está registrada y su lógica se probó ejecutándola en el momento; nunca ha corrido dentro de un worker de Celery con Redis. Tampoco se probó la reanudación automática al arrancar el worker.
- **Dos procesos sobre el mismo lote en SQL Server.** La reserva del lote se probó sobre el motor en memoria; falta comprobar la sentencia con bloqueos reales.
- **Lectura de PDF reales.** La extracción de texto se probó con PDF y DOCX sintéticos. Los PDF reales (columnas, tablas, fuentes incrustadas) pueden dar texto desordenado.
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
| Tabla `ai_budgets` | No existe: el límite mensual vive en `ai.providers` y el consumo en `ai.executions` | Un límite por proveedor es un solo dato |
| Generador de prompts con IA | El borrador lo genera el sistema a partir del perfil, con un criterio por requisito y sin IA. La IA interviene después y solo para mejorar la redacción de los criterios que ya existen | Garantiza que el prompt no contenga requisitos que no estén en el perfil (sección 11.3) y que el flujo funcione aunque no haya proveedor configurado |
| Tablas `prompt_version_layers` y `rubric_versions` | Las capas van en una columna JSON de `ai.prompt_versions` y la rúbrica forma parte de la versión del prompt (`ai.rubric_criteria`) | Son diez capas fijas y siempre se leen juntas; un prompt y su rúbrica se aprueban como una sola cosa |
| Tablas `cv_processing_batches`, `cv_documents`, `cv_evaluations` y `cv_evaluation_scores` | Dos tablas: `ai.cv_batches` y `ai.cv_batch_items`. El resultado de cada CV (niveles, evidencias, justificaciones) va en una columna JSON del CV del lote | Hasta la Fase 5 no existen candidatos ni postulaciones a los que enlazar una evaluación; ahí se decide si los niveles pasan a tabla propia |
| Un estado por cada uno de los 15 pasos de la sección 12.1 | Cada CV guarda el último paso completado (`RECIBIDO`, `TEXTO_EXTRAIDO`, `ANALIZADO`, `CALIFICADO`), su estado y, si falló, el código del error | Recibir, validar, guardar y calcular el hash ya tienen sus estados en `files.file_assets`; los archivos generados son del lote, no del CV |
| OCR y conversión de DOC | No construidos: esos CV quedan como «no evaluable» con el motivo | Requieren programas adicionales en el servidor (Tesseract, LibreOffice) que hay que acordar con Sistemas |
| Ocultar los datos de contacto antes de enviar el CV (decisión 13) | Se ocultan correos y teléfonos. El nombre y la dirección no | No se pueden reconocer de forma fiable sin otro modelo; se reevalúa con la extracción estructurada |
| Extracción estructurada del CV y permanencia laboral (12.2 y 12.3) en la Fase 4 | Pasan a la Fase 5 | Su resultado alimenta el expediente del candidato, que aún no existe; hacerlo ahora duplicaría el costo por CV sin tener dónde mostrarlo |
| Procesamiento en el worker | En producción y en contenedores lo hace el worker (Celery). Sin Redis configurado, lo hace un hilo de la propia API; en las pruebas y en el modo demostración se ejecuta en el momento | Permite trabajar en un equipo sin Redis. El estado vive siempre en SQL Server |
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
- En el límite mensual y en los precios, un número con más decimales de los admitidos da el aviso genérico «Revisa los campos indicados».
- El costo es una estimación con el precio capturado; no se concilia con la factura del proveedor.
- El perfil y el prompt se abren dentro de la pantalla de Vacantes: no tienen dirección propia, así que al recargar la página se vuelve a la lista.
- Una versión de perfil anterior se ve en la lista de versiones, pero no se puede abrir para leer su contenido.
- La propuesta de la IA para el perfil sustituye lo que haya en el formulario; no hay vista de comparación campo por campo.
- Las exportaciones de un lote que se reintenta se vuelven a generar; las anteriores se conservan en el servidor y en `files.file_assets`, pero la pantalla solo enlaza las más recientes.
- En el Excel, el nombre del criterio no aparece si la versión del prompt se eliminara; hoy las versiones no se eliminan.
- El resultado de un CV muestra el código del criterio (C1, C2…) y no su nombre; el nombre sí está en el Excel.
- Un lote admite como máximo 500 CV.
- Si un CV se elimina después de evaluarlo, sigue en los resultados como «CV eliminado» y deja de incluirse en los ZIP nuevos.
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
- 11 nov 2026: modo demostración (`scripts/demo.py`) para ver las pantallas sin SQL Server: datos en memoria que se borran al cerrar y proveedores de IA simulados. No sustituye a SQL Server.
- 11 nov 2026: Fase 4, segunda parte: perfiles de puesto por versiones y prompts de evaluación con rúbrica y flujo de aprobación.
- 11 nov 2026: Fase 4, tercera parte (inicio): llamadas a los proveedores con reintentos, registro de consumo, precios por modelo y límite mensual.
- 11 nov 2026: Fase 4, tercera parte: evaluación de CV por lotes, puntuación en Python, clasificación, Excel y ZIP, tarea del worker y pestaña «Evaluación de CV». El modo demostración trae una vacante lista para evaluar.
- 11 nov 2026: Fase 4, cierre: llenar el perfil con IA desde un documento o texto y proponer mejoras a los criterios con IA.
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
2. Diseñar las pantallas de la Fase 5.
3. Fase 5: expedientes y postulaciones a partir de los CV evaluados (con la extracción estructurada y la permanencia laboral), etapas, bancos de preguntas y llamadas.
4. Acordar con Sistemas si el servidor tendrá OCR y conversión de DOC.
