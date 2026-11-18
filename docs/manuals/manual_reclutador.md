# Manual del reclutador

Para quien lleva vacantes y candidatos. Explica qué puedes hacer en cada pantalla, en el orden en que normalmente se usa. Los nombres entre comillas son los que aparecen en pantalla.

> Este manual describe el sistema tal como está construido. Todavía no se ha usado con datos reales: si algo no coincide con lo que ves, avisa.

## Lo esencial

- **Entras con tu correo y la contraseña que te dio el administrador.** No hay recuperación por correo: si la olvidas, el administrador te pone una nueva. Tras cinco intentos fallidos la cuenta se bloquea quince minutos.
- **Solo ves tus vacantes y las que te compartieron.** Las de otras personas no aparecen ni en listas, ni en reportes, ni escribiendo su dirección a mano.
- **La IA propone y resume; tú decides.** Clasifica los CV y ordena información, pero avanzar, descartar o contratar a alguien lo registra siempre una persona, con su nombre.
- **Nada se borra al avanzar.** Cada cambio queda en el historial del candidato.
- La sesión dura doce horas: no se cierra por dejar de usar el sistema un rato. A las doce horas hay que volver a entrar. Si te levantas de la computadora, usa «Cerrar sesión» o bloquea el equipo, porque la sesión queda abierta.

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

Quien recibe la vacante ve **todo su contenido**, también las pruebas psicométricas, los estudios socioeconómicos y la recomendación de la IA; lo mismo los administradores. Antes hacía falta un permiso adicional por persona: desde el 18 de noviembre de 2026 ya no, por decisión de la dirección. Tenlo presente al compartir. Puedes quitar cualquier acceso cuando quieras; la persona deja de ver la vacante en ese momento.

### Documentos

En el detalle de la vacante, «Cargar documento» admite PDF, DOCX, DOC, JPG y PNG de hasta 20 MB; para el perfil de puesto y el estudio socioeconómico admite además el formato de la empresa en Excel (XLSX). Eliges el tipo (CV, perfil del puesto, psicometría, prueba técnica, estudio socioeconómico o adjunto). Un CV en el formato DOC antiguo se guarda, pero la IA no puede leerlo: conviértelo a DOCX o PDF. El sistema rechaza archivos disfrazados o infectados y avisa si el documento ya estaba cargado. Los documentos se guardan en el servidor de la empresa; los sensibles, cifrados. Solo un administrador puede eliminar un documento, y debe dar el motivo.

## Perfil, prompt y evaluación de CV

Al abrir una vacante, arriba del panel está «Pasos de la vacante»: los cuatro pasos en orden (perfil de puesto, prompt de evaluación, cargar y evaluar CV, candidatos y etapas), cómo va cada uno y, resaltado, el que sigue. Pulsa un paso para abrir su pantalla. Los tres primeros son las tres pestañas de «Perfil y evaluación».

### 1. Perfil del puesto

El perfil sigue el formato de la empresa «SGC.F15.RH. Perfil de puesto»: identificación del puesto, propósito, alcance y relaciones, requisitos, funciones, actividades con su periodicidad y KPI. La forma más rápida de llenarlo es «Subir formato del perfil»: eliges el formato en Excel y el sistema copia sus datos a cada campo, sin IA. La edad y el género que pide el formato no se copian, porque no se usan para evaluar a las personas candidatas; el sistema te avisa cuando el formato los trae. Si subes un PDF o un Word, o usas «Usar un documento ya cargado o pegar texto», el perfil lo lee la IA. En todos los casos es una propuesta: revísala, corrígela y pulsa «Guardar perfil». De cada requisito indispensable sale un criterio de la rúbrica con la que se revisan los CV.

### 2. Prompt de evaluación

Es la instrucción con la que la IA leerá los CV, con una rúbrica de criterios.

