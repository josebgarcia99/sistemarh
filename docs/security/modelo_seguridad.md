# Modelo de seguridad

> Origen: propuesta de arquitectura aprobada el 10 de noviembre de 2026.
> Este archivo es la copia de trabajo del repositorio y se actualiza en cada fase.

## 9. Seguridad y descarga de documentos

Toda descarga pasa por la API, que evalúa el permiso en ese momento, no cuando se generó el archivo. Por eso una revocación también bloquea exportaciones antiguas.

| Control | Cómo se aplica |
| --- | --- |
| Privado por defecto | El disco está fuera del directorio público; no hay carpetas estáticas ni enlaces directos. |
| Autorización por objeto | `GET /api/v1/files/{id}/download` exige sesión, acceso vigente a la vacante y, si aplica, permiso de documento sensible. |
| Documentos sensibles | Psicometría, estudios socioeconómicos y fotografías documentales requieren un permiso adicional por persona. Compartir la vacante no lo concede. |
| Path traversal | Las claves las genera el servidor; el usuario nunca envía rutas. La ruta resuelta debe quedar dentro de la raíz. |
| Validación de archivos | Lista de formatos permitidos, verificación del tipo real, límite de 20 MB configurable, rechazo de documentos con macros. |
| Archivos maliciosos | Antivirus local en el servidor. Ningún documento se envía a servicios externos de análisis. |
| Respuesta de descarga | Nombre original saneado, `nosniff`, sin caché. La vista previa de PDF se sirve aislada. |
| Cifrado en reposo | Cifrado del volumen a cargo de Sistemas; cifrado adicional por archivo para la clase sensible (decisión 8). |
| Registro | Cada descarga y cada intento denegado genera un evento de auditoría. |
| Rutas físicas | Nunca aparecen en respuestas de la API, errores ni logs de usuario. |

## 10. Modelo de usuarios y autenticación

Las sesiones se guardan en SQL Server y viajan en una cookie `HttpOnly`. Así, desactivar a un usuario cierra sus sesiones al instante, algo que un token autocontenido no garantiza.

| Elemento | Diseño |
| --- | --- |
| Roles | `ADMINISTRADOR` y `RECLUTADOR`, en tablas `roles` y `user_roles` para poder añadir después el rol de gerente sin migrar usuarios. |
| Alta | Solo el administrador crea usuarios, con correo, nombre completo y contraseña inicial. No hay registro público ni envío de correos. |
| Contraseña inicial | La contraseña inicial la define el administrador al crear la cuenta. El usuario la conserva hasta que el administrador la restablezca, por decisión del 10 nov 2026. |
| Contraseñas | Hash Argon2id. Mínimo de 12 caracteres y rechazo de contraseñas comunes. |
| Sesión | Identificador aleatorio guardado como hash en `sessions`. Cookie `HttpOnly`, `Secure` y `SameSite=Lax`. Caduca a los 30 minutos sin actividad y a las 12 horas en total. |
| CSRF | Token por sesión exigido en toda operación que modifica datos. |
| Intentos abusivos | Bloqueo temporal tras 5 intentos fallidos por cuenta, límite por dirección IP y mensajes de error que no revelan si el correo existe. |
| Recuperación | El administrador asigna una contraseña nueva desde la pantalla de Usuarios. Al hacerlo se cierran todas las sesiones de ese usuario. |
| Baja | El usuario se desactiva, nunca se borra. Conserva su autoría histórica y pierde sesiones y accesos. |
| Primer administrador | El usuario maestro se crea con un comando de instalación que pide correo, nombre y contraseña. No hay credenciales en el código. |

Los plazos y umbrales son valores iniciales configurables.

El sistema no envía correos, por decisión tuya del 10 nov 2026. Las contraseñas se guardan solo como hash Argon2id: ni el administrador ni Sistemas pueden leerlas, solo restablecerlas.

