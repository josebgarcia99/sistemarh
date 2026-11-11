import { z } from "zod";
import { apiFetch } from "./client";

export const kindSchema = z.enum([
  "PSICOMETRIA",
  "ENTREVISTA",
  "PRUEBA_TECNICA",
  "ESTUDIO_SOCIOECONOMICO",
]);
export type Kind = z.infer<typeof kindSchema>;
export const KIND_LABELS: Record<Kind, string> = {
  PSICOMETRIA: "Prueba psicométrica",
  ENTREVISTA: "Entrevista con gerente",
  PRUEBA_TECNICA: "Prueba técnica",
  ESTUDIO_SOCIOECONOMICO: "Estudio socioeconómico",
};
/** Tipo de documento de la vacante que se adjunta a cada evaluación. */
export const KIND_DOCUMENT: Record<Kind, string> = {
  PSICOMETRIA: "PSICOMETRIA",
  ENTREVISTA: "ADJUNTO",
  PRUEBA_TECNICA: "PRUEBA_TECNICA",
  ESTUDIO_SOCIOECONOMICO: "ESTUDIO_SOCIOECONOMICO",
};
export const STATUS_LABELS: Record<string, string> = {
  PENDIENTE: "Pendiente",
  PRESENTADA: "Presentada",
  NO_PRESENTADA: "No presentada",
  INCOMPLETA: "Incompleta",
  NO_APLICA: "No aplica",
  ANULADA: "Anulada",
  VALIDADA: "Validada por un profesional",
  PROGRAMADA: "Programada",
  REALIZADA: "Realizada",
  NO_REALIZADA: "No realizada",
  CANCELADA: "Cancelada",
  EN_PROCESO: "En proceso",
  COMPLETADO: "Completado",
  ANULADO: "Anulado",
};
export const FIELD_TYPE_LABELS: Record<string, string> = {
  TEXTO: "Texto corto",
  PARRAFO: "Texto largo",
  FECHA: "Fecha",
  NUMERO: "Número",
  OPCIONES: "Opciones",
  CASILLA: "Casilla",
  DOCUMENTO: "Documento",
  OBSERVACION: "Observación",
};

const fieldSchema = z.object({
  id: z.string(),
  label: z.string(),
  type: z.string(),
  required: z.boolean(),
  options: z.array(z.string()),
  minimum: z.string().nullable(),
  maximum: z.string().nullable(),
});
export type FormField = z.infer<typeof fieldSchema>;
const sectionSchema = z.object({ title: z.string(), fields: z.array(fieldSchema) });
export type FormSection = z.infer<typeof sectionSchema>;

const templateSchema = z.object({
  id: z.string(),
  name: z.string(),
  description: z.string().nullable(),
  status: z.enum(["ACTIVA", "ARCHIVADA"]),
  version_number: z.number(),
  sections: z.array(sectionSchema),
});
export type FormTemplate = z.infer<typeof templateSchema>;
export type FieldInput = {
  id: string | null;
  label: string;
  type: string;
  required: boolean;
  options: string[];
  minimum: string | null;
  maximum: string | null;
};
export type TemplateInput = {
  name: string;
  description: string | null;
  sections: { title: string; fields: FieldInput[] }[];
  expected_version: number;
};

/** Lo capturado depende del tipo de evaluación; el servidor lo valida. */
export type AssessmentData = Record<string, unknown>;

const assessmentSchema = z.object({
  id: z.string(),
  application_id: z.string(),
  kind: kindSchema,
  status: z.string(),
  statuses: z.array(z.string()),
  event_date: z.string().nullable(),
  file_id: z.string().nullable(),
  data: z.record(z.string(), z.unknown()),
  score: z.string().nullable(),
  ai_summary: z.record(z.string(), z.union([z.string(), z.array(z.string())])).nullable(),
  ai_summary_at: z.string().nullable(),
  form: z.array(sectionSchema).nullable(),
  version: z.number(),
  updated_at: z.string(),
  updated_by_name: z.string().nullable(),
});
export type Assessment = z.infer<typeof assessmentSchema>;

const listSchema = z.object({
  items: z.array(assessmentSchema),
  restricted: z.array(kindSchema),
  writable: z.array(kindSchema),
});
export type AssessmentList = z.infer<typeof listSchema>;

const digitizationSchema = z.object({
  values: z.record(z.string(), z.union([z.string(), z.boolean()])),
  illegible: z.array(z.string()),
  missing: z.array(z.string()),
});
export type Digitization = z.infer<typeof digitizationSchema>;

export const SYNTHESIS_SECTIONS: [string, string][] = [
  ["hechos_documentados", "Hechos documentados"],
  ["declaraciones", "Lo que la persona declaró"],
  ["observaciones_humanas", "Observaciones de quienes la evaluaron"],
  ["resultados_tecnicos", "Resultados técnicos"],
  ["informacion_pendiente", "Información pendiente"],
  ["discrepancias_verificables", "Diferencias por aclarar entre fuentes"],
];
const synthesisSchema = z.object({
  id: z.string(),
  created_at: z.string(),
  created_by_name: z.string().nullable(),
  result: z.record(z.string(), z.array(z.string())),
  sources: z.array(z.string()),
  includes_psychometrics: z.boolean(),
});
export type Synthesis = z.infer<typeof synthesisSchema>;
const synthesisViewSchema = z.object({
  latest: synthesisSchema.nullable(),
  total: z.number(),
  hidden: z.boolean(),
});

export function listTemplates(signal?: AbortSignal) {
  return apiFetch("/form-templates", { schema: z.array(templateSchema), signal });
}

export function saveTemplate(templateId: string | null, input: TemplateInput) {
  return apiFetch(templateId ? `/form-templates/${templateId}` : "/form-templates", {
    method: templateId ? "PUT" : "POST",
    body: input,
    schema: templateSchema,
  });
}

export function templateAction(templateId: string, action: "archive" | "restore") {
  return apiFetch(`/form-templates/${templateId}/${action}`, {
    method: "POST",
    schema: templateSchema,
  });
}

export function listAssessments(applicationId: string, signal?: AbortSignal) {
  return apiFetch(`/applications/${applicationId}/assessments`, { schema: listSchema, signal });
}

export function createAssessment(
  applicationId: string,
  input: { kind: Kind; data: AssessmentData; template_id?: string | null },
) {
  return apiFetch(`/applications/${applicationId}/assessments`, {
    method: "POST",
    body: input,
    schema: assessmentSchema,
  });
}

export function updateAssessment(
  id: string,
  input: {
    status: string;
    data: AssessmentData;
    event_date: string | null;
    file_id: string | null;
    version: number;
  },
) {
  return apiFetch(`/assessments/${id}`, { method: "PUT", body: input, schema: assessmentSchema });
}

export function summarizeAssessment(id: string) {
  return apiFetch(`/assessments/${id}/summary`, { method: "POST", schema: assessmentSchema });
}

export function digitizeStudy(id: string, fileId: string) {
  return apiFetch(`/assessments/${id}/digitization`, {
    method: "POST",
    body: { file_id: fileId },
    schema: digitizationSchema,
  });
}

export function getSyntheses(applicationId: string, signal?: AbortSignal) {
  return apiFetch(`/applications/${applicationId}/syntheses`, {
    schema: synthesisViewSchema,
    signal,
  });
}

export function createSynthesis(applicationId: string) {
  return apiFetch(`/applications/${applicationId}/syntheses`, {
    method: "POST",
    schema: synthesisSchema,
  });
}
