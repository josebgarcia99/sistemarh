# Contratos de la API

> Generado por `scripts/generate_docs.py` a partir del contrato OpenAPI. No editar a mano.

Versión de la API: `0.8.0`. Rutas: 110. Todas cuelgan de `/api/v1`.

**Reglas comunes**

- Solo tres rutas responden sin sesión (marcadas como «Pública»). Las demás exigen la cookie de sesión y, si modifican algo, la cabecera `X-CSRF-Token`.
- Tener sesión no basta: cada operación comprueba el permiso sobre el objeto concreto (ver `docs/permissions/matriz_permisos.md`). Un recurso ajeno responde 404, igual que si no existiera.
- Los errores usan el formato `application/problem+json` con `code`, `detail` y `correlation_id`.
- Las fechas van en UTC (ISO 8601). Los identificadores son UUID.
- Fuera de producción, el contrato completo y navegable está en `/api/v1/docs`.

## Auditoría

| Método | Ruta | Qué hace | Entrada | Respuesta |
| --- | --- | --- | --- | --- |
| GET | `/audit/events` | Eventos de auditoría | — | 200 `AuditPage` |

## Bancos de preguntas y llamadas

| Método | Ruta | Qué hace | Entrada | Respuesta |
| --- | --- | --- | --- | --- |
| GET | `/applications/{application_id}/calls` | Llamadas de una postulación | — | 200 lista de `CallOut` |
| POST | `/applications/{application_id}/calls` | Abre una llamada con la versión vigente de un banco | `NewCallIn` | 201 `CallOut` |
| GET | `/calls/{call_id}` | Una llamada | — | 200 `CallOut` |
| PUT | `/calls/{call_id}` | Guarda o cierra la llamada | `CallIn` | 200 `CallOut` |
| POST | `/calls/{call_id}/analysis` | La IA resume lo que aporta la llamada; no decide nada | — | 200 `CallOut` |
| GET | `/question-banks` | Bancos propios y compartidos | — | 200 lista de `BankOut` |
| POST | `/question-banks` | Crea un banco de preguntas | `BankIn` | 201 `BankOut` |
| POST | `/question-banks/question-proposals` | La IA propone preguntas a partir del perfil de una vacante, sin guardar | `ProposalIn` | 200 lista de `ProposedQuestionOut` |
| GET | `/question-banks/{bank_id}` | Banco y sus versiones | — | 200 `BankDetailOut` |
| PUT | `/question-banks/{bank_id}` | Guarda el banco; si cambian las preguntas crea una versión nueva | `BankUpdateIn` | 200 `BankOut` |
| POST | `/question-banks/{bank_id}/archive` | Archiva el banco | — | 200 `BankOut` |
| POST | `/question-banks/{bank_id}/duplicate` | Copia el banco como propio y privado | — | 201 `BankOut` |
| POST | `/question-banks/{bank_id}/restore` | Restaura un banco archivado | — | 200 `BankOut` |

## Documentos

| Método | Ruta | Qué hace | Entrada | Respuesta |
| --- | --- | --- | --- | --- |
| GET | `/files/{file_id}` | Metadatos de un documento | — | 200 `FileOut` |
| POST | `/files/{file_id}/deletion` | Eliminación controlada (solo administradores, con motivo) | `FileDeletionIn` | 204 — |
| GET | `/files/{file_id}/download` | Descarga autorizada de un documento | — | 200 — |
| POST | `/storage/reconciliation` | Concilia SQL Server con el disco de documentos | `ReconciliationIn` | 200 `ReconciliationOut` |
| GET | `/storage/status` | Estado del almacenamiento | — | 200 `StorageStatusOut` |
| GET | `/vacancies/{vacancy_id}/files` | Documentos de una vacante que el usuario puede ver | — | 200 lista de `FileOut` |
| POST | `/vacancies/{vacancy_id}/files` | Carga un documento (el cuerpo de la petición es el archivo) | — | 201 `FileUploadOut` |

## Evaluaciones posteriores

