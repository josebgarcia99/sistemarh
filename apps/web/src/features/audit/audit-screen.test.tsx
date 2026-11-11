import { cleanup, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { makeUser, mockApi, renderApp } from "@/test/helpers";
import { AuditScreen } from "./audit-screen";

const event = (overrides: Record<string, unknown> = {}) => ({
  id: "20000000-0000-0000-0000-000000000001",
  occurred_at: "2026-11-11T18:00:00Z",
  action: "vacante.compartida",
  result: "PERMITIDO",
  actor_user_id: "00000000-0000-0000-0000-000000000002",
  actor_name: "Reclutadora de Prueba",
  resource_type: "vacante",
  resource_id: "10000000-0000-0000-0000-000000000001",
  ip: "192.0.2.10",
  correlation_id: "soporte-12345678",
  details: { tipo_acceso: "LECTURA" },
  ...overrides,
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("AuditScreen", () => {
  it("un reclutador no ve la auditoría ni se consulta", () => {
    const fetchMock = mockApi({});
    renderApp(<AuditScreen />, { session: makeUser({ role: "RECLUTADOR" }) });
    expect(screen.getByRole("alert").textContent).toContain("solo para administradores");
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("lista los eventos con nombre legible, autor y detalle", async () => {
    mockApi({
      "GET /api/v1/audit/events": {
        body: {
          items: [
            event(),
            event({
              id: "20000000-0000-0000-0000-000000000002",
              action: "sesion.inicio_fallido",
              result: "FALLIDO",
              actor_user_id: null,
              actor_name: null,
              details: {},
            }),
          ],
          total: 2,
          page: 1,
          page_size: 20,
        },
      },
    });
    renderApp(<AuditScreen />, { session: makeUser() });
    expect(await screen.findByRole("cell", { name: "Vacante compartida" })).toBeTruthy();
    expect(screen.getByText("2 eventos")).toBeTruthy();
    expect(screen.getByText("Reclutadora de Prueba")).toBeTruthy();
    expect(screen.getByText("tipo_acceso: LECTURA")).toBeTruthy();
    expect(screen.getByText("Sin identificar")).toBeTruthy();
    expect(screen.getByText("Fallido")).toBeTruthy();
  });

  it("filtra por tipo de evento y pagina", async () => {
    const fetchMock = mockApi({
      "GET /api/v1/audit/events": { body: { items: [event()], total: 45, page: 1, page_size: 20 } },
    });
    const user = userEvent.setup();
    renderApp(<AuditScreen />, { session: makeUser() });
    expect(await screen.findByText("Página 1 de 3")).toBeTruthy();

    await user.click(screen.getByRole("button", { name: "Siguiente" }));
    await vi.waitFor(() =>
      expect(fetchMock.mock.calls.some(([url]) => String(url).includes("page=2"))).toBe(true),
    );
    await user.selectOptions(
      screen.getByLabelText("Filtrar por tipo de evento"),
      "usuario.desactivado",
    );
    await vi.waitFor(() => {
      const last = String(fetchMock.mock.calls.at(-1)?.[0]);
      expect(last).toContain("action=usuario.desactivado");
      expect(last).toContain("page=1");
    });
  });
});
