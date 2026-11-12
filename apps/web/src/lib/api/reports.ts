import { z } from "zod";
import { apiFetch } from "./client";

const snapshotSchema = z.object({
  vacancies: z.number(),
  vacancies_open: z.number(),
  own: z.number(),
  shared: z.number(),
  active_applications: z.number(),
  in_calls: z.number(),
  tests_pending: z.number(),
  interviews_pending: z.number(),
});
const totalsSchema = z.object({
  cv_analyzed: z.number(),
  ai_accepted: z.number(),
  ai_rejected: z.number(),
  ai_unevaluable: z.number(),
  applications: z.number(),
  closed: z.number(),
  hires: z.number(),
  withdrawals: z.number(),
  not_hired: z.number(),
  not_located: z.number(),
  cancelled: z.number(),
  other_closures: z.number(),
  coverage_days: z.number().nullable(),
});
const stageRowSchema = z.object({
  name: z.string(),
  kind: z.string(),
  active: z.number(),
  reached: z.number(),
  conversion: z.number().nullable(),
  average_days: z.number().nullable(),
  stays: z.number(),
});
export type StageRow = z.infer<typeof stageRowSchema>;
const vacancyRowSchema = z.object({
  id: z.string(),
  name: z.string(),
  department: z.string(),
  status: z.string(),
  owner_name: z.string(),
  positions: z.number(),
  hires_total: z.number(),
  active: z.number(),
  cv_analyzed: z.number(),
  applications: z.number(),
  closed: z.number(),
  hires: z.number(),
  coverage_days: z.number().nullable(),
});
const recruiterRowSchema = z.object({
  user_id: z.string(),
  name: z.string(),
  vacancies: z.number(),
  vacancies_open: z.number(),
  collaborating: z.number(),
  active: z.number(),
  closed: z.number(),
  hires: z.number(),
});
const monthRowSchema = z.object({
  month: z.string(),
  cv_analyzed: z.number(),
  applications: z.number(),
  closed: z.number(),
  hires: z.number(),
  withdrawals: z.number(),
});
const aiUsageSchema = z.object({
  calls: z.number(),
  failures: z.number(),
  cost_usd: z.string(),
  operations: z.array(
    z.object({
      operation: z.string(),
      calls: z.number(),
      failures: z.number(),
      cost_usd: z.string(),
    }),
  ),
});
const activitySchema = z.object({
  occurred_at: z.string(),
  kind: z.string(),
  candidate: z.string(),
  vacancy_id: z.string(),
  vacancy: z.string(),
  stage: z.string().nullable(),
  actor_name: z.string().nullable(),
});
export type Activity = z.infer<typeof activitySchema>;

const overviewSchema = z.object({
  snapshot: snapshotSchema,
  totals: totalsSchema,
  stages: z.array(stageRowSchema),
  funnel_hired: z.number(),
  vacancies: z.array(vacancyRowSchema),
  months: z.array(monthRowSchema),
  recent: z.array(activitySchema),
  // Solo llegan a un administrador.
  recruiters: z.array(recruiterRowSchema).nullable(),
  ai: aiUsageSchema.nullable(),
  cv_failures: z.number().nullable(),
});
export type Overview = z.infer<typeof overviewSchema>;

const historyRowSchema = z.object({
  application_id: z.string(),
  vacancy_id: z.string(),
  candidate: z.string(),
  vacancy: z.string(),
  department: z.string(),
  owner_name: z.string(),
  stage: z.string(),
  outcome: z.string(),
  outcome_reason: z.string().nullable(),
  ai_classification: z.string().nullable(),
  ai_score: z.string().nullable(),
  model: z.string().nullable(),
  prompt_version: z.number().nullable(),
  created_at: z.string(),
  cv_uploaded_at: z.string().nullable(),
  evaluated_at: z.string().nullable(),
  last_movement_at: z.string().nullable(),
  closed_at: z.string().nullable(),
  closed_by_name: z.string().nullable(),
  start_date: z.string().nullable(),
});
export type HistoryRow = z.infer<typeof historyRowSchema>;
const historySchema = z.object({ rows: z.array(historyRowSchema), total: z.number() });

const optionSchema = z.object({ id: z.string(), name: z.string() });
const optionsSchema = z.object({
  vacancies: z.array(optionSchema),
  owners: z.array(optionSchema),
  collaborators: z.array(optionSchema),
  departments: z.array(z.string()),
  stages: z.array(z.string()),
  models: z.array(z.string()),
  prompt_versions: z.array(optionSchema),
  banks: z.array(optionSchema),
});
export type ReportOptions = z.infer<typeof optionsSchema>;

