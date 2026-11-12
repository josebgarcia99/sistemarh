# Plan de pruebas

> Origen: propuesta de arquitectura aprobada el 10 de noviembre de 2026.
> Este archivo es la copia de trabajo del repositorio y se actualiza en cada fase.

## 22. Plan de pruebas

Ninguna funcionalidad se da por terminada sin pruebas automatizadas, y todas usan datos sintéticos.

| Nivel | Herramienta | Qué comprueba |
| --- | --- | --- |
| Unitarias de dominio | pytest | Reglas de negocio, estados, puntuaciones, versionado y permanencia laboral |
| Integración de API | pytest contra SQL Server de pruebas | Permisos por objeto, transferencias, persistencia, concurrencia e idempotencia |
| Worker | pytest con proveedor de IA simulado | Pasos del lote, reintentos, recuperación y caída del proveedor |
| Componentes de frontend | Vitest y Testing Library | Formularios, validación y estados de carga y error |
| Recorridos completos | Playwright | Flujos de usuario de punta a punta |
| Seguridad | Suite pytest dedicada y revisión de dependencias | Las 10 comprobaciones de la sección 32.3 |
| Almacenamiento | pytest y scripts sobre Docker | Las 14 comprobaciones de la sección 32.4 |
| Migraciones | Aplicar y revertir sobre base vacía y con datos | Que ninguna migración pierda información |
| Rendimiento | Locust | Lote de 500 CV sintéticos y 50 usuarios simultáneos |

**Seguridad (32.3).** Cada punto es una prueba con nombre propio:

1. El reclutador A no ve vacantes privadas de B.
2. Compartir permite solo lo autorizado por el tipo de acceso.
3. Revocar bloquea consultas y descargas, incluidas exportaciones previas.
4. Cambiar un UUID en la URL no da acceso.
5. Un usuario desactivado pierde sus sesiones.
6. El administrador puede transferir vacantes.
7. Una transferencia no pierde documentos.
8. Los archivos sensibles exigen el permiso adicional.
9. Las API keys no aparecen en respuestas ni en logs.
10. Los reportes históricos respetan los permisos vigentes.

Además, una prueba genérica recorre todas las rutas de la API y verifica que ninguna responde sin sesión ni sin permiso sobre el objeto.

**Almacenamiento (32.4).** Carga de CV, reinicio de la aplicación, persistencia tras reiniciar Docker, recuperación del documento, descarga autorizada y denegada, duplicado, fallo durante la escritura y su recuperación, respaldo, restauración, verificación SHA-256, consistencia entre SQL Server y archivos, y eliminación controlada.

**Flujo completo (32.5).** Un solo escenario recorre los 20 pasos del documento maestro, desde que el administrador crea usuarios hasta la transferencia final de la vacante, y termina comprobando que los documentos siguen disponibles y los permisos cambiaron.

**Datos de prueba.** Un generador produce CV ficticios en PDF y DOCX, versiones escaneadas para OCR y muestras hostiles: archivo de prueba de antivirus, textos con fórmulas de Excel, un CV con instrucciones ocultas para la IA y nombres de archivo con rutas.

**Límite actual.** Las pruebas contra SQL Server, la persistencia en Docker y el respaldo con restauración no pueden ejecutarse hasta contar con una instancia de pruebas (decisión 2). Mientras tanto, las pruebas de la API ejecutan los repositorios reales sobre un motor SQLite en memoria que solo existe dentro de las pruebas; eso no valida el comportamiento propio de SQL Server. El estado de cada comprobación está en `docs/estado_proyecto.md`.

## Estado al cierre de la Fase 8 (12 nov 2026)

Lo que sigue describe las pruebas que existen hoy y dónde están. Todas corren sin SQL Server, sobre el motor en memoria de las pruebas, con datos sintéticos y proveedores de IA simulados.

### Cómo ejecutarlas

```bash
cd apps/api && pytest            # 374 pruebas de la API
cd apps/worker && pytest         # 5 pruebas del worker
cd apps/web && npm test          # 102 pruebas de pantallas
python scripts/generate_docs.py --check   # la documentación generada está al día
python scripts/medir_rendimiento.py       # medición con volumen sintético
python tests/e2e/run.py                   # seis recorridos en navegador (requiere las pantallas compiladas)
```

### Seguridad (32.3): dónde está cada comprobación

