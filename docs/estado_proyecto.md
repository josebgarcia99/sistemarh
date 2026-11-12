# Estado del proyecto

Última actualización: 12 de noviembre de 2026.

## Fase actual

**Fases 2 (Seguridad y usuarios) y 3 (Almacenamiento documental): construidas y probadas sin SQL Server; pendientes de validar contra SQL Server 2022, Docker y ClamAV reales.**

Ninguna de las dos se declara cerrada hasta ejecutar los scripts y las pruebas en un entorno real (ver "No verificado todavía"). La Fase 1 (fundamentos) está terminada.

**Fase 4 (Inteligencia documental): construida y probada con proveedores de IA simulados; pendiente de validar con SQL Server, con el worker y Redis, y con un modelo real.** Incluye la clave maestra y el cifrado de documentos sensibles, la configuración de IA, los perfiles de puesto y prompts, la evaluación de CV por lotes con su Excel y sus ZIP, la lectura de CV escaneados con OCR y las ayudas de IA para el perfil y la rúbrica.

**Fase 5 (Reclutamiento operativo): construida completa y probada con datos sintéticos y proveedores simulados; pendiente de la misma validación.** Incluye expedientes y postulaciones, convocatorias, etapas configurables por versiones, movimientos con historial, bancos de preguntas, llamadas telefónicas y su análisis con IA, y la extracción estructurada del CV con la permanencia laboral. Su criterio de cierre ("un candidato rechazado por la IA avanza a llamada por decisión humana y queda registrado") pasa en las pruebas y en el recorrido en navegador.

**Fase 6 (Evaluaciones posteriores): construida completa y probada con datos sintéticos y proveedores simulados; pendiente de la misma validación.** Incluye psicometría, entrevistas con gerente, pruebas técnicas, estudios socioeconómicos con formularios configurables y digitalización, y la síntesis del expediente. Su criterio de cierre ("el expediente muestra todas las etapas con sus fuentes") pasa en las pruebas y en el recorrido en navegador.

**Fase 7 (Cierre e indicadores): construida completa y probada con datos sintéticos; pendiente de la misma validación.** Incluye los resultados finales de las postulaciones (contrataciones incluidas), el tablero de inicio, la pantalla de indicadores con filtros e históricos, el histórico de candidatos y los reportes en Excel guardados en el servidor. Su criterio de cierre («los tableros coinciden con los datos del flujo sintético») pasa en las pruebas y en el recorrido en navegador.

**Fase 8 (Calidad y preparación productiva): construido todo lo que no depende del servidor; NO cerrada.** Hecho: prueba del flujo completo, pruebas de seguridad transversales, revisión del esquema y de los scripts de SQL Server, respaldo de reportes, medición de rendimiento con volumen sintético, métricas y registro de accesos, cabeceras de seguridad, archivos de despliegue para producción, recorridos en navegador dentro del repositorio y toda la documentación obligatoria. **Falta lo que da por cerrada la fase y el proyecto:** ejecutar todo en SQL Server 2022 y en contenedores, con antivirus, cola de tareas y proveedores de IA reales, y probar una restauración completa. Eso requiere el servidor de Sistemas y las claves de IA.

