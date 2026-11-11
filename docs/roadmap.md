# Plan de desarrollo

> Origen: propuesta de arquitectura aprobada el 10 de noviembre de 2026.
> Este archivo es la copia de trabajo del repositorio y se actualiza en cada fase.

## 23. Plan de desarrollo por fases

Son las nueve fases del documento maestro, de la 0 a la 8, cada una con un criterio de cierre comprobable. Una fase no se declara terminada si no funciona de extremo a extremo.

| Fase | Entregables | Se cierra cuando |
| --- | --- | --- |
| 0. Arquitectura | Este documento y las maquetas de pantallas | Tú la apruebas |
| 1. Fundamentos | Estructura del proyecto, API FastAPI, frontend Next.js, contratos comunes, configuración local y pruebas iniciales | El proyecto arranca en local y sus pruebas pasan |
| 2. Seguridad y usuarios | Autenticación, administradores, reclutadores, autorización, vacantes, compartición, transferencias y auditoría | Pasan las pruebas de seguridad 1 a 6 |
| 3. Almacenamiento documental | `FileStorageService`, carga, persistencia, descargas autorizadas, hash, recuperación y respaldos | Pasan las pruebas de almacenamiento, incluido el reinicio |
| 4. Inteligencia documental | Perfiles, generador de prompts, rúbricas, configuración de API keys, procesamiento de CV, calificaciones, ZIP, Excel e histórico | Un lote sintético produce Excel y ZIP de principio a fin |
| 5. Reclutamiento operativo | Expedientes, etapas, movimientos, bancos de preguntas, llamadas y análisis de respuestas | Un candidato rechazado por la IA avanza a llamada por decisión humana y queda registrado |
| 6. Evaluaciones posteriores | Psicometría, gerentes, pruebas técnicas, estudios, digitalización y síntesis acumulativa | El expediente muestra todas las etapas con sus fuentes |
| 7. Cierre e indicadores | Resultados finales, contrataciones, dashboards, reportes y estadísticas históricas | Los tableros coinciden con los datos del flujo sintético |
| 8. Calidad y preparación productiva | Pruebas de seguridad, integración y rendimiento, respaldos, restauración, documentación y revisión de SQL Server | Pasa el flujo completo y Sistemas recibe el paquete de despliegue |

**Reglas de trabajo en cada fase**

- Las pantallas de la fase se diseñan antes de construirlas.
- Cada fase termina con `docs/estado_proyecto.md` actualizado: lo terminado, lo pendiente, las pruebas ejecutadas y los problemas conocidos.
- Reviso contigo el resultado antes de empezar la siguiente.
- El paquete definitivo de scripts T-SQL se genera cuando lo pidas.
- Cuando autorices Git, primero te muestro el plan de incorporación y el resultado de la comprobación de secretos.
- El despliegue lo hace Sistemas; yo entrego la guía y la configuración.