const exportSchema = z.object({
  id: z.string(),
  kind: z.enum(["INDICADORES", "POSTULACIONES"]),
  name: z.string(),
  filters: z.record(z.string(), z.string()),
  row_count: z.number(),
  size_bytes: z.number(),
  sha256: z.string(),
  created_at: z.string(),
});
export type ReportExport = z.infer<typeof exportSchema>;
export type ExportKind = ReportExport["kind"];

export const DATE_KIND_LABELS: Record<string, string> = {
  CARGA: "Carga del CV",
  EVALUACION: "Evaluación del CV",
  MOVIMIENTO: "Movimiento",
  CIERRE: "Cierre",
};
export const VACANCY_STATUS_LABELS: Record<string, string> = {
  BORRADOR: "Borrador",
  ABIERTA: "Abierta",
  PAUSADA: "Pausada",
  CERRADA: "Cerrada",
  CANCELADA: "Cancelada",
  ARCHIVADA: "Archivada",
};
export const OPERATION_LABELS: Record<string, string> = {
  ANALISIS_PERFILES: "Análisis de perfiles",
  GENERACION_PROMPTS: "Generación de prompts",
  EXTRACCION_CV: "Extracción de CV",
  EVALUACION_DOCUMENTAL: "Evaluación de CV",
  ANALISIS_LLAMADAS: "Análisis de llamadas",
  LECTURA_DOCUMENTOS: "Lectura de documentos",
  RESUMEN_PRUEBAS: "Resumen de pruebas",
  SINTESIS_EXPEDIENTES: "Síntesis de expedientes",
  DESCRIPCION_FOTOGRAFIAS: "Descripción de fotografías",
};

/** Filtros de los reportes. Una cadena vacía significa «sin filtro». */
export type ReportFilters = {
  date_from: string;
  date_to: string;
  vacancy_id: string;
  owner_id: string;
  collaborator_id: string;
  department: string;
  vacancy_status: string;
  date_kind: string;
  stage: string;
  candidate: string;
  ai_classification: string;
  score_min: string;
  score_max: string;
  model: string;
  prompt_version_id: string;
  bank_id: string;
  outcome: string;
};
export const EMPTY_FILTERS: ReportFilters = {
  date_from: "",
  date_to: "",
  vacancy_id: "",
  owner_id: "",
  collaborator_id: "",
  department: "",
  vacancy_status: "",
  date_kind: "CARGA",
  stage: "",
  candidate: "",
  ai_classification: "",
  score_min: "",
  score_max: "",
  model: "",
  prompt_version_id: "",
  bank_id: "",
  outcome: "",
};

/** Solo los filtros con valor, tal como los espera la API. */
export function activeFilters(filters: Partial<ReportFilters>): Record<string, string> {
  const active: Record<string, string> = {};
  for (const [key, value] of Object.entries(filters)) {
    const text = (value ?? "").trim();
    if (text && !(key === "date_kind" && text === "CARGA")) active[key] = text;
  }
  return active;
}

export function getOverview(filters: Partial<ReportFilters>, signal?: AbortSignal) {
  return apiFetch("/reports/overview", {
    schema: overviewSchema,
    query: activeFilters(filters),
    signal,
  });
}

export function getHistory(
  filters: Partial<ReportFilters>,
  page: { limit: number; offset: number },
  signal?: AbortSignal,
) {
  return apiFetch("/reports/applications", {
    schema: historySchema,
    query: { ...activeFilters(filters), ...page },
    signal,
  });
}

export function getReportOptions(signal?: AbortSignal) {
  return apiFetch("/reports/options", { schema: optionsSchema, signal });
}

export function listExports(signal?: AbortSignal) {
  return apiFetch("/reports/exports", { schema: z.array(exportSchema), signal });
}

export function createExport(kind: ExportKind, filters: Partial<ReportFilters>) {
  return apiFetch("/reports/exports", {
    method: "POST",
    body: { kind, ...activeFilters(filters) },
    schema: exportSchema,
  });
}

export function exportDownloadUrl(exportId: string): string {
  return `/api/v1/reports/exports/${exportId}/download`;
}

/** Día de hoy y el de hace ``days`` días, en la hora de Ciudad de México. */
export function lastDays(days: number, now: Date = new Date()): { date_from: string; date_to: string } {
  const day = new Intl.DateTimeFormat("en-CA", { timeZone: "America/Mexico_City" });
  const start = new Date(now.getTime() - (days - 1) * 86_400_000);
  return { date_from: day.format(start), date_to: day.format(now) };
}
