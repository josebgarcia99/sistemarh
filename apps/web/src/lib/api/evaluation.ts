import { z } from "zod";
import { apiFetch } from "./client";

/** Datos de una línea: identificación del puesto y datos del documento. */
export const PROFILE_LINE_FIELDS = [
  "position_name",
  "area",
  "location",
  "reports_to",
  "supervises",
  "contract_type",
  "work_mode",
  "schedule",
  "offer",
  "specialty",
  "document_version",
  "document_date",
] as const;
export const PROFILE_TEXT_FIELDS = [
  "objective",
  "internal_relations",
  "external_relations",
  "experience",
  "education",
] as const;
/** Listas que se capturan una por línea. */
export const PROFILE_LIST_FIELDS = [
  "must_have",
  "knowledge",
  "skills",
  "functions",
  "nice_to_have",
  "certifications",
  "responsibilities",
  "ambiguities",
] as const;
export type ProfileLineField = (typeof PROFILE_LINE_FIELDS)[number];
export type ProfileTextField = (typeof PROFILE_TEXT_FIELDS)[number];
export type ProfileListField = (typeof PROFILE_LIST_FIELDS)[number];

/** Niveles de «Formación académica» y periodicidades, como en el formato de la empresa. */
export const EDUCATION_LEVELS = [
  "Maestría",
  "Licenciatura",
  "Ingeniería",
  "TSU",
  "Bachillerato",
  "Secundaria",
] as const;
export const FREQUENCIES = ["Ocasional", "Diaria", "Semanal", "Mensual", "Anual"] as const;

/** Etiquetas del formato «SGC.F15.RH. Perfil de puesto». */
export const PROFILE_LABELS: Record<
  ProfileLineField | ProfileTextField | ProfileListField,
  string
> = {
  position_name: "Nombre del puesto",
  area: "Área o departamento",
  location: "Ubicación",
  reports_to: "Reporta a",
  supervises: "Supervisa a",
  contract_type: "Tipo de contratación",
  work_mode: "Modalidad",
  schedule: "Horario",
  offer: "Oferta",
  specialty: "Especialidad",
  document_version: "Versión del perfil",
  document_date: "Fecha de actualización",
  objective: "Propósito del puesto",
  internal_relations: "Relaciones internas",
  external_relations: "Relaciones externas",
  experience: "Experiencia previa",
  education: "Aclaraciones sobre la formación",
  must_have: "Requisitos indispensables",
  knowledge: "Conocimientos específicos",
  skills: "Habilidades blandas",
  functions: "Funciones del puesto",
  nice_to_have: "Requisitos deseables",
  certifications: "Certificaciones",
  responsibilities: "Responsabilidades",
  ambiguities: "Requisitos que no están claros",
};

const items = z.array(z.string());
const activitySchema = z.object({ description: z.string(), frequency: z.string() });
const kpiSchema = z.object({ name: z.string(), goal: z.string(), formula: z.string() });
export type ProfileActivity = z.infer<typeof activitySchema>;
export type ProfileKpi = z.infer<typeof kpiSchema>;

const profileFields = {
  position_name: z.string(),
  area: z.string(),
  location: z.string(),
  reports_to: z.string(),
  supervises: z.string(),
  contract_type: z.string(),
  work_mode: z.string(),
  schedule: z.string(),
  offer: z.string(),
  specialty: z.string(),
  document_version: z.string(),
  document_date: z.string(),
  objective: z.string(),
  internal_relations: z.string(),
  external_relations: z.string(),
  experience: z.string(),
  education: z.string(),
  education_levels: items,
  must_have: items,
  knowledge: items,
  skills: items,
  functions: items,
  nice_to_have: items,
  certifications: items,
  responsibilities: items,
  ambiguities: items,
  activities: z.array(activitySchema),
  kpis: z.array(kpiSchema),
};
const profileOriginSchema = z.enum(["MANUAL", "IA", "FORMATO"]);
export type ProfileOrigin = z.infer<typeof profileOriginSchema>;

const profileVersionSchema = z.object({
  id: z.string(),
  version_number: z.number(),
  origin: profileOriginSchema,
  change_note: z.string().nullable(),
  created_at: z.string(),
  created_by_name: z.string().nullable(),
  ...profileFields,
});
export type ProfileVersion = z.infer<typeof profileVersionSchema>;
export type ProfileInput = Record<ProfileLineField | ProfileTextField, string> &
  Record<ProfileListField, string[]> & {
    education_levels: string[];
    activities: ProfileActivity[];
    kpis: ProfileKpi[];
    change_note: string | null;
    expected_version: number;
    /** De dónde partió la persona: captura manual, propuesta de la IA o formato de la empresa. */
    origin: ProfileOrigin;
    /** Documento de la vacante del que salió la propuesta. */
    source_file_id: string | null;
  };

