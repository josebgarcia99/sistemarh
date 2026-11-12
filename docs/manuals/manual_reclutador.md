# Manual del reclutador

Para quien lleva vacantes y candidatos. Explica qué puedes hacer en cada pantalla, en el orden en que normalmente se usa. Los nombres entre comillas son los que aparecen en pantalla.

> Este manual describe el sistema tal como está construido. Todavía no se ha usado con datos reales: si algo no coincide con lo que ves, avisa.

## Lo esencial

- **Entras con tu correo y la contraseña que te dio el administrador.** No hay recuperación por correo: si la olvidas, el administrador te pone una nueva. Tras cinco intentos fallidos la cuenta se bloquea quince minutos.
- **Solo ves tus vacantes y las que te compartieron.** Las de otras personas no aparecen ni en listas, ni en reportes, ni escribiendo su dirección a mano.
- **La IA propone y resume; tú decides.** Clasifica los CV y ordena información, pero avanzar, descartar o contratar a alguien lo registra siempre una persona, con su nombre.
- **Nada se borra al avanzar.** Cada cambio queda en el historial del candidato.
- La sesión se cierra sola tras 30 minutos sin actividad y, en cualquier caso, a las doce horas.

## Inicio

Es tu tablero. Muestra tus vacantes propias y compartidas, los procesos pendientes, cuántas personas están en llamada, en pruebas y en entrevista, lo ocurrido en los últimos 30 días (CV analizados, aceptados y rechazados por la IA, procesos cerrados, contrataciones) y la actividad reciente. El botón «Ver indicadores y reportes» lleva al detalle.

## Vacantes

### Crear y abrir una vacante

1. En «Vacantes», pulsa «Nueva vacante», llena los datos (nombre, departamento, ubicación, modalidad, tipo de contrato, número de plazas) y pulsa «Crear vacante». Queda como borrador.
2. Abre la vacante y cámbiale el estado con «Pasar a abierta» cuando empiece el reclutamiento. Los estados son: borrador, abierta, pausada, cerrada, cancelada y archivada.
3. «Editar datos» sirve para corregirla. El número de plazas limita cuántas personas se pueden contratar.

### Compartir

Con «Compartir» das acceso a otra persona, de dos formas:

| Tipo de acceso | Puede | No puede |
| --- | --- | --- |
| Lectura | Ver la vacante, los candidatos y los expedientes; descargar CV, Excel y ZIP; ver reportes | Cargar documentos, mover candidatos, registrar resultados |
| Colaboración | Todo lo anterior y, además, cargar documentos, evaluar CV, mover candidatos, hacer llamadas, registrar evaluaciones y resultados finales | Editar los datos de la vacante, cambiar su estado, compartirla |

Los documentos de psicometría y los estudios socioeconómicos son **datos sensibles**: aunque alguien tenga acceso a la vacante, solo los ve si además le das ese permiso adicional, en el apartado «Documentos sensibles» de la misma pantalla de compartir. Puedes quitar cualquier acceso cuando quieras; deja de ver la vacante en ese momento.

### Documentos

En el detalle de la vacante, «Cargar documento» admite PDF, DOCX, DOC, JPG y PNG de hasta 20 MB; para el perfil de puesto y el estudio socioeconómico admite además el formato de la empresa en Excel (XLSX). Eliges el tipo (CV, perfil del puesto, psicometría, prueba técnica, estudio socioeconómico o adjunto). Un CV en el formato DOC antiguo se guarda, pero la IA no puede leerlo: conviértelo a DOCX o PDF. El sistema rechaza archivos disfrazados o infectados y avisa si el documento ya estaba cargado. Los documentos se guardan en el servidor de la empresa; los sensibles, cifrados. Solo un administrador puede eliminar un documento, y debe dar el motivo.

## Perfil, prompt y evaluación de CV

Desde la vacante, pulsa «Perfil, prompt y evaluación de CV». Tiene tres pestañas.

### 1. Perfil del puesto

