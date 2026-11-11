# Decisiones arquitectónicas

> Origen: propuesta de arquitectura aprobada el 10 de noviembre de 2026.
> Este archivo es la copia de trabajo del repositorio y se actualiza en cada fase.

## 3. Por qué monorepositorio y monolito modular

Un equipo pequeño, un solo servidor operado por Sistemas y operaciones que cruzan varios dominios en una misma transacción hacen que los microservicios cuesten más de lo que aportan.

| Decisión | Razón | Costo aceptado |
| --- | --- | --- |
| Monorepositorio | Un cambio de contrato actualiza API, tipos del frontend, worker y migración en un mismo commit. Sistemas revisa un solo lugar. | El repositorio crece; se compensa con carpetas independientes por aplicación. |
| Monolito modular | La baja de un reclutador mueve vacantes, accesos, pendientes y sesiones en una transacción de SQL Server. Entre servicios eso exigiría transacciones distribuidas. | Todos los módulos se despliegan juntos. |
| Worker como proceso aparte | OCR e IA tardan minutos y no deben bloquear la API. Comparte código de dominio, no es otro servicio. | Hay que operar Redis. |
| Sin microservicios | El documento maestro exige justificación comprobable y hoy no existe. | Ninguno por ahora. |

**Cuándo separar un módulo en el futuro.**

- Procesamiento documental: si la cola de OCR e IA supera de forma sostenida la capacidad del servidor, los workers se mueven a otra máquina sin cambiar código.
- Pasarela de IA: si otros sistemas de la empresa van a compartir claves y presupuesto.
- Reportes: si los tableros históricos degradan la operación, se llevan a una réplica de lectura.

## 25. Decisiones que requieren tu aprobación

Son 14 decisiones. Si respondes "apruebo", se toma la opción recomendada en todas; indica solo las que quieras cambiar. Las decisiones 1 a 4 son las únicas necesarias para empezar la Fase 1.

| N.º | Decisión | Opción recomendada | Alternativa |
| --- | --- | --- | --- |
| 1 | Cómo recibes el código | Decidido el 10 nov: repositorio en GitHub, josebgarcia99/sistemarh | Ninguna |
| 2 | SQL Server para desarrollo y pruebas | Sistemas habilita una base de pruebas en SQL Server 2022 | Avanzar solo con repositorios de prueba y validar al final, con más riesgo |
| 3 | Forma de despliegue | Docker Compose con contenedores Linux | Instalación como servicios del sistema, si Sistemas no admite Docker |
| 4 | Arquitectura y modelo | Aprobar el monolito modular, las tecnologías de la sección 2, el módulo `privacy` y los cambios al modelo de la sección 13 | Indicar qué cambiar |
| 5 | Custodia de la clave maestra | Secreto administrado por Sistemas en el servidor | Gestor de secretos que la empresa ya opere |
| 6 | OCR y antivirus | Tesseract en español y ClamAV, ambos locales | Otra solución local autorizada |
| 7 | Archivos DOC antiguos | Convertirlos con LibreOffice en un contenedor aislado | Rechazarlos y pedir PDF o DOCX |
| 8 | Cifrado en reposo | Volumen cifrado por Sistemas y cifrado por archivo para documentos sensibles | Solo cifrado de volumen |
| 9 | Correo para invitaciones y recuperación | Decidido el 10 nov: sin correo; el administrador crea usuarios y restablece contraseñas | Ninguna |
| 10 | Alcance del acceso "Colaboración" | Opera el proceso, pero no aprueba prompts, no comparte ni cambia el estado de la vacante; solo el administrador transfiere | Ampliar facultades del colaborador o permitir que el responsable ceda su vacante |
| 11 | Row-Level Security | Activarla como segunda barrera desde la Fase 2 | Dejarla para la Fase 8 |
| 12 | Auditoría inalterable | Permisos de solo inserción para la aplicación | Añadir tablas ledger de SQL Server 2022, con más garantía y más operación |
| 13 | Datos de contacto hacia la IA | Enmascarar teléfono, correo y domicilio antes de enviar un CV | Enviar el texto completo |
| 14 | Respaldos | Frecuencias y retención de la sección 21 | Lo que definan Sistemas y tu área legal |

**Pendientes que no bloquean la aprobación, pero sí el uso de datos reales**

- [ ] Política de retención de documentos y plazo de conservación.
- [ ] Aviso de privacidad que cubra el envío de datos a proveedores de IA.
- [ ] Verificación de la configuración de retención de datos en tus cuentas de Anthropic y OpenAI.
- [ ] Datos del servidor que debe informar Sistemas (sección 1).
