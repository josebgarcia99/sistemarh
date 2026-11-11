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
| Clave por variable de entorno | `RECLU_ANTHROPIC_API_KEY` y `RECLU_OPENAI_API_KEY`. La pantalla la muestra como "definida por Sistemas" y no permite cambiarla ni revocarla |
| Probar la conexión | Pide al proveedor su lista de modelos. No envía ningún documento ni dato personal |
| Modelos | No hay identificadores de modelos en el código: la lista sale de lo que cada proveedor informa. Si un proveedor retira un modelo, deja de poder asignarse |
| Errores | Los mensajes los redacta la aplicación; nunca incluyen la clave ni la respuesta completa del proveedor |
| Auditoría | Registro, sustitución, revocación, pruebas, cambios de proveedor y asignaciones. Solo se anota la terminación de la clave |

**Sin verificar:** la aplicación nunca se ha conectado a Anthropic ni a OpenAI. Las pruebas usan proveedores simulados y claves ficticias. La dirección, la cabecera de autorización y la versión de la API de Anthropic (`2026-10-21`, configurable) se tomaron de la documentación pública de cada proveedor consultada el 11 de noviembre de 2026.

**Pendiente:** registro de consumo y costos, aplicación del límite mensual y validación de capacidades antes de usar un modelo. Llegan con el procesamiento de CV.
