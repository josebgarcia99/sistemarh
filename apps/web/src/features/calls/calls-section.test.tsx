import { cleanup, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { Bank, Call } from "@/lib/api/calls";
import { makeUser, mockApi, renderApp } from "@/test/helpers";
import { CallsSection } from "./calls-section";

const CALLS_URL = "/api/v1/applications/a1/calls";
const BANK: Bank = {
  id: "b1",
  name: "Banco de nómina",
  description: null,
  owner_name: "Reclutadora de Prueba",
  mine: true,
  can_edit: true,
  shared: false,
  status: "ACTIVO",
  version_number: 1,
  questions: [],
  updated_at: "2026-11-11T18:00:00Z",
};

function makeCall(overrides: Partial<Call> = {}): Call {
  return {
    id: "l1",
    application_id: "a1",
    status: "BORRADOR",
    bank_name: "Banco de nómina",
    bank_version: 1,
    called_at: "2026-11-11T18:00:00Z",
    created_by_name: "Reclutadora de Prueba",
    notes: "",
    questions: [
      { id: "q1", text: "¿Qué nóminas has calculado?", competency: "Nómina", guidance: "", origin: "MANUAL", answer: "", notes: "", not_asked: false },
      { id: "q2", text: "¿Cómo validas el IMSS?", competency: "", guidance: "", origin: "MANUAL", answer: "", notes: "", not_asked: false },
    ],
    analysis: null,
    analysis_at: null,
    closed_at: null,
    ...overrides,
  };
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("CallsSection", () => {
  it("abre una llamada con un banco, captura respuestas y la cierra", async () => {
    let calls: Call[] = [];
    const fetchMock = mockApi({
      [`GET ${CALLS_URL}`]: () => ({ body: calls }),
      ["GET /api/v1/question-banks"]: { body: [BANK, { ...BANK, id: "b2", name: "Archivado", status: "ARCHIVADO" }] },
      [`POST ${CALLS_URL}`]: () => {
        calls = [makeCall()];
        return { status: 201, body: calls[0] };
      },
      ["PUT /api/v1/calls/l1"]: ({ init }) => {
        const sent = JSON.parse(String(init.body));
        calls = [makeCall({ status: sent.close ? "CERRADA" : "BORRADOR" })];
        return { body: calls[0] };
      },
    });
    const user = userEvent.setup();
    renderApp(<CallsSection applicationId="a1" canEdit active />, { session: makeUser() });
    await user.click(await screen.findByRole("button", { name: "Nueva llamada" }));
    // Solo se ofrecen bancos activos.
    expect(within(await screen.findByLabelText("Banco de preguntas")).getAllByRole("option")).toHaveLength(1);
    await user.click(screen.getByRole("button", { name: "Abrir llamada" }));

    await user.type(await screen.findByLabelText("Respuesta a la pregunta 1"), "Nómina quincenal de 200 personas");
    await user.click(screen.getAllByRole("checkbox", { name: "No se realizó" })[1]);
    await user.type(screen.getByLabelText("Observaciones generales"), "Llamada de 15 minutos");
    await user.click(screen.getByRole("button", { name: "Cerrar llamada" }));

    expect(await screen.findByText("Cerrada")).toBeTruthy();
    const put = fetchMock.mock.calls.find(([, init]) => init?.method === "PUT");
    expect(JSON.parse(String(put?.[1]?.body))).toEqual({
      answers: [
        { question_id: "q1", answer: "Nómina quincenal de 200 personas", notes: "", not_asked: false },
        { question_id: "q2", answer: "", notes: "", not_asked: true },
      ],
      notes: "Llamada de 15 minutos",
      close: true,
    });
    // Cerrada: ya no se puede guardar ni cerrar otra vez.
    expect(screen.queryByRole("button", { name: /^Guardar$|Cerrar llamada/ })).toBeNull();
  });

  it("muestra el análisis de la IA como resumen, sin recomendación", async () => {
    const analysis = {
      resumen: "Describe tres años calculando nómina.",
      evidencias: ["Nómina de 200 personas"],
      discrepancias_verificables: ["El CV indica 2020 a 2022; en la llamada dijo tres años"],
      preguntas_de_seguimiento: [],
    };
    const closed = makeCall({ status: "CERRADA" });
    let analyzed = false;
    mockApi({
      [`GET ${CALLS_URL}`]: () => ({ body: [analyzed ? { ...closed, analysis } : closed] }),
      ["POST /api/v1/calls/l1/analysis"]: () => {
        analyzed = true;
        return { body: { ...closed, analysis } };
      },
    });
    const user = userEvent.setup();
    renderApp(<CallsSection applicationId="a1" canEdit active />, { session: makeUser() });
    await user.click(await screen.findByRole("button", { name: /Banco de nómina/ }));
    await user.click(screen.getByRole("button", { name: "Analizar con IA" }));
    const panel = await screen.findByRole("region", { name: "Análisis de la IA" });
    expect(within(panel).getByText("Describe tres años calculando nómina.")).toBeTruthy();
    expect(within(panel).getByText("Diferencias por aclarar con el CV")).toBeTruthy();
    expect(within(panel).queryByText("Preguntas de seguimiento")).toBeNull();
    expect(within(panel).getByText(/esa decisión es tuya/)).toBeTruthy();
  });

  it("con acceso de lectura se consultan las llamadas sin poder abrir ni analizar", async () => {
    mockApi({ [`GET ${CALLS_URL}`]: { body: [makeCall({ status: "CERRADA" })] } });
    const user = userEvent.setup();
    renderApp(<CallsSection applicationId="a1" canEdit={false} active />, { session: makeUser() });
    await user.click(await screen.findByRole("button", { name: /Banco de nómina/ }));
    expect(screen.getByText("1. ¿Qué nóminas has calculado?")).toBeTruthy();
    expect(screen.queryByRole("button", { name: /Nueva llamada|Analizar con IA|Guardar/ })).toBeNull();
  });
});
