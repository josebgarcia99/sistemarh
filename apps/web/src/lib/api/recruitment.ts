import { z } from "zod";
import { apiFetch } from "./client";

export const STAGE_KIND_LABELS: Record<string, string> = {
  EVALUACION_CV: "Evaluación de CV",
  REVISION_RH: "Revisión de RH",
  LLAMADA: "Llamada telefónica",
  PSICOMETRIA: "Pruebas psicométricas",
  ENTREVISTA: "Entrevista",
  PRUEBA_TECNICA: "Prueba técnica",
  ESTUDIO_SOCIOECONOMICO: "Estudio socioeconómico",
  RESULTADO: "Resultado final",
  OTRA: "Otra",
};

const stageSchema = z.object({
  id: z.string(),
  position: z.number(),
  name: z.string(),
  kind: z.string(),
  is_optional: z.boolean(),
});
export type Stage = z.infer<typeof stageSchema>;

const pipelineSchema = z.object({
  id: z.string(),
  version_number: z.number(),
  created_at: z.string(),
  stages: z.array(stageSchema),
});
export type Pipeline = z.infer<typeof pipelineSchema>;
export type StageInput = { name: string; kind: string; is_optional: boolean };

const campaignSchema = z.object({
  id: z.string(),
  number: z.number(),
  name: z.string(),
  status: z.enum(["ABIERTA", "CERRADA"]),
  opened_at: z.string(),
  closed_at: z.string().nullable(),
});
export type Campaign = z.infer<typeof campaignSchema>;

export const applicationStatusSchema = z.enum([
  "ACTIVA",
  "DESISTIO",
  "DESCARTADA",
  "CANCELADA",
  "CONTRATADA",
  "NO_LOCALIZADA",
  "OTRO_CIERRE",
]);
export type ApplicationStatus = z.infer<typeof applicationStatusSchema>;
export const APPLICATION_STATUS_LABELS: Record<ApplicationStatus, string> = {
  ACTIVA: "Activa",
  DESISTIO: "Desistió",
  DESCARTADA: "No contratada",
  CANCELADA: "Vacante cancelada",
  CONTRATADA: "Contratada",
  NO_LOCALIZADA: "No localizada",
  OTRO_CIERRE: "Otro cierre",
};

/** Resultados finales de una postulación. Siempre los registra una persona. */
export const OUTCOME_KINDS = [
  "CONTRATADO",
  "NO_CONTRATADO",
  "DESISTIO",
  "NO_LOCALIZADO",
  "VACANTE_CANCELADA",
  "OTRO_CIERRE",
] as const;
export type OutcomeKind = (typeof OUTCOME_KINDS)[number];
export const OUTCOME_LABELS: Record<string, string> = {
  EN_PROCESO: "En proceso",
  CONTRATADO: "Contratado",
  NO_CONTRATADO: "No contratado",
  DESISTIO: "Desistió",
  NO_LOCALIZADO: "No localizado",
  VACANTE_CANCELADA: "Vacante cancelada",
  OTRO_CIERRE: "Otro cierre",
};
export const AI_LABELS: Record<string, string> = {
  ACEPTADO_IA: "Aceptado por IA",
  RECHAZADO_IA: "Rechazado por IA",
  NO_EVALUABLE: "No evaluable",
};

const applicationSchema = z.object({
  id: z.string(),
  candidate_id: z.string(),
  full_name: z.string(),
  email: z.string().nullable(),
  phone: z.string().nullable(),
  stage_id: z.string(),
  status: applicationStatusSchema,
  outcome: z.string(),
  ai_classification: z.string().nullable(),
  ai_score: z.string().nullable(),
  cv_file_id: z.string().nullable(),
  due_at: z.string().nullable(),
  created_at: z.string(),
  updated_at: z.string(),
});
export type Application = z.infer<typeof applicationSchema>;

const boardSchema = z.object({
  campaigns: z.array(campaignSchema),
  campaign: campaignSchema.nullable(),
  pipeline: pipelineSchema.nullable(),
  applications: z.array(applicationSchema),
  positions: z.number(),
  hires: z.number(),
});
export type Board = z.infer<typeof boardSchema>;

export const MOVEMENT_LABELS: Record<string, string> = {
  ALTA: "Alta",
  AVANCE: "Avance",
  RETROCESO: "Regreso",
  OMISION: "Etapa omitida",
  DESISTIMIENTO: "Desistimiento",
  DESCARTE: "Descarte",
  CANCELACION: "Cancelación",
  REACTIVACION: "Reactivación",
  REPROGRAMACION: "Reprogramación",
  INCIDENCIA: "Incidencia",
  CONTRATACION: "Contratación",
  NO_LOCALIZADO: "No localizado",
  CIERRE: "Otro cierre",
};

const outcomeSchema = z.object({
  id: z.string(),
  outcome: z.string(),
  reason: z.string().nullable(),
  notes: z.string().nullable(),
  start_date: z.string().nullable(),
  recorded_at: z.string(),
  recorded_by_name: z.string().nullable(),
  voided_at: z.string().nullable(),
  voided_by_name: z.string().nullable(),
  void_reason: z.string().nullable(),
});
export type Outcome = z.infer<typeof outcomeSchema>;

