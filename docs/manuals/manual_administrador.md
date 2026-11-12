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
- **Analista de estudios socioeconómicos.** Es un rol aparte para quien solo hace estudios: ve la lista de personas en proceso de todas las vacantes y trabaja su estudio (formato, fotografías y ayudas de IA). No ve vacantes, CV, otras evaluaciones, indicadores ni configuración, y no hace falta compartirle ninguna vacante. Los reclutadores y administradores siguen viendo y editando los estudios como antes.
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

## Inteligencia artificial

Menú «IA». Hasta que configures un proveedor, las funciones de IA no están disponibles; el resto del sistema funciona igual.

### Claves de los proveedores

1. Elige el proveedor (Anthropic, OpenAI o Google Gemini) y pulsa «Registrar clave». Pega la clave y «Guardar clave».
2. «Probar conexión» comprueba que la clave funciona.
3. «Habilitar» activa el proveedor.

La clave se guarda cifrada y **no vuelve a mostrarse**: solo verás sus cuatro últimos caracteres. No aparece en respuestas, reportes ni registros. «Revocar clave» la retira. Si Sistemas definió la clave en el servidor, la pantalla lo indica y no se puede cambiar desde aquí.

### Modelos y asignaciones

Cada tarea de IA usa el modelo que tú le asignes: análisis de perfiles, generación de prompts, evaluación de CV, extracción de datos del CV, análisis de llamadas, lectura de documentos, resumen de pruebas y síntesis de expedientes. Una tarea sin modelo asignado no se puede usar, y la pantalla lo avisa a quien lo intente. «Probar» comprueba un modelo concreto.

### Costos y límite mensual

- Captura el precio de cada modelo para que el sistema estime el costo de cada llamada.
- Define un **límite mensual** por proveedor. Al alcanzarlo, las llamadas a la IA se detienen con un aviso; lo ya evaluado no se pierde.
- «Consumo y costos de este mes» muestra llamadas, fallos y costo estimado por tarea. El costo es una estimación con tus precios; no sustituye a la factura del proveedor.

### Documentos reales y privacidad

Por omisión el sistema **no envía documentos reales** a los proveedores de IA. Activarlo es una decisión que se toma con Sistemas (variable `RECLU_AI_ALLOW_REAL_DOCUMENTS`), con el aviso de privacidad vigente y sabiendo qué hace cada proveedor con los datos. Antes de enviar un CV se ocultan correos y teléfonos. Los estudios socioeconómicos nunca se incluyen en la síntesis de un expediente.

## Etapas del proceso

Menú «Etapas». Define las etapas por las que pasa un candidato (por omisión: evaluación de CV, revisión local de RH, llamada telefónica, pruebas psicométricas, entrevista con gerente, prueba técnica, estudio socioeconómico y resultado final). Puedes renombrarlas, reordenarlas, marcarlas como opcionales y agregar otras.

«Guardar como versión nueva» crea una versión: las convocatorias ya abiertas siguen con la suya y las nuevas usan la más reciente. Así un cambio de etapas no altera procesos en curso.

## Formularios del estudio socioeconómico

Menú «Formularios». «Nuevo formulario» crea una plantilla con secciones y campos (texto, fecha, número, opciones, casilla, documento, observación y tabla), indicando cuáles son obligatorios. En una tabla escribes los nombres de sus columnas separados por coma. «Solo captura manual» marca los campos que la IA no debe llenar al leer un documento. Cada cambio guarda una versión; los estudios ya capturados conservan la suya. Un formulario que ya no se usa se archiva.

Para que el botón «Describir con IA» de las fotografías funcione, en la pantalla «IA» asigna a la operación «Descripción de fotografías del estudio» un modelo que acepte imágenes (por ejemplo, uno de Google Gemini, después de registrar su API key y habilitar el proveedor). Cada descripción cuenta en el consumo de ese proveedor.

La plantilla inicial es el formato de la empresa «SGC.F3.RH. Estudio socioeconómico». Ese formato incluye un dictamen, cinco indicadores con nivel (suficiente, medio, inferior), un «score total» y si la persona se considera viable. El sistema guarda lo que anote quien aplicó el estudio, pero no calcula esa puntuación, la IA no la llena y no se usa en la síntesis del expediente ni en los reportes. Si la empresa decide no registrar esos datos en el sistema, basta con quitar esos campos de la plantilla.

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
