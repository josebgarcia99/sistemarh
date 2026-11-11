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
