import { z } from "zod";
import { apiFetch } from "./client";

export const providerCodeSchema = z.enum(["ANTHROPIC", "OPENAI"]);
export type ProviderCode = z.infer<typeof providerCodeSchema>;

const providerSchema = z.object({
  code: providerCodeSchema,
  name: z.string(),
  enabled: z.boolean(),
  key_configured: z.boolean(),
  key_source: z.enum(["PANTALLA", "ENTORNO"]).nullable(),
  key_mask: z.string().nullable(),
  key_updated_at: z.string().nullable(),
  key_updated_by_name: z.string().nullable(),
  last_test_at: z.string().nullable(),
  last_test_ok: z.boolean().nullable(),
  last_test_error: z.string().nullable(),
  monthly_limit_usd: z.string().nullable(),
  models_available: z.number(),
});
export type AiProvider = z.infer<typeof providerSchema>;

const overviewSchema = z.object({
  encryption_available: z.boolean(),
  providers: z.array(providerSchema),
});
export type AiOverview = z.infer<typeof overviewSchema>;

const modelSchema = z.object({
  id: z.string(),
  provider_code: providerCodeSchema,
  provider_name: z.string(),
  model_id: z.string(),
  display_name: z.string(),
  is_available: z.boolean(),
  reports_capabilities: z.boolean(),
});
export type AiModel = z.infer<typeof modelSchema>;

const assignmentSchema = z.object({
  operation: z.string(),
  model: modelSchema.nullable(),
  updated_at: z.string().nullable(),
});
export type AiAssignment = z.infer<typeof assignmentSchema>;

const testResultSchema = z.object({
  ok: z.boolean(),
  error: z.string().nullable(),
  models_found: z.number(),
  provider: providerSchema,
});
export type AiTestResult = z.infer<typeof testResultSchema>;

export const OPERATION_LABELS: Record<string, string> = {
  ANALISIS_PERFILES: "Análisis de perfiles de puesto",
  GENERACION_PROMPTS: "Generación de prompts",
  EXTRACCION_CV: "Extracción de datos de CV",
  EVALUACION_DOCUMENTAL: "Evaluación de CV",
  ANALISIS_LLAMADAS: "Análisis de llamadas",
  LECTURA_DOCUMENTOS: "Lectura de documentos",
  RESUMEN_PRUEBAS: "Resumen de pruebas",
  SINTESIS_EXPEDIENTES: "Síntesis de expedientes",
};

export function getAiOverview(signal?: AbortSignal): Promise<AiOverview> {
  return apiFetch("/ai/providers", { schema: overviewSchema, signal });
}

/** La clave viaja una sola vez al servidor, que la cifra. Nunca se devuelve. */
export function setProviderKey(code: ProviderCode, apiKey: string): Promise<AiProvider> {
  return apiFetch(`/ai/providers/${code}/key`, {
    method: "PUT",
    body: { api_key: apiKey },
    schema: providerSchema,
  });
}

export function revokeProviderKey(code: ProviderCode): Promise<AiProvider> {
  return apiFetch(`/ai/providers/${code}/key`, { method: "DELETE", schema: providerSchema });
}

export function testProvider(code: ProviderCode): Promise<AiTestResult> {
  return apiFetch(`/ai/providers/${code}/test`, { method: "POST", schema: testResultSchema });
}

export function updateProvider(
  code: ProviderCode,
  input: { enabled: boolean; monthly_limit_usd: string | null },
): Promise<AiProvider> {
  return apiFetch(`/ai/providers/${code}`, { method: "PUT", body: input, schema: providerSchema });
}

export function listAiModels(signal?: AbortSignal): Promise<AiModel[]> {
  return apiFetch("/ai/models", { schema: z.array(modelSchema), signal });
}

export function listAssignments(signal?: AbortSignal): Promise<AiAssignment[]> {
  return apiFetch("/ai/assignments", { schema: z.array(assignmentSchema), signal });
}

export function assignModel(operation: string, modelId: string | null): Promise<AiAssignment> {
  return apiFetch(`/ai/assignments/${operation}`, {
    method: "PUT",
    body: { model_id: modelId },
    schema: assignmentSchema,
  });
}