Quedan diseñados como ampliación, sin construirse en la primera versión: segundo factor para administradores, inicio de sesión con el directorio corporativo y acceso directo para gerentes.

## 15. Integración con Anthropic y OpenAI

Los módulos de negocio piden una operación, por ejemplo "evaluar CV", y no un modelo. Un adaptador por proveedor traduce esa operación al SDK oficial, así que añadir un proveedor es añadir un adaptador.

| Pieza | Diseño |
| --- | --- |
| Puerto `AIProvider` | Interfaz única con tres adaptadores: Anthropic, OpenAI y uno simulado para pruebas. |
| Registro de modelos | El administrador escribe el identificador del modelo; no hay ninguno fijo en el código. Cada modelo declara capacidades: texto, salida JSON estructurada, lectura de imágenes y tamaño máximo. |
| Verificación de capacidades | Al registrar un modelo se prueba cada capacidad con una llamada sintética. Una operación no puede asignarse a un modelo que no pasó la prueba que necesita. |
| Operaciones | Las ocho del documento maestro, cada una con su modelo asignado. |
| Salida | Se valida contra un esquema. Si no cumple, se reintenta una vez; si vuelve a fallar, el CV queda `NO_EVALUABLE` con incidencia. |
| Puntuación | La IA devuelve nivel 0 a 4 y evidencia por criterio. El cálculo ponderado y la clasificación por umbral se hacen en Python. |
| Reproducibilidad | Cada ejecución guarda versión de prompt y de rúbrica, modelo, parámetros, hash del texto de entrada y respuesta completa. |
| Fallos del proveedor | Reintentos con espera creciente y tope. Si persisten, el lote se pausa. No se cambia de proveedor automáticamente, porque cambiaría los resultados. |
| Consumo | `ai_executions` registra tokens, modelo, operación, fecha, costo estimado, costo confirmado, duración, errores y reintentos. |
| Presupuesto | Límite mensual, máximo de CV por lote y estimación de costo antes de lanzar. Al llegar al límite se detienen los lotes nuevos. |

**Defensa contra prompt injection.**

- El texto del CV se entrega como datos delimitados, con la instrucción de no obedecer su contenido.
- El modelo no tiene herramientas ni puede ejecutar acciones.
- La puntuación se calcula fuera del modelo, así que un CV no puede "asignarse" una calificación.
- Cada cita de evidencia se busca en el texto extraído; si no aparece, se marca como no verificada.
- Lo que devuelve la IA se trata como texto no confiable en pantalla y en Excel.

**Privacidad.**

- Los entornos de desarrollo y pruebas traen bloqueado el envío de documentos reales; solo aceptan datos sintéticos.
- Se propone enmascarar teléfono, correo y domicilio antes de enviar un CV, porque no se necesitan para evaluarlo (decisión 13).
- Los documentos psicométricos y socioeconómicos solo se envían si habilitas esa operación de forma expresa.
- La retención y el uso de datos por parte de cada proveedor se configuran en tu cuenta con ellos; debes verificarlo antes de usar datos reales.