| Método | Ruta | Qué hace | Entrada | Respuesta |
| --- | --- | --- | --- | --- |
| GET | `/applications/{application_id}/assessments` | Evaluaciones posteriores de una postulación que el usuario puede ver | — | 200 `AssessmentListOut` |
| POST | `/applications/{application_id}/assessments` | Registra una evaluación de la postulación | `NewAssessmentIn` | 201 `AssessmentOut` |
| GET | `/applications/{application_id}/syntheses` | Última síntesis del expediente que el usuario puede ver | — | 200 `SynthesisViewOut` |
| POST | `/applications/{application_id}/syntheses` | La IA sintetiza el expediente por tipo de fuente; no puntúa ni recomienda | — | 201 `SynthesisOut` |
| GET | `/assessments/{assessment_id}` | Una evaluación | — | 200 `AssessmentOut` |
| PUT | `/assessments/{assessment_id}` | Guarda la evaluación | `AssessmentUpdateIn` | 200 `AssessmentOut` |
| POST | `/assessments/{assessment_id}/digitization` | La IA lee un formulario escaneado y propone valores, sin guardar ni verificar | `DigitizationIn` | 200 `DigitizationOut` |
| POST | `/assessments/{assessment_id}/photo-descriptions` | La IA describe lo que se ve en una fotografía del estudio, sin guardar nada | `PhotoDescriptionIn` | 200 `PhotoDescriptionOut` |
| POST | `/assessments/{assessment_id}/summary` | La IA resume lo documentado; no diagnostica ni decide | — | 200 `AssessmentOut` |
| GET | `/form-templates` | Formularios de estudio socioeconómico | — | 200 lista de `TemplateOut` |
| POST | `/form-templates` | Crea un formulario (solo administradores) | `TemplateIn` | 201 `TemplateOut` |
| PUT | `/form-templates/{template_id}` | Guarda el formulario; si cambian sus campos crea una versión nueva | `TemplateIn` | 200 `TemplateOut` |
| POST | `/form-templates/{template_id}/archive` | Archiva el formulario | — | 200 `TemplateOut` |
| POST | `/form-templates/{template_id}/restore` | Restaura un formulario archivado | — | 200 `TemplateOut` |

## Evaluación de cv

| Método | Ruta | Qué hace | Entrada | Respuesta |
| --- | --- | --- | --- | --- |
| GET | `/cv-batches/{batch_id}` | Lote y sus CV | — | 200 `BatchDetailOut` |
| POST | `/cv-batches/{batch_id}/cancel` | Cancela un lote en curso; lo ya evaluado se conserva | — | 200 `BatchDetailOut` |
| POST | `/cv-batches/{batch_id}/retry` | Reintenta los CV fallidos y continúa con los pendientes | — | 200 `BatchDetailOut` |
| GET | `/vacancies/{vacancy_id}/cv-batches` | Estado de la evaluación de CV de una vacante y sus lotes | — | 200 `app__modules__cv_processing__api__router__OverviewOut` |
| POST | `/vacancies/{vacancy_id}/cv-batches` | Evalúa en segundo plano los CV de la vacante con el prompt aprobado | `BatchIn` | 201 `BatchDetailOut` |

## Inteligencia artificial

| Método | Ruta | Qué hace | Entrada | Respuesta |
| --- | --- | --- | --- | --- |
| GET | `/ai/assignments` | Modelo de cada operación | — | 200 lista de `AssignmentOut` |
| PUT | `/ai/assignments/{operation}` | Asigna un modelo | `AssignmentIn` | 200 `AssignmentOut` |
| GET | `/ai/models` | Modelos que informan los proveedores | — | 200 lista de `ModelOut` |
| PUT | `/ai/models/{model_id}/prices` | Precio por millón de tokens | `PricesIn` | 200 `ModelOut` |
| POST | `/ai/models/{model_id}/test` | Pide al modelo una respuesta mínima (no envía documentos) | — | 200 `ModelTestOut` |
| GET | `/ai/providers` | Proveedores y estado de sus claves | — | 200 `AiOverviewOut` |
| PUT | `/ai/providers/{code}` | Habilita y fija el límite mensual | `ProviderSettingsIn` | 200 `ProviderOut` |
| PUT | `/ai/providers/{code}/key` | Registra o sustituye la API key | `ApiKeyIn` | 200 `ProviderOut` |
| DELETE | `/ai/providers/{code}/key` | Revoca la API key | — | 200 `ProviderOut` |
| POST | `/ai/providers/{code}/test` | Prueba la conexión y actualiza la lista de modelos (no envía documentos) | — | 200 `TestResultOut` |
| GET | `/ai/usage` | Consumo y costo estimado de un mes | — | 200 `UsageOut` |

## Perfil y prompt