**Cambios posteriores a la Fase 8 (12 de noviembre de 2026): construidos y probados con datos sintéticos; pendientes de la misma validación.** Google Gemini como tercer proveedor de IA; el perfil de puesto sigue el formato de la empresa «SGC.F15.RH. Perfil de puesto» y se llena al subir ese formato en Excel, sin IA; el estudio socioeconómico usa como plantilla el formato «SGC.F3.RH. Estudio socioeconómico». Además, en el estudio se adjuntan fotografías ahí mismo y la IA (el modelo que el administrador asigne a «Descripción de fotografías del estudio», por ejemplo uno de Gemini) propone una descripción de lo que se observa. También existe el puesto de analista de estudios socioeconómicos (rol nuevo). El esquema pasa a la versión `0016`.

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
| Validación de archivos | PDF, DOCX, DOC, JPG y PNG hasta 20 MB; además Excel (XLSX) solo en los tipos «Perfil de puesto» y «Estudio socioeconómico», que tienen un formato de la empresa. Se comprueba el tipo real por contenido; se rechazan archivos disfrazados, vacíos, dañados y documentos de Word o Excel con macros |
| Antivirus local | Cliente de ClamAV (`clamd`). Si está activado y no responde, la carga se rechaza. Los documentos nunca se envían a servicios externos |
| Escritura recuperable | Estados `RECIBIENDO`, `CONFIRMADO`, `RECHAZADO`, `FALLIDO` y `ELIMINADO`. Solo se responde "guardado" después de sincronizar a disco, mover el archivo y confirmar el registro |
| Descarga autorizada | Solo por la API; el permiso se evalúa en cada descarga, así que revocar un acceso o transferir la vacante bloquea lo ya cargado. Cada descarga queda auditada |
| Clave maestra | Clave AES-256 en un archivo del servidor, fuera de SQL Server y del repositorio; comando para crearla. Obligatoria en producción |
| Documentos sensibles | Psicometría y estudios socioeconómicos se guardan cifrados archivo por archivo y se descifran al descargarlos. El permiso adicional por persona se aplica al cargar, listar y descargar. Sin clave maestra no se aceptan |
| Duplicados | Se detectan por SHA-256 dentro de la vacante y se avisa; cada documento conserva su propio archivo |
| Eliminación controlada | Solo el administrador y con motivo. Borra el archivo, conserva los metadatos y queda auditada |
| Conciliación | Comando y ruta de administrador que cierran cargas interrumpidas, mandan a cuarentena archivos sin registro, reportan registros sin archivo y verifican hashes |
| Respaldos | Comandos para generar el manifiesto de documentos y para verificar una copia o una restauración contra él |
| Configuración de IA | Pantalla de administrador para registrar, sustituir y revocar las API keys de Anthropic, OpenAI y Google Gemini (cifradas con la clave maestra y nunca devueltas), probar la conexión, habilitar proveedores, fijar un límite mensual y asignar un modelo a cada una de las nueve operaciones. También admite claves inyectadas por Sistemas como variables de entorno |
| Registro de modelos | La lista de modelos sale de lo que informa cada proveedor al probar la conexión; no hay identificadores de modelos en el código |
| Llamadas a los proveedores de IA | Una sola vía para llamar a Anthropic y a OpenAI: comprueba modelo, clave y autorización para enviar documentos, reintenta los fallos pasajeros y registra tokens, costo estimado, duración y resultado, sin guardar el contenido |
| Precios y límite mensual | El administrador captura el precio de cada modelo; con él se estima el costo y se detienen las llamadas al alcanzar el límite mensual del proveedor. Pantalla con el consumo del mes y botón para probar cada modelo |
| Perfil de puesto | Captura con las secciones del formato de la empresa «SGC.F15.RH. Perfil de puesto»: identificación del puesto, propósito, alcance y relaciones, requisitos (formación académica, especialidad, experiencia, requisitos indispensables, conocimientos, habilidades blandas), funciones, actividades con su periodicidad y KPI con meta y fórmula. Por versiones: cada corrección crea una versión nueva y las anteriores no cambian |
| Perfil desde el formato en Excel | «Subir formato del perfil»: el sistema lee las celdas del formato de la empresa (por sus etiquetas, sin IA y sin necesitar ninguna clave) y llena el formulario. La edad y el género que pide el formato no se copian y se avisa a quien revisa. Es una propuesta: no se guarda hasta que la persona la revisa. La versión queda marcada como leída del formato y enlazada a su documento |
| Prompt de evaluación | Diez capas y una rúbrica con escala 0 a 4, pesos y umbral. El borrador se genera del perfil con un criterio por requisito, sin inventar ninguno. Flujo borrador, en revisión, aprobado y archivado; una versión aprobada es inmutable y se duplica para cambiarla. Quien colabora edita y envía a revisión; solo el responsable o un administrador aprueba |
| Perfil desde otro documento | Si el documento no es el formato en Excel (un PDF, un Word, otro Excel o un texto pegado), lo lee la IA: toma un documento de tipo «Perfil de puesto» cargado en la vacante, o un texto pegado, y llena el formulario con lo que el documento dice, marcando los requisitos ambiguos. Es una propuesta: no se guarda hasta que la persona la revisa y pulsa guardar. La versión queda marcada como originada con IA y enlazada a su documento |
| Mejoras a la rúbrica con IA | En un borrador, «Proponer mejoras con IA» sugiere una redacción más clara de la descripción y los niveles 0 a 4 de cada criterio. El sistema descarta cualquier criterio que no exista ya en la rúbrica, así que la IA no puede añadir requisitos. Nada cambia hasta que la persona aplica la sugerencia y guarda |
| Lectura de CV | Se extrae el texto de PDF y de DOCX dentro del servidor; los escaneados y las imágenes, con OCR. Un DOC antiguo, un PDF con contraseña o un archivo dañado quedan como «no evaluable» con su motivo; nunca como rechazo |
| Evaluación de CV por lotes | Desde la vacante, con el prompt aprobado vigente. Cada CV se guarda en cuanto se evalúa; si el proveedor falla, lo evaluado se conserva y el lote se reanuda. Antes de enviar el texto se ocultan correos y teléfonos. Un CV repetido dentro del lote no se evalúa dos veces |
| Puntuación y clasificación | La IA solo asigna un nivel de 0 a 4 por criterio; Python valida la respuesta contra la rúbrica y calcula el promedio ponderado (0 a 100). Con el umbral aprobado clasifica en `ACEPTADO_IA`, `RECHAZADO_IA` o `NO_EVALUABLE`. La calidad documental se informa aparte y no cambia la puntuación. Es una sugerencia inicial: no decide nada y no se sobrescribe |
| Excel y ZIP | Al terminar un lote se generan `Reporte_Evaluacion.xlsx`, `Aceptados.zip`, `Rechazados.zip` y, si los hay, `No_Evaluables.zip`, con los originales intactos, nombres numerados para que no choquen y un manifiesto con el SHA-256. Se guardan en el servidor, se descargan con el mismo permiso que los documentos y quedan auditados. El Excel neutraliza los textos que parecen fórmulas |
| Segundo plano | Estados `EN_COLA`, `PROCESANDO`, `COMPLETADO`, `COMPLETADO_CON_INCIDENCIAS`, `FALLIDO` y `CANCELADO`. El lote se detiene solo si se alcanza el límite de gasto, si falta el modelo o si el proveedor falla tres veces seguidas; se puede cancelar, reintentar y reanudar. Dos procesos no atienden el mismo lote |
| Lectura de CV escaneados (OCR) | Un PDF sin texto o una imagen (JPG, PNG) se lee con Tesseract, instalado en el propio servidor: nada sale hacia servicios externos. A la IA se le avisa de que el texto viene de un escaneo, para que no cuente los errores de lectura como faltas de la persona. Si Tesseract no está instalado, esos CV quedan como «no evaluable» |
| Datos ordenados del CV | Al evaluar un lote, y si el administrador asignó un modelo a «Extracción de CV», la IA ordena nombre, experiencia, estudios, habilidades, certificaciones y proyectos, sin completar fechas ni inferir atributos personales. El correo y el teléfono se toman del texto con reglas locales, sin IA. Si esta parte falla, el CV queda evaluado igualmente |
| Permanencia laboral | Calculada en Python: duración por empleo, promedio, mediana, tiempo total documentado sin contar dos veces los periodos simultáneos, traslapes y empleos sin fechas completas. Es información de apoyo, nunca un criterio de rechazo |
| Candidatos y postulaciones | Cada persona tiene un identificador global; cada participación en una convocatoria es una postulación independiente, con su CV, su evaluación inicial, su etapa, su historial y sus llamadas. Al terminar un lote, cada CV evaluado entra como postulación en «Revisión local RH» con la clasificación inicial de la IA; también se dan de alta a mano |
| Convocatorias | Periodos de reclutamiento de una vacante. Cerrar una la deja solo para consulta; abrir otra permite reutilizar la vacante sin alterar el pasado, y la misma persona puede volver a participar |
| Etapas configurables | Ocho etapas iniciales. El administrador las cambia desde «Etapas»; cada cambio es una versión nueva que usan las convocatorias que se abran después. Las abiertas conservan las suyas |
| Movimientos | Avanzar, regresar, omitir etapas, mover en grupo, desistimiento, descarte, cancelación, reactivación, incidencia y reprogramación. Todo queda en un historial que solo crece. Exigen motivo: regresar, omitir una etapa no opcional, cualquier baja o reactivación, y **avanzar a quien la IA no clasificó como aceptado** |
| Bancos de preguntas | Privados o compartidos, por versiones, con competencia y guía por pregunta. Se crean, editan, duplican, comparten y archivan. La IA propone preguntas a partir del perfil de una vacante y la persona elige cuáles añade |
| Llamadas telefónicas | Sobre una postulación y con un banco: respuestas, observaciones y preguntas no realizadas. Varias por postulación. Al cerrarla queda fija, y conserva la versión del banco con la que se hizo |
| Análisis de llamadas con IA | Resume evidencias, competencias exploradas, información que faltó, coincidencias y diferencias por aclarar con el CV, y preguntas de seguimiento. No evalúa tono ni sinceridad, no afirma que alguien mintió y no recomienda avanzar o descartar |
| Pruebas psicométricas | Instrumento, versión, proveedor, fecha, estado (los siete del documento maestro), documento, resultado documentado y observaciones. Marcarla como validada exige indicar qué profesional la interpretó. Es un dato sensible: exige el permiso adicional sobre la vacante y su documento se guarda cifrado. La IA resume lo que el reporte documenta; no diagnostica ni declara aptitud |
| Entrevistas con gerente | RH captura fecha, entrevistador, preguntas y respuestas, competencias observadas, retroalimentación, evidencias y observaciones. Marcarla como realizada exige la conclusión de quien entrevistó. La IA organiza y resume; no cambia la conclusión |
| Pruebas técnicas | Opcionales. Tipo, competencia, fecha, responsable, documento, resultado, evidencias, comentarios y rúbrica. Con la rúbrica completa, el sistema calcula la calificación (puntos obtenidos entre posibles) y, si hay mínimo aprobatorio, si lo alcanza. «No aplica» permite omitirla |
| Formularios del estudio socioeconómico | El administrador crea plantillas con secciones y campos de texto, fecha, número, opciones, casilla, documento, observación y tabla (filas con las mismas columnas), con obligatoriedad y rangos. Un campo puede marcarse como «solo captura manual»: la IA no lo llena. Por versiones: los estudios ya capturados conservan la suya. La plantilla inicial es el formato de la empresa «SGC.F3.RH. Estudio socioeconómico» (19 secciones). El dictamen, los niveles del reporte cuantitativo, el «score total» y la viabilidad que pide ese formato los anota quien aplicó el estudio: el sistema no los calcula, la IA no los llena y no entran en la síntesis ni en los reportes |
| Estudios socioeconómicos | Captura sobre una plantilla, con validación por tipo de campo. Es un dato sensible con el mismo permiso adicional. **No tiene puntuación de ningún tipo.** Cada dato lleva una marca de «verificado» que solo pone una persona |
| Digitalización | La IA lee un formulario escaneado (con OCR si hace falta) y propone el valor de cada campo, avisando de lo ilegible y de lo que falta. No guarda nada: lo que la persona acepta entra marcado como «leído por la IA» y sin verificar |
| Expediente por etapas | En el expediente, cada etapa del proceso muestra si está cubierta, es la actual, se omitió o está por venir, y las fuentes que tiene: CV y evaluación, llamadas, evaluaciones y documentos. Lo que exige un permiso que la persona no tiene aparece solo como existente |
| Fotografías del estudio descritas por la IA | En cada campo de documento del estudio: «Adjuntar foto o archivo» la carga sin salir del formulario (cifrada, como todo documento del estudio). Si es una imagen JPG o PNG, «Describir con IA» propone un texto con lo que se observa; la persona lo corrige y lo guarda junto a la foto. Queda marcado como propuesto por la IA hasta que alguien lo edita. Las descripciones guardadas entran en la síntesis del expediente y en el Excel de postulaciones (columna «Fotografías del estudio socioeconómico»), solo para quien tiene el permiso del estudio. La foto viaja reducida y sin metadatos. Requiere un modelo que acepte imágenes asignado a la operación «Descripción de fotografías del estudio» |
| Analista de estudios socioeconómicos | Rol `ANALISTA_ESTUDIOS`. Su inicio es una lista de trabajo con las personas en proceso de todas las vacantes y el estado de su estudio. Puede registrar y capturar el estudio, cargar y ver sus documentos y fotografías y usar las ayudas de IA del estudio. Todo lo demás le está cerrado por una lista de rutas permitidas (403 y auditoría). Los reclutadores y administradores conservan su acceso al estudio |
| Síntesis del expediente con IA | Ordena la información en hechos documentados, declaraciones, observaciones humanas, resultados técnicos, información pendiente y diferencias por aclarar. No produce puntuaciones, índices ni recomendaciones: el servidor descarta cualquier otro dato de la respuesta. La psicometría solo entra si está validada por un profesional y quien pide la síntesis tiene ese permiso; el contenido del estudio socioeconómico nunca entra |
| Resultados finales | Seis resultados (contratado, no contratado, desistió, no localizado, vacante cancelada, otro cierre); mientras no hay ninguno, la postulación está «en proceso». Los registra una persona con permiso de colaboración sobre la vacante: nunca el sistema ni la IA. Guardan fecha, responsable, motivo (obligatorio salvo en la contratación), observaciones y, en la contratación, fecha de incorporación. No se contrata a más personas que plazas tiene la vacante. Reabrir exige motivo y anula el resultado anterior sin borrarlo. Contratar a alguien que la IA no clasificó como aceptado queda anotado en la auditoría como decisión humana |
| Tablero de inicio | Para cada persona, sobre sus vacantes y las compartidas: vacantes propias y compartidas, procesos pendientes, candidatos en llamada, pruebas y entrevistas pendientes; y de los últimos 30 días, CV analizados, aceptados y rechazados por la IA, procesos cerrados y contrataciones, más la actividad reciente |
| Indicadores | Pantalla «Indicadores» con periodo y filtros por vacante, departamento, responsable, colaborador y estado: fotografía de hoy, totales del periodo, embudo por etapa con conversión, tiempo promedio por etapa, tiempo de cobertura, tabla por vacante e histórico por mes. Solo para administradores: carga de trabajo por responsable, uso y costo de IA y errores técnicos. Una contratación se cuenta una sola vez, a nombre del responsable de la vacante, aunque tenga colaboradores |
| Histórico de candidatos | Lista de postulaciones con todos los filtros de la sección 24.3: fechas (de carga, evaluación, movimiento o cierre), vacante, responsable, colaborador, departamento, estado, etapa, candidato, clasificación y calificación de la IA, modelo, versión del prompt, banco de preguntas y resultado final. Paginada |
| Reportes en Excel | De indicadores (varias hojas) y de postulaciones, con los filtros aplicados. Se guardan en el servidor con identificador, fecha, tamaño y SHA-256. Los textos capturados no pueden ejecutarse como fórmula. Un reporte solo se descarga mientras quien lo generó conserve acceso a todas las vacantes que contiene |
| Permisos de los reportes | Las cifras se calculan en cada consulta con los permisos que la persona tiene hoy: un administrador ve todo; los demás, sus vacantes y las compartidas. Vale igual para un histórico de años anteriores |
| Flujo completo probado | Una sola prueba recorre los 20 pasos de la sección 32.5, de la creación de usuarios a la transferencia final de la vacante, y comprueba que los documentos siguen disponibles y que los permisos cambian |
| Barrido de acceso directo | Una prueba recorre las 76 rutas con identificador pidiendo, como una persona sin acceso, recursos reales de otra: ninguna lectura entrega datos y ninguna escritura cambia nada. Las rutas nuevas entran solas |
| Cabeceras de seguridad | Todas las respuestas de la API y de las pantallas impiden enmarcar la aplicación, interpretar tipos y, en la API, guardar respuestas en cachés; HSTS en producción |
| Métricas y registro de accesos | Cada solicitud deja una línea estructurada con método, ruta, estado y duración (sin la consulta, que puede llevar nombres). `GET /system/metrics`, solo para administradores, muestra solicitudes, errores y duración por ruta |
| Versión del esquema en la comprobación de salud | `/health/ready` falla si la base no tiene la versión de esquema que espera la aplicación |
| Validaciones de integridad | `validaciones_integridad.sql`: 18 comprobaciones de solo lectura para ejecutar tras instalar, actualizar o restaurar |
| Respaldo de reportes | El manifiesto de respaldo y la comprobación del almacenamiento incluyen los Excel de reportes |
| Despliegue de producción | Compose de producción (proxy, pantallas, API, worker, cola y antivirus), configuración de nginx con HTTPS, variables de ejemplo por entorno e imagen con solo las dependencias de ejecución. Sin ejecutar |
| Documentación derivada del código | `scripts/generate_docs.py` genera los contratos de la API y el diagrama entidad-relación; una prueba falla si quedan desactualizados |
| Base de datos | Migraciones `0001` (identidad y auditoría), `0002` (vacantes y transferencias), `0003` (documentos), `0004` (cifrado de documentos), `0005` (configuración de IA), `0006` (perfiles y prompts), `0007` (consumo de IA), `0008` (lotes de CV), `0009` (reclutamiento operativo) `0010` (evaluaciones posteriores), `0011` (resultados finales y reportes) y `0012` (índices para reportes): 36 tablas en los esquemas `auth`, `vacancy`, `files`, `ai`, `recruitment` y `ops` |
| Scripts para Sistemas | `database/sqlserver/`: instalación completa, actualizaciones entre versiones consecutivas (de `0001` a `0012`), reversión, plantilla de permisos del usuario de la aplicación y validaciones de integridad |
| Pantallas | Inicio de sesión, Inicio, Vacantes (lista, alta, detalle, compartir, documentos, perfil, prompt y evaluación de CV, candidatos con expediente y llamadas, historial, transferir), Bancos de preguntas, Etapas, Formularios, Usuarios, Bajas (baja con transferencia), Configuración de IA y Auditoría. El menú cambia según el rol |
| Worker Celery | Configuración segura, tarea `system.ping` y tarea `cv.process_batch`, que procesa un lote de CV y, al arrancar, vuelve a encolar los lotes que quedaron a medias |
| Reglas entre módulos | 13 contratos de `import-linter`: capas por módulo y dominios independientes |

