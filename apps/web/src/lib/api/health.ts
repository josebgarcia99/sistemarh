import { z } from "zod";
import { apiFetch } from "./client";

export const componentStatusSchema = z.enum(["ok", "fallo", "sin_configurar"]);
export type ComponentStatus = z.infer<typeof componentStatusSchema>;

export const readinessSchema = z.object({
  ready: z.boolean(),
  components: z.array(z.object({ name: z.string(), status: componentStatusSchema })),
});
export type Readiness = z.infer<typeof readinessSchema>;

export function fetchReadiness(signal?: AbortSignal): Promise<Readiness> {
  // 503 significa "no listo" y trae el mismo cuerpo: es un dato, no un error.
  return apiFetch("/health/ready", { schema: readinessSchema, acceptStatuses: [503], signal });
}
