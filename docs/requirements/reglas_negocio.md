# Reglas de negocio

> Origen: propuesta de arquitectura aprobada el 10 de noviembre de 2026.
> Este archivo es la copia de trabajo del repositorio y se actualiza en cada fase.

## 19. Arquitectura de procesamiento documental

Cada CV avanza por 12 pasos y cada paso guarda su estado en SQL Server. Un fallo detiene ese CV en su paso, no el lote, y el original ya está a salvo.

| Paso | Qué hace | Si falla |
| --- | --- | --- |
| 1. Recibir | Escribe el archivo en la zona temporal | Se informa al usuario; no queda nada a medias |
| 2. Validar | Formato, tipo real, tamaño, estructura y antivirus | `RECHAZADO` con motivo |
| 3. Guardar original | Movimiento atómico y confirmación | Protocolo recuperable de la sección 8 |
| 4. Calcular hash | SHA-256 del original | Se recalcula |
| 5. Detectar duplicados | Mismo hash en la convocatoria | Se vincula y se reporta; no se evalúa dos veces |
| 6. Extraer texto | PyMuPDF para PDF, python-docx para DOCX, conversión aislada para DOC | Pasa a OCR o queda `NO_EVALUABLE` |
| 7. OCR | Solo si el archivo no trae texto útil; guarda el nivel de confianza | `NO_EVALUABLE`; nunca penaliza al candidato |
| 8. Normalizar | Secciones, fechas y permanencia laboral calculada en Python | Se marcan fechas incompletas |
| 9. Análisis IA | Extracción y nivel por criterio con evidencia | Reintentos; después incidencia |
| 10. Validar JSON | Esquema estricto | Un reintento; después `NO_EVALUABLE` |
| 11. Puntuar y clasificar | Cálculo ponderado en Python y umbral; calidad documental aparte | Error de cálculo detiene el CV |
| 12. Guardar y generar | Resultados, Excel, ZIP y actualización de indicadores | La exportación se puede regenerar |

**Estados de los trabajos.** Lotes y elementos usan `PENDIENTE`, `EN_COLA`, `PROCESANDO`, `COMPLETADO`, `COMPLETADO_CON_INCIDENCIAS`, `FALLIDO` y `CANCELADO`.

**Idempotencia y recuperación.** Cada tarea se identifica por elemento y paso; repetir un paso ya completado no hace nada. Los errores transitorios se reintentan hasta tres veces con espera creciente. Al reiniciar, un proceso de barrido vuelve a encolar lo que quedó en `PROCESANDO`. Si se pierde Redis, la cola se reconstruye desde SQL Server.

**Permanencia laboral.** Python calcula duración por empleo, promedio, mediana, total documentado, superposiciones y fechas incompletas. Es información para RH y no entra en ninguna regla de rechazo.

**Exportaciones.** Los ZIP llevan los archivos originales con un consecutivo delante del nombre para evitar colisiones, más un manifiesto con hash y clasificación. Las celdas de Excel que empiezan con `=`, `+`, `-` o `@` se neutralizan. Cada exportación guarda identificador, fecha y hash, y se puede volver a descargar mientras su conservación esté autorizada.

**Otros flujos.** El análisis de perfiles, la digitalización de estudios, el resumen de pruebas y la síntesis de expedientes usan el mismo mecanismo de tareas, estados e incidencias.

## 20. Versionado y auditoría

Todo lo que influye en una evaluación se versiona y lo aprobado no se modifica. Cada acción relevante deja un evento de auditoría que solo admite inserción.

| Qué se versiona | Cómo | Qué queda fijo |
| --- | --- | --- |
| Perfil de puesto | Cada corrección crea una versión | El prompt indica de qué versión nació |
| Prompt | Borrador, en revisión, aprobado, archivado; lo aprobado es inmutable | Cada lote guarda su versión |
| Rúbrica y umbral | Versión nueva ante cualquier cambio de criterio o peso | Cada evaluación guarda su versión |
| Flujo de etapas | Plantilla con versiones | Cada convocatoria usa la versión con la que se abrió |
| Banco de preguntas | Editar o quitar preguntas crea una versión | Cada llamada guarda la versión usada |
| Plantilla de estudio | Versión nueva ante cualquier cambio de campos | Cada estudio guarda su versión |
| Evaluación de CV | Solo inserción; un reanálisis crea otra evaluación | La original siempre se puede consultar |
| Archivo | Versiones con su propio hash | El original nunca se sobrescribe |

**Auditoría.** Se registran los 15 tipos de evento del documento maestro: inicios de sesión, accesos denegados, altas, activaciones y bajas, comparticiones, revocaciones, transferencias, creación de vacantes, movimientos, cargas, evaluaciones, descargas, cambios de configuración, exportaciones y cierres. Cada evento guarda fecha en UTC, actor, acción, recurso, vacante, resultado, dirección IP e identificador de correlación. El acceso a documentos sensibles guarda además la finalidad declarada.

**Observabilidad.** Logs estructurados con un identificador de correlación que viaja de la API al worker y a la llamada de IA. Hay puntos de salud que comprueban SQL Server, Redis y el disco, y métricas de cola, duración de tareas, errores de IA, costo y espacio libre. Los logs no contienen claves, contraseñas ni contenido de documentos.
