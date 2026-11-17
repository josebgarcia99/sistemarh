import { z } from "zod";

/**
 * Cliente HTTP de la API.
 *
 * Todas las llamadas van al mismo origen (/api/v1/...), de modo que la cookie de
 * sesión HttpOnly viaja sola y el navegador nunca conoce direcciones internas.
 * El token CSRF se guarda solo en memoria y se envía al modificar datos.
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

let csrfToken: string | null = null;

export function setCsrfToken(token: string | null): void {
  csrfToken = token;
}

type Method = "GET" | "POST" | "PUT" | "PATCH" | "DELETE";

type RequestOptions<T> = {
  /** Esquema de la respuesta. Omitir cuando la API responde sin cuerpo (204). */
  schema?: z.ZodType<T>;
  method?: Method;
  body?: unknown;
  /** Archivo que se envía tal cual como cuerpo de la petición. */
  file?: Blob;
  query?: Record<string, string | number | undefined>;
  /** Códigos distintos de 2xx cuyo cuerpo también cumple el esquema. */
  acceptStatuses?: number[];
  signal?: AbortSignal;
};

function buildUrl(path: string, query?: RequestOptions<unknown>["query"]): string {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(query ?? {})) {
    if (value !== undefined && value !== "") params.set(key, String(value));
  }
  const suffix = params.toString();
  return `/api/v1${path}${suffix ? `?${suffix}` : ""}`;
}

export async function apiFetch<T = void>(path: string, options: RequestOptions<T> = {}): Promise<T> {
  const { schema, method = "GET", body, file, query, acceptStatuses = [], signal } = options;

  const headers: Record<string, string> = {};
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (file !== undefined) headers["Content-Type"] = "application/octet-stream";
  if (method !== "GET" && csrfToken) headers["X-CSRF-Token"] = csrfToken;

  const response = await fetch(buildUrl(path, query), {
    method,
    credentials: "same-origin",
    headers,
    body: file ?? (body === undefined ? undefined : JSON.stringify(body)),
    signal,
  });

  if (response.ok || acceptStatuses.includes(response.status)) {
    if (!schema) return undefined as T;
    const payload: unknown = await response.json().catch(() => null);
    return schema.parse(payload);
  }

  throw await failure(response);
}

async function failure(response: Response): Promise<ApiError> {
  const payload: unknown = await response.json().catch(() => null);
  const problem = problemSchema.safeParse(payload);
  return new ApiError(
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

/** Descarga un archivo que la API genera al momento, con su nombre sugerido. */
export async function apiDownload(
  path: string,
): Promise<{ blob: Blob; name: string | null; headers: Headers }> {
  const response = await fetch(buildUrl(path), { credentials: "same-origin" });
  if (!response.ok) throw await failure(response);
  const named = /filename\*=UTF-8''([^;]+)/.exec(response.headers.get("Content-Disposition") ?? "");
  return {
    blob: await response.blob(),
    name: named ? decodeURIComponent(named[1]) : null,
    headers: response.headers,
  };
}

/** Entrega al navegador un archivo ya descargado, para que lo guarde. */
export function saveBlob(blob: Blob, name: string): void {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = name;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

/** Mensaje para mostrar a la persona, con el identificador de soporte si existe. */
export function describeError(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status >= 500 && error.correlationId) {
      return `${error.message} Identificador para soporte: ${error.correlationId}`;
    }
    return error.message;
  }
  return "No se pudo conectar con el servidor.";
}
