# Requisitos funcionales

> Origen: propuesta de arquitectura aprobada el 10 de noviembre de 2026.
> Este archivo es la copia de trabajo del repositorio y se actualiza en cada fase.

## 18. Flujo funcional de reclutamiento

La IA clasifica, extrae y resume; cada avance de etapa y el resultado final los registra una persona.

1. El administrador crea usuarios y configura proveedores de IA.
2. El reclutador crea la vacante, que nace privada, y abre una convocatoria. Puede compartirla.
3. Carga el perfil de puesto. La IA extrae su estructura y marca requisitos ambiguos; el reclutador corrige y se guarda una versión.
4. La IA propone el prompt en diez capas y la rúbrica. El responsable los edita, fija el umbral y los aprueba.
5. Carga los CV en bloque. El lote queda atado a las versiones aprobadas.
6. El worker procesa cada CV y lo clasifica como `ACEPTADO_IA`, `RECHAZADO_IA` o `NO_EVALUABLE`.
7. Se generan `Reporte_Evaluacion.xlsx`, `Aceptados.zip` y `Rechazados.zip`.
8. RH descarga ambos ZIP, revisa todos los CV y decide quién avanza, incluidos los rechazados por la IA. La evaluación original no cambia.
9. Llamada telefónica con un banco de preguntas; se guardan respuestas y análisis.
10. Pruebas psicométricas: registro, documento y validación profesional.
11. Entrevista con gerente, capturada por RH.
12. Prueba técnica, o marca de `NO_APLICA`.
13. Estudio socioeconómico: formulario, digitalización y verificación humana.
14. El expediente acumula todo y ofrece una síntesis con sus fuentes.
15. Un usuario autorizado registra el resultado final y, si aplica, la contratación.
16. Dashboards e histórico reflejan el proceso.

En cualquier etapa se puede retroceder, reprogramar, cancelar, registrar desistimiento o incidencia y omitir lo que no aplique. El historial conserva cada movimiento.

| Etapa | Qué hace la IA | Qué decide la persona | Qué no hace la IA |
| --- | --- | --- | --- |
| CV | Extrae datos y asigna nivel por criterio con evidencia | Quién avanza | No inventa datos, no infiere atributos sensibles, no rechaza por permanencias cortas |
| Llamada | Analiza el contenido de las respuestas y sugiere seguimiento | El avance | No infiere emociones, honestidad ni personalidad; no afirma que alguien mintió |
| Psicometría | Extrae y resume resultados documentados | Validación profesional y avance | No diagnostica ni declara aptitud |
| Entrevista | Ordena y resume lo capturado | La conclusión del entrevistador | No sustituye su decisión |
| Estudio | Lee formularios y señala faltantes o texto ilegible | Qué dato queda verificado | No puntúa condición económica, domicilio ni familia; no infiere nada de fotografías |
| Expediente | Sintetiza separando hechos, declaraciones, observaciones y pendientes | La lectura del conjunto | No genera un índice global de idoneidad |
| Cierre | Nada | El resultado final | No decide contrataciones |

## 17. Diseño de las pantallas