## Pruebas ejecutadas

Ejecutadas el 12 de noviembre de 2026 en el entorno de construcción (Linux, Python 3.13, Node.js 22):

| Prueba | Resultado |
| --- | --- |
| API: `pytest` | 374 pruebas, todas pasan |
| Worker: `pytest` | 5 pruebas, todas pasan |
| `ruff check` y `lint-imports` | Sin errores; 13 contratos cumplidos |
| Frontend: `tsc --noEmit`, `eslint` | Sin errores |
| Frontend: `vitest` | 102 pruebas, todas pasan |
| Frontend: `next build` | Compila |
| Recorrido en navegador real, identidad | 10 pasos: redirección sin sesión, credenciales erróneas, inicio de sesión, alta de usuario, restablecer contraseña, recarga, cierre de sesión, contraseña anterior rechazada, reclutador sin acceso a Usuarios y respuesta 403 de la API |
| Recorrido en navegador real, vacantes | 11 pasos: alta de dos reclutadores, alta de dos vacantes, cambio de estado, compartir en lectura, la otra persona solo ve la compartida y no puede editarla, la API le niega cambiar el estado, transferencia individual, baja con transferencia, auditoría con el acceso denegado, la persona dada de baja ya no entra y el receptor queda como responsable |
| Recorrido en navegador real, evaluación de CV | 9 pasos sobre el modo demostración, con CV ficticios y un proveedor simulado: la pestaña muestra el prompt aprobado y los CV sin evaluar; el lote evalúa 4 CV y deja uno como no evaluable; el detalle muestra niveles, evidencia y motivo; se descargan el Excel y los ZIP, que suman los 4 originales con su manifiesto; se repite la evaluación y el lote anterior se conserva; los archivos generados no se mezclan con los documentos; con acceso de lectura se consulta y se descarga sin poder operar; auditoría y consumo lo registran; en móvil no hay desbordamiento |
| Flujo completo (32.5) | `test_flujo_completo.py`: los 20 pasos en una prueba, con datos sintéticos e IA simulada. Pasa |
| Gemini y formatos de la empresa | `test_ai_gemini.py`, `test_perfil_formato.py` y `test_estudio_formato.py`: cliente de Gemini con respuestas simuladas, lectura del formato del perfil en Excel (con la distribución de celdas del formato real y datos inventados), Excel aceptado solo como perfil o estudio, plantilla del estudio, tablas y campos de captura manual. Recorrido en navegador `recorrido_formatos.py` (6 pasos). Pasan |
| Seguridad transversal | `test_seguridad.py`: barrido de las 76 rutas con identificador, rutas de administración, textos hostiles en búsquedas, CV con instrucciones ocultas, cabeceras, registro de accesos y métricas. Pasan |
| Revisión de SQL Server sin servidor | El modelo y las migraciones coinciden en columnas e índices; cadena de migraciones lineal y reversible; claves foráneas sin índice revisadas una a una; el script de validaciones solo lee y nombra columnas que existen. Pasan |
| Recorridos en navegador, los cinco, tras la Fase 8 | `python tests/e2e/run.py`: 40 pasos en cinco recorridos (ayudas de IA, evaluación de CV, reclutamiento, evaluaciones posteriores e indicadores), cada uno sobre un modo demostración recién arrancado y con las cabeceras de seguridad activas. Pasan |
| Medición de rendimiento | `scripts/medir_rendimiento.py` con 2 000, 20 000 y 50 000 postulaciones inventadas, en el motor en memoria. Resultados en `docs/testing/plan_pruebas.md` |
| Recorrido en navegador real, Fase 7 | 9 pasos sobre el modo demostración: el inicio muestra el tablero propio; una contratación queda con fecha de incorporación, responsable e historial, y la persona ya no se mueve de etapa; un desistimiento se reabre y el resultado anterior queda anulado, no borrado; el inicio pasa a mostrar 4 CV analizados, 2 procesos cerrados y 1 contratación; los indicadores de la reclutadora no traen los datos reservados al administrador; el histórico se filtra por resultado y el Excel descargado se abre y contiene esa única fila; el administrador ve la carga por responsable, el uso de IA y descarga el Excel de seis hojas; la segunda persona solo ve lo propio y lo compartido; en móvil, inicio e indicadores no se desbordan |
| Recorrido en navegador real, Fase 6 | 8 pasos sobre el modo demostración: la calificación de una prueba técnica la calcula el sistema con la rúbrica; la entrevista exige la conclusión humana y la IA solo organiza; validar una psicometría exige al profesional y la IA resume el documento cifrado; en el estudio la IA llena campos sin verificar y la persona marca lo verificado; el expediente muestra cada etapa con sus fuentes y la síntesis por tipo de fuente; sin el permiso adicional no se ven psicometría, estudio ni la síntesis que los incluye; el administrador guarda una versión nueva del formulario; en móvil no hay desbordamiento |
| Recorrido en navegador real, Fase 5 | 9 pasos sobre el modo demostración: los 4 CV evaluados entran como candidatos en revisión de RH con su nombre; un rechazado por la IA avanza a llamada solo con motivo; el expediente muestra historial, clasificación inicial intacta y experiencia con permanencia; llamada con banco, análisis de IA y cierre; reprogramación y desistimiento en el historial; banco nuevo con una pregunta propuesta por la IA; con lectura se consulta sin operar y no se ve un banco privado ajeno; el administrador guarda una versión nueva de etapas y la auditoría registra los movimientos; la convocatoria abierta conserva sus 8 etapas y en móvil no hay desbordamiento |
| OCR real | Tesseract 5.3 leyó un PDF escaneado y una imagen PNG sintéticos, y el lote los evaluó. Es la única integración externa de esta fase que se ejecutó de verdad |
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
- **Anthropic, OpenAI y Google Gemini reales.** La aplicación nunca se ha conectado a ningún proveedor de IA: todas las pruebas usan proveedores simulados y claves ficticias. La forma de la llamada se tomó de la documentación pública de cada proveedor.
- **El formato de perfil real en la aplicación.** El lector del formato «SGC.F15.RH» se comprobó con el archivo de ejemplo que entregaste (fuera del repositorio) y con libros generados en las pruebas con la misma distribución de celdas. No se ha probado con otros perfiles llenados por la empresa ni con archivos guardados desde Google Sheets o LibreOffice.
- **Descripción de fotografías con un modelo real.** La forma de enviar imágenes a Gemini se tomó de la documentación pública de Google consultada el 12 de noviembre de 2026; la de Anthropic y OpenAI, de su documentación conocida. Ninguna se ha ejecutado contra el servicio real, así que no se ha visto una descripción producida por un modelo de verdad ni se ha comprobado que el modelo respete las instrucciones.
- **Migraciones `0013` a `0016` en SQL Server.** Como el resto de los scripts, se generó sin conexión y no se ha ejecutado contra un SQL Server real.
- **Los resúmenes, la digitalización y la síntesis con un modelo real.** Probados con respuestas programadas. No se sabe todavía si un modelo real respeta siempre las prohibiciones (no diagnosticar, no recomendar, no puntuar); el servidor descarta lo que no cabe en el formato, pero el texto de un resumen puede contener una frase indebida. Hay que revisarlo con casos sintéticos antes de usarlo.
- **OCR con documentos reales.** Tesseract se probó con imágenes sintéticas de letra impresa y nítida. Con escaneos reales (torcidos, con sellos, en baja resolución o manuscritos) la lectura será peor; hay que medirla. Tampoco se ha construido la imagen Docker con Tesseract.
- **Extracción del CV y análisis de llamadas con un modelo real.** Probados con respuestas programadas.
- **Lo construido en la Fase 8 para producción no se ha ejecutado.** No hay Docker en el entorno de construcción: `docker-compose.prod.yml`, la configuración de nginx (HTTPS, límite de intentos, restricción de las métricas), la imagen con `requirements-prod.lock` y su comprobación de salud están escritos y revisados, no probados.
- **Las cabeceras de seguridad de las pantallas en producción.** Se probaron con el servidor de Next.js en los recorridos; no detrás del proxy.
- **`validaciones_integridad.sql`** se comprobó contra el modelo (sintaxis, tablas y columnas), no se ha ejecutado.
- **La comprobación de la versión del esquema** se probó con un motor en memoria, no con SQL Server.
- **La IP real del usuario detrás del proxy** (cabecera `X-Forwarded-For` y `FORWARDED_ALLOW_IPS`).
- **Carga con usuarios simultáneos.** La medición de rendimiento envía una solicitud a la vez.
- **Los reportes en SQL Server.** Las consultas de los tableros (subconsultas de vacantes visibles, uniones entre esquemas) y la carga inicial de resultados finales de la migración `0011` solo se han ejecutado sobre el motor en memoria o se generaron sin conexión. Falta ejecutarlas en SQL Server y medir su tiempo.
- **Los tableros con volumen real.** Las cifras se calculan en cada consulta leyendo las postulaciones y movimientos de las vacantes visibles. Con los datos sintéticos responde al instante; no se ha medido con miles de postulaciones.
- **El índice único de «un resultado vigente por postulación»** es un índice filtrado: se probó en el motor en memoria, no en SQL Server.
- **Zona horaria en el servidor.** Los periodos se calculan con la zona `America/Mexico_City` de la librería de Python (`tzdata`). No se ha comprobado dentro de la imagen Docker.
- **Concurrencia en SQL Server.** Dos personas moviendo a la misma candidata a la vez, y el índice único de correo de candidatos, solo se probaron sobre el motor en memoria.
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
| Ocultar los datos de contacto antes de enviar el CV (decisión 13) | Se ocultan correos y teléfonos. El nombre y la dirección no | No se pueden reconocer de forma fiable sin otro modelo; se reevalúa con la extracción estructurada |
| Procesamiento en el worker | En producción y en contenedores lo hace el worker (Celery). Sin Redis configurado, lo hace un hilo de la propia API; en las pruebas y en el modo demostración se ejecuta en el momento | Permite trabajar en un equipo sin Redis. El estado vive siempre en SQL Server |
| Tablas de etapas (`stage_definitions`, `stage_versions`, `application_stage_history`), de bancos (`questions`, `question_bank_versions`) y de llamadas (`call_sessions`, `call_answers`, `call_analyses`) | Nueve tablas en el esquema `recruitment`. Las preguntas de una versión de banco y las respuestas de una llamada van en columnas JSON; el análisis de una llamada va en la propia llamada y solo se conserva el más reciente | Se leen y se guardan siempre juntas. Una llamada apunta a la versión exacta del banco con la que se hizo |
| Resultado final de la postulación | El resultado final es el estado de la postulación (siete valores) más un registro en `recruitment.application_outcomes`. Los atajos de la Fase 5 (desistió, descartar, cancelar) se convirtieron en resultados finales | Evita tener dos conceptos para lo mismo |
| Tablas de indicadores o cifras precalculadas | No existen: cada tablero se calcula al consultarlo, a partir de las tablas operativas | Así no puede contradecir al expediente y respeta siempre los permisos de hoy. Si el volumen lo exige, se añaden resúmenes después |
| Reportes «por evaluación, por vacante, por reclutador y administrativos» (sección 30) como archivos distintos | Dos Excel: indicadores (hojas Resumen, Etapas, Vacantes, Reclutadores, Mensual e IA) y postulaciones. El de un lote de CV ya existía. Se acotan con los filtros | Los mismos datos, sin multiplicar formatos |
| Filtros de etapa, candidato, clasificación, calificación, modelo, prompt, banco y resultado en los tableros | Se aplican en el histórico de candidatos y en su Excel. Los tableros se filtran por periodo, vacante, departamento, responsable, colaborador y estado | En cifras agregadas esos filtros darían números difíciles de interpretar |
| Exportaciones a PDF y a Word (sección 30) | No construidas | No se han pedido; el Excel cubre los reportes |
| Prueba de carga con Locust (plan de pruebas) | Medición propia con volumen sintético, una solicitud a la vez | Una prueba de carga con usuarios simultáneos solo tiene sentido contra SQL Server |
| Recorridos completos «con Playwright» como pruebas del frontend | Cinco guiones de Playwright en `tests/e2e/`, en Python, que se ejecutan sobre el modo demostración | Necesitan la API y las pantallas arrancadas; no forman parte de `npm test` |
| Vistas SQL entre los scripts (25.5) | No hay vistas | Los reportes se calculan en la aplicación para aplicar los permisos |
| Los reportes en `files.file_assets` | Tienen su propio registro, `ops.report_exports`, porque no pertenecen a una sola vacante. La conciliación del almacenamiento los reconoce | La tabla de documentos exige una vacante |
| Conversión de DOC antiguos | No construida: esos CV quedan como «no evaluable» | Requiere LibreOffice en el servidor; no se ha pedido |
| Pantallas diseñadas antes de construirlas | Las de la Fase 5 se construyeron directamente con el sistema visual aprobado, sin maqueta previa | Se pidió la fase completa de una vez |
| Tablas separadas para psicometría, entrevistas, pruebas técnicas y estudios | Una sola tabla `recruitment.assessments` con el tipo y lo capturado en JSON, validado en Python según el tipo; más plantillas de formulario y síntesis: cuatro tablas en total | Los cuatro tipos comparten postulación, estado, fecha, documento, resumen de IA y control de edición simultánea |
| «Capacidades multimodales» para leer formularios y fotografías (21.2) | Los formularios se leen por su texto (con OCR). Las fotografías del estudio sí se envían al proveedor de IA, pero solo cuando una persona pulsa «Describir con IA» en una foto concreta (autorizado el 12 de noviembre de 2026). Se envían reducidas y sin metadatos (fecha, teléfono, coordenadas) | La instrucción a la IA es describir lo que se ve, sin inferir nivel socioeconómico, confiabilidad, moralidad, religión, salud ni idoneidad, y sin identificar ni describir personas. La respuesta solo conserva la descripción; es una propuesta que la persona revisa. No entra en la síntesis ni en los reportes |
| Acceso directo para gerentes (19) | No construido: RH captura las observaciones del gerente | El documento maestro lo deja como ampliación futura. El rol nuevo se añadiría sin cambiar las tablas |
| El estudio socioeconómico en la síntesis del expediente y en los reportes | Entran únicamente las descripciones guardadas junto a sus fotografías (a petición tuya, 12 de noviembre de 2026), y solo para quien tiene el permiso del estudio: la síntesis que las incluye queda oculta para los demás y la columna del Excel de postulaciones no se genera sin ese permiso. El resto del estudio (economía, salud, religión, dictamen, niveles, score, viabilidad) nunca entra | El documento maestro prohíbe combinar información socioeconómica en un índice de idoneidad. La síntesis no puntúa ni recomienda, y la instrucción a la IA le prohíbe sacar conclusiones sobre la persona a partir de las fotografías |
| Edad y género del formato de perfil (SGC.F15.RH) | No se copian al perfil; el sistema avisa cuando el formato los trae | El documento maestro prohíbe evaluar por características protegidas, y el perfil alimenta el prompt con el que se revisan los CV |
| Dictamen, niveles, «score total» y viabilidad del formato del estudio (SGC.F3.RH) | Se guardan como campos de captura manual: los anota quien aplicó el estudio. El sistema no los calcula, la IA no los llena y no entran en la síntesis ni en los reportes | El formato de la empresa los pide, pero el documento maestro prohíbe que el sistema construya una puntuación por condición económica o un índice de idoneidad. Queda pendiente de tu confirmación: si prefieres no registrarlos, se quitan de la plantilla |
| Lectura directa de un estudio lleno en Excel | No construida: el formato lleno lo transcribe la IA (como el escaneado) y la persona verifica | Solo se recibió el formato en blanco; sin un ejemplo lleno no se sabe en qué celda queda cada respuesta |
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

