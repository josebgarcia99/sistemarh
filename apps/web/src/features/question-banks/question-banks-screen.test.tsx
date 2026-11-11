import { cleanup, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { Bank } from "@/lib/api/calls";
import { makeUser, mockApi, renderApp } from "@/test/helpers";
import { QuestionBanksScreen } from "./question-banks-screen";

const URL = "/api/v1/question-banks";
function makeBank(overrides: Partial<Bank> = {}): Bank {
  return {
    id: "b1",
    name: "Banco de nómina",
    description: null,
    owner_name: "Reclutadora de Prueba",
    mine: true,
    can_edit: true,
    shared: false,
    status: "ACTIVO",
    version_number: 1,
    questions: [{ id: "q1", text: "¿Qué nóminas has calculado?", competency: "Nómina", guidance: "", origin: "MANUAL" }],
    updated_at: "2026-11-11T18:00:00Z",
    ...overrides,
  };
}
const DETAIL = (bank: Bank) => ({
  bank,
  versions: [{ version_number: 1, questions: 1, change_note: null, created_at: "2026-11-11T18:00:00Z", created_by_name: "Reclutadora de Prueba" }],
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("QuestionBanksScreen", () => {
  it("crea un banco con sus preguntas y con una propuesta de la IA aceptada", async () => {
    let banks: Bank[] = [];
    const created = makeBank();
    const fetchMock = mockApi({
      [`GET ${URL}`]: () => ({ body: banks }),
      ["GET /api/v1/vacancies"]: { body: { items: [{ id: "v1", name: "Analista de Nómina", department: "", location: "", work_mode: "HIBRIDA", contract_type: "", description: "", positions: 1, notes: null, status: "ABIERTA", owner: null, my_access: "RESPONSABLE", version: 1, created_at: "2026-11-11T18:00:00Z", updated_at: "2026-11-11T18:00:00Z", opened_at: null, closed_at: null }], total: 1, page: 1, page_size: 50 } },
      [`POST ${URL}/question-proposals`]: { body: [{ text: "¿Usas CONTPAQi?", competency: "Sistemas", guidance: "Módulos" }] },
      [`POST ${URL}`]: () => {
        banks = [created];
        return { status: 201, body: created };
      },
      [`GET ${URL}/b1`]: { body: DETAIL(created) },
    });
    const user = userEvent.setup();
    renderApp(<QuestionBanksScreen />, { session: makeUser() });
    expect(await screen.findByText(/Todavía no hay bancos/)).toBeTruthy();
    await user.click(screen.getByRole("button", { name: "Nuevo banco" }));
    await user.type(screen.getByLabelText("Nombre"), "Banco de nómina");
    await user.type(screen.getByLabelText("Pregunta 1"), "¿Qué nóminas has calculado?");
    await user.click(screen.getByRole("button", { name: "Proponer preguntas con IA" }));
    await user.click(await screen.findByRole("button", { name: "Proponer" }));
    const proposals = await screen.findByRole("list", { name: "Preguntas propuestas" });
    await user.click(within(proposals).getByRole("button", { name: "Añadir" }));
    expect(screen.getByLabelText("Pregunta 2 · propuesta por la IA")).toBeTruthy();
    await user.click(screen.getByRole("checkbox", { name: /Compartir con todo el equipo/ }));
    await user.click(screen.getByRole("button", { name: "Crear banco" }));

    expect((await screen.findByRole("status")).textContent).toContain("Banco guardado");
    const post = fetchMock.mock.calls.find(([url, init]) => String(url).endsWith(URL) && init?.method === "POST");
    expect(JSON.parse(String(post?.[1]?.body))).toEqual({
      name: "Banco de nómina",
      description: null,
      shared: true,
      questions: [
        { id: null, text: "¿Qué nóminas has calculado?", competency: "", guidance: "", origin: "MANUAL" },
        { id: null, text: "¿Usas CONTPAQi?", competency: "Sistemas", guidance: "Módulos", origin: "IA" },
      ],
    });
  });

  it("un banco compartido por otra persona se consulta y se duplica, pero no se modifica", async () => {
    const shared = makeBank({ mine: false, can_edit: false, shared: true, owner_name: "Segunda Reclutadora" });
    const copy = makeBank({ id: "b2", name: "Banco de nómina (copia)" });
    let banks = [shared];
    const fetchMock = mockApi({
      [`GET ${URL}`]: () => ({ body: banks }),
      [`GET ${URL}/b1`]: { body: DETAIL(shared) },
      [`GET ${URL}/b2`]: { body: DETAIL(copy) },
      [`POST ${URL}/b1/duplicate`]: () => {
        banks = [shared, copy];
        return { status: 201, body: copy };
      },
    });
    const user = userEvent.setup();
    renderApp(<QuestionBanksScreen />, { session: makeUser() });
    expect(await screen.findByText("De Segunda Reclutadora")).toBeTruthy();
    await user.click(screen.getByRole("button", { name: "Banco de nómina" }));
    expect((screen.getByLabelText("Pregunta 1") as HTMLInputElement).readOnly).toBe(true);
    expect(screen.queryByRole("button", { name: /Guardar cambios|Archivar|Agregar pregunta/ })).toBeNull();
    await user.click(screen.getByRole("button", { name: "Duplicar" }));
    expect((await screen.findByRole("status")).textContent).toContain("tu copia");
    expect(await screen.findByRole("heading", { name: "Banco de nómina (copia) · versión 1" })).toBeTruthy();
    expect(fetchMock.mock.calls.some(([url]) => String(url).endsWith("/b1/duplicate"))).toBe(true);
  });
});
