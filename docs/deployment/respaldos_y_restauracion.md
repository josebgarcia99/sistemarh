# Respaldos y restauración

> Origen: propuesta de arquitectura aprobada el 10 de noviembre de 2026.
> Este archivo es la copia de trabajo del repositorio y se actualiza en cada fase.

## 21. Estrategia de respaldos

SQL Server y el disco de documentos se respaldan como un solo conjunto, con manifiesto, y la restauración se prueba. Respaldar solo la base de datos no sirve.

1. **Base de datos.** Respaldo completo semanal, diferencial diario y de registro de transacciones cada 15 minutos, con suma de verificación y cifrado.
2. **Documentos.** Copia incremental cifrada de `private/` y `generated/` al destino que defina Sistemas.
3. **Orden.** Primero la base de datos y después los archivos. Como un archivo confirmado no cambia, todo lo que la base referencia existe en la copia de archivos.
4. **Manifiesto.** Cada respaldo genera desde SQL Server la lista de archivos con clave, tamaño y SHA-256, ligada al identificador del respaldo de base de datos.
5. **Comprobación.** Tras copiar, se compara el manifiesto contra los archivos copiados; el hash completo se verifica cada semana.
6. **Clave maestra y configuración.** Se respaldan aparte, bajo custodia de Sistemas.
7. **Restauración de prueba.** Cada trimestre, en el entorno de pruebas: se restauran base y archivos y se ejecuta la verificación de integridad, que reporta referencias faltantes, huérfanos y hashes distintos.
8. **Eliminaciones.** Tras restaurar, se vuelven a aplicar las solicitudes de eliminación posteriores al respaldo, para que un dato borrado no reaparezca.

Las frecuencias, la retención propuesta (30 respaldos diarios, 12 semanales y 12 mensuales) y los objetivos de recuperación son una propuesta para Sistemas (decisión 14). Entrego los scripts y la guía; no ejecuto nada en producción.

## Herramientas ya construidas (Fase 3)

Probadas con una copia local de archivos sintéticos. **No se ha hecho ningún respaldo ni restauración reales de SQL Server**; los comandos de SQL Server son responsabilidad de Sistemas.

**Al respaldar**

1. Respaldar SQL Server (`BACKUP DATABASE … WITH CHECKSUM`).
2. Generar el manifiesto de documentos, inmediatamente después:
   ```bash
   python -m app.cli storage-manifest --output manifiesto_AAAAMMDD.jsonl
   ```
   Lista cada documento confirmado y cada Excel de reportes generado, con su clave, tamaño y SHA-256. No contiene rutas absolutas ni nombres de personas.
3. Copiar las carpetas `private/` y `generated/` del almacenamiento al destino del respaldo, cifrado.
4. Verificar la copia contra el manifiesto. No necesita la base de datos:
   ```bash
   python -m app.cli storage-verify --manifest manifiesto_AAAAMMDD.jsonl --root /ruta/de/la/copia
   python -m app.cli storage-verify --manifest manifiesto_AAAAMMDD.jsonl --root /ruta/de/la/copia --full   # semanal
   ```
   Sin `--full` comprueba que cada archivo existe y mide lo mismo; con `--full` recalcula el SHA-256. Código de salida 0 si coincide, 2 si no.
5. Guardar el manifiesto junto con el respaldo de la base del mismo día.

Como el manifiesto se genera después del respaldo de la base, puede listar documentos cargados en ese intervalo: sobran en la copia, no faltan. Un documento eliminado en ese intervalo aparecería como faltante; se resuelve repitiendo el paso 2.

**Al restaurar (en el entorno de pruebas)**

1. Restaurar la base y copiar los archivos a la carpeta de almacenamiento.
2. `storage-verify --full` contra el manifiesto de ese respaldo.
3. Con la aplicación apuntando a lo restaurado: `python -m app.cli storage-check --verify-hashes all`. Reporta referencias faltantes, archivos sin registro y hashes distintos. Incluye los Excel de reportes.
4. Ejecutar `database/sqlserver/validaciones_integridad.sql` en la base restaurada: todas las filas deben mostrar 0. Comprueba, entre otras cosas, que hay un administrador activo, que cada postulación cerrada tiene su resultado final y que ningún documento sensible quedó sin cifrar.
5. Volver a aplicar las eliminaciones posteriores al respaldo.

## Qué se respalda, en una tabla

| Qué | Dónde está | Cómo se respalda | Sin ello |
| --- | --- | --- | --- |
| Base de datos | SQL Server | Respaldo completo, diferencial y de registro, con suma de verificación | Se pierde todo el proceso |
| Documentos (`private/`) y archivos generados (`generated/`) | Carpeta del servidor | Copia cifrada, verificada contra el manifiesto | Se pierden CV, pruebas, estudios, Excel y ZIP |
| Clave maestra | Archivo del servidor, fuera de lo anterior | Aparte, bajo custodia de Sistemas | No se abren las claves de IA ni los documentos sensibles, aunque la base y los archivos estén intactos |
| Variables de entorno y certificado | Servidor | Con la configuración del servidor | Hay que volver a configurarlo |

No hace falta respaldar Redis (solo es la cola), ni las carpetas `processing/` y `quarantine/` del almacenamiento.

## Estado de las pruebas de restauración

- **Probado con datos sintéticos:** generar el manifiesto, verificar una copia, detectar un archivo dañado o faltante (documentos y reportes) y comprobar el almacenamiento restaurado contra la base.
- **Sin probar:** el respaldo y la restauración de SQL Server, el orden real de los pasos en el servidor y el tiempo que tardan. El criterio de aceptación 25 («los respaldos pueden restaurarse») no puede darse por cumplido hasta hacer una restauración completa en el entorno de pruebas.