## Documentos de `docs/`

Están los veinte que exige la sección 36 del documento maestro; una prueba lo comprueba. Además: `deployment/despliegue_produccion.md`, `database/revision_sql_server.md` y `database/diagrama_entidad_relacion.md`.

## Problemas conocidos

- `starlette` avisa de que `httpx` quedará obsoleto para pruebas en favor de `httpx2`. No afecta hoy.
- `npm audit` reporta avisos de severidad moderada en dependencias de desarrollo del frontend. Pendiente de revisar uno por uno.
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
- En una evaluación, los documentos se eligen entre los ya cargados en la vacante con el tipo correspondiente; no se cargan desde el propio expediente.
- De cada evaluación solo se conserva el resumen de IA más reciente. Las síntesis del expediente sí se conservan todas, aunque la pantalla muestra la más reciente.
- Una casilla del estudio sin marcar no se guarda: no se distingue «no» de «sin dato».
- En el formulario del estudio, las opciones se escriben separadas por coma, así que una opción no puede contener comas.
- Con «Indicadores», el menú del administrador tiene diez entradas y ocupa dos líneas.
- El tablero del administrador sobre todo el histórico tarda en proporción a las postulaciones (unos 6 segundos con 50 000, medido en memoria). Con un periodo acotado lee menos.
- Las métricas son de cada proceso de la API y se reinician al reiniciarlo; no hay integración con una herramienta de monitoreo.
- La política de contenido de las pantallas todavía no limita el origen de los scripts.
- No hay procedimiento para rotar la clave maestra.
- Los guiones de `tests/e2e/` son compactos y no siguen el estilo del resto del código.
- «Pruebas pendientes» y «entrevistas pendientes» cuentan las postulaciones activas que están en esas etapas, no las evaluaciones con estado pendiente.
- Para contratar no se exige que la persona esté en la etapa «Resultado final»; el resultado se puede registrar desde cualquier etapa.
- Cerrar una convocatoria o cancelar una vacante no cierra sus postulaciones: siguen «en proceso» hasta que alguien registre su resultado.
- Los reportes generados no se borran ni caducan; todavía no hay política de retención para ellos.
- El uso de IA de los indicadores es de todo el sistema; al filtrar por vacante solo se cuenta el que quedó asociado a esas vacantes.
- El histórico de candidatos se abre dentro de «Indicadores»; desde una fila no se salta al expediente.
- Las cifras de tiempo aparecen en días con un decimal; estancias de minutos se ven como «0 días».
- La extracción de datos del CV duplica las llamadas a la IA por cada CV de un lote. Es opcional: sin un modelo asignado a «Extracción de CV» no se hace, y el nombre de la persona se toma del nombre del archivo.
- Dos CV distintos de la misma persona (mismo correo) en una convocatoria generan una sola postulación, con el primero.
- Los datos de una persona se comparten entre sus postulaciones: corregir su nombre o correo desde una vacante lo cambia en todas.
- De una llamada solo se conserva el análisis de IA más reciente.
- El expediente y los candidatos se abren dentro de la pantalla de Vacantes y no tienen dirección propia; al recargar la página se vuelve a la lista.
- En el expediente, los niveles de la evaluación muestran el código del criterio (C1, C2…) y no su nombre.
- La lista de candidatos no tiene búsqueda ni paginación; está pensada para convocatorias de hasta unos cientos de personas.
- Con el menú «Bancos» y «Etapas», el encabezado del administrador ocupa dos líneas en pantallas medianas.
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
- 11 nov 2026: lectura de CV escaneados con OCR (Tesseract en el servidor).
- 11 nov 2026: Fase 5 completa: candidatos, postulaciones, convocatorias, etapas por versiones, movimientos, bancos de preguntas, llamadas y análisis con IA, extracción del CV y permanencia laboral.
- 11 nov 2026: Fase 6 completa: psicometría, entrevistas con gerente, pruebas técnicas, formularios y estudios socioeconómicos con digitalización, expediente por etapas y síntesis con IA.
- 11 nov 2026: Fase 7 completa: resultados finales y contrataciones, tablero de inicio, indicadores con filtros e históricos, histórico de candidatos y reportes en Excel guardados en el servidor.
- 11 nov 2026: los atajos «Desistió», «Descartar» y «Cancelar proceso» del expediente se sustituyen por «Registrar resultado final»; «Reactivar» pasa a llamarse «Reabrir proceso».
- 12 nov 2026: Fase 8, lo que no depende del servidor: flujo completo, seguridad transversal, revisión de SQL Server (migración `0012` con cinco índices), validaciones de integridad, respaldo de reportes, métricas, cabeceras de seguridad, despliegue de producción, manuales, modelo de amenazas, contratos de API y recorridos en navegador dentro del repositorio.
- 12 nov 2026: los reportes leen solo las columnas y las postulaciones que necesitan; el tablero era 2.4 veces más lento. Lo detectó la medición de rendimiento.
- 12 nov 2026: el Excel de postulaciones tardaba 14.7 s con 5 000 filas por un cálculo que crecía con el cuadrado de las filas; ahora tarda 1 s. Lo detectó la medición de rendimiento.
- 12 nov 2026: al guardar el perfil del puesto, el aviso «Perfil guardado» desaparecía al instante porque el formulario se volvía a crear. Lo detectaron los recorridos en navegador.
- 12 nov 2026: el manifiesto de respaldo no incluía los Excel de reportes de la Fase 7; ahora sí.
- 12 nov 2026: las dependencias de producción se separan en `requirements-prod.lock`; la línea de acceso de la API sale en JSON.
- 11 nov 2026: al guardar una evaluación, el aviso de «guardada» desaparecía porque el editor se volvía a crear con la versión nueva. Lo detectó el recorrido en navegador.
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

Lo que queda no se puede hacer sin el servidor ni las claves:

1. **Sistemas monta el entorno de pruebas** siguiendo `docs/deployment/despliegue_produccion.md`: SQL Server 2022, contenedores, antivirus y certificado.
2. **Validar ahí todo lo marcado como «no verificado»:** scripts T-SQL, permisos del usuario de aplicación, las pruebas de la API contra SQL Server, la evaluación de CV con el worker y la cola, y una restauración completa.
3. **Con las claves de IA:** probar con casos sintéticos que un modelo real respeta el formato y las prohibiciones, y medir el OCR con escaneos reales de prueba.
4. **Decisiones pendientes** (sección anterior): retención de documentos y aviso de privacidad, custodia de la clave maestra, antivirus definitivo.
5. Solo entonces: producción, con datos reales.
