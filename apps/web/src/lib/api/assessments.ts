import { z } from "zod";
import { apiDownload, apiFetch } from "./client";
import type { DocumentType } from "./files";

export const kindSchema = z.enum([
  "PSICOMETRIA",
  "ENTREVISTA",
  "PRUEBA_TECNICA",
  "ESTUDIO_SOCIOECONOMICO",
  "REFERENCIAS",
]);
export type Kind = z.infer<typeof kindSchema>;
export const KIND_LABELS: Record<Kind, string> = {
  PSICOMETRIA: "Prueba psicométrica",
  ENTREVISTA: "Entrevista con gerente",
  PRUEBA_TECNICA: "Prueba técnica",
  ESTUDIO_SOCIOECONOMICO: "Estudio socioeconómico",
  REFERENCIAS: "Referencias laborales y personales",
};
/** Tipo de documento de la vacante que se adjunta a cada evaluación. */
export const KIND_DOCUMENT: Record<Kind, DocumentType> = {
  PSICOMETRIA: "PSICOMETRIA",
  ENTREVISTA: "ADJUNTO",
  PRUEBA_TECNICA: "PRUEBA_TECNICA",
  ESTUDIO_SOCIOECONOMICO: "ESTUDIO_SOCIOECONOMICO",
  REFERENCIAS: "ADJUNTO",
};
export const REFERENCE_TYPES: [string, string][] = [
  ["LABORAL", "Laboral"],
  ["PERSONAL", "Personal"],
];
export const REFERENCE_RESULTS: [string, string][] = [
  ["PENDIENTE", "Pendiente de contactar"],
  ["CONTACTADA", "Contactada"],
  ["NO_LOCALIZADA", "No se localizó"],
  ["SE_NEGO", "Se negó a dar referencias"],
];
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
  TABLA: "Tabla",
};

const fieldSchema = z.object({
  id: z.string(),
  label: z.string(),
  type: z.string(),
  required: z.boolean(),
  options: z.array(z.string()),
  minimum: z.string().nullable(),
  maximum: z.string().nullable(),
  /** Encabezados de las columnas, si el campo es una tabla. */
  columns: z.array(z.string()),
  /** Solo lo captura una persona: la IA no lo llena al leer un documento. */
  manual_only: z.boolean(),
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
  /** Ya se cargó el Excel en blanco del formato de la empresa. */
  has_study_format: z.boolean().default(false),
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
  columns: string[];
  manual_only: boolean;
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
  values: z.record(z.string(), z.union([z.string(), z.boolean(), z.array(z.array(z.string()))])),
  illegible: z.array(z.string()),
  missing: z.array(z.string()),
});
export type Digitization = z.infer<typeof digitizationSchema>;

export const SYNTHESIS_SECTIONS: [string, string][] = [
  ["avance_por_etapa", "Qué aportó cada etapa frente a las anteriores"],
  ["hechos_documentados", "Hechos documentados"],
  ["declaraciones", "Lo que la persona declaró"],
  ["observaciones_humanas", "Observaciones de quienes la evaluaron"],
  ["resultados_tecnicos", "Resultados técnicos"],
  ["informacion_pendiente", "Información pendiente"],
  ["coincidencias_entre_fuentes", "Coincidencias entre fuentes"],
  ["discrepancias_verificables", "Diferencias por aclarar entre fuentes"],
  ["preguntas_sugeridas", "Preguntas sugeridas para la siguiente etapa"],
];
const synthesisSchema = z.object({
  id: z.string(),
  created_at: z.string(),
  created_by_name: z.string().nullable(),
  result: z.record(z.string(), z.array(z.string())),
  sources: z.array(z.string()),
  includes_psychometrics: z.boolean(),
  /** Usó descripciones de fotografías del estudio: verla exige ese permiso. */
  includes_study: z.boolean(),
});
export type Synthesis = z.infer<typeof synthesisSchema>;
const synthesisViewSchema = z.object({
  latest: synthesisSchema.nullable(),
  total: z.number(),
  /** Las síntesis visibles, de la más reciente a la más antigua. */
  history: z.array(synthesisSchema).default([]),
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

/** Carga el Excel en blanco del formato de la empresa (solo administradores). */
export function uploadStudyFormat(templateId: string, file: File) {
  return apiFetch(`/form-templates/${templateId}/study-format`, {
    method: "PUT",
    file,
    schema: z.object({ missing_sections: z.array(z.string()) }),
  });
}

/** El estudio guardado, en el formato de la empresa. Avisa de lo que no cupo. */
export async function downloadStudyFile(id: string) {
  const { blob, name, headers } = await apiDownload(`/assessments/${id}/study-format`);
  let unplaced: string[] = [];
  try {
    unplaced = z.array(z.string()).parse(JSON.parse(decodeURIComponent(headers.get("X-Unplaced") ?? "[]")));
  } catch {
    unplaced = [];
  }
  return { blob, name: name ?? "Estudio socioeconomico.xlsx", unplaced };
}

export function digitizeStudy(id: string, fileId: string) {
  return apiFetch(`/assessments/${id}/digitization`, {
    method: "POST",
    body: { file_id: fileId },
    schema: digitizationSchema,
  });
}

const studyQueueItemSchema = z.object({
  application_id: z.string(),
  vacancy_id: z.string(),
  candidate_name: z.string(),
  vacancy_name: z.string(),
  active: z.boolean(),
  study_status: z.string().nullable(),
  study_updated_at: z.string().nullable(),
  references_status: z.string().nullable().default(null),
});
export type StudyQueueItem = z.infer<typeof studyQueueItemSchema>;

/** Lista de trabajo del analista de estudios: personas en proceso y su estudio. */
export function listStudyQueue(search: string, signal?: AbortSignal) {
  return apiFetch("/study-queue", {
    query: search ? { search } : undefined,
    schema: z.array(studyQueueItemSchema),
    signal,
  });
}

const photoDescriptionSchema = z.object({
  description: z.string(),
  unclear: z.array(z.string()),
});
export type PhotoDescription = z.infer<typeof photoDescriptionSchema>;

/** La IA describe lo que se ve en una fotografía del estudio. No guarda nada. */
export function describePhoto(id: string, fileId: string, fieldId: string | null, title?: string) {
  return apiFetch(`/assessments/${id}/photo-descriptions`, {
    method: "POST",
    // Una fotografía adicional no pertenece a un campo: viaja con su título.
    body: { file_id: fileId, field_id: fieldId, title: title || null },
    schema: photoDescriptionSchema,
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
