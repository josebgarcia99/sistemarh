# Manual del administrador

Para quien administra el sistema: da de alta a las personas, configura la IA, define etapas y formularios, transfiere vacantes y revisa la auditoría. Todo lo que hace un reclutador también lo puedes hacer; está en el [manual del reclutador](manual_reclutador.md).

> Este manual describe el sistema tal como está construido. Todavía no se ha usado con datos reales ni se ha instalado en el servidor de la empresa.

## Tu papel

- Ves **todas** las vacantes, candidatos y reportes.
- Eres la única persona que puede crear usuarios, cambiar contraseñas, transferir vacantes, configurar la IA, eliminar documentos y consultar la auditoría.
- Lo que no puedes hacer: desactivarte a ti mismo, quitarte el rol de administrador o dejar el sistema sin ningún administrador activo. El sistema lo impide.

## Usuarios

Menú «Usuarios».

- **Dar de alta.** «Nuevo usuario»: correo, nombre completo, contraseña y rol (administrador, reclutador o analista de estudios socioeconómicos) → «Crear usuario». El sistema no envía correos: comunica tú la contraseña a la persona por un medio seguro. La contraseña debe tener al menos 12 caracteres.
- **Restablecer contraseña.** «Restablecer contraseña» pone una nueva y cierra todas las sesiones abiertas de esa persona.
- **Editar.** Puedes cambiar el nombre y el rol.
- **Analista de estudios socioeconómicos.** Es un rol aparte para quien solo hace estudios: ve la lista de personas en proceso de todas las vacantes y trabaja su estudio (formato, fotografías y ayudas de IA) y sus referencias laborales y personales. No ve vacantes, CV, otras evaluaciones, indicadores ni configuración, y no hace falta compartirle ninguna vacante. Los reclutadores y administradores siguen viendo y editando los estudios como antes.
- **Cuenta bloqueada.** Tras cinco intentos fallidos la cuenta se bloquea quince minutos y se desbloquea sola. Restablecer la contraseña también la libera.

Las contraseñas no se pueden consultar: el sistema guarda solo una huella irreversible.

## Bajas y transferencias

Cuando alguien deja la empresa o cambia de área, sus vacantes deben pasar a otra persona. Nada se pierde: candidatos, documentos, evaluaciones e historial pertenecen a la vacante, no a quien la llevaba.

### Transferir una vacante

En el detalle de la vacante, «Transferir responsable»: eliges a la nueva persona, escribes el motivo y decides si la anterior se queda como colaboradora. La nueva responsable debe estar activa.

### Dar de baja a una persona con todas sus vacantes

Menú «Bajas»:

1. Elige a la persona que sale y a quien recibe.
2. «Ver vista previa» muestra qué vacantes se transfieren, en cuáles colaboraba y qué accesos se revocan.
3. «Dar de baja y transferir» lo ejecuta todo junto: transfiere las vacantes, revoca los accesos, cierra las sesiones y desactiva la cuenta. Si algo falla a la mitad, no cambia nada.

La cuenta queda desactivada, no borrada: lo que esa persona hizo sigue apareciendo a su nombre en los historiales.

## Eliminar una vacante

Solo los administradores ven esta opción. Es la única operación del sistema que **borra de verdad** datos de reclutamiento, y **no se puede deshacer**: no hay papelera. Está pensada para quitar vacantes de prueba o creadas por error.

1. En «Vacantes», abre la vacante. Al final del panel está «Eliminar vacante».
2. El sistema te muestra qué contiene y se borraría: postulaciones, candidatos, CV evaluados, llamadas, evaluaciones, síntesis y documentos.
3. Escribe el nombre de la vacante para confirmar y pulsa «Eliminar definitivamente».

Qué se borra: la vacante, su perfil y sus prompts; los lotes de CV con sus evaluaciones; las postulaciones con su historial de etapas; las llamadas; las evaluaciones posteriores (psicometría, entrevista, prueba técnica, referencias, estudio socioeconómico); las síntesis; los resultados finales; todos sus documentos, también el archivo guardado en el servidor; y los permisos sobre la vacante.

Qué conviene saber:

