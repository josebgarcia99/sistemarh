import { z } from "zod";
import { apiFetch } from "./client";

export const PROFILE_TEXT_FIELDS = ["objective", "experience", "education"] as const;
export const PROFILE_LIST_FIELDS = [
  "must_have",
  "nice_to_have",
  "functions",
  "responsibilities",
  "knowledge",
  "skills",
  "certifications",
  "ambiguities",
] as const;
export type ProfileTextField = (typeof PROFILE_TEXT_FIELDS)[number];
export type ProfileListField = (typeof PROFILE_LIST_FIELDS)[number];

export const PROFILE_LABELS: Record<ProfileTextField | ProfileListField, string> = {
  objective: "Objetivo del puesto",
  experience: "Experiencia",
  education: "Formación",
  must_have: "Requisitos indispensables",
  nice_to_have: "Requisitos deseables",
  functions: "Funciones",
  responsibilities: "Responsabilidades",
  knowledge: "Conocimientos",
  skills: "Habilidades",
  certifications: "Certificaciones",
  ambiguities: "Requisitos que no están claros",
};

const items = z.array(z.string());
const profileVersionSchema = z.object({
  id: z.string(),
  version_number: z.number(),
  origin: z.string(),
  change_note: z.string().nullable(),
  created_at: z.string(),
  created_by_name: z.string().nullable(),
  objective: z.string(),
  experience: z.string(),
  education: z.string(),
  functions: items,
  responsibilities: items,
  knowledge: items,
  skills: items,
  certifications: items,
  must_have: items,
  nice_to_have: items,
  ambiguities: items,
});
export type ProfileVersion = z.infer<typeof profileVersionSchema>;
export type ProfileInput = Record<ProfileTextField, string> &
  Record<ProfileListField, string[]> & { change_note: string | null; expected_version: number };

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