const movementSchema = z.object({
  id: z.string(),
  kind: z.string(),
  occurred_at: z.string(),
  actor_name: z.string().nullable(),
  from_stage: z.string().nullable(),
  to_stage: z.string().nullable(),
  note: z.string().nullable(),
  due_at: z.string().nullable(),
  mass: z.boolean(),
});
export type Movement = z.infer<typeof movementSchema>;

const jobSchema = z.object({
  title: z.string(),
  company: z.string(),
  start: z.string(),
  end: z.string(),
  current: z.boolean(),
  months: z.number().nullable(),
  approximate: z.boolean(),
});
const criterionResultSchema = z.object({
  id: z.string(),
  nivel: z.number().nullable(),
  sin_evidencia: z.boolean(),
  evidencia: z.string(),
  justificacion: z.string(),
});
const detailSchema = z.object({
  application: applicationSchema,
  campaign: campaignSchema,
  pipeline: pipelineSchema,
  movements: z.array(movementSchema),
  evaluation: z
    .object({
      classification: z.string(),
      score: z.string().nullable(),
      file_name: z.string(),
      result: z
        .object({
          criterios: z.array(criterionResultSchema).optional(),
          motivo: z.string().nullable().optional(),
          observaciones: z.string().nullable().optional(),
        })
        .passthrough(),
      extraction: z
        .object({
          habilidades: z.array(z.string()).optional(),
          certificaciones: z.array(z.string()).optional(),
          estudios: z
            .array(z.object({ titulo: z.string(), institucion: z.string(), periodo: z.string() }))
            .optional(),
        })
        .passthrough(),
    })
    .nullable(),
  tenure: z
    .object({
      jobs: z.array(jobSchema),
      average_months: z.number().nullable(),
      median_months: z.number().nullable(),
      total_months: z.number(),
      overlaps: z.number(),
      incomplete: z.number(),
    })
    .nullable(),
  outcomes: z.array(outcomeSchema),
});
export type ApplicationDetail = z.infer<typeof detailSchema>;

export type CandidateInput = { full_name: string; email: string | null; phone: string | null };
export type OutcomeInput = {
  outcome: OutcomeKind;
  reason: string | null;
  notes: string | null;
  start_date: string | null;
};

export function getBoard(vacancyId: string, campaignId: string | null, signal?: AbortSignal) {
  return apiFetch(`/vacancies/${vacancyId}/applications`, {
    schema: boardSchema,
    query: campaignId ? { campaign_id: campaignId } : undefined,
    signal,
  });
}

export function addCandidate(vacancyId: string, input: CandidateInput) {
  return apiFetch(`/vacancies/${vacancyId}/applications`, {
    method: "POST",
    body: input,
    schema: detailSchema,
  });
}

export function openCampaign(vacancyId: string, name: string | null) {
  return apiFetch(`/vacancies/${vacancyId}/campaigns`, {
    method: "POST",
    body: { name },
    schema: campaignSchema,
  });
}

export function closeCampaign(campaignId: string) {
  return apiFetch(`/campaigns/${campaignId}/close`, { method: "POST", schema: campaignSchema });
}

export function moveApplications(
  vacancyId: string,
  applicationIds: string[],
  toStageId: string,
  note: string | null,
) {
  return apiFetch(`/vacancies/${vacancyId}/application-moves`, {
    method: "POST",
    body: { application_ids: applicationIds, to_stage_id: toStageId, note },
    schema: z.array(applicationSchema),
  });
}

export function getApplication(applicationId: string, signal?: AbortSignal) {
  return apiFetch(`/applications/${applicationId}`, { schema: detailSchema, signal });
}

export function updateCandidate(applicationId: string, input: CandidateInput) {
  return apiFetch(`/applications/${applicationId}/candidate`, {
    method: "PUT",
    body: input,
    schema: detailSchema,
  });
}

export function recordOutcome(applicationId: string, input: OutcomeInput) {
  return apiFetch(`/applications/${applicationId}/outcome`, {
    method: "POST",
    body: input,
    schema: detailSchema,
  });
}

/** Reabre una postulación cerrada; su resultado final queda anulado. */
export function reopenApplication(applicationId: string, reason: string) {
  return apiFetch(`/applications/${applicationId}/reopening`, {
    method: "POST",
    body: { reason },
    schema: detailSchema,
  });
}

/** Con fecha es una reprogramación; sin ella, una incidencia. */
export function annotate(applicationId: string, note: string, dueAt: string | null) {
  return apiFetch(`/applications/${applicationId}/notes`, {
    method: "POST",
    body: { note, due_at: dueAt },
    schema: detailSchema,
  });
}

export function getPipeline(signal?: AbortSignal) {
  return apiFetch("/pipeline", { schema: pipelineSchema, signal });
}

export function savePipeline(stages: StageInput[], expectedVersion: number) {
  return apiFetch("/pipeline", {
    method: "PUT",
    body: { stages, expected_version: expectedVersion },
    schema: pipelineSchema,
  });
}

/** "2 años 6 meses" a partir de un número de meses. */
export function formatMonths(months: number | null): string {
  if (months === null) return "sin fechas completas";
  const whole = Math.round(months);
  const years = Math.floor(whole / 12);
  const rest = whole % 12;
  const parts = [];
  if (years > 0) parts.push(`${years} ${years === 1 ? "año" : "años"}`);
  if (rest > 0 || years === 0) parts.push(`${rest} ${rest === 1 ? "mes" : "meses"}`);
  return parts.join(" ");
}
