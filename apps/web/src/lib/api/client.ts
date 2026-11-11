import { z } from "zod";

/**
 * Cliente HTTP de la API.
 *
 * Todas las llamadas van al mismo origen (/api/v1/...), de modo que la cookie de
 * sesión HttpOnly viaja sola y el navegador nunca conoce direcciones internas.
 */

const problemSchema = z.object({
  title: z.string(),
  status: z.number(),
  detail: z.string(),
  code: z.string(),
  correlation_id: z.string().nullable().optional(),
});

export type Problem = z.infer<typeof problemSchema>;

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly correlationId: string | null;

  constructor(problem: Problem) {
    super(problem.detail);
    this.name = "ApiError";
    this.status = problem.status;
    this.code = problem.code;
    this.correlationId = problem.correlation_id ?? null;
  }
}

type RequestOptions<T> = {
  schema: z.ZodType<T>;
  method?: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
  body?: unknown;
  /** Códigos distintos de 2xx cuyo cuerpo también cumple el esquema. */
  acceptStatuses?: number[];
  signal?: AbortSignal;
};

export async function apiFetch<T>(path: string, options: RequestOptions<T>): Promise<T> {
  const { schema, method = "GET", body, acceptStatuses = [], signal } = options;

  const response = await fetch(`/api/v1${path}`, {
    method,
    credentials: "same-origin",
    headers: body === undefined ? undefined : { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
    signal,
  });

  const payload: unknown = await response.json().catch(() => null);

  if (response.ok || acceptStatuses.includes(response.status)) {
    return schema.parse(payload);
  }

  const problem = problemSchema.safeParse(payload);
  throw new ApiError(
    problem.success
      ? problem.data
      : {
          title: "Error de comunicación",
          status: response.status,
          detail: "El servidor no respondió como se esperaba.",
          code: "respuesta_no_reconocida",
          correlation_id: response.headers.get("X-Correlation-ID"),
        },
  );
}
