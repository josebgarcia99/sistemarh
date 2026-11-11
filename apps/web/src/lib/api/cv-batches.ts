import { z } from "zod";
import { apiFetch } from "./client";

export const batchStatusSchema = z.enum([
  "PENDIENTE",
  "EN_COLA",
  "PROCESANDO",
  "COMPLETADO",
  "COMPLETADO_CON_INCIDENCIAS",
  "FALLIDO",
  "CANCELADO",
]);
export type BatchStatus = z.infer<typeof batchStatusSchema>;
export const BATCH_STATUS_LABELS: Record<BatchStatus, string> = {
  PENDIENTE: "Pendiente",
  EN_COLA: "En cola",
  PROCESANDO: "Procesando",
  COMPLETADO: "Completado",
  COMPLETADO_CON_INCIDENCIAS: "Completado con incidencias",
  FALLIDO: "Detenido por un error",
  CANCELADO: "Cancelado",
};
const ACTIVE: BatchStatus[] = ["PENDIENTE", "EN_COLA", "PROCESANDO"];
export const isActive = (batch: { status: BatchStatus }) => ACTIVE.includes(batch.status);

export const classificationSchema = z.enum(["ACEPTADO_IA", "RECHAZADO_IA", "NO_EVALUABLE"]);
export type Classification = z.infer<typeof classificationSchema>;
export const CLASSIFICATION_LABELS: Record<Classification, string> = {
  ACEPTADO_IA: "Aceptado por IA",
  RECHAZADO_IA: "Rechazado por IA",
  NO_EVALUABLE: "No evaluable",
};

const batchSchema = z.object({
  id: z.string(),
  vacancy_id: z.string(),
  status: batchStatusSchema,
  stalled: z.boolean(),
  total: z.number(),
  evaluated: z.number(),
  failed: z.number(),
  pending: z.number(),
  accepted: z.number(),
  rejected: z.number(),
  unevaluable: z.number(),
  error: z.string().nullable(),
  created_at: z.string(),
  created_by_name: z.string().nullable(),
  started_at: z.string().nullable(),
  finished_at: z.string().nullable(),
  report_file_id: z.string().nullable(),
  accepted_zip_file_id: z.string().nullable(),
  rejected_zip_file_id: z.string().nullable(),
  unevaluable_zip_file_id: z.string().nullable(),
});
export type CvBatch = z.infer<typeof batchSchema>;

const overviewSchema = z.object({
  approved_prompt: z
    .object({
      id: z.string(),
      version_number: z.number(),
      pass_threshold: z.string(),
      criteria: z.number(),
    })
    .nullable(),
  total_cvs: z.number(),
  pending_cvs: z.number(),
  batches: z.array(batchSchema),
});
export type CvOverview = z.infer<typeof overviewSchema>;

const itemSchema = z.object({
  id: z.string(),
  file_id: z.string(),
  file_name: z.string(),
  position: z.number(),
  status: z.enum(["PENDIENTE", "EVALUADO", "FALLIDO"]),
  step: z.string(),
  classification: classificationSchema.nullable(),
  score: z.string().nullable(),
  reason: z.string().nullable(),
  notes: z.string().nullable(),
  quality: z.record(z.string(), z.number()).nullable(),
  digitization_suspect: z.boolean(),
  truncated: z.boolean(),
  duplicate: z.boolean(),
  error_code: z.string().nullable(),
  error_message: z.string().nullable(),
  attempts: z.number(),
  criteria: z.array(
    z.object({
      code: z.string(),
      level: z.number().nullable(),
      no_evidence: z.boolean(),
      evidence: z.string(),
      justification: z.string(),
    }),
  ),
});
export type CvBatchItem = z.infer<typeof itemSchema>;

const detailSchema = z.object({ batch: batchSchema, items: z.array(itemSchema) });
export type CvBatchDetail = z.infer<typeof detailSchema>;

export function getCvOverview(vacancyId: string, signal?: AbortSignal): Promise<CvOverview> {
  return apiFetch(`/vacancies/${vacancyId}/cv-batches`, { schema: overviewSchema, signal });
}

export function startCvBatch(vacancyId: string, reevaluate: boolean): Promise<CvBatchDetail> {
  return apiFetch(`/vacancies/${vacancyId}/cv-batches`, {
    method: "POST",
    body: { reevaluate },
    schema: detailSchema,
  });
}

export function getCvBatch(batchId: string, signal?: AbortSignal): Promise<CvBatchDetail> {
  return apiFetch(`/cv-batches/${batchId}`, { schema: detailSchema, signal });
}

export function cvBatchAction(batchId: string, action: "retry" | "cancel"): Promise<CvBatchDetail> {
  return apiFetch(`/cv-batches/${batchId}/${action}`, { method: "POST", schema: detailSchema });
}
