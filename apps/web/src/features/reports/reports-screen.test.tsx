import { cleanup, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { HomeScreen } from "@/features/home/home-screen";
import { activeFilters, EMPTY_FILTERS, lastDays, type Overview } from "@/lib/api/reports";
import { makeUser, mockApi, problem, renderApp } from "@/test/helpers";
import { ReportsScreen } from "./reports-screen";

const OPTIONS = {
  vacancies: [{ id: "v1", name: "Analista de Nómina" }],
  owners: [{ id: "u1", name: "Ana Reclutadora" }],
  collaborators: [{ id: "u2", name: "Beto Colaborador" }],
  departments: ["Finanzas"],
  stages: ["Revisión local RH", "Llamada telefónica"],
  models: ["modelo-grande-1"],
  prompt_versions: [{ id: "p1", name: "Analista de Nómina · versión 1" }],
  banks: [{ id: "b1", name: "Banco de nómina" }],
};

function makeOverview(overrides: Partial<Overview> = {}): Overview {
  return {
    snapshot: {
      vacancies: 3,
      vacancies_open: 1,
      own: 2,
      shared: 1,
      active_applications: 5,
      in_calls: 2,
      tests_pending: 1,
      interviews_pending: 0,
    },
    totals: {
      cv_analyzed: 12,
      ai_accepted: 7,
      ai_rejected: 4,
      ai_unevaluable: 1,
      applications: 12,
      closed: 4,
      hires: 1,
      withdrawals: 2,
      not_hired: 1,
      not_located: 0,
      cancelled: 0,
      other_closures: 0,
      coverage_days: 18.5,
    },
    stages: [
      { name: "Revisión local RH", kind: "REVISION_RH", active: 3, reached: 12, conversion: 50, average_days: 2.5, stays: 9 },
      { name: "Llamada telefónica", kind: "LLAMADA", active: 2, reached: 6, conversion: null, average_days: null, stays: 0 },
    ],
    funnel_hired: 1,
    vacancies: [
      {
        id: "v1",
        name: "Analista de Nómina",
        department: "Finanzas",
        status: "ABIERTA",
        owner_name: "Ana Reclutadora",
        positions: 2,
        hires_total: 1,
        active: 5,
        cv_analyzed: 12,
        applications: 12,
        closed: 4,
        hires: 1,
        coverage_days: 18.5,
      },
    ],
    months: [{ month: "2026-11", cv_analyzed: 12, applications: 12, closed: 4, hires: 1, withdrawals: 2 }],
    recent: [
      {
        occurred_at: "2026-11-13T18:00:00Z",
        kind: "CONTRATACION",
        candidate: "Ana Pérez",
        vacancy_id: "v1",
        vacancy: "Analista de Nómina",
        stage: "Resultado final",
        actor_name: null,
      },
    ],
    recruiters: null,
    ai: null,
    cv_failures: null,
    ...overrides,
  };
}

const ADMIN_EXTRAS = {
  recruiters: [
    { user_id: "u1", name: "Ana Reclutadora", vacancies: 3, vacancies_open: 1, collaborating: 0, active: 5, closed: 4, hires: 1 },
  ],
  ai: {
    calls: 30,
    failures: 2,
    cost_usd: "1.250000",
    operations: [{ operation: "EVALUACION_DOCUMENTAL", calls: 30, failures: 2, cost_usd: "1.250000" }],
  },
  cv_failures: 1,
};

const ROW = {
  application_id: "a1",
  vacancy_id: "v1",
  candidate: "Ana Pérez",
  vacancy: "Analista de Nómina",
  department: "Finanzas",
  owner_name: "Ana Reclutadora",
  stage: "Llamada telefónica",
  outcome: "CONTRATADO",
  outcome_reason: null,
  ai_classification: "ACEPTADO_IA",
  ai_score: "87.50",
  model: "modelo-grande-1",
  prompt_version: 1,
  created_at: "2026-11-10T15:00:00Z",
  cv_uploaded_at: "2026-11-10T15:00:00Z",
  evaluated_at: "2026-11-10T15:00:02Z",
  last_movement_at: "2026-11-13T15:00:00Z",
  closed_at: "2026-11-13T15:00:00Z",
  closed_by_name: "Ana Reclutadora",
  start_date: "2026-12-01",
};
const EXPORT = {
  id: "e1",
  kind: "POSTULACIONES" as const,
  name: "Postulaciones_20261113_0900.xlsx",
  filters: { Desde: "2026-11-01", Candidato: "ana" },
  row_count: 1,
  size_bytes: 6200,
  sha256: "ab".repeat(32),
  created_at: "2026-11-13T15:00:00Z",
};

function query(fetchMock: ReturnType<typeof mockApi>, path: string): URLSearchParams {
  const calls = fetchMock.mock.calls.filter(([url]) => String(url).split("?")[0] === path);
  return new URL(String(calls[calls.length - 1][0]), "http://prueba").searchParams;
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("filtros de los reportes", () => {
  it("solo envía los filtros con valor y calcula el periodo en hora de México", () => {
    expect(activeFilters(EMPTY_FILTERS)).toEqual({});
    expect(activeFilters({ ...EMPTY_FILTERS, candidate: "  ana ", date_kind: "CIERRE" })).toEqual({
      candidate: "ana",
      date_kind: "CIERRE",
    });
    // A las 03:00 UTC del día 13 en México todavía es día 12.
    expect(lastDays(30, new Date("2026-11-13T03:00:00Z"))).toEqual({
      date_from: "2026-10-14",
      date_to: "2026-11-12",
    });
  });
});

describe("pantalla de indicadores", () => {
  it("muestra el tablero de una reclutadora sin los datos reservados al administrador", async () => {
    const fetchMock = mockApi({
      ["GET /api/v1/reports/options"]: { body: OPTIONS },
      ["GET /api/v1/reports/overview"]: { body: makeOverview() },
    });
    renderApp(<ReportsScreen />, { session: makeUser({ role: "RECLUTADOR" }) });

    const today = await screen.findByRole("region", { name: "Hoy" });
    expect(within(today).getByText("Procesos pendientes").nextSibling?.textContent).toBe("5");
    const period = screen.getByRole("region", { name: "En el periodo" });
    expect(within(period).getByText("Aceptados: 7 · rechazados: 4 · no evaluables: 1")).toBeTruthy();
    expect(within(period).getByText("18.5 días")).toBeTruthy();
    const funnel = within(screen.getByRole("list", { name: "Embudo por etapa" })).getAllByRole("listitem");
    expect(funnel.map((item) => item.textContent)).toEqual([
      "Revisión local RH12 · pasa 50 %",
      "Llamada telefónica6",
      "Contratadas1",
    ]);
    const vacancies = within(screen.getByRole("table", { name: "Vacantes" })).getAllByRole("row");
    expect(vacancies[1].textContent).toContain("1 de 2");
    expect(screen.getByRole("table", { name: "Histórico mensual" }).textContent).toContain("Noviembre de 2026");
    expect(screen.queryByRole("region", { name: "Reclutadores" })).toBeNull();
    expect(screen.queryByRole("region", { name: "Uso de IA" })).toBeNull();
    expect(screen.getByText(/tus vacantes y las que tienes compartidas hoy/)).toBeTruthy();
    // Por omisión se consultan los últimos 90 días.
    const sent = query(fetchMock, "/api/v1/reports/overview");
    expect(sent.get("date_from")).toBeTruthy();
    expect(sent.get("date_to")).toBeTruthy();
  });

  it("al administrador le muestra la carga por responsable y el uso de IA, y aplica filtros", async () => {
    const fetchMock = mockApi({
      ["GET /api/v1/reports/options"]: { body: OPTIONS },
      ["GET /api/v1/reports/overview"]: { body: makeOverview(ADMIN_EXTRAS) },
    });
    const user = userEvent.setup();
    renderApp(<ReportsScreen />, { session: makeUser({ role: "ADMINISTRADOR" }) });

    const people = await screen.findByRole("table", { name: "Reclutadores" });
    expect(within(people).getAllByRole("row")[1].textContent).toContain("Ana Reclutadora");
    const usage = screen.getByRole("region", { name: "Uso de IA" });
    expect(within(usage).getAllByText("USD 1.25")).toHaveLength(2);
    expect(within(usage).getByText("Evaluación de CV")).toBeTruthy();

    await user.selectOptions(await screen.findByLabelText("Departamento"), "Finanzas");
    await user.selectOptions(screen.getByLabelText("Colaborador"), "u2");
    await user.click(screen.getByRole("button", { name: "Todo" }));
    // «Todo» aplica de inmediato y quita las fechas.
    await screen.findByRole("table", { name: "Reclutadores" });
    const sent = query(fetchMock, "/api/v1/reports/overview");
    expect(Object.fromEntries(sent)).toEqual({ department: "Finanzas", collaborator_id: "u2" });
  });

  it("consulta el histórico con filtros, pagina y genera el Excel", async () => {
    const fetchMock = mockApi({
      ["GET /api/v1/reports/options"]: { body: OPTIONS },
      ["GET /api/v1/reports/overview"]: { body: makeOverview() },
      ["GET /api/v1/reports/applications"]: { body: { rows: [ROW], total: 60 } },
      ["POST /api/v1/reports/exports"]: { status: 201, body: EXPORT },
      ["GET /api/v1/reports/exports"]: { body: [EXPORT] },
    });
    const user = userEvent.setup();
    renderApp(<ReportsScreen />, { session: makeUser({ role: "RECLUTADOR" }) });

    await user.click(screen.getByRole("button", { name: "Histórico de candidatos" }));
    const table = await screen.findByRole("table", { name: "Postulaciones" });
    const row = within(table).getAllByRole("row")[1];
    expect(row.textContent).toContain("Ana Pérez");
    expect(row.textContent).toContain("Contratado");
    expect(row.textContent).toContain("Entra el 1 dic 2026");
    expect(row.textContent).toContain("Aceptado por IA · 87.5");
    expect(row.textContent).toContain("modelo-grande-1 · prompt v1");
    expect(screen.getByText("60 postulaciones")).toBeTruthy();

    await user.type(screen.getByLabelText("Candidato"), "ana");
    await user.selectOptions(screen.getByLabelText("Resultado final"), "CONTRATADO");
    await user.selectOptions(screen.getByLabelText("Fecha que se compara"), "CIERRE");
    await user.click(screen.getByRole("button", { name: "Aplicar filtros" }));
    await screen.findByRole("table", { name: "Postulaciones" });
    let sent = query(fetchMock, "/api/v1/reports/applications");
    expect(sent.get("candidate")).toBe("ana");
    expect(sent.get("outcome")).toBe("CONTRATADO");
    expect(sent.get("date_kind")).toBe("CIERRE");
    expect(sent.get("offset")).toBe("0");

    await user.click(screen.getByRole("button", { name: "Siguiente" }));
    expect(await screen.findByText("Página 2 de 3")).toBeTruthy();
    sent = query(fetchMock, "/api/v1/reports/applications");
    expect(sent.get("offset")).toBe("25");

    await user.click(screen.getByRole("button", { name: "Descargar en Excel" }));
    const link = await screen.findByRole("link", { name: "Descargar Postulaciones_20261113_0900.xlsx" });
    expect(link.getAttribute("href")).toBe("/api/v1/reports/exports/e1/download");
    const created = fetchMock.mock.calls.find(([, init]) => init?.method === "POST");
    const body = JSON.parse(String(created?.[1]?.body));
    expect(body.kind).toBe("POSTULACIONES");
    expect(body.candidate).toBe("ana");
    expect(body.outcome).toBe("CONTRATADO");

    await user.click(screen.getByRole("button", { name: "Reportes generados" }));
    const reports = within(await screen.findByRole("list", { name: "Reportes" })).getAllByRole("listitem");
    expect(reports[0].textContent).toContain("1 postulación");
    expect(reports[0].textContent).toContain("Desde: 2026-11-01 · Candidato: ana");
    expect(reports[0].textContent).toContain("SHA-256: abab");
  });

  it("explica el error cuando el reporte no se puede generar", async () => {
    mockApi({
      ["GET /api/v1/reports/options"]: { body: OPTIONS },
      ["GET /api/v1/reports/overview"]: { body: makeOverview() },
      ["POST /api/v1/reports/exports"]: problem(503, "servicio_no_disponible", "El almacenamiento documental no está configurado."),
    });
    const user = userEvent.setup();
    renderApp(<ReportsScreen />, { session: makeUser({ role: "RECLUTADOR" }) });
    await screen.findByRole("region", { name: "Hoy" });
    await user.click(screen.getByRole("button", { name: "Descargar en Excel" }));
    expect((await screen.findByRole("alert")).textContent).toContain("almacenamiento documental");
    expect(screen.queryByRole("link", { name: /Descargar/ })).toBeNull();
  });
});

describe("inicio", () => {
  it("muestra a la reclutadora sus vacantes, lo pendiente y la actividad reciente", async () => {
    mockApi({ ["GET /api/v1/reports/overview"]: { body: makeOverview() } });
    renderApp(<HomeScreen />, { session: makeUser({ role: "RECLUTADOR", full_name: "Ana Reclutadora" }) });

    expect(screen.getByRole("heading", { name: "Hola, Ana" })).toBeTruthy();
    const today = await screen.findByRole("region", { name: "Hoy" });
    expect(within(today).getByText("Vacantes propias").nextSibling?.textContent).toBe("2");
    expect(within(today).getByText("Vacantes compartidas").nextSibling?.textContent).toBe("1");
    expect(within(today).getByText("Candidatos en llamada").nextSibling?.textContent).toBe("2");
    const period = screen.getByRole("region", { name: "Últimos 30 días" });
    expect(within(period).getByText("Contrataciones").nextSibling?.textContent).toBe("1");
    const recent = within(screen.getByRole("list", { name: "Actividad reciente" })).getAllByRole("listitem");
    expect(recent[0].textContent).toContain("Ana Pérez · Contratación (Resultado final)");
    expect(recent[0].textContent).toContain("Sistema");
    expect(screen.getByRole("link", { name: "Ver indicadores y reportes" }).getAttribute("href")).toBe(
      "/indicadores",
    );
    expect(screen.queryByText("Estado del sistema")).toBeNull();
  });
});
