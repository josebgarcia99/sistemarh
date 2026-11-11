import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import type { ReactElement } from "react";
import { vi } from "vitest";
import { SESSION_QUERY_KEY } from "@/features/auth/use-session";
import type { Session, User } from "@/lib/api/auth";
import { setCsrfToken } from "@/lib/api/client";

export function makeUser(overrides: Partial<User> = {}): User {
  return {
    id: "00000000-0000-0000-0000-000000000001",
    email: "admin@ejemplo.test",
    full_name: "Administradora de Prueba",
    role: "ADMINISTRADOR",
    is_active: true,
    created_at: "2026-11-10T15:00:00Z",
    last_activity_at: "2026-11-10T16:30:00Z",
    deactivated_at: null,
    ...overrides,
  };
}

/** Renderiza con React Query y, si se indica, con una sesión ya iniciada. */
export function renderApp(ui: ReactElement, options: { session?: User } = {}) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, staleTime: Infinity } },
  });
  if (options.session) {
    const session: Session = { user: options.session, csrf_token: "csrf-de-prueba" };
    queryClient.setQueryData(SESSION_QUERY_KEY, session);
    setCsrfToken(session.csrf_token);
  } else {
    setCsrfToken(null);
  }
  return {
    queryClient,
    ...render(<QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>),
  };
}

type Route = { status?: number; body?: unknown };
type Handler = Route | ((request: { url: string; init: RequestInit }) => Route);

/** Sustituye fetch por rutas "MÉTODO /ruta". Devuelve el espía para inspeccionar llamadas. */
export function mockApi(routes: Record<string, Handler>) {
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init: RequestInit = {}) => {
    const url = String(input);
    const key = `${init.method ?? "GET"} ${url.split("?")[0]}`;
    const handler = routes[key];
    if (!handler) throw new Error(`Llamada inesperada en la prueba: ${key}`);
    const route = typeof handler === "function" ? handler({ url, init }) : handler;
    const status = route.status ?? 200;
    return new Response(route.body === undefined ? null : JSON.stringify(route.body), { status });
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

export function problem(status: number, code: string, detail: string) {
  return {
    status,
    body: { title: detail, status, detail, code, correlation_id: "soporte-12345678" },
  };
}