| Método | Ruta | Qué hace | Entrada | Respuesta |
| --- | --- | --- | --- | --- |
| GET | `/prompts/{version_id}` | Una versión del prompt | — | 200 `PromptOut` |
| PUT | `/prompts/{version_id}` | Edita un borrador | `PromptEditIn` | 200 `PromptOut` |
| POST | `/prompts/{version_id}/approve` | Aprueba la versión (queda inmutable) | `RevisionIn` | 200 `PromptOut` |
| POST | `/prompts/{version_id}/archive` | Archiva la versión | `RevisionIn` | 200 `PromptOut` |
| POST | `/prompts/{version_id}/criteria-proposals` | La IA propone una mejor redacción de los criterios de un borrador, sin guardar | — | 200 `CriteriaProposalOut` |
| POST | `/prompts/{version_id}/duplicate` | Copia la versión como borrador nuevo | — | 201 `PromptOut` |
| POST | `/prompts/{version_id}/return` | Devuelve a borrador para corregir | `RevisionIn` | 200 `PromptOut` |
| POST | `/prompts/{version_id}/submit` | Envía el borrador a revisión | `RevisionIn` | 200 `PromptOut` |
| POST | `/vacancies/{vacancy_id}/profile-extractions` | Lee un perfil (formato en Excel, documento o texto) y lo devuelve como propuesta | `ProfileExtractionIn` | 200 `ProfileProposalOut` |
| GET | `/vacancies/{vacancy_id}/profile-versions` | Versiones del perfil de puesto, de la más reciente a la más antigua | — | 200 lista de `ProfileVersionOut` |
| POST | `/vacancies/{vacancy_id}/profile-versions` | Guarda el perfil como una versión nueva | `ProfileIn` | 201 `ProfileVersionOut` |
| GET | `/vacancies/{vacancy_id}/prompts` | Versiones del prompt de evaluación | — | 200 lista de `PromptOut` |
| POST | `/vacancies/{vacancy_id}/prompts` | Genera un borrador a partir del perfil vigente | — | 201 `PromptOut` |

## Reclutamiento

| Método | Ruta | Qué hace | Entrada | Respuesta |
| --- | --- | --- | --- | --- |
| GET | `/applications/{application_id}` | Expediente de una postulación | — | 200 `ApplicationDetailOut` |
| PUT | `/applications/{application_id}/candidate` | Corrige los datos de la persona | `CandidateIn` | 200 `ApplicationDetailOut` |
| POST | `/applications/{application_id}/notes` | Registra una incidencia o reprograma la etapa actual | `NoteIn` | 200 `ApplicationDetailOut` |
| POST | `/applications/{application_id}/outcome` | Registra el resultado final de la postulación | `OutcomeIn` | 200 `ApplicationDetailOut` |
| POST | `/applications/{application_id}/reopening` | Reabre una postulación cerrada y anula su resultado final | `ReopenIn` | 200 `ApplicationDetailOut` |
| POST | `/applications/{application_id}/status` | Desistimiento, descarte, cancelación o reactivación, con motivo | `StatusIn` | 200 `ApplicationDetailOut` |
| POST | `/campaigns/{campaign_id}/close` | Cierra la convocatoria | — | 200 `CampaignOut` |
| GET | `/pipeline` | Etapas vigentes del proceso | — | 200 `PipelineOut` |
| PUT | `/pipeline` | Guarda las etapas como una versión nueva (solo administradores) | `PipelineIn` | 200 `PipelineOut` |
| POST | `/vacancies/{vacancy_id}/application-moves` | Mueve una o varias postulaciones a una etapa | `MoveIn` | 200 lista de `ApplicationOut` |
| GET | `/vacancies/{vacancy_id}/applications` | Postulaciones de una convocatoria de la vacante, con sus etapas | — | 200 `BoardOut` |
| POST | `/vacancies/{vacancy_id}/applications` | Alta manual de un candidato en la convocatoria abierta | `NewApplicationIn` | 201 `ApplicationDetailOut` |
| POST | `/vacancies/{vacancy_id}/campaigns` | Abre una convocatoria nueva con las etapas vigentes | `CampaignIn` | 201 `CampaignOut` |

## Reportes

| Método | Ruta | Qué hace | Entrada | Respuesta |
| --- | --- | --- | --- | --- |
| GET | `/reports/applications` | Histórico de postulaciones con filtros | — | 200 `HistoryOut` |
| GET | `/reports/exports` | Reportes que generó la persona | — | 200 lista de `ExportOut` |
| POST | `/reports/exports` | Genera un Excel y lo guarda en el servidor | `ExportIn` | 201 `ExportOut` |
| GET | `/reports/exports/{export_id}/download` | Descarga un reporte generado | — | 200 — |
| GET | `/reports/options` | Valores para los filtros | — | 200 `OptionsOut` |
| GET | `/reports/overview` | Indicadores de las vacantes que la persona puede ver | — | 200 `app__modules__reporting__api__router__OverviewOut` |