- **Candidatos.** Una persona se borra solo si no tiene postulación en otra vacante. Si está en otra, se conserva.
- **Lo que no se borra.** El registro de auditoría (incluido quién eliminó la vacante, cuándo y qué contenía), el costo de IA ya registrado y los reportes que ya se hubieran descargado. Los respaldos anteriores de la base y de los documentos tampoco cambian: lo borrado sigue en ellos hasta que caduquen.
- **CV en proceso.** Si la vacante tiene un lote de CV procesándose, hay que esperar a que termine o cancelarlo.
- **Si avisa que la base de datos no lo permite.** En un servidor instalado antes del 18 de noviembre de 2026, Sistemas debe ejecutar una vez el script `permisos_eliminar_vacantes.sql`. Mientras no lo haga, el botón no borra nada.
- **Para lo que no es una prueba**, lo normal sigue siendo cerrar o cancelar la vacante y archivarla: así se conserva el historial.

## Inteligencia artificial

Menú «IA». Hasta que configures un proveedor, las funciones de IA no están disponibles; el resto del sistema funciona igual.

### Claves de los proveedores

1. Elige el proveedor (Anthropic, OpenAI o Google Gemini) y pulsa «Registrar clave». Pega la clave y «Guardar clave». Si Sistemas ya puso la clave en el archivo `.env` del servidor, el proveedor aparece como «definida por Sistemas» con sus últimos cuatro caracteres: sáltate este paso (desde la pantalla no se puede cambiar; se cambia en el servidor).
2. «Probar conexión» comprueba que la clave funciona.
3. «Habilitar» activa el proveedor.

La clave se guarda cifrada y **no vuelve a mostrarse**: solo verás sus cuatro últimos caracteres. No aparece en respuestas, reportes ni registros. «Revocar clave» la retira. Si Sistemas definió la clave en el servidor, la pantalla lo indica y no se puede cambiar desde aquí.

### Modelos y asignaciones

Cada tarea de IA usa el modelo que tú le asignes: análisis de perfiles, generación de prompts, evaluación de CV, extracción de datos del CV, análisis de llamadas (también organiza las entrevistas y analiza las referencias), lectura de documentos, resumen de pruebas y síntesis de expedientes. Una tarea sin modelo asignado no se puede usar, y la pantalla lo avisa a quien lo intente. «Probar» comprueba un modelo concreto.

### Costos y límite mensual

- Captura el precio de cada modelo para que el sistema estime el costo de cada llamada.
- Define un **límite mensual** por proveedor. Al alcanzarlo, las llamadas a la IA se detienen con un aviso; lo ya evaluado no se pierde.
- «Consumo y costos de este mes» muestra llamadas, fallos y costo estimado por tarea. El costo es una estimación con tus precios; no sustituye a la factura del proveedor.

### Cuando la IA no responde

El sistema pide cada respuesta **por partes**: el proveedor va mandando señales conforme trabaja. Así se sabe en qué paso está cada solicitud (se conectó, el modelo empezó a contestar, terminó) y, si algo falla, el mensaje dice en qué paso fue:

| Mensaje | En qué paso falló | Qué hacer |
| --- | --- | --- |
| «No se pudo conectar con el proveedor» | No se llegó al proveedor (red o salida a internet). Se reintenta solo dos veces | Si persiste, pedir a Sistemas que revise la salida HTTPS hacia el proveedor |
| «El proveedor recibió la solicitud, pero el modelo no empezó a responder» | Se conectó, pero pasaron 90 segundos sin que el modelo escribiera nada | Volver a intentarlo. Si se repite, el proveedor puede estar saturado: probar más tarde |
| «El modelo empezó a responder y la respuesta se interrumpió antes de terminar» | Ya había texto y la conexión se cortó o se quedó en silencio | Volver a intentarlo |
| «El modelo llevaba más de 4 minutos respondiendo y se dejó de esperar» | Seguía escribiendo, pero rebasó el tope total | Volver a intentarlo; si se repite, la respuesta pedida es demasiado larga (por ejemplo, una rúbrica muy grande) |
| «El proveedor no pudo generar la respuesta (código)» | El proveedor aceptó la solicitud y avisó de un error propio antes de escribir. Se reintenta solo | Si persiste, anotar el código entre paréntesis y avisar a soporte |
| «El proveedor limitó las solicitudes» | Demasiadas solicitudes en poco tiempo o saldo agotado en el proveedor. Se reintenta solo | Esperar unos minutos; revisar el saldo en la consola del proveedor |
| «El proveedor rechazó la clave» | La clave no es válida o no tiene permisos | Revisar la clave en el servidor |

