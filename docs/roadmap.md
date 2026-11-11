# Plan de desarrollo

> Origen: propuesta de arquitectura aprobada el 10 de noviembre de 2026.
> Este archivo es la copia de trabajo del repositorio y se actualiza en cada fase.

## 23. Plan de desarrollo por fases

Son las nueve fases del documento maestro, de la 0 a la 8, cada una con un criterio de cierre comprobable. Una fase no se declara terminada si no funciona de extremo a extremo.

| Fase | Entregables | Se cierra cuando |
| --- | --- | --- |
| 0. Arquitectura | Este documento y las maquetas de pantallas | Tú la apruebas |
| 1. Fundamentos | Estructura del proyecto, API FastAPI, frontend Next.js, contratos comunes, configuración local y pruebas iniciales | El proyecto arranca en local y sus pruebas pasan |
| 2. Seguridad y usuarios | Autenticación, administradores, reclutadores, autorización, vacantes, compartición, transferencias y auditoría | Pasan las pruebas de seguridad 1 a 6. **Estado:** construida; pasan sobre el motor de pruebas, falta repetirlas en SQL Server |
| 3. Almacenamiento documental | `FileStorageService`, carga, persistencia, descargas autorizadas, hash, recuperación y respaldos | Pasan las pruebas de almacenamiento, incluido el reinicio. **Estado:** construida; falta probarla con SQL Server, Docker y ClamAV reales |
| 4. Inteligencia documental | Perfiles, generador de prompts, rúbricas, configuración de API keys, procesamiento de CV, calificaciones, ZIP, Excel e histórico | Un lote sintético produce Excel y ZIP de principio a fin. **Estado:** construida; ese lote funciona con un proveedor simulado. Falta repetirlo con SQL Server, con el worker y con un modelo real |
| 5. Reclutamiento operativo | Expedientes, etapas, movimientos, bancos de preguntas, llamadas y análisis de respuestas | Un candidato rechazado por la IA avanza a llamada por decisión humana y queda registrado |
| 6. Evaluaciones posteriores | Psicometría, gerentes, pruebas técnicas, estudios, digitalización y síntesis acumulativa | El expediente muestra todas las etapas con sus fuentes |
| 7. Cierre e indicadores | Resultados finales, contrataciones, dashboards, reportes y estadísticas históricas | Los tableros coinciden con los datos del flujo sintético |
| 8. Calidad y preparación productiva | Pruebas de seguridad, integración y rendimiento, respaldos, restauración, documentación y revisión de SQL Server | Pasa el flujo completo y Sistemas recibe el paquete de despliegue |

**Reglas de trabajo en cada fase**

- Las pantallas de la fase se diseñan antes de construirlas.
- Cada fase termina con `docs/estado_proyecto.md` actualizado: lo terminado, lo pendiente, las pruebas ejecutadas y los problemas conocidos.
- Por decisión del 10 de noviembre de 2026, se avanza de fase sin esperar revisión; los cambios se piden sobre la marcha.
- Los scripts T-SQL de lo construido están en `database/sqlserver/` y se regeneran con cada migración (`scripts/generate_sql.py`).
- Antes de cada subida a GitHub se ejecuta una comprobación de secretos y archivos sensibles.
- El despliegue lo hace Sistemas; yo entrego la guía y la configuración.