Las 8 maquetas ya diseñadas cubren 11 de las 26 pantallas obligatorias; las 15 restantes siguen el mismo sistema visual y se diseñan antes de construir cada fase. Las maquetas están en el [lienzo de diseño](https://claude.ai/artifact/4SaJ7B7sVDEMFKuAKxhoZZ).

| Pantalla | Contenido principal | Diseño |
| --- | --- | --- |
| Inicio de sesión | Correo y contraseña | Hecho (construida) |
| Dashboard | Indicadores, embudo por etapa, actividad y pendientes | Hecho |
| Mis vacantes | Lista con estado, colaboradores, posiciones y candidatos | Hecho |
| Vacantes compartidas | Lista con responsable y tipo de acceso | Hecho, en la misma pantalla |
| Administración de vacantes | Alta y edición, estados, convocatorias | Pendiente |
| Compartir vacante | Colaboradores, tipo de acceso, permisos de documentos sensibles | Hecho, como panel lateral |
| Transferir vacante | Transferencia individual y asistente de transferencia masiva | Pendiente |
| Usuarios | Alta con contraseña, rol, restablecer contraseña, baja y reactivación | Hecho (construida) |
| Perfiles | Carga, extracción con IA, corrección humana y versiones | Pendiente |
| Generador de prompts | Diez capas, avisos de calidad, versiones y aprobación | Hecho |
| Evaluación de CV | Carga masiva, pasos del lote, incidencias | Hecho |
| Resultados | Puntuación por candidato, clasificación, Excel y ZIP | Hecho, dentro de Evaluación de CV |
| Histórico | Lotes, evaluaciones y exportaciones de cualquier periodo autorizado | Pendiente |
| Expedientes | Recorrido por etapas, síntesis con fuentes, documentos, resultado | Hecho |
| Etapas | Tablero por etapa, movimientos masivos, historial | Hecho |
| Bancos de preguntas | Bancos, versiones, preguntas, competencias y alcance | Pendiente |
| Llamadas | Sesión con banco, respuestas, análisis y decisión humana | Hecho |
| Psicometría | Instrumento, estado, documento, validación profesional | Pendiente |
| Entrevistas | Captura de la entrevista con gerente y su conclusión | Pendiente |
| Pruebas técnicas | Prueba opcional, rúbrica, resultado o "no aplica" | Pendiente |
| Estudios | Plantillas de formulario, digitalización y verificación | Pendiente |
| Contrataciones | Resultados finales y fechas de incorporación | Pendiente |
| Reportes | Reportes por vacante, reclutador y administrativos | Pendiente |
| Administración | Parámetros, plantillas, almacenamiento y procesos | Pendiente |
| Configuración de IA | Claves, modelos por operación, presupuesto y consumo | Hecho |
| Auditoría | Búsqueda de eventos por fecha, usuario y recurso | Pendiente |

**Reglas de interfaz**

- Menú superior por área de trabajo y carril lateral para módulos globales; cada rol ve solo lo que puede usar.
- Toda pantalla define sus estados de carga, vacío, error y éxito.
- Las operaciones masivas y las irreversibles piden confirmación y muestran qué van a afectar.
- Formularios con validación en el navegador y en el servidor, con el mismo esquema.
- Contraste y navegación por teclado conforme a WCAG 2.1 nivel AA; diseño responsivo.
- Ninguna pantalla se entrega sin estar conectada a su API real.

## Cobertura del documento maestro

Las 38 secciones del documento maestro están atendidas; la tabla indica dónde. Dos temas no tenían punto propio en la primera entrega y se resumen aquí.

**Convenciones de la API (sección 26).** Los 26 recursos viven bajo `/api/v1/` y cada uno pertenece a un módulo. Todos comparten paginación, filtros y ordenamiento declarados, un formato único de error, clave de idempotencia en altas y operaciones masivas, control de concurrencia con `ROWVERSION` e identificador de correlación. El contrato OpenAPI se genera del código.

**Controles web (sección 29).** Consultas siempre parametrizadas, escape de salida y política de seguridad de contenido contra XSS, token CSRF, HTTPS obligatorio y cabeceras de seguridad en el proxy.

| Sección del documento maestro | Dónde se atiende |
| --- | --- |
| 0. Restricciones obligatorias | Secciones 1, 3, 8, 13, 15, 16, 18, 22 y 23 |
| 1. Visión del producto | Sección 18 |
| 2 y 3. Arquitectura y tecnologías | Secciones 2 y 3 |
| 4. Estructura de carpetas | Sección 5 |
| 5. Almacenamiento persistente | Secciones 8, 9 y 21 |
| 6. Configuración de API keys | Secciones 15 y 16 |
| 7. Administración de usuarios | Secciones 10 y 11 |
| 8 y 9. Permisos, compartición, transferencia y baja | Secciones 11 y 12 |
| 10 y 11. Vacantes, perfiles y prompts | Secciones 6, 13, 18 y 20 |
| 12 y 13. Procesamiento y calificación de CV | Secciones 15 y 19 |
| 14 y 15. Expedientes y etapas | Secciones 13, 14, 18 y 20 |
| 16 y 17. Bancos de preguntas y llamadas | Secciones 13, 18 y 20 |
| 18 a 21. Psicometría, entrevistas, pruebas técnicas y estudios | Secciones 9, 13 y 18 |
| 22 y 23. Expediente acumulativo y resultados | Secciones 13 y 18 |
| 24. Dashboard | Secciones 13 y 17 |
| 25. Base de datos | Secciones 13 y 14 |
| 26. API REST | Esta sección y la 2 |
| 27. Interfaz | Sección 17 |
| 28. Procesamiento en segundo plano | Sección 19 |
| 29. Seguridad y privacidad | Secciones 9, 10, 11, 15 y 16, y esta |
| 30. Reportes y exportaciones | Secciones 13 y 19 |
| 31. Auditoría y observabilidad | Sección 20 |
| 32. Pruebas | Sección 22 |
| 33. Infraestructura y despliegue | Secciones 1, 2 y 21 |
| 34. Git y Visual Studio Code | Secciones 1 y 23 |
| 35. Plan por fases | Sección 23 |
| 36. Documentación obligatoria | Los 20 archivos se crean en la Fase 1 a partir de este documento y se mantienen en cada fase |
| 37. Criterios de aceptación | Secciones 22 y 23 |
| 38. Primera entrega | Este documento |