Qué conviene saber:

- **Mientras sigan llegando pedazos, el sistema sigue esperando.** No hay un tope corto: solo se rinde tras 90 segundos de silencio o 4 minutos en total.
- **Lo que se reintenta solo y lo que no.** Se reintenta cuando no se llegó a generar nada (sin conexión, límite, error inicial del proveedor). Cuando el proveedor ya había aceptado la solicitud no se reintenta, porque cada intento se cobra: lo decide la persona.
- **En pantalla.** Mientras la IA responde aparece «La IA está trabajando» con el tiempo transcurrido. Una respuesta larga puede tardar más de un minuto.
- **«Probar» en «Modelos y precios»** dice cuánto tardó cada paso: en cuánto conectó, cuándo empezó a contestar y cuándo terminó. Sirve para comprobar que la conexión con un modelo funciona de principio a fin.
- **En un lote de CV**, los archivos que fallaron quedan con «Error» y el motivo; «Reintentar» vuelve a procesar solo esos.

Antecedente: hasta el 17 de noviembre de 2026 el sistema pedía la respuesta completa y esperaba solo 20 segundos, y avisaba «No se pudo conectar con el proveedor» aunque la conexión estuviera bien; por eso fallaban las evaluaciones largas y «Proponer mejoras con IA».

### Documentos reales y privacidad

Por omisión el sistema **no envía documentos reales** a los proveedores de IA. Activarlo es una decisión que se toma con Sistemas (variable `RECLU_AI_ALLOW_REAL_DOCUMENTS`), con el aviso de privacidad vigente y sabiendo qué hace cada proveedor con los datos. Antes de enviar un CV se ocultan correos y teléfonos. Los estudios socioeconómicos nunca se incluyen en la síntesis de un expediente.

## Preguntas generales de la empresa

Son las preguntas que se hacen a todas las personas candidatas, sin importar la vacante. En el menú «Bancos», crea un banco (o abre uno) y marca «Preguntas generales de la empresa». Desde ese momento se agregan solas a cada llamada nueva, antes de las preguntas de los bancos que elija quien llama (puede no elegir ninguno), y aparecen marcadas como «General».

- Las crean y las modifican los administradores y los reclutadores: son de toda la empresa, no de quien las escribió. Cada cambio crea una versión nueva del banco, con quién lo hizo y cuándo, y queda en la auditoría.
- Si las cambias, las llamadas ya abiertas conservan las preguntas con las que se abrieron.
- Si en una llamada alguna no aplica, quien llama la quita **de esa llamada** con «Quitar», o le cambia la redacción solo para esa llamada. El banco general no cambia: en la siguiente llamada vuelve a aparecer completa. En la llamada cerrada queda a la vista qué preguntas no se usaron, y la auditoría registra cuántas se quitaron, se redactaron distinto o se escribieron.
- Para dejar de usarlas, archiva el banco o desmarca la casilla.
- En cada pregunta puedes anotar «qué se espera de la respuesta». Con eso la IA mide la cobertura de la llamada.

## Etapas del proceso

Menú «Etapas». Define las etapas por las que pasa un candidato (por omisión: evaluación de CV, revisión local de RH, llamada telefónica, pruebas psicométricas, entrevista con gerente, prueba técnica, estudio socioeconómico y resultado final). Puedes renombrarlas, reordenarlas, marcarlas como opcionales y agregar otras.

«Guardar como versión nueva» crea una versión: las convocatorias ya abiertas siguen con la suya y las nuevas usan la más reciente. Así un cambio de etapas no altera procesos en curso.

## Formularios del estudio socioeconómico

Menú «Formularios». «Nuevo formulario» crea una plantilla con secciones y campos (texto, fecha, número, opciones, casilla, documento, observación y tabla), indicando cuáles son obligatorios. En una tabla escribes los nombres de sus columnas separados por coma. «Solo captura manual» marca los campos que la IA no debe llenar al leer un documento. Cada cambio guarda una versión; los estudios ya capturados conservan la suya. Un formulario que ya no se usa se archiva.

Para que el botón «Describir con IA» de las fotografías funcione, en la pantalla «IA» asigna a la operación «Descripción de fotografías del estudio» un modelo que acepte imágenes (por ejemplo, uno de Google Gemini, después de registrar su API key y habilitar el proveedor). Cada descripción cuenta en el consumo de ese proveedor.

