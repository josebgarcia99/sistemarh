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