Enviar datos personales a un proveedor externo es un tratamiento por cuenta tuya. Tu área legal debe confirmar que el aviso de privacidad lo cubre conforme a la [Ley Federal de Protección de Datos Personales en Posesión de los Particulares](https://www.diputados.gob.mx/LeyesBiblio/pdf/LFPDPPP.pdf), vigente desde el 21 de marzo de 2025 según [EY](https://www.ey.com/es_mx/technical/tax/boletines-fiscales/nueva-ley-federal-proteccion-datos-personal-posesion-particulares).

## 16. Configuración segura de tus API keys

La clave se escribe una vez en la pantalla de administración, se cifra en el backend y nunca vuelve a mostrarse completa.

1. El administrador pega la clave en "Configuración de inteligencia artificial".
2. La API la cifra con AES-256-GCM usando una clave maestra que vive fuera de SQL Server y del repositorio.
3. Se guardan el texto cifrado, la versión de la clave maestra y los últimos cuatro caracteres para el identificador enmascarado.
4. La interfaz recibe solo el identificador enmascarado, el estado y la fecha de la última prueba.
5. El worker descifra la clave en memoria al momento de llamar. No viaja en mensajes de la cola ni se escribe en disco.
6. Sustituir crea un registro nuevo y revoca el anterior; revocar borra el texto cifrado. Ambas acciones quedan en auditoría, sin el secreto.

| Riesgo | Control |
| --- | --- |
| Clave en el código o en Git | Ninguna clave en el repositorio; `.env.example` solo trae marcadores; comprobación de secretos antes del primer commit. |
| Clave en el navegador | Nunca se usa en variables públicas de Next.js ni se devuelve en respuestas. |
| Clave en logs o errores | Filtro que oculta patrones de clave en logs, trazas y auditoría, con prueba automatizada. |
| Robo de la base de datos | Sin la clave maestra el texto cifrado no sirve. Sistemas la resguarda y la respalda por separado. |
| Rotación | Procedimiento para cambiar la clave maestra y volver a cifrar. |

También se admite inyectar la clave por variable de entorno del servidor; en ese caso la pantalla la muestra como "definida por entorno". Si Sistemas ya opera un gestor de secretos, se conecta mediante la misma interfaz (decisión 5).

## Clave maestra: lo construido (Fase 4, primera parte)

Estado al 11 de noviembre de 2026.

| Aspecto | Cómo quedó |
| --- | --- |
| Qué es | Una clave AES-256 guardada en un archivo del servidor. Cifra los documentos de clase sensible y cifrará las API keys de los proveedores de IA |
| Dónde vive | En la ruta que indique `RECLU_MASTER_KEY_FILE`. Nunca en SQL Server, en el repositorio ni en `.env` (ahí solo va la ruta) |
| Cómo se crea | `python -m app.cli generate-master-key --output <ruta>`. El archivo nace legible solo por su propietario y el comando se niega a sobrescribir uno existente. Solo muestra el identificador de la clave |
| Custodia | Sistemas (decisión 5). Debe respaldarse **por separado** de la base de datos y de los documentos |
| Si se pierde | Los documentos sensibles y las API keys guardadas quedan ilegibles. No hay forma de recuperarlos sin la clave |
| En producción | La API no arranca si `RECLU_MASTER_KEY_FILE` no está definida, o si el archivo falta o no es válido |
| Qué se registra | Solo el identificador de la clave (una huella que no permite deducirla). La clave no aparece en logs, errores ni auditoría |
| Documentos sensibles | Se validan y analizan con el antivirus en claro, dentro del servidor, y se cifran antes de llegar a su ubicación definitiva (AES-256-GCM por bloques; detecta archivos alterados, recortados o cifrados con otra clave). Se descifran al descargarlos, después de comprobar el permiso |
| Sin clave | Los documentos ordinarios funcionan igual; los sensibles no se aceptan |

**Pendiente:** el procedimiento de rotación (cambiar la clave maestra y volver a cifrar lo existente) no está construido. Mientras no exista, la clave no debe cambiarse una vez que haya documentos cifrados.

## Configuración de IA: lo construido (Fase 4, primera parte)

| Aspecto | Cómo quedó |
| --- | --- |
| Pantalla | "Configuración de inteligencia artificial", solo para administradores: registrar, sustituir y revocar la clave; probar la conexión; habilitar o deshabilitar; límite de gasto mensual; modelo de cada operación |
| Dónde está la clave | Cifrada con la clave maestra en `ai.provider_credentials`. El navegador la envía una sola vez, por HTTPS, y nunca la recibe de vuelta: solo ve `••••` y los últimos cuatro caracteres |
| Sustituir y revocar | Sustituir crea un registro nuevo y borra el texto cifrado del anterior. Revocar borra el texto cifrado y deshabilita el proveedor |
| Clave por variable de entorno | `RECLU_ANTHROPIC_API_KEY`, `RECLU_OPENAI_API_KEY` y `RECLU_GEMINI_API_KEY`. La pantalla la muestra como "definida por Sistemas" y no permite cambiarla ni revocarla |
| Probar la conexión | Pide al proveedor su lista de modelos. No envía ningún documento ni dato personal |
| Modelos | No hay identificadores de modelos en el código: la lista sale de lo que cada proveedor informa. Si un proveedor retira un modelo, deja de poder asignarse |
| Errores | Los mensajes los redacta la aplicación; nunca incluyen la clave ni la respuesta completa del proveedor |
| Auditoría | Registro, sustitución, revocación, pruebas, cambios de proveedor y asignaciones. Solo se anota la terminación de la clave |

**Sin verificar:** la aplicación nunca se ha conectado a Anthropic, a OpenAI ni a Google Gemini. La clave de Gemini viaja en la cabecera `x-goog-api-key` (nunca en la dirección) y la versión de su API (`v1beta`) es configurable. Las pruebas usan proveedores simulados y claves ficticias. La dirección, la cabecera de autorización y la versión de la API de Anthropic (`2026-10-21`, configurable) se tomaron de la documentación pública de cada proveedor consultada el 11 de noviembre de 2026.

**Llamadas a los proveedores (Fase 4, tercera parte).**

| Aspecto | Cómo quedó |
| --- | --- |
| Qué se registra | Cada llamada deja en `ai.executions` la operación, el modelo, los tokens, el costo estimado, la duración, los intentos y el resultado. No se guarda lo enviado ni lo recibido |
| Costo | Se estima con el precio por millón de tokens que el administrador captura para cada modelo. No hay precios en el código. Es una estimación: la factura del proveedor puede diferir |
| Límite mensual | Antes de cada llamada se compara el gasto estimado del mes con el límite del proveedor; si se alcanzó, la llamada no se hace. Si hay límite y el modelo no tiene precio, la llamada se rechaza para no gastar a ciegas |
| Reintentos | Fallos de red, de límite de solicitudes o del proveedor se reintentan dos veces, con espera. Una clave rechazada no se reintenta. Un fallo definitivo se registra y se informa; no tumba el proceso que lo llamó |
| Documentos | Fuera de producción, una llamada que lleve un documento se rechaza salvo que `RECLU_AI_ALLOW_REAL_DOCUMENTS` sea `true` (restricción 8) |
| OpenAI | Se envía `store: false` para que el proveedor no conserve lo enviado |

**Sin verificar:** las llamadas de generación tampoco se han ejecutado contra los servicios reales. La forma de la llamada a OpenAI se tomó de su documentación pública consultada el 11 de noviembre de 2026; la de Anthropic se escribió a partir de la forma conocida de su API de mensajes, sin poder consultar esa página de la documentación ese día.

**Pendiente:** validar las capacidades de un modelo antes de usarlo y conciliar el costo estimado con la factura real.

## Evaluación de CV: lo construido (Fase 4, tercera parte)

| Aspecto | Cómo quedó |
| --- | --- |
| Qué sale del servidor | Solo el texto del CV, extraído dentro del servidor, y el prompt aprobado. Nunca el archivo. Antes de enviarlo se sustituyen correos y teléfonos por marcas |
| Qué no se oculta | El nombre y la dirección, si están en el texto del CV. Ocultarlos de forma fiable requiere otro análisis; queda pendiente |
| Autorización para enviar | La regla de la restricción 8 se aplica igual: fuera de producción, sin `RECLU_AI_ALLOW_REAL_DOCUMENTS=true` el lote ni siquiera se crea |
| Texto del CV como dato | El CV se envía delimitado y con la instrucción de no obedecer nada de lo que diga. Aun así, la respuesta se valida contra la rúbrica: criterios exactos, niveles enteros de 0 a 4. Una respuesta que no cumple se pide una vez más y, si persiste, el CV queda con error; nunca se acepta un porcentaje dado por la IA |
| Decisión humana | La clasificación es una sugerencia inicial y no cambia el estado de ningún candidato. «No evaluable» y «sin evidencia» nunca se convierten en rechazo |
| Dónde queda el resultado | En `ai.cv_batch_items`, con fragmentos del CV usados como evidencia. Se consulta con acceso a la vacante |
| Excel y ZIP | Se guardan en el área `generated/` del almacenamiento privado y se descargan por la misma ruta autorizada que los documentos: el permiso se evalúa en cada descarga y queda auditada. El Excel antepone un apóstrofo a cualquier texto que empiece por `=`, `+`, `-` o `@` |
| Archivos de CV hostiles | La lectura limita las páginas de un PDF y el tamaño del XML de un DOCX, no resuelve entidades externas y trata cualquier fallo como «no evaluable» |
| Auditoría | Creación, fin, reanudación y cancelación de cada lote, y cada exportación generada con su tamaño y su SHA-256 |

**Sin verificar:** nada de esto se ha ejecutado con un modelo real ni con CV reales.

## Ayudas de IA para el perfil y la rúbrica (Fase 4, cierre)

| Aspecto | Cómo quedó |
| --- | --- |
| Qué se envía | Para el perfil, el texto del documento de perfil o el texto pegado. Para la rúbrica, el perfil guardado y los nombres de los criterios. Ningún CV ni dato de candidatos |
| Autorización | Leer un perfil desde un documento sigue la misma regla que los CV: fuera de producción exige `RECLU_AI_ALLOW_REAL_DOCUMENTS=true` |
| Nada se guarda solo | Las dos ayudas devuelven una propuesta. La versión del perfil o el cambio en el borrador solo existen cuando una persona con acceso de colaboración los guarda |
| La IA no añade requisitos | Del perfil solo se aceptan los once campos conocidos. De la rúbrica solo se aceptan mejoras de criterios que ya existen, con cinco niveles distintos; todo lo demás se descarta en el servidor |
| Atributos personales | Las instrucciones piden no copiar a los requisitos condiciones de edad, sexo, estado civil, embarazo, religión, origen, apariencia, salud o discapacidad, y anotarlas como requisito que no debe usarse. Depende del modelo: la persona debe revisar la propuesta |
| Documento como dato | El texto va delimitado y con la instrucción de no obedecer lo que diga |
| Si la IA falla | Se informa el motivo, el consumo de la llamada queda registrado y la auditoría anota el intento como fallido |

**Sin verificar:** con un modelo real.

## Reclutamiento operativo (Fase 5)

| Aspecto | Cómo quedó |
| --- | --- |
| Acceso a candidatos | Un candidato solo se ve a través de una postulación, y la postulación sigue el permiso de su vacante: lectura para consultar, colaboración para dar de alta y mover, responsable o administrador para abrir y cerrar convocatorias. Sin acceso a la vacante, la postulación responde «no encontrado» |
| Decisión humana | Ningún movimiento es automático salvo el alta desde un lote, que deja a la persona en revisión de RH. Avanzar a quien la IA clasificó como rechazado o no evaluable exige escribir el motivo; queda en el historial con quién y cuándo, y en la auditoría. La clasificación inicial nunca se sobrescribe |
| Historial | `recruitment.application_movements` solo recibe altas; la plantilla de permisos niega `UPDATE` y `DELETE` al usuario de la aplicación |
| Bancos de preguntas | Un banco privado ajeno responde «no encontrado». Solo el propietario o un administrador lo modifica. Las preguntas propuestas por la IA no entran a ningún banco sin que una persona las añada |
| Preguntas indebidas | A la IA se le pide no proponer preguntas sobre edad, estado civil, hijos, embarazo, religión, origen, salud, discapacidad, apariencia, afiliación política ni domicilio. Depende del modelo: la persona revisa cada propuesta |
| Análisis de llamadas | Se envían las notas escritas de la llamada, los requisitos del puesto y los datos ordenados del CV (puestos, empresas y periodos). No se envían el nombre, el correo ni el teléfono. Las instrucciones prohíben inferir emociones, honestidad o personalidad, afirmar que alguien mintió y recomendar una decisión; el servidor solo conserva los campos conocidos de la respuesta |
| OCR | Tesseract corre dentro del servidor, con límite de páginas, de tamaño de imagen y de tiempo. Ninguna imagen se envía a servicios externos |
| Datos del CV | El correo y el teléfono se extraen con reglas locales; a la IA se le envía el texto con esos datos ocultos |
| Auditoría | Postulaciones creadas, movimientos (con cuántas personas no aceptadas por la IA se avanzaron), cambios de estado, anotaciones, convocatorias, versiones de etapas, bancos, y apertura, guardado, cierre y análisis de llamadas |

**Sin verificar:** con SQL Server, con un modelo real y con escaneos reales.

## Evaluaciones posteriores y síntesis (Fase 6)

| Aspecto | Cómo quedó |
| --- | --- |
| Datos sensibles | La psicometría y el estudio socioeconómico exigen, además del acceso a la vacante, el permiso adicional por persona (el mismo de sus documentos). Sin él, la evaluación responde «sin permiso» y en las listas solo se indica que existe. El responsable y el administrador lo tienen siempre. Compartir la vacante no lo concede |
| Documentos | Los reportes psicométricos y los estudios se guardan cifrados. Para resumirlos o digitalizarlos se descifran en memoria dentro del servidor; el texto es lo único que se envía al proveedor |
| Sin decisiones automáticas | Registrar o cambiar una evaluación nunca mueve de etapa ni cambia el estado de una postulación |
| Psicometría | El sistema no diagnostica ni declara aptitud. «Validada» exige el nombre del profesional que la interpretó. A la IA se le pide transcribir lo que el reporte documenta; su respuesta se reduce a resumen, resultados documentados, datos ilegibles y avisos |
| Estudio socioeconómico | El sistema no calcula ninguna puntuación. El formato de la empresa (SGC.F3.RH) pide un dictamen, niveles por indicador, un «score total» y la viabilidad: son campos de captura manual que anota quien aplicó el estudio; la IA no los recibe ni los llena, y no entran en la síntesis ni en los reportes. Los datos de salud, religión y antecedentes que pide el formato quedan bajo el mismo permiso adicional por persona. A la IA se le prohíbe inferir nivel socioeconómico, confiabilidad, moralidad, religión, salud o idoneidad; solo se aceptan valores para campos de la plantilla. Un dato leído por la IA entra sin verificar y solo una persona puede marcarlo como verificado. No se envían fotografías ni imágenes a ningún proveedor |
| Síntesis del expediente | Seis listas por tipo de fuente; cualquier puntuación, índice o recomendación en la respuesta se descarta en el servidor. No se envían el nombre ni el contacto. La psicometría entra solo si está validada y quien pide la síntesis tiene ese permiso; una síntesis que la incluye solo la ve quien lo tiene. El contenido del estudio socioeconómico nunca entra |
| Auditoría | Alta y cambios de cada evaluación (tipo y estado, nunca el contenido), resúmenes, digitalizaciones, versiones de formularios y síntesis con sus fuentes |

**Límite conocido:** el servidor controla la forma de la respuesta de la IA, no cada frase. Un resumen podría contener una valoración indebida escrita dentro de un texto permitido. Por eso cada pantalla lo presenta como resumen y no como conclusión, y por eso debe revisarse con casos sintéticos antes de usarlo con datos reales.

**Sin verificar:** con SQL Server y con un modelo real.

## Resultados finales, indicadores y reportes (Fase 7)

- **La contratación es una decisión humana.** El resultado final solo se registra desde una petición de una persona con sesión y con permiso de colaboración sobre la vacante. Ninguna tarea automática ni respuesta de la IA escribe en `recruitment.application_outcomes`; la columna de quién lo registró no admite valores vacíos. Contratar a alguien que la IA no clasificó como aceptado se anota en la auditoría.
- **Nada se borra.** Reabrir una postulación exige motivo y deja el resultado anterior anulado, con quién lo anuló y cuándo. El usuario de base de datos de la aplicación no tiene permiso de borrado en ese esquema.
- **Permisos de hoy, también en los históricos.** Los tableros y el histórico no guardan cifras: se calculan en cada consulta sobre las vacantes que la persona puede ver en ese momento (las suyas y las compartidas; todas si es administradora). Quien pierde el acceso a una vacante deja de verla en cualquier periodo, pasado o presente. Pedir por identificador una vacante ajena devuelve resultados vacíos, sin revelar que existe.
- **Datos solo para administradores.** El uso y costo de IA, los errores técnicos y la carga de trabajo por persona no se envían a quien no es administrador; no es que la pantalla los oculte.
- **Excel sin fórmulas ejecutables.** Todo texto capturado por alguien (nombres, motivos, filtros) se escribe de forma que Excel no lo interprete como fórmula.
- **Los reportes se quedan en el servidor.** Cada Excel se guarda en el almacenamiento documental con su identificador, fecha, tamaño y SHA-256, y queda en la auditoría quién lo generó y quién lo descargó. Solo lo descarga quien lo generó (o un administrador), y solo mientras conserve acceso a todas las vacantes que contiene; si perdió alguna, debe generar uno nuevo. No se envía a ningún servicio externo.
- **Lo que un reporte contiene.** El de postulaciones lleva nombres de candidatos, etapa, resultado y su motivo, y la clasificación inicial de la IA. No lleva datos de contacto, psicometría, estudios socioeconómicos ni contenido de llamadas.
- **Pendiente.** Política de retención y borrado de los reportes generados; revisión de las consultas de reportes en SQL Server.

## Preparación productiva (Fase 8)

- **Cabeceras en toda respuesta de la API:** `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: no-referrer`, `Cross-Origin-Resource-Policy: same-origin`, `Cache-Control: no-store` y una política de contenido que no permite cargar ni ejecutar nada. En producción se añade `Strict-Transport-Security`. Una ruta puede fijar las suyas (las descargas usan `sandbox`). Las pantallas llevan las equivalentes desde la configuración de Next.js; su política de contenido aún no limita el origen de los scripts.
- **Registro de accesos propio.** Una línea JSON por solicitud con método, ruta, estado, duración e identificador de correlación. No incluye la cadena de consulta, que puede llevar nombres de candidatos. La línea de acceso de Uvicorn se apaga.
- **Métricas.** `GET /api/v1/system/metrics`, solo para administradores: contadores por ruta declarada (`/vacancies/{vacancy_id}`), nunca con identificadores reales. El proxy de ejemplo las limita además a la red interna.
- **IP real del usuario.** Detrás del proxy se toma de la cabecera que este envía, y solo si la conexión viene de una dirección listada en `FORWARDED_ALLOW_IPS`. El proxy de ejemplo sobrescribe lo que mande el cliente.
- **Versión del esquema.** La comprobación de salud falla si la base no tiene la versión que espera el código, para no dar servicio a medio actualizar.
- **Barrido de acceso directo.** Una prueba pide como persona sin acceso cada ruta con identificador, con datos reales de otra persona; toda ruta nueva entra sola en el barrido.
- **Imagen de producción** sin herramientas de desarrollo; el contenedor corre con un usuario sin privilegios; solo el proxy publica puertos; la clave maestra se monta en solo lectura.
- **Amenazas y riesgos abiertos:** en [`modelo_amenazas.md`](modelo_amenazas.md).
