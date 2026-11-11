import { cleanup, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { CvBatch, CvBatchItem, CvOverview } from "@/lib/api/cv-batches";
import { makeUser, mockApi, problem, renderApp } from "@/test/helpers";
import { CvEvaluationTab } from "./cv-evaluation-tab";

const VACANCY_ID = "10000000-0000-0000-0000-000000000001";
const BATCH_ID = "80000000-0000-0000-0000-000000000001";
const OVERVIEW_URL = `/api/v1/vacancies/${VACANCY_ID}/cv-batches`;
const BATCH_URL = `/api/v1/cv-batches/${BATCH_ID}`;

function makeBatch(overrides: Partial<CvBatch> = {}): CvBatch {
  return {
    id: BATCH_ID,
    vacancy_id: VACANCY_ID,
    status: "COMPLETADO",
    stalled: false,
    total: 3,
    evaluated: 3,
    failed: 0,
    pending: 0,
    accepted: 1,
    rejected: 1,
    unevaluable: 1,
    error: null,
    created_at: "2026-11-11T18:00:00Z",
    created_by_name: "Reclutadora de Prueba",
    started_at: "2026-11-11T18:00:01Z",
    finished_at: "2026-11-11T18:00:20Z",
    report_file_id: "90000000-0000-0000-0000-000000000001",
    accepted_zip_file_id: "90000000-0000-0000-0000-000000000002",
    rejected_zip_file_id: "90000000-0000-0000-0000-000000000003",
    unevaluable_zip_file_id: null,
    ...overrides,
  };
}

function makeItem(overrides: Partial<CvBatchItem> = {}): CvBatchItem {
  return {
    id: "a0000000-0000-0000-0000-000000000001",
    file_id: "b0000000-0000-0000-0000-000000000001",
    file_name: "ana.pdf",
    position: 1,
    status: "EVALUADO",
    step: "CALIFICADO",
    classification: "ACEPTADO_IA",
    score: "87.50",
    reason: null,
    notes: "Perfil cercano al puesto.",
    quality: { redaccion: 3, ortografia: 4 },
    digitization_suspect: false,
    truncated: false,
    duplicate: false,
    error_code: null,
    error_message: null,
    attempts: 1,
    criteria: [
      { code: "C1", level: 4, no_evidence: false, evidence: "5 años en nómina", justification: "Cumple" },
      { code: "C2", level: null, no_evidence: true, evidence: "", justification: "No lo menciona" },
    ],
    ...overrides,
  };
}

function makeOverview(overrides: Partial<CvOverview> = {}): CvOverview {
  return {
    approved_prompt: { id: "p1", version_number: 2, pass_threshold: "60.00", criteria: 5 },
    total_cvs: 3,
    pending_cvs: 3,
    batches: [],
    ...overrides,
  };
}

const ITEMS = [
  makeItem(),
  makeItem({
    id: "a0000000-0000-0000-0000-000000000002",
    file_name: "beto.docx",
    classification: "RECHAZADO_IA",
    score: "25.00",
    criteria: [],
    notes: null,
    quality: null,
  }),
  makeItem({
    id: "a0000000-0000-0000-0000-000000000003",
    file_name: "escaneado.pdf",
    classification: "NO_EVALUABLE",
    score: null,
    reason: "El archivo no contiene texto legible.",
    criteria: [],
    notes: null,
    quality: null,
  }),
];

function renderTab(canEdit = true) {
  return renderApp(<CvEvaluationTab vacancyId={VACANCY_ID} canEdit={canEdit} />, {
    session: makeUser(),
  });
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("CvEvaluationTab", () => {
  it("sin prompt aprobado explica qué falta y no ofrece evaluar", async () => {
    mockApi({ [`GET ${OVERVIEW_URL}`]: { body: makeOverview({ approved_prompt: null }) } });
    renderTab();
    expect(await screen.findByText(/hace falta un prompt aprobado/)).toBeTruthy();
    expect(screen.queryByRole("button", { name: /Evaluar/ })).toBeNull();
  });

  it("inicia un lote con los CV pendientes y muestra los resultados", async () => {
    let created = false;
    const batch = makeBatch();
    const fetchMock = mockApi({
      [`GET ${OVERVIEW_URL}`]: () => ({
        body: makeOverview(created ? { pending_cvs: 0, batches: [batch] } : {}),
      }),
      [`POST ${OVERVIEW_URL}`]: () => {
        created = true;
        return { status: 201, body: { batch, items: ITEMS } };
      },
      [`GET ${BATCH_URL}`]: { body: { batch, items: ITEMS } },
    });
    const user = userEvent.setup();
    renderTab();
    expect(await screen.findByText("Versión 2 · 5 criterios")).toBeTruthy();
    expect(screen.getByText("60 de 100")).toBeTruthy();
    await user.click(screen.getByRole("button", { name: "Evaluar 3 CV" }));

    expect((await screen.findByRole("status")).textContent).toContain("terminó");
    const post = fetchMock.mock.calls.find(([, init]) => init?.method === "POST");
    expect(JSON.parse(String(post?.[1]?.body))).toEqual({ reevaluate: false });

    const list = await screen.findByRole("list", { name: "CV del lote" });
    const rows = within(list).getAllByRole("listitem");
    expect(rows).toHaveLength(3);
    expect(rows[0].textContent).toContain("ana.pdf");
    expect(rows[0].textContent).toContain("Aceptado por IA");
    expect(rows[0].textContent).toContain("87.5 / 100");
    expect(rows[0].textContent).toContain("Sin evidencia");
    expect(rows[0].textContent).toContain("no significan que la persona no cumpla");
    expect(rows[1].textContent).toContain("Rechazado por IA");
    expect(rows[2].textContent).toContain("No evaluable");
    expect(rows[2].textContent).toContain("no contiene texto legible");
    expect(screen.getByText(/3 de 3 CV procesados/)).toBeTruthy();
    // Ya no queda nada por evaluar: el botón se desactiva.
    expect(screen.getByRole("button", { name: "Evaluar 0 CV" }).hasAttribute("disabled")).toBe(true);
  });

  it("las descargas pasan por la ruta autorizada de documentos", async () => {
    const batch = makeBatch();
    mockApi({
      [`GET ${OVERVIEW_URL}`]: { body: makeOverview({ pending_cvs: 0, batches: [batch] }) },
      [`GET ${BATCH_URL}`]: { body: { batch, items: ITEMS } },
    });
    renderTab();
    const report = await screen.findByRole("link", { name: "Descargar Reporte_Evaluacion.xlsx" });
    expect(report.getAttribute("href")).toBe(`/api/v1/files/${batch.report_file_id}/download`);
    expect(screen.getByRole("link", { name: "Descargar Aceptados.zip" })).toBeTruthy();
    expect(screen.getByRole("link", { name: "Descargar Rechazados.zip" })).toBeTruthy();
    expect(screen.queryByRole("link", { name: "Descargar No_Evaluables.zip" })).toBeNull();
    expect(screen.queryByRole("button", { name: /Reintentar|Reanudar|Cancelar/ })).toBeNull();
  });

  it("un lote detenido muestra el motivo y se puede reintentar", async () => {
    const stopped = makeBatch({
      status: "FALLIDO",
      evaluated: 1,
      failed: 1,
      pending: 1,
      accepted: 1,
      rejected: 0,
      unevaluable: 0,
      error: "Se alcanzó el límite de gasto mensual de Anthropic.",
      report_file_id: null,
      accepted_zip_file_id: null,
      rejected_zip_file_id: null,
    });
    const failedItem = makeItem({
      id: "a0000000-0000-0000-0000-000000000002",
      file_name: "beto.docx",
      status: "FALLIDO",
      classification: null,
      score: null,
      criteria: [],
      notes: null,
      quality: null,
      error_code: "proveedor",
      error_message: "El proveedor de IA no respondió.",
    });
    let retried = false;
    const done = makeBatch({ evaluated: 3, accepted: 2, rejected: 1, unevaluable: 0 });
    const fetchMock = mockApi({
      [`GET ${OVERVIEW_URL}`]: () => ({
        body: makeOverview({ pending_cvs: 2, batches: [retried ? done : stopped] }),
      }),
      [`GET ${BATCH_URL}`]: () => ({
        body: retried
          ? { batch: done, items: ITEMS }
          : { batch: stopped, items: [makeItem(), failedItem] },
      }),
      [`POST ${BATCH_URL}/retry`]: () => {
        retried = true;
        return { body: { batch: done, items: ITEMS } };
      },
    });
    const user = userEvent.setup();
    renderTab();
    expect(await screen.findByText(/límite de gasto mensual/)).toBeTruthy();
    expect(screen.getByText("Detenido por un error")).toBeTruthy();
    expect(await screen.findByText("El proveedor de IA no respondió.")).toBeTruthy();
    await user.click(screen.getByRole("button", { name: "Reintentar" }));
    expect(await screen.findByText("Completado")).toBeTruthy();
    expect(fetchMock.mock.calls.some(([url]) => String(url).endsWith("/retry"))).toBe(true);
    expect(screen.queryByText(/límite de gasto mensual/)).toBeNull();
  });

  it("un lote en curso se puede cancelar y bloquea iniciar otro", async () => {
    const running = makeBatch({
      status: "PROCESANDO",
      evaluated: 1,
      pending: 2,
      accepted: 1,
      rejected: 0,
      unevaluable: 0,
      report_file_id: null,
      accepted_zip_file_id: null,
      rejected_zip_file_id: null,
    });
    let cancelled = false;
    const after = { ...running, status: "CANCELADO" as const };
    mockApi({
      [`GET ${OVERVIEW_URL}`]: () => ({
        body: makeOverview({ pending_cvs: 2, batches: [cancelled ? after : running] }),
      }),
      [`GET ${BATCH_URL}`]: () => ({
        body: { batch: cancelled ? after : running, items: [makeItem()] },
      }),
      [`POST ${BATCH_URL}/cancel`]: () => {
        cancelled = true;
        return { body: { batch: after, items: [makeItem()] } };
      },
    });
    const user = userEvent.setup();
    renderTab();
    expect(await screen.findByText("Procesando")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Evaluar 2 CV" }).hasAttribute("disabled")).toBe(true);
    expect(screen.getByRole("progressbar").getAttribute("aria-valuenow")).toBe("1");
    await user.click(screen.getByRole("button", { name: "Cancelar lote" }));
    expect(await screen.findByText("Cancelado")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Reanudar" })).toBeTruthy();
  });

  it("muestra el motivo cuando no se puede iniciar y permite repetir la evaluación", async () => {
    const fetchMock = mockApi({
      [`GET ${OVERVIEW_URL}`]: { body: makeOverview({ pending_cvs: 0 }) },
      [`POST ${OVERVIEW_URL}`]: problem(
        422,
        "validacion",
        "Esta operación no tiene un modelo asignado.",
      ),
    });
    const user = userEvent.setup();
    renderTab();
    const button = await screen.findByRole("button", { name: "Evaluar 0 CV" });
    expect(button.hasAttribute("disabled")).toBe(true);
    await user.click(screen.getByRole("checkbox", { name: /Volver a evaluar/ }));
    await user.click(screen.getByRole("button", { name: "Evaluar 3 CV" }));
    expect((await screen.findByRole("alert")).textContent).toContain("modelo asignado");
    const post = fetchMock.mock.calls.find(([, init]) => init?.method === "POST");
    expect(JSON.parse(String(post?.[1]?.body))).toEqual({ reevaluate: true });
  });

  it("con acceso de lectura se consulta y se descarga, pero no se opera", async () => {
    const batch = makeBatch({ status: "COMPLETADO_CON_INCIDENCIAS", failed: 1, evaluated: 2 });
    mockApi({
      [`GET ${OVERVIEW_URL}`]: { body: makeOverview({ batches: [batch] }) },
      [`GET ${BATCH_URL}`]: { body: { batch, items: ITEMS } },
    });
    renderTab(false);
    expect(await screen.findByRole("link", { name: "Descargar Aceptados.zip" })).toBeTruthy();
    expect(screen.queryByRole("button", { name: /Evaluar/ })).toBeNull();
    expect(screen.queryByRole("checkbox")).toBeNull();
    expect(screen.queryByRole("button", { name: /Reintentar|Reanudar|Cancelar/ })).toBeNull();
  });
});