La plantilla inicial es el formato de la empresa «SGC.F3.RH. Estudio socioeconómico». Ese formato incluye un dictamen, cinco indicadores con nivel (suficiente, medio, inferior), un «score total» y si la persona se considera viable. El sistema guarda lo que anote quien aplicó el estudio, pero no calcula esa puntuación, la IA no la llena y no se usa en la síntesis del expediente ni en los reportes. Si la empresa decide no registrar esos datos en el sistema, basta con quitar esos campos de la plantilla.

**Formato de la empresa para descargar el estudio.** Al abrir un formulario, arriba aparece «Formato de la empresa para descargar el estudio». Sube ahí, una sola vez, el Excel **en blanco** del formato SGC.F3.RH (archivo .xlsx, hasta 5 MB). A partir de ese momento, cualquier estudio capturado con ese formulario se puede descargar en ese mismo archivo, con sus datos puestos. Qué conviene saber:

- Solo un administrador lo sube o lo sustituye. Si el formato cambia de versión, vuelve a subirlo: el vigente es siempre el último.
- El sistema revisa que sea el formato del estudio (busca los títulos de sus apartados). Si falta alguno te lo dice, porque los datos de ese apartado no se podrán colocar.
- El sistema ubica cada dato por el texto de su etiqueta («Nombre completo:», «Rentada:», etc.), no por la celda. Si en una versión nueva cambias el texto de una etiqueta, ese dato puede quedar sin colocar; quien descarga recibe el aviso de cuáles fueron.
- El archivo se guarda en el almacenamiento de documentos del servidor, no en el código ni en la base de datos, y entra en los respaldos normales de esa carpeta.
- No hace falta ningún cambio en la base de datos.

## Documentos

- **Eliminar.** Solo tú puedes eliminar un documento, con motivo. Se conserva el registro de que existió, quién lo eliminó y por qué.
- **Estado del sistema** (en Inicio). Indica si la base de datos, la cola de tareas y el almacenamiento responden.
- **Documentos sensibles.** Psicometría y estudios socioeconómicos se guardan cifrados. Ni siquiera tú los abres sin motivo: cada descarga queda en la auditoría.

## Indicadores

Además de lo que ve un reclutador, en «Indicadores» tienes:

- **Carga de trabajo por responsable:** vacantes, postulaciones activas, cierres y contrataciones de cada persona. Una contratación se cuenta una sola vez, a nombre de quien es responsable de la vacante, aunque haya colaboradores.
- **Uso de IA y errores técnicos:** llamadas, fallos, costo estimado y CV que no se pudieron evaluar.
- El Excel de indicadores incluye las hojas «Reclutadores» e «IA».

## Auditoría

Menú «Auditoría». Registra, entre otros: inicios de sesión y sus fallos, accesos denegados, altas y bajas de usuarios, compartir y revocar, transferencias, cargas y descargas de documentos, evaluaciones, movimientos, cambios de configuración de IA, reportes generados y descargados, y resultados finales.

- Se filtra por tipo de evento y se navega por páginas.
- No se puede modificar ni borrar desde la aplicación.
- No contiene contraseñas, claves ni el contenido de los documentos.

Úsala para responder «quién hizo qué y cuándo» y para revisar los accesos denegados: varios seguidos de la misma persona merecen una pregunta.

## Revisión periódica recomendada

| Cada cuánto | Qué revisar |
| --- | --- |
| Semanal | Accesos denegados en la auditoría; consumo de IA frente al límite |
| Mensual | Usuarios que ya no deberían estar activos; vacantes abiertas sin movimiento; reportes de indicadores |
| Al salir alguien | Baja con transferencia el mismo día |
| Con Sistemas | Que los respaldos se hacen y se prueban; ver [`respaldos_y_restauracion.md`](../deployment/respaldos_y_restauracion.md) |

## Qué pedir a Sistemas

Estas tareas no se hacen desde las pantallas: instalar y actualizar el sistema, crear el primer administrador, respaldos y restauración, el certificado HTTPS, la clave maestra de cifrado, el antivirus y la revisión de los registros del servidor. Están descritas en [`despliegue_produccion.md`](../deployment/despliegue_produccion.md).