| # | Comprobación | Prueba |
| --- | --- | --- |
| 1 | Un reclutador no consulta vacantes privadas de otro | `test_api_vacancies.py::test_seguridad_1_…` |
| 2 | Compartir permite solo lo autorizado | `test_api_vacancies.py::test_seguridad_2_…` (dos pruebas) y `test_api_files.py::test_el_acceso_de_lectura_descarga_pero_no_carga` |
| 3 | Revocar bloquea consultas y descargas | `test_api_vacancies.py::test_seguridad_3_…`, `test_api_files.py::test_revocar_el_acceso_bloquea_la_descarga_de_lo_ya_cargado` y, para reportes ya generados, `test_api_reporting.py::test_un_reporte_solo_se_descarga_mientras_se_conserva_el_acceso` |
| 4 | Cambiar el UUID de la dirección no da acceso | `test_api_vacancies.py::test_seguridad_4_…` y, para **todas** las rutas, `test_seguridad.py::test_ninguna_ruta_entrega_ni_modifica_recursos_ajenos` |
| 5 | Un usuario desactivado pierde sus sesiones | `test_api_auth_users.py::test_un_usuario_desactivado_pierde_sus_sesiones_y_no_puede_entrar` |
| 6 | El administrador transfiere vacantes | `test_api_vacancies.py::test_seguridad_6_y_7_…` |
| 7 | Una transferencia no pierde documentos | `test_api_files.py::test_una_transferencia_no_pierde_los_documentos` y el flujo completo |
| 8 | Los archivos sensibles exigen el permiso adicional | `test_api_files.py::test_seguridad_8_…` y `test_api_vacancies.py::test_seguridad_8_…` |
| 9 | Las API keys no aparecen en respuestas ni en registros | `test_api_ai_settings.py::test_seguridad_9_…` |
| 10 | Los reportes históricos respetan los permisos vigentes | `test_api_reporting.py::test_cada_persona_ve_solo_sus_vacantes_y_el_administrador_todas` |

Transversales, en `test_seguridad.py` y `test_route_protection.py`:

- **Barrido de acceso directo.** Una reclutadora sin acceso pide, con identificadores reales y cuerpos bien formados, las 76 rutas que llevan identificador. Ninguna lectura devuelve datos (403 o 404), ninguna escritura cambia nada y ninguna termina en error interno. Una ruta nueva entra sola en el barrido.
- **Sin sesión.** Las 109 rutas responden 401 salvo las tres públicas.
- **Textos hostiles** (inyección SQL, código, rutas) en búsquedas y filtros: se tratan como texto.
- **CV con instrucciones ocultas:** la calificación no cambia aunque el modelo simulado «obedezca».
- **Cabeceras de seguridad** en toda respuesta, HSTS solo en producción.
- **Registro de accesos** sin la cadena de consulta; **métricas** sin identificadores.

### Almacenamiento (32.4): dónde está cada comprobación

| Comprobación | Prueba |
| --- | --- |
| Carga de CV | `test_api_files.py::test_cargar_un_cv_lo_guarda_en_el_disco_con_sus_metadatos` |
| Reinicio de la aplicación | `test_storage.py::test_los_documentos_sobreviven_a_un_reinicio` |
| Persistencia tras reiniciar Docker | **Sin probar**: requiere el servidor |
| Recuperación de documento y descarga autorizada | `test_api_files.py::test_descarga_autorizada_devuelve_el_archivo_integro` |
| Descarga denegada | `test_api_files.py::test_descarga_denegada_sin_acceso_a_la_vacante`, `…::test_sin_sesion_no_hay_descarga` |
| Documento duplicado | `test_api_files.py::test_un_documento_duplicado_se_guarda_y_se_avisa` |
| Fallo durante la escritura y recuperación | `test_api_files.py::test_un_fallo_al_escribir_no_declara_guardado_el_documento`, `…::test_la_conciliacion_recupera_una_carga_interrumpida` |
| Respaldo y restauración | `test_api_files.py::test_respaldo_y_restauracion_con_manifiesto` y `test_api_reporting.py::test_los_reportes_entran_en_el_respaldo_y_en_la_comprobacion_del_almacenamiento`. Con copias de archivos sintéticos; **la restauración de SQL Server, sin probar** |
| Verificación SHA-256 | `test_api_files.py::test_la_verificacion_sha256_detecta_un_archivo_alterado` |
| Consistencia entre la base y los archivos | `test_api_files.py::test_un_archivo_faltante_se_reporta_y_no_se_descarga`, `…::test_un_archivo_sin_registro_va_a_cuarentena_y_no_se_borra` |
| Eliminación autorizada y controlada | `test_api_files.py::test_solo_un_administrador_elimina_y_debe_dar_un_motivo` |

