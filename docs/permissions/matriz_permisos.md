# Matriz de permisos

> Origen: propuesta de arquitectura aprobada el 10 de noviembre de 2026.
> Este archivo es la copia de trabajo del repositorio y se actualiza en cada fase.

## 11. Matriz de permisos

Todo se deniega por defecto y el permiso se evalúa en el backend en cada operación, sobre el objeto concreto. Ocultar un botón en la interfaz no cuenta como control.

**Permisos sobre una vacante**

| Operación | Administrador | Responsable | Colaboración | Lectura | Sin acceso |
| --- | --- | --- | --- | --- | --- |
| Ver vacante, candidatos, evaluaciones y expedientes | Sí | Sí | Sí | Sí | No |
| Descargar CV, Excel y ZIP | Sí | Sí | Sí | Sí | No |
| Ver reportes e histórico de la vacante | Sí | Sí | Sí | Sí | No |
| Generar y descargar reportes en Excel de la vacante | Sí | Sí | Sí | Sí | No |
| Registrar el resultado final de una postulación (contratación incluida) o reabrirla | Sí | Sí | Sí | No | No |
| Editar datos de la vacante y cambiar su estado | Sí | Sí | No | No | No |
| Compartir y revocar accesos | Sí | Sí | No | No | No |
| Transferir el responsable | Sí | No | No | No | No |
| Cargar perfil y editar borradores de prompt y rúbrica | Sí | Sí | Sí | No | No |
| Aprobar prompt, rúbrica y umbral | Sí | Sí | No | No | No |
| Cargar CV e iniciar lotes | Sí | Sí | Sí | No | No |
| Mover candidatos de etapa y registrar incidencias | Sí | Sí | Sí | No | No |
| Registrar llamadas, psicometría, entrevistas y pruebas | Sí | Sí | Sí | No | No |
| Registrar el resultado final | Sí | Sí | Sí | No | No |
| Ver documentos psicométricos y socioeconómicos | Con finalidad registrada | Sí | Solo con permiso adicional | Solo con permiso adicional | No |

**Funciones globales**

| Función | Administrador | Reclutador |
| --- | --- | --- |
| Crear sus propias vacantes | Sí | Sí |
| Crear bancos de preguntas y compartirlos | Sí | Sí, los propios |
| Dashboard y reportes | Globales | Solo vacantes propias y compartidas |
| Usuarios, permisos y transferencias masivas | Sí | No |
| Configuración de IA, claves y presupuestos | Sí | No |
| Auditoría, almacenamiento y parámetros | Sí | No |
| Plantillas de etapas y de estudios | Sí | Solo usarlas |

**Cómo se hace efectivo.**

- Los repositorios reciben al usuario que actúa y filtran por pertenencia a la vacante; no existe una consulta "sin filtro" para reclutadores.
- Un UUID ajeno responde "no encontrado", para no revelar que el recurso existe.
- La búsqueda global de candidatos solo devuelve postulaciones de vacantes autorizadas.
- El worker comprueba de nuevo el permiso antes de procesar y antes de generar exportaciones.
- Los reportes históricos usan los permisos vigentes hoy, no los del momento del evento.
- Row-Level Security de SQL Server se propone como segunda barrera (decisión 11). Todavía no está implementada.
- Documentos (Fase 3): ver la lista y descargar exige acceso de lectura a la vacante; cargar exige colaboración; los de clase sensible exigen además el permiso adicional, salvo para el responsable y el administrador; eliminar es solo del administrador y con motivo. El permiso se evalúa en cada descarga.
- Todo intento rechazado queda en la auditoría como `acceso.denegado`, también cuando la respuesta es "no encontrado" para no revelar que el recurso existe.

## 12. Reglas de compartición y transferencia

Compartir da acceso sin cambiar al responsable; transferir cambia al responsable sin mover ni un documento.

**Compartición**

- Toda vacante es privada al crearse y tiene exactamente un responsable principal.
- Hay dos tipos de acceso: `LECTURA` y `COLABORACION`. Un usuario tiene como máximo uno por vacante.
- Comparten el responsable y el administrador. No se puede compartir con usuarios inactivos.
- El acceso a documentos sensibles es un permiso aparte, por persona y por clase de documento.
- La revocación surte efecto en la siguiente petición e incluye exportaciones anteriores.
- Cada compartición y revocación queda en auditoría.

**Transferencia individual.** El administrador elige vacante y nuevo responsable activo. Se guardan responsable anterior, nuevo, fecha, motivo y quién autorizó. El responsable anterior pierde el acceso, salvo que el administrador lo deje como colaborador.

**Transferencia masiva por baja de un reclutador**

1. Seleccionar al usuario saliente.
2. Listar sus vacantes como responsable.
3. Listar sus colaboraciones en vacantes de otros.
4. Mostrar sus tareas pendientes, bancos de preguntas y plantillas.
5. Elegir al usuario receptor, que debe estar activo.
6. Previsualizar: qué se transfiere, qué se revoca y qué se reasigna.
7. Confirmar. Si los datos cambiaron desde la previsualización, se exige repetirla.
8. Transferir las vacantes y escribir el historial de cada una.
9. Reasignar los pendientes autorizados y los bancos en uso.
10. Revocar los accesos del usuario saliente.
11. Cerrar sus sesiones y desactivarlo.
12. Generar el registro de auditoría de la operación completa.

Los pasos 8 a 12 corren en una sola transacción de SQL Server. La operación tiene un identificador propio: si se interrumpe, repetirla continúa donde quedó sin duplicar nada.

**Invariantes que la base de datos hace cumplir**

- Ninguna vacante activa queda sin responsable.
- No se transfiere a usuarios inactivos.
- La autoría de acciones pasadas no cambia.
- El usuario no se borra físicamente.
- Los documentos pertenecen a la postulación y a la vacante, no al reclutador, así que una transferencia no mueve archivos.