1. «Generar borrador desde el perfil» crea un criterio por cada requisito.
2. Ajusta los criterios, su peso y el umbral de aceptación. **Nada de lo que cambies cuenta hasta que pulses «Guardar cambios»**: mientras tanto el prompt sigue siendo el anterior, y la pantalla lo avisa con «Tienes cambios sin guardar». «Enviar a revisión» guarda antes lo que tengas en pantalla, para que lo que se revisa y se aprueba sea lo que estás viendo. Si cierras la pantalla o cambias de versión sin guardar, los cambios se pierden. **Para la calificación cuenta el peso**, no el tipo: al generar el borrador, los criterios indispensables salen con peso 3 y los deseables con peso 1, y al cambiar el tipo el peso cambia con él (salvo que ya le hayas puesto un peso propio, que se respeta). Los pesos son relativos: si quitas criterios, los que quedan se reparten el total. La IA solo califica lo que está en la rúbrica: si quieres que valore algo más (por ejemplo, cuánto tiempo permaneció la persona en sus empleos), agrégalo como criterio con «Agregar criterio» y describe sus niveles. «Proponer mejoras con IA» sugiere mejor redacción para los criterios que ya existen; tú decides cuáles aplicar. La IA trabaja sobre lo último guardado: si quitaste o cambiaste criterios, pulsa antes «Guardar cambios». Cada mejora sigue a su criterio aunque cambie de número (si quitas criterios, el antiguo C10 puede pasar a ser el C7 y la mejora dirá «Aplicar a C7»); las mejoras de criterios que ya quitaste dejan de mostrarse.
3. «Enviar a revisión» y después «Aprobar». Solo un prompt aprobado puede evaluar CV, y una vez aprobado no se modifica: para cambiarlo se usa «Duplicar» y se aprueba la copia.

### 3. Evaluación de CV

1. En «Cargar CV», elige los archivos: puedes seleccionar varios a la vez (hasta 100 por carga). Si alguno no entra, la pantalla dice cuál y por qué. También siguen sirviendo los que subas en los documentos de la vacante con el tipo CV.
2. Antes de evaluar puedes abrir «Ver el prompt con el que se evaluarán los CV»: muestra el texto exacto que recibe la IA con cada currículum (las instrucciones con la rúbrica y el mensaje que acompaña al CV). En el editor del prompt hay una vista previa igual para cada versión.
3. Pulsa «Evaluar N CV». El lote se procesa en segundo plano; puedes seguir trabajando.
3. Al terminar, cada CV queda como **aceptado por IA**, **rechazado por IA** o **no evaluable** (por ejemplo, un archivo ilegible), con una calificación de 0 a 100, el nivel alcanzado en cada criterio y la evidencia tomada del propio CV.
4. Descarga «Reporte_Evaluacion.xlsx» y los ZIP de aceptados, rechazados y no evaluables.
5. «Ver candidatos y etapas» te lleva a las personas evaluadas para seguir el proceso.

Qué conviene saber:

- La calificación **la calcula el sistema** con los niveles que la IA asigna a cada criterio; la IA no pone el número final.
- Los CV escaneados se leen con reconocimiento de texto. Si un escaneo sale mal, quedará como no evaluable.
- Antes de enviar un CV a la IA se ocultan correos y teléfonos.
- **Volver a evaluar** (porque aprobaste un prompt nuevo o marcaste «Volver a evaluar también los ya evaluados») no duplica candidatos: cada persona muestra el **resultado más reciente** de su CV y en su historial queda anotado el anterior («La IA volvió a evaluar el CV: antes…; ahora…»). Nadie cambia de etapa por esto. Las personas cuya postulación ya está cerrada (contratadas, no contratadas, desistieron) conservan la evaluación con la que se decidió. Los resultados de cada lote anterior siguen disponibles en su lote.
- Si el proveedor de IA falla, el lote se detiene y puedes usar «Reintentar» o «Reanudar».

## Candidatos y etapas

Desde la vacante, el paso 4, «Candidatos y etapas» (o el botón «Ver candidatos y etapas» al terminar de evaluar los CV). Las personas evaluadas entran solas a la etapa «Revisión local RH» con la clasificación de la IA. También puedes dar de alta a alguien a mano.

### Mover de etapa

Selecciona a una o varias personas y pulsa «Mover de etapa». Se pide motivo cuando:

- regresas a alguien a una etapa anterior,
- te saltas una etapa obligatoria,
- avanzas a alguien que la IA clasificó como rechazado o no evaluable.

Esto último está permitido a propósito: la clasificación de la IA es una ayuda, no un veto. Queda registrado que fue una decisión tuya.

### Expediente de la persona

Al pulsar el nombre se abre su expediente: datos de contacto, evaluación del CV, permanencia en empleos anteriores, historial de movimientos, llamadas, evaluaciones posteriores, resultado final y, por etapa, qué fuentes de información tiene.

### Llamadas telefónicas

