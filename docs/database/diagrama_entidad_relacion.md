# Diagrama entidad-relación

> Generado por `scripts/generate_docs.py` a partir del modelo de datos. No editar a mano.

Versión del esquema: `0013`. Tablas: 36. El detalle de cada columna está en [`diccionario_datos.md`](diccionario_datos.md).

Cada diagrama muestra las tablas de un esquema y sus relaciones, también con tablas de otros esquemas. Para que se lean, se omiten las columnas de autoría (quién creó, modificó o aprobó algo), que apuntan todas a `auth.users`.

## Identidad (`auth`)

```mermaid
erDiagram
  auth_roles {
    unicode code PK
  }
  auth_sessions {
    uuid id PK
  }
  auth_user_roles {
    uuid user_id PK
    unicode role_code PK
  }
  auth_users {
    uuid id PK
  }
  auth_users ||--o{ auth_sessions : user_id
  auth_roles ||--o{ auth_user_roles : role_code
  auth_users ||--o{ auth_user_roles : user_id
```

## Vacantes y acceso (`vacancy`)

```mermaid
erDiagram
  vacancy_job_profile_versions {
    uuid id PK
  }
  vacancy_vacancies {
    uuid id PK
  }
  vacancy_vacancy_members {
    uuid id PK
  }
  vacancy_vacancy_ownership_history {
    uuid id PK
  }
  vacancy_vacancy_sensitive_grants {
    uuid id PK
  }
  vacancy_vacancy_transfers {
    uuid id PK
  }
  files_file_assets ||--o{ vacancy_job_profile_versions : source_file_id
  vacancy_vacancies ||--o{ vacancy_job_profile_versions : vacancy_id
  auth_users ||--o{ vacancy_vacancies : owner_user_id
  auth_users ||--o{ vacancy_vacancy_members : user_id
  vacancy_vacancies ||--o{ vacancy_vacancy_members : vacancy_id
  auth_users ||--o{ vacancy_vacancy_ownership_history : new_owner_id
  auth_users ||--o{ vacancy_vacancy_ownership_history : previous_owner_id
  vacancy_vacancy_transfers ||--o{ vacancy_vacancy_ownership_history : transfer_id
  vacancy_vacancies ||--o{ vacancy_vacancy_ownership_history : vacancy_id
  auth_users ||--o{ vacancy_vacancy_sensitive_grants : user_id
  vacancy_vacancies ||--o{ vacancy_vacancy_sensitive_grants : vacancy_id
  auth_users ||--o{ vacancy_vacancy_transfers : from_user_id
  auth_users ||--o{ vacancy_vacancy_transfers : to_user_id
```

## Documentos (`files`)

```mermaid
erDiagram
  files_file_assets {
    uuid id PK
  }
  vacancy_vacancies ||--o{ files_file_assets : vacancy_id
```

## Inteligencia artificial (`ai`)

```mermaid
erDiagram
  ai_cv_batch_items {
    uuid id PK
  }
  ai_cv_batches {
    uuid id PK
  }
  ai_executions {
    uuid id PK
  }
  ai_models {
    uuid id PK
  }
  ai_operation_assignments {
    string operation PK
  }
  ai_prompt_versions {
    uuid id PK
  }
  ai_provider_credentials {
    uuid id PK
  }
  ai_providers {
    string code PK
  }
  ai_rubric_criteria {
    uuid id PK
  }
  ai_cv_batches ||--o{ ai_cv_batch_items : batch_id
  ai_cv_batch_items ||--o{ ai_cv_batch_items : duplicate_of
  files_file_assets ||--o{ ai_cv_batch_items : file_id
  files_file_assets ||--o{ ai_cv_batches : accepted_zip_file_id
  ai_prompt_versions ||--o{ ai_cv_batches : prompt_version_id
  files_file_assets ||--o{ ai_cv_batches : rejected_zip_file_id
  files_file_assets ||--o{ ai_cv_batches : report_file_id
  files_file_assets ||--o{ ai_cv_batches : unevaluable_zip_file_id
  vacancy_vacancies ||--o{ ai_cv_batches : vacancy_id
  ai_providers ||--o{ ai_models : provider_code
  ai_models ||--o{ ai_operation_assignments : model_ref
  ai_prompt_versions ||--o{ ai_prompt_versions : duplicated_from
  vacancy_job_profile_versions ||--o{ ai_prompt_versions : profile_version_id
  vacancy_vacancies ||--o{ ai_prompt_versions : vacancy_id
  ai_providers ||--o{ ai_provider_credentials : provider_code
  ai_prompt_versions ||--o{ ai_rubric_criteria : prompt_version_id
```