### Flujo completo (32.5)

`test_flujo_completo.py::test_flujo_completo_de_principio_a_fin` recorre los 20 pasos del documento maestro en una sola prueba: la administradora crea usuarios; la reclutadora crea la vacante, la comparte, carga el perfil con ayuda de la IA y aprueba el prompt; carga los CV; la IA evalúa y se generan el Excel y los ZIP; RH revisa; un rechazado por la IA avanza a llamada por decisión humana; se responden las preguntas y se registra el análisis; se carga la psicometría; se registra la entrevista; la prueba técnica se marca como «no aplica»; se digitaliza un formulario; se registra la contratación; se consulta el histórico; la vacante se transfiere; y al final los documentos siguen disponibles para la nueva responsable y dejan de estarlo para la anterior.

En navegador, seis recorridos con Playwright (`tests/e2e/`, 48 pasos en total) usan la aplicación como una persona: formatos de la empresa (subir el perfil en Excel, Gemini y la plantilla del estudio), evaluación de CV, ayudas de IA, reclutamiento, evaluaciones posteriores e indicadores. Cada uno arranca un modo demostración nuevo. No recorren los 20 pasos seguidos en una sola sesión: eso lo hace la prueba de la API. Los recorridos de identidad y de vacantes de las primeras fases se hicieron a mano con guiones que no se conservaron en el repositorio.

### Migraciones y scripts

`test_sql_structure.py`: el modelo y las migraciones definen las mismas columnas e índices; las migraciones forman una sola cadena y todas documentan su reversión; la reversión completa elimina todas las tablas; el script de validaciones de integridad solo lee y solo nombra tablas y columnas que existen. **Aplicar y revertir sobre una base real con datos, sin probar.**

### Rendimiento

`scripts/medir_rendimiento.py` mide la API completa con miles de postulaciones inventadas. Resultados del 12 de noviembre de 2026 (mediana de cinco repeticiones, una solicitud a la vez):

| Operación | 2 000 postulaciones | 20 000 | 50 000 |
| --- | --- | --- | --- |
| Tablero del administrador, todo el histórico | 0.19 s | 2.3 s | 6.3 s |
| Tablero del administrador, un año | 0.12 s | 1.4 s | 4.4 s |
| Tablero de un reclutador (la décima parte de las vacantes) | 0.03 s | 0.21 s | 0.51 s |
| Histórico de candidatos, primera página | 0.06 s | 0.72 s | 2.1 s |
| Histórico filtrado por resultado y nombre | 0.06 s | 0.59 s | 1.7 s |
| Excel de postulaciones de un reclutador | 0.05 s | 0.36 s | 0.99 s |
| Lista de vacantes | 0.01 s | 0.01 s | 0.01 s |
| Candidatos de una vacante (100 personas) | 0.01 s | 0.01 s | 0.01 s |
| Expediente de una persona | 0.01 s | 0.01 s | 0.01 s |

Cómo leerlos:

- **No son tiempos de SQL Server.** Los datos están en memoria, en el motor de las pruebas. Sirven para ver cómo crece el tiempo con los datos, no para saber cuánto tardará en el servidor.
- El trabajo diario (vacantes, candidatos, expedientes) no depende del volumen total.
- Los tableros y el histórico crecen en proporción a las postulaciones que leen. El tablero del administrador sobre todo el histórico es la operación más lenta; con un periodo acotado lee menos.
- La medición sirvió para corregir dos cosas: los reportes leían más columnas y filas de las necesarias (el tablero tardaba 2.4 veces más) y el Excel tenía un cálculo que crecía con el cuadrado de las filas (de 14.7 s a 1 s con 5 000 filas).

**Sin medir:** usuarios simultáneos, un lote de 500 CV con un proveedor real y cualquier cosa en SQL Server. La prueba de carga con 50 usuarios prevista con Locust queda para cuando exista el entorno de pruebas.