1. En «Bancos» (menú) crea un banco de preguntas con «Nuevo banco»; «Proponer preguntas con IA» sugiere preguntas a partir del perfil de una vacante. Los bancos pueden ser privados o compartidos y guardan sus versiones. En cada pregunta puedes anotar **qué se espera de la respuesta**: con eso la IA mide después la llamada. Si marcas «Preguntas generales de la empresa», ese banco se agrega solo a todas las llamadas de todo el equipo, y cualquier reclutador o administrador puede modificarlo; cada cambio queda como una versión nueva.
2. En el expediente, «Nueva llamada». Las **preguntas generales de la empresa** (las que se hacen a todas las personas) entran solas, sin elegirlas. Si quieres, marca además uno o varios bancos para sumar sus preguntas; también puedes no marcar ninguno. «Abrir llamada».
3. **Ajusta las preguntas de esta llamada.** Cada llamada tiene su propia lista y lo que cambies aquí **no modifica los bancos**:
   - **Quitar.** «Quitar» saca una pregunta que no aplica. Pasa a «Quitadas de esta llamada», de donde la recuperas con «Volver a incluir». Una pregunta quitada no se pregunta, no se analiza y no cuenta para cerrar. Es distinto de «No se realizó», que es para una pregunta que sí tocaba y no se alcanzó a hacer.
   - **Cambiar la redacción.** «Cambiar redacción» te deja reescribir la pregunta solo para esta llamada. Queda marcada como «Redacción cambiada», se muestra la redacción del banco y puedes volver a ella.
   - **Escribir una pregunta.** En «Agregar preguntas a esta llamada», «Escribir una pregunta» agrega una que existe solo en esta llamada (marcada «Solo de esta llamada»). Puedes anotar qué se espera de la respuesta para que la IA la mida.
   - **Tomar de un banco.** «Tomar de un banco» muestra las preguntas de cualquiera de tus bancos; marcas las que quieras y «Agregar las elegidas». Las que ya están en la llamada no se repiten.
   Cada pregunta indica de dónde viene: «General», el nombre de su banco o «Solo de esta llamada». Una llamada admite hasta 80 preguntas.
4. Captura cada respuesta o márcala como no realizada, y pulsa «Guardar». Los cambios en las preguntas se guardan con ese mismo botón.
5. «Analizar con IA» resume lo que aportó la llamada y señala diferencias con el CV por aclarar. No recomienda contratar ni descartar. Trabaja con las preguntas que quedaron en la llamada y con su redacción. Además muestra la **cobertura de la llamada**: en cada pregunta contestada que tenía anotado qué se espera, indica si la respuesta lo cubre, lo cubre en parte o no lo cubre, con la frase en que se basa, y un número de 0 a 100 que calcula el sistema. Mide qué tanto se cubrió lo esperado en la llamada; no es una calificación de la persona. Si después del análisis quitas, agregas o cambias preguntas, el análisis se retira al guardar (porque numera las preguntas) y hay que pedirlo de nuevo.
6. «Cerrar llamada» la deja fija, con las preguntas que se hicieron y, aparte, las que no se usaron. Puede haber varias llamadas por persona.

### Evaluaciones posteriores

En el expediente, «Registrar evaluación»:

- **Psicometría.** Instrumento, fecha, estado, documento y resultado. El reporte se adjunta ahí mismo con «Adjuntar archivo». Para marcarla como validada hay que indicar qué profesional la interpretó. «Resumir e interpretar con IA» trabaja sobre el reporte, que ya viene interpretado por un profesional: lo resume, lista los resultados tal como aparecen, **explica en lenguaje claro qué significa cada uno según el propio reporte** y propone preguntas para la siguiente etapa. Si el reporte no explica un resultado, la IA lo dice y remite al profesional en lugar de adivinar. No diagnostica ni declara a nadie apto o no apto.
- **Preguntas para la siguiente etapa.** Además de la síntesis, las proponen los análisis de la psicometría, la prueba técnica y las referencias (la llamada y la entrevista ya traían sus preguntas de seguimiento). Tratan del puesto y de situaciones de trabajo; nunca de edad, estado civil, hijos, salud ni situación económica o familiar. Del estudio socioeconómico no se generan preguntas, por tratarse de datos familiares y económicos.
- **Entrevista con gerente.** Recursos Humanos captura las preguntas, respuestas, competencias observadas y la conclusión del gerente. Marcarla como realizada exige esa conclusión. «Organizar con IA» ordena lo capturado sin cambiar la conclusión.
- **Prueba técnica.** Opcional. Con la rúbrica («Agregar criterio») el sistema calcula la calificación. Si el puesto no la requiere, regístrala como «no aplica».
- **Estudio socioeconómico.** Se llena sobre un formulario definido por el administrador. La plantilla inicial es el formato de la empresa «SGC.F3.RH. Estudio socioeconómico», con sus tablas (formación académica, familiares, contactos de emergencia). El formato lleno (Excel, PDF, Word o escaneado) se adjunta en el propio estudio con «Adjuntar archivo», y «Leer el formato con IA» propone los valores de cada campo a partir de él; entran marcados como leídos por IA y **sin verificar** hasta que una persona los revise. **Fotografías.** En los campos de fotografía (higiene, localización, fachada) eliges una foto ya cargada o pulsas «Adjuntar foto o archivo» para subirla ahí mismo (JPG o PNG). Con la foto elegida, «Describir con IA» propone un texto con lo que se observa en la imagen; revísalo, corrígelo y guarda el estudio. La IA describe solo lo que se ve: no opina sobre la persona ni califica la vivienda, y la foto se le envía reducida y sin fecha ni ubicación. Las descripciones que guardes aparecen después en la síntesis del expediente y en el Excel de postulaciones, pero solo para quienes tienen el permiso del estudio socioeconómico; el resto del estudio no sale de él. El dictamen, los niveles, el «score total» y la viabilidad los anotas tú: la IA no los llena y el sistema no los calcula ni los usa para ordenar candidatos. **Fotografías adicionales.** Debajo de las fotografías del formato puedes agregar hasta 20 más, varias a la vez, cada una con su título y su descripción (que la IA puede proponer). Entran a la síntesis y al reporte igual que las del formato.