## Reclutamiento (`recruitment`)

```mermaid
erDiagram
  recruitment_application_movements {
    uuid id PK
  }
  recruitment_application_outcomes {
    uuid id PK
  }
  recruitment_application_syntheses {
    uuid id PK
  }
  recruitment_applications {
    uuid id PK
  }
  recruitment_assessments {
    uuid id PK
  }
  recruitment_call_sessions {
    uuid id PK
  }
  recruitment_campaigns {
    uuid id PK
  }
  recruitment_candidates {
    uuid id PK
  }
  recruitment_form_template_versions {
    uuid id PK
  }
  recruitment_form_templates {
    uuid id PK
  }
  recruitment_pipeline_stages {
    uuid id PK
  }
  recruitment_pipeline_versions {
    uuid id PK
  }
  recruitment_question_bank_versions {
    uuid id PK
  }
  recruitment_question_banks {
    uuid id PK
  }
  recruitment_applications ||--o{ recruitment_application_movements : application_id
  recruitment_pipeline_stages ||--o{ recruitment_application_movements : from_stage_id
  recruitment_pipeline_stages ||--o{ recruitment_application_movements : to_stage_id
  recruitment_applications ||--o{ recruitment_application_outcomes : application_id
  vacancy_vacancies ||--o{ recruitment_application_outcomes : vacancy_id
  recruitment_applications ||--o{ recruitment_application_syntheses : application_id
  vacancy_vacancies ||--o{ recruitment_application_syntheses : vacancy_id
  recruitment_campaigns ||--o{ recruitment_applications : campaign_id
  recruitment_candidates ||--o{ recruitment_applications : candidate_id
  files_file_assets ||--o{ recruitment_applications : cv_file_id
  ai_cv_batch_items ||--o{ recruitment_applications : evaluation_item_id
  recruitment_pipeline_stages ||--o{ recruitment_applications : stage_id
  vacancy_vacancies ||--o{ recruitment_applications : vacancy_id
  recruitment_applications ||--o{ recruitment_assessments : application_id
  files_file_assets ||--o{ recruitment_assessments : file_id
  recruitment_form_template_versions ||--o{ recruitment_assessments : template_version_id
  vacancy_vacancies ||--o{ recruitment_assessments : vacancy_id
  recruitment_applications ||--o{ recruitment_call_sessions : application_id
  recruitment_question_bank_versions ||--o{ recruitment_call_sessions : bank_version_id
  vacancy_vacancies ||--o{ recruitment_call_sessions : vacancy_id
  recruitment_pipeline_versions ||--o{ recruitment_campaigns : pipeline_version_id
  vacancy_vacancies ||--o{ recruitment_campaigns : vacancy_id
  recruitment_form_templates ||--o{ recruitment_form_template_versions : template_id
  recruitment_pipeline_versions ||--o{ recruitment_pipeline_stages : pipeline_version_id
  recruitment_question_banks ||--o{ recruitment_question_bank_versions : bank_id
  recruitment_question_banks ||--o{ recruitment_question_banks : duplicated_from
  auth_users ||--o{ recruitment_question_banks : owner_user_id
```

## Operación (`ops`)

```mermaid
erDiagram
  ops_audit_events {
    uuid id PK
  }
  ops_report_exports {
    uuid id PK
  }
```
