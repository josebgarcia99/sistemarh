import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { SystemStatus } from "./system-status";

function renderWithQuery() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <SystemStatus />
    </QueryClientProvider>,
  );
}

function mockApi(status: number, body: unknown) {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue(new Response(JSON.stringify(body), { status })),
  );
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("SystemStatus", () => {
  it("muestra el estado de carga antes de recibir respuesta", () => {
    vi.stubGlobal("fetch", vi.fn().mockReturnValue(new Promise(() => {})));
    renderWithQuery();
    expect(screen.getByRole("status").textContent).toContain("Comprobando los servicios");
  });

  it("lista los servicios cuando todo responde", async () => {
    mockApi(200, {
      ready: true,
      components: [
        { name: "sql_server", status: "ok" },
        { name: "redis", status: "ok" },
        { name: "almacenamiento", status: "ok" },
      ],
    });
    renderWithQuery();
    expect(await screen.findByText("Todos los servicios responden.")).toBeTruthy();
    expect(screen.getByText("SQL Server")).toBeTruthy();
    expect(screen.getAllByText("Responde")).toHaveLength(3);
  });

  it("trata el 503 como estado, no como error, y marca lo que falla", async () => {
    mockApi(503, {
      ready: false,
      components: [
        { name: "sql_server", status: "sin_configurar" },
        { name: "redis", status: "fallo" },
      ],
    });
    renderWithQuery();
    expect(await screen.findByText("No responde")).toBeTruthy();
    expect(screen.getByText("Sin configurar")).toBeTruthy();
    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("muestra el identificador de soporte cuando la API devuelve un error", async () => {
    mockApi(500, {
      title: "Error interno",
      status: 500,
      detail: "Ocurrió un error inesperado.",
      code: "error_interno",
      correlation_id: "soporte-12345678",
    });
    renderWithQuery();
    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toContain("soporte-12345678");
  });
});