- **Descargar el estudio en el formato de la empresa.** Dentro del estudio, «Descargar en el formato de la empresa (Excel)» baja el formato SGC.F3.RH, el mismo archivo de la empresa, con los datos capturados ya puestos en su lugar: datos de identificación, casillas marcadas, tablas, economía, salud, contactos, dictamen, niveles, firmas, la ubicación y las fotografías del formato (localización, fachada e higiene) dentro de su recuadro. Tres cosas que conviene saber: (1) usa **lo último guardado**, así que guarda antes de descargar; (2) las fotografías adicionales no forman parte del formato oficial y se quedan en el sistema; (3) si algún dato no encontró lugar (por ejemplo, más familiares que renglones tiene la tabla), el sistema te avisa cuáles fueron para que los anotes a mano. Si aparece «Todavía no se ha cargado el formato en blanco de la empresa», pídele a un administrador que lo suba en «Formularios»; se hace una sola vez. El sistema no agrega ni calcula nada: el archivo lleva solo lo que una persona capturó o verificó. Cada descarga queda en la auditoría.

- **Referencias laborales y personales.** No tienen etapa propia: se registran en cualquier momento, antes o después del estudio socioeconómico, y las puede capturar tanto Recursos Humanos como el analista de estudios. «Agregar referencia» y, en cada una: si es laboral o personal, nombre, empresa o relación, puesto, teléfono, periodo, quién la contactó y cuándo, el resultado del contacto (pendiente, contactada, no se localizó, se negó) y **lo que dijo**, tal como lo dijo. Para marcarlas como completadas, ninguna puede quedar pendiente. «Analizar con IA» resume lo que dijo cada referencia y compara las laborales con los empleos del CV: qué coincide, qué no cuadra y qué quedó sin confirmar. No califica ni recomienda; lo que dice una referencia es su opinión, no un hecho comprobado. A la IA no se le envían el nombre ni el teléfono de las referencias.

**Puntos de atención.** Cada análisis de la IA (llamada, psicometría, prueba técnica, entrevista y referencias) trae ahora una lista de «Puntos de atención (generado por IA)»: lo que salió bajo, desfavorable o sin resolver, con el dato en que se basa. Es un aviso para revisar, no un veredicto.

**Escalas de la prueba psicométrica.** Al pulsar «Resumir e interpretar con IA», la IA recibe el texto del reporte y también la imagen de sus páginas, para leer el nivel que marca cada gráfica o aguja (por ejemplo, 3 de 5). El resumen muestra «Escalas leídas del reporte» con el número, la frase del reporte y su lectura (favorable, intermedia o desfavorable). Bajo no siempre es malo: en robo o uso de sustancias lo favorable es una tendencia baja; en lealtad u honestidad, una alta. El sistema comprueba que el número leído coincida con la frase; si no coinciden, la escala aparece en «Revisar en el reporte» y no se usa. **Compruébalo siempre contra el documento**: la IA puede leer mal una gráfica. La IA no diagnostica: dice «el reporte ubica la escala en…», nunca que la persona tiene o hace algo.