## Salud

| Método | Ruta | Qué hace | Entrada | Respuesta |
| --- | --- | --- | --- | --- |
| GET | `/health/live` | El proceso responde (Pública) | — | 200 `LivenessResponse` |
| GET | `/health/ready` | SQL Server, Redis y almacenamiento responden (Pública) | — | 200 `ReadinessResponse` |
| GET | `/system/metrics` | Solicitudes atendidas por este proceso: cuántas, errores y duración | — | 200 `MetricsResponse` |

## Sesión

| Método | Ruta | Qué hace | Entrada | Respuesta |
| --- | --- | --- | --- | --- |
| POST | `/auth/login` | Iniciar sesión (Pública) | `LoginIn` | 200 `SessionOut` |
| POST | `/auth/logout` | Cerrar sesión | — | 204 — |
| GET | `/auth/me` | Sesión actual | — | 200 `SessionOut` |

## Transferencias

| Método | Ruta | Qué hace | Entrada | Respuesta |
| --- | --- | --- | --- | --- |
| GET | `/vacancies/{vacancy_id}/ownership-history` | Historial de responsables de la vacante | — | 200 lista de `OwnershipChangeOut` |
| POST | `/vacancy-transfers/individual` | Cambiar el responsable de una vacante | `IndividualTransferIn` | 204 — |
| POST | `/vacancy-transfers/mass` | Transferir todo lo de un reclutador y darlo de baja | `MassTransferIn` | 200 `MassTransferOut` |
| POST | `/vacancy-transfers/mass/preview` | Vista previa de la baja de un reclutador | `MassPreviewIn` | 200 `MassPreviewOut` |

## Usuarios

| Método | Ruta | Qué hace | Entrada | Respuesta |
| --- | --- | --- | --- | --- |
| GET | `/users` | Lista de usuarios | — | 200 `UserPage` |
| POST | `/users` | Alta | `UserCreateIn` | 201 `UserOut` |
| GET | `/users/directory` | Buscar usuarios activos para compartir una vacante | — | 200 lista de `DirectoryEntry` |
| GET | `/users/{user_id}` | Detalle | — | 200 `UserOut` |
| PATCH | `/users/{user_id}` | Editar nombre o rol | `UserUpdateIn` | 200 `UserOut` |
| POST | `/users/{user_id}/activate` | Reactivar | — | 200 `UserOut` |
| POST | `/users/{user_id}/deactivate` | Dar de baja | — | 200 `UserOut` |
| POST | `/users/{user_id}/reset-password` | Restablecer contraseña y cerrar sus sesiones | `PasswordResetIn` | 200 `PasswordResetOut` |

## Vacantes

| Método | Ruta | Qué hace | Entrada | Respuesta |
| --- | --- | --- | --- | --- |
| GET | `/vacancies` | Vacantes que el usuario puede ver | — | 200 `VacancyPage` |
| POST | `/vacancies` | Alta | `VacancyIn` | 201 `app__modules__vacancies__api__schemas__VacancyOut` |
| GET | `/vacancies/{vacancy_id}` | Detalle | — | 200 `app__modules__vacancies__api__schemas__VacancyOut` |
| PUT | `/vacancies/{vacancy_id}` | Editar datos | `VacancyUpdateIn` | 200 `app__modules__vacancies__api__schemas__VacancyOut` |
| GET | `/vacancies/{vacancy_id}/members` | Con quién está compartida | — | 200 lista de `MemberOut` |
| PUT | `/vacancies/{vacancy_id}/members/{user_id}` | Compartir o cambiar el tipo de acceso | `MemberIn` | 204 — |
| DELETE | `/vacancies/{vacancy_id}/members/{user_id}` | Revocar el acceso | — | 204 — |
| PUT | `/vacancies/{vacancy_id}/members/{user_id}/sensitive-grants` | Permisos adicionales para documentos sensibles | `SensitiveGrantsIn` | 200 `SensitiveGrantsOut` |
| POST | `/vacancies/{vacancy_id}/status` | Cambiar estado | `StatusChangeIn` | 200 `app__modules__vacancies__api__schemas__VacancyOut` |
