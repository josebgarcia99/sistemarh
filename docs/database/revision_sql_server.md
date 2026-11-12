# Revisión de SQL Server

Resultado de la revisión del esquema y de los scripts en la Fase 8, y lista de lo que Sistemas debe comprobar en el servidor.

> **Esta revisión se hizo sin SQL Server.** Los scripts se generan sin conexión y se comprueban con pruebas automáticas sobre su texto y sobre el modelo de datos. Ninguno se ha ejecutado todavía en una instancia real. Lo marcado como «por comprobar» solo puede cerrarse allí.

## Qué se revisó y cómo

| Aspecto | Comprobación automática | Resultado |
| --- | --- | --- |
| El modelo de la aplicación y las migraciones definen las mismas tablas y columnas | `test_el_modelo_y_la_migracion_definen_las_mismas_columnas` | Coinciden (36 tablas) |
| Y los mismos índices, con las mismas columnas y unicidad | `test_el_modelo_y_la_migracion_definen_los_mismos_indices` | Coinciden |
| Las migraciones forman una sola cadena, sin saltos, y cada una documenta su reversión | `test_las_migraciones_forman_una_cadena_y_todas_se_pueden_revertir` | `0001` a `0012`, lineal |
| La reversión completa elimina todas las tablas | La misma prueba | Sí |
| El T-SQL generado usa los tipos previstos (`UNIQUEIDENTIFIER`, `DATETIME2(3)`, `NVARCHAR`, `ROWVERSION`, `ISJSON`) y ninguno obsoleto | `test_la_migracion_genera_t_sql_para_sql_server`, `test_ninguna_columna_usa_tipos_obsoletos_de_sql_server` | Sí |
| Los scripts son sintácticamente T-SQL válido | Análisis con `sqlglot` | Sin errores de análisis; no equivale a ejecutarlos |
| Claves foráneas sin índice | `test_las_claves_foraneas_sin_indice_son_una_decision_revisada` | Ver abajo |
| El script de validaciones solo lee y nombra tablas y columnas que existen | `test_las_validaciones_de_integridad_solo_leen_y_usan_columnas_que_existen` | Sí |

## Índices

SQL Server no crea índices para las claves foráneas. Se revisaron las 99 que tiene el esquema:

- **Con índice** (por clave primaria, restricción única o índice propio): las que se usan para buscar o unir tablas.
- **Añadidos en esta revisión** (migración `0012`), porque los usan las consultas de los reportes:

  | Índice | Para qué |
  | --- | --- |
  | `recruitment.call_sessions (vacancy_id)` | Bancos de preguntas usados en las vacantes visibles |
  | `recruitment.call_sessions (bank_version_id)` | Filtro del histórico por banco de preguntas |
  | `ai.cv_batches (prompt_version_id)` | Versión del prompt de cada postulación |
  | `recruitment.applications (evaluation_item_id)` | Unión con la evaluación inicial del CV |
  | `ai.executions (vacancy_id, occurred_at)` | Uso de IA de unas vacantes en un periodo |

- **Sin índice, a propósito**:
  - Las 42 columnas que apuntan a `auth.users` para dejar constancia de quién hizo algo (`created_by`, `updated_by`, `approved_by`, origen y destino de una transferencia…). Los usuarios nunca se borran y esas columnas no se usan para buscar; indexarlas solo encarecería las escrituras.
  - Otras 20, en tablas pequeñas o en columnas que no se consultan (por ejemplo, los cuatro archivos generados de cada lote, o la etapa de origen y destino de un movimiento). La lista exacta está en la prueba; cualquier clave foránea nueva sin índice la hace fallar hasta que se decide qué hacer con ella.

**Por comprobar en el servidor:** los planes de ejecución de las consultas de reportes (`apps/api/app/modules/reporting/infrastructure/sql_source.py`) con datos reales. Usan subconsultas `IN (SELECT …)` sobre las vacantes visibles; si el optimizador no las resuelve bien, se reescriben con `EXISTS` o tablas temporales.

## Rendimiento de los reportes

Los tableros no tienen tablas de cifras: se calculan al consultarlos. Con un periodo, solo se leen las postulaciones que cuentan para él (las activas, las dadas de alta en él y las que tuvieron movimientos en él). Las mediciones, hechas **en el motor en memoria y no en SQL Server**, están en `docs/testing/plan_pruebas.md`. El tiempo crece en proporción al número de postulaciones; si el volumen real hace lento el tablero «de todo el histórico», el siguiente paso es una tabla de resumen mensual.

## Concurrencia

| Mecanismo | Dónde | Por comprobar en el servidor |
| --- | --- | --- |
| Control optimista con número de versión | Vacantes, prompts, bancos, evaluaciones | Que dos ediciones simultáneas den conflicto y no se pisen |
| Índices únicos filtrados | Un acceso vigente por persona y vacante; una clave vigente por proveedor; un resultado final vigente por postulación | Que SQL Server los aplique como el motor de pruebas |
| Reserva de un lote de CV por un solo proceso | `ai.cv_batches` (`runner_token`, `lease_until`) | La sentencia de reserva con bloqueos reales y dos workers |
| Baja con transferencia en una sola transacción | `vacancy` y `auth` | Que un fallo a la mitad no deje cambios |

**Recomendación:** activar `READ_COMMITTED_SNAPSHOT` en la base, para que las lecturas largas de los reportes no bloqueen a quien está capturando. Es una decisión de Sistemas; la aplicación funciona con o sin él.

## Restricciones

- Los estados y tipos se validan con `CHECK` además de en la aplicación. El motor de pruebas no aplica esos `CHECK`: **por comprobar** que ningún valor que escribe la aplicación quede fuera de las listas (la migración `0011` las amplió para los resultados finales).
- Las columnas JSON llevan `ISJSON(...) = 1`.
- No hay borrados en cascada.
- La carga inicial de resultados finales de la migración `0011` (`INSERT … SELECT` con `NEWID()`) solo se ha analizado, no ejecutado.

## Permisos

`permisos_usuario_aplicacion.sql` da al usuario de la aplicación lo mínimo por esquema y le niega modificar o borrar la auditoría y el historial de movimientos. **Por comprobar:** ejecutar la aplicación completa con ese usuario y confirmar que no le falta ni le sobra ningún permiso. La aplicación nunca debe conectarse con un usuario administrador.

## Lista para Sistemas

1. Decidir edición e intercalación. El esquema usa `NVARCHAR` y no depende de una intercalación concreta, pero las búsquedas por nombre distinguirán o no acentos y mayúsculas según la que se elija.
2. Ejecutar `instalacion_completa.sql` en una base vacía de pruebas y anotar cualquier error.
3. Ejecutar la cadena de actualizaciones (`0001` → `0012`) en otra base y comparar el resultado con la instalación completa.
4. Aplicar los permisos y arrancar la aplicación con el usuario de aplicación.
5. Ejecutar `validaciones_integridad.sql`: todo en 0.
6. Repetir las pruebas automáticas de la API contra esa base (ver `docs/testing/plan_pruebas.md`).
7. Definir modelo de recuperación, respaldos y mantenimiento de índices y estadísticas.
8. Valorar `READ_COMMITTED_SNAPSHOT` y el cifrado de la base en reposo (TDE) si la edición lo permite.