**Recomendación de la IA.** «Generar síntesis» da además una recomendación en palabras: **recomendable, recomendable con reservas o no recomendable**, con su conclusión y sus razones, cada una con la fuente. También reúne los puntos de atención de todas las etapas y los **contrastes**: cuando dos fuentes no coinciden (lo que dijo la persona, su prueba, una fotografía), dice qué dice cada una y cierra con su conclusión. Siempre aparece marcada «Generado por IA. No es una decisión»: no mueve a nadie de etapa, no descarta ni contrata, y no calcula ninguna puntuación global. Cuentan el CV, las llamadas, las pruebas, la entrevista, las referencias, la prueba psicométrica presentada (aunque no la haya validado un profesional) y las fotografías del estudio, estas últimas solo por lo que sus descripciones dicen de orden y organización; nunca por el tipo de vivienda, la zona, los recursos o la familia.

«Generar síntesis» ordena todo el expediente en hechos documentados, declaraciones, observaciones humanas, resultados técnicos, información pendiente y diferencias por aclarar, y añade **preguntas sugeridas para la siguiente etapa** (hasta seis, para aclarar lo que quedó pendiente). Además relaciona las etapas entre sí: **«Qué aportó cada etapa frente a las anteriores»** (una línea por etapa: qué añadió, qué confirma de lo anterior y qué deja abierto) y **«Coincidencias entre fuentes»** (dónde dos fuentes dicen lo mismo, citando ambas). Es un razonamiento con los datos del expediente para ayudarte a decidir: describe, no valora. De la psicometría solo relaciona la interpretación del profesional, y nunca relaciona las fotografías del estudio ni datos económicos o familiares. No produce una calificación global ni una recomendación.

La síntesis **se actualiza sola** cuando, con el expediente abierto, cierras una llamada o registras el resultado de una evaluación; abrir el expediente no consulta a la IA. Cada síntesis queda guardada: en «Síntesis guardadas» puedes abrir las anteriores para ver cómo fue cambiando el análisis.

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

**«No viable».** Si decides que una persona no sigue, pulsa «No viable» y escribe el motivo. El sistema cierra su proceso como «No contratado», anota en qué etapa se quedó y la IA redacta el **análisis de cierre**: hasta dónde llegó, qué mostró en cada etapa, los puntos de atención y cómo se relaciona tu motivo con el expediente. Queda guardado en el expediente, marcado como generado por IA. La decisión es tuya: la IA solo la documenta. Si la IA falla en ese momento, el cierre queda hecho y puedes pedir el análisis después con «Generar análisis de cierre». «Reabrir proceso» lo deshace.

Todos piden motivo, salvo la contratación. No se puede contratar a más personas que plazas tiene la vacante: si se abrió otra plaza, primero actualiza la vacante. Con resultado final la persona ya no se mueve de etapa. Si hubo un error o la situación cambió, «Reabrir proceso» lo deshace: pide motivo y el resultado anterior queda anulado, a la vista, sin borrarse.

## Si tu puesto es analista de estudios socioeconómicos

Al entrar verás solo «Estudios»: la lista de personas en proceso de todas las vacantes, con el estado de su estudio y de sus referencias. Puedes buscar por persona o por vacante.

1. Abre a la persona. Si no tiene estudio, «Registrar evaluación» lo crea con el formato de la empresa.
2. Captura el formato. Con «Adjuntar archivo» subes el formato lleno y «Leer el formato con IA» te propone los datos de cada campo. Con «Adjuntar foto o archivo» subes las fotografías que pide el formato, y en «Fotografías adicionales» agregas las demás (hasta 20, varias a la vez), cada una con su título. «Describir con IA» te propone la descripción de cada foto, que tú revisas.
3. Anota el dictamen y guarda. Cuando esté terminado, cambia el estado a «Completado».
4. Para tener el estudio en el formato de la empresa, pulsa «Descargar en el formato de la empresa (Excel)». Se explica abajo, en «Descargar el estudio en el formato de la empresa».
5. Para las referencias, «Registrar evaluación» → «Referencias laborales y personales». Captura cada referencia y lo que dijo, guarda y, si quieres, pulsa «Analizar con IA» (se explica arriba, en «Evaluaciones posteriores»).

No verás el CV ni el resto del expediente: tu puesto solo da acceso a los estudios y a las referencias. El análisis de referencias sí menciona los empleos del CV (puesto, empresa y periodo), porque sirve para compararlos. La reclutadora responsable y los administradores ven el estudio que captures.

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

**No puedo abrir un reporte de psicometría.** Lo ve quien tiene la vacante compartida. Si no la ves, pide a su responsable que te la comparta.

**Voy a dejar la empresa o cambio de área.** El administrador transfiere tus vacantes a otra persona. No se pierde nada: candidatos, documentos e historial siguen en la vacante.