const profileProposalSchema = z.object({
  ...profileFields,
  truncated: z.boolean(),
  source_file_id: z.string().nullable(),
  origin: profileOriginSchema,
  notices: z.array(z.string()),
});
/** Perfil leído del formato de la empresa o propuesto por la IA. No está guardado. */
export type ProfileProposal = z.infer<typeof profileProposalSchema>;

const criteriaProposalSchema = z.object({
  suggestions: z.array(
    z.object({
      id: z.string(),
      code: z.string(),
      name: z.string(),
      description: z.string(),
      levels: z.array(z.string()).length(5),
    }),
  ),
  observations: z.array(z.string()),
});
/** Mejoras de redacción propuestas por la IA. No están guardadas. */
export type CriteriaProposal = z.infer<typeof criteriaProposalSchema>;

export const promptStatusSchema = z.enum(["BORRADOR", "EN_REVISION", "APROBADO", "ARCHIVADO"]);
export type PromptStatus = z.infer<typeof promptStatusSchema>;
export const PROMPT_STATUS_LABELS: Record<PromptStatus, string> = {
  BORRADOR: "Borrador",
  EN_REVISION: "En revisión",
  APROBADO: "Aprobado",
  ARCHIVADO: "Archivado",
};

const criterionSchema = z.object({
  id: z.string(),
  code: z.string(),
  name: z.string(),
  description: z.string(),
  kind: z.enum(["INDISPENSABLE", "DESEABLE"]),
  weight: z.string(),
  levels: z.array(z.string()).length(5),
  origin: z.enum(["PERFIL", "MANUAL"]),
});
export type Criterion = z.infer<typeof criterionSchema>;

const promptSchema = z.object({
  id: z.string(),
  vacancy_id: z.string(),
  version_number: z.number(),
  status: promptStatusSchema,
  profile_version_number: z.number().nullable(),
  pass_threshold: z.string(),
  revision: z.number(),
  layers: z.array(
    z.object({ key: z.string(), title: z.string(), content: z.string(), locked: z.boolean() }),
  ),
  criteria: z.array(criterionSchema),
  rendered: z.string(),
  length: z.number(),
  max_length: z.number(),
  issues: z.array(z.string()),
  duplicated_from: z.string().nullable(),
  created_at: z.string(),
  created_by_name: z.string().nullable(),
  updated_at: z.string(),
  approved_at: z.string().nullable(),
  approved_by_name: z.string().nullable(),
});
export type PromptVersion = z.infer<typeof promptSchema>;

export type CriterionInput = {
  id: string | null;
  name: string;
  description: string;
  kind: "INDISPENSABLE" | "DESEABLE";
  weight: string;
  levels: string[];
};
export type PromptEdit = {
  layers: Record<string, string>;
  criteria: CriterionInput[];
  pass_threshold: string;
  revision: number;
};
export type PromptAction = "submit" | "return" | "approve" | "archive";

export function listProfileVersions(vacancyId: string, signal?: AbortSignal) {
  return apiFetch(`/vacancies/${vacancyId}/profile-versions`, {
    schema: z.array(profileVersionSchema),
    signal,
  });
}

export function saveProfile(vacancyId: string, input: ProfileInput): Promise<ProfileVersion> {
  return apiFetch(`/vacancies/${vacancyId}/profile-versions`, {
    method: "POST",
    body: input,
    schema: profileVersionSchema,
  });
}

export function listPrompts(vacancyId: string, signal?: AbortSignal): Promise<PromptVersion[]> {
  return apiFetch(`/vacancies/${vacancyId}/prompts`, { schema: z.array(promptSchema), signal });
}

export function generatePrompt(vacancyId: string): Promise<PromptVersion> {
  return apiFetch(`/vacancies/${vacancyId}/prompts`, { method: "POST", schema: promptSchema });
}

export function updatePrompt(id: string, edit: PromptEdit): Promise<PromptVersion> {
  return apiFetch(`/prompts/${id}`, { method: "PUT", body: edit, schema: promptSchema });
}

export function promptAction(
  id: string,
  action: PromptAction,
  revision: number,
): Promise<PromptVersion> {
  return apiFetch(`/prompts/${id}/${action}`, {
    method: "POST",
    body: { revision },
    schema: promptSchema,
  });
}

export function duplicatePrompt(id: string): Promise<PromptVersion> {
  return apiFetch(`/prompts/${id}/duplicate`, { method: "POST", schema: promptSchema });
}

/** Lee un perfil desde un documento de la vacante (el formato en Excel se lee sin IA) o desde un texto. */
export function extractProfile(
  vacancyId: string,
  source: { fileId: string } | { text: string },
): Promise<ProfileProposal> {
  return apiFetch(`/vacancies/${vacancyId}/profile-extractions`, {
    method: "POST",
    body: "fileId" in source ? { file_id: source.fileId } : { text: source.text },
    schema: profileProposalSchema,
  });
}

export function proposeCriteria(promptId: string): Promise<CriteriaProposal> {
  return apiFetch(`/prompts/${promptId}/criteria-proposals`, {
    method: "POST",
    schema: criteriaProposalSchema,
  });
}