El perfil sigue el formato de la empresa «SGC.F15.RH. Perfil de puesto»: identificación del puesto, propósito, alcance y relaciones, requisitos, funciones, actividades con su periodicidad y KPI. La forma más rápida de llenarlo es «Subir formato del perfil»: eliges el formato en Excel y el sistema copia sus datos a cada campo, sin IA. La edad y el género que pide el formato no se copian, porque no se usan para evaluar a las personas candidatas; el sistema te avisa cuando el formato los trae. Si subes un PDF o un Word, o usas «Usar un documento ya cargado o pegar texto», el perfil lo lee la IA. En todos los casos es una propuesta: revísala, corrígela y pulsa «Guardar perfil». De cada requisito indispensable sale un criterio de la rúbrica con la que se revisan los CV.

### 2. Prompt de evaluación

Es la instrucción con la que la IA leerá los CV, con una rúbrica de criterios.

1. «Generar borrador desde el perfil» crea un criterio por cada requisito.
2. Ajusta los criterios, su peso y el umbral de aceptación. «Proponer mejoras con IA» sugiere mejor redacción para los criterios que ya existen; tú decides cuáles aplicar.
3. «Enviar a revisión» y después «Aprobar». Solo un prompt aprobado puede evaluar CV, y una vez aprobado no se modifica: para cambiarlo se usa «Duplicar» y se aprueba la copia.

### 3. Evaluación de CV

1. Carga los CV en los documentos de la vacante.
2. Pulsa «Evaluar N CV». El lote se procesa en segundo plano; puedes seguir trabajando.
3. Al terminar, cada CV queda como **aceptado por IA**, **rechazado por IA** o **no evaluable** (por ejemplo, un archivo ilegible), con una calificación de 0 a 100, el nivel alcanzado en cada criterio y la evidencia tomada del propio CV.
4. Descarga «Reporte_Evaluacion.xlsx» y los ZIP de aceptados, rechazados y no evaluables.

Qué conviene saber:

- La calificación **la calcula el sistema** con los niveles que la IA asigna a cada criterio; la IA no pone el número final.
- Los CV escaneados se leen con reconocimiento de texto. Si un escaneo sale mal, quedará como no evaluable.
- Antes de enviar un CV a la IA se ocultan correos y teléfonos.
- Volver a evaluar no borra la evaluación anterior.
- Si el proveedor de IA falla, el lote se detiene y puedes usar «Reintentar» o «Reanudar».

## Candidatos y etapas

Desde la vacante, «Candidatos y etapas». Las personas evaluadas entran solas a la etapa «Revisión local RH» con la clasificación inicial de la IA. También puedes dar de alta a alguien a mano.

### Mover de etapa

Selecciona a una o varias personas y pulsa «Mover de etapa». Se pide motivo cuando:

- regresas a alguien a una etapa anterior,
- te saltas una etapa obligatoria,
- avanzas a alguien que la IA clasificó como rechazado o no evaluable.

Esto último está permitido a propósito: la clasificación de la IA es una ayuda, no un veto. Queda registrado que fue una decisión tuya.

### Expediente de la persona

Al pulsar el nombre se abre su expediente: datos de contacto, evaluación del CV, permanencia en empleos anteriores, historial de movimientos, llamadas, evaluaciones posteriores, resultado final y, por etapa, qué fuentes de información tiene.

### Llamadas telefónicas

1. En «Bancos» (menú) crea un banco de preguntas con «Nuevo banco»; «Proponer preguntas con IA» sugiere preguntas a partir del perfil de una vacante. Los bancos pueden ser privados o compartidos y guardan sus versiones.
2. En el expediente, «Nueva llamada» → elige el banco → «Abrir llamada».
3. Captura cada respuesta o márcala como no realizada, y pulsa «Guardar».
4. «Analizar con IA» resume lo que aportó la llamada y señala diferencias con el CV por aclarar. No recomienda contratar ni descartar.
5. «Cerrar llamada» la deja fija. Puede haber varias llamadas por persona.

### Evaluaciones posteriores

En el expediente, «Registrar evaluación»:

- **Psicometría.** Instrumento, fecha, estado, documento y resultado. Para marcarla como validada hay que indicar qué profesional la interpretó. La IA puede resumir el documento, pero no diagnostica ni declara a nadie apto o no apto.
- **Entrevista con gerente.** Recursos Humanos captura las preguntas, respuestas, competencias observadas y la conclusión del gerente. Marcarla como realizada exige esa conclusión. «Organizar con IA» ordena lo capturado sin cambiar la conclusión.
- **Prueba técnica.** Opcional. Con la rúbrica («Agregar criterio») el sistema calcula la calificación. Si el puesto no la requiere, regístrala como «no aplica».
- **Estudio socioeconómico.** Se llena sobre un formulario definido por el administrador. La plantilla inicial es el formato de la empresa «SGC.F3.RH. Estudio socioeconómico», con sus tablas (formación académica, familiares, contactos de emergencia). «Leer el formulario escaneado con IA» propone los valores de cada campo a partir del formato lleno (escaneado, en PDF, Word o Excel); entran marcados como leídos por IA y **sin verificar** hasta que una persona los revise. **Fotografías.** En los campos de fotografía (higiene, localización, fachada) eliges una foto ya cargada o pulsas «Adjuntar foto o archivo» para subirla ahí mismo (JPG o PNG). Con la foto elegida, «Describir con IA» propone un texto con lo que se observa en la imagen; revísalo, corrígelo y guarda el estudio. La IA describe solo lo que se ve: no opina sobre la persona ni califica la vivienda, y la foto se le envía reducida y sin fecha ni ubicación. El dictamen, los niveles, el «score total» y la viabilidad los anotas tú: la IA no los llena y el sistema no los calcula ni los usa para ordenar candidatos.

«Generar síntesis» ordena todo el expediente en hechos documentados, declaraciones, observaciones humanas, resultados técnicos, información pendiente y diferencias por aclarar. No produce una calificación global ni una recomendación.

### Resultado final

Cuando el proceso de una persona termina, pulsa «Registrar resultado final» y elige:

| Resultado | Cuándo usarlo |
| --- | --- |
| Contratado | Se le contrata. Puedes anotar la fecha de incorporación |
| No contratado | Terminó el proceso y no fue elegida |
| Desistió | La persona se retiró |
| No localizado | No fue posible contactarla |
| Vacante cancelada | El puesto ya no se cubrirá |
| Otro cierre | Cualquier otro motivo |

Todos piden motivo, salvo la contratación. No se puede contratar a más personas que plazas tiene la vacante: si se abrió otra plaza, primero actualiza la vacante. Con resultado final la persona ya no se mueve de etapa. Si hubo un error o la situación cambió, «Reabrir proceso» lo deshace: pide motivo y el resultado anterior queda anulado, a la vista, sin borrarse.

## Indicadores

Menú «Indicadores». Tiene tres secciones:

- **Tablero.** Elige el periodo (30 días, 90 días, 12 meses o todo) y, si quieres, filtra por vacante, departamento, responsable, colaborador o estado. Verás la fotografía de hoy, los totales del periodo, el embudo por etapa (cuántas personas llegaron a cada una y qué porcentaje pasó a la siguiente), el tiempo promedio en cada etapa, el tiempo de cobertura y el detalle por vacante y por mes.
- **Histórico de candidatos.** Lista de postulaciones con más filtros: candidato, etapa, resultado final, clasificación y calificación de la IA, modelo, versión del prompt y banco de preguntas. Puedes elegir qué fecha se compara con el periodo: la de carga del CV, la de evaluación, la de algún movimiento o la de cierre.
- **Reportes generados.** Los Excel que has descargado.

«Descargar en Excel» genera el reporte con los filtros aplicados. Los reportes se guardan en el servidor. Si dejas de tener acceso a alguna vacante incluida en un reporte, ya no podrás descargarlo: genera uno nuevo.

Las fechas se cuentan en la hora de Ciudad de México.

## Preguntas frecuentes

**No veo una vacante que antes veía.** Te quitaron el acceso o la vacante se transfirió a otra persona. Pídeselo a quien la lleva.

**La IA rechazó a alguien que me interesa.** Avánzalo de etapa escribiendo el motivo. Es tu decisión.

**Un lote de CV se quedó a medias.** Entra a la pestaña «Evaluación de CV» y usa «Reanudar» o «Reintentar». Si aparece el aviso de que se alcanzó el límite mensual de IA, avisa al administrador.

**Me equivoqué al registrar un resultado final.** Usa «Reabrir proceso» y regístralo de nuevo. Ambos pasos quedan en el historial.

**No puedo abrir un reporte de psicometría.** Es un dato sensible: necesitas el permiso adicional, además del acceso a la vacante.

**Voy a dejar la empresa o cambio de área.** El administrador transfiere tus vacantes a otra persona. No se pierde nada: candidatos, documentos e historial siguen en la vacante.
