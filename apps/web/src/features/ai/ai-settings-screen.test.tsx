import { cleanup, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { AiModel, AiProvider } from "@/lib/api/ai";
import { makeUser, mockApi, problem, renderApp } from "@/test/helpers";
import { AiSettingsScreen } from "./ai-settings-screen";

const FAKE_KEY = "clave-ficticia-de-prueba-0000-ABCD";

function makeProvider(overrides: Partial<AiProvider> = {}): AiProvider {
  return {
    code: "ANTHROPIC",
    name: "Anthropic",
    enabled: false,
    key_configured: false,
    key_source: null,
    key_mask: null,
    key_updated_at: null,
    key_updated_by_name: null,
    last_test_at: null,
    last_test_ok: null,
    last_test_error: null,
    monthly_limit_usd: null,
    models_available: 0,
    ...overrides,
  };
}
const openai = makeProvider({ code: "OPENAI", name: "OpenAI" });
const withKey = makeProvider({
  key_configured: true,
  key_source: "PANTALLA",
  key_mask: "••••ABCD",
  key_updated_at: "2026-11-11T18:00:00Z",
  key_updated_by_name: "Administradora de Prueba",
});
const model: AiModel = {
  id: "40000000-0000-0000-0000-000000000001",
  provider_code: "ANTHROPIC",
  provider_name: "Anthropic",
  model_id: "modelo-grande-1",
  display_name: "Modelo Grande 1",
  is_available: true,
  reports_capabilities: true,
  input_price: null,
  output_price: null,
};
const assignments = (assigned: AiModel | null = null) => [
  { operation: "EXTRACCION_CV", model: assigned, updated_at: null },
  { operation: "EVALUACION_DOCUMENTAL", model: null, updated_at: null },
];
const emptyUsage = {
  year: 2026,
  month: 11,
  rows: [],
  providers: [
    { code: "ANTHROPIC", name: "Anthropic", spent_usd: "0", limit_usd: null },
    { code: "OPENAI", name: "OpenAI", spent_usd: "0", limit_usd: null },
  ],
};
const base = (providers: AiProvider[], encryption = true) => ({
  "GET /api/v1/ai/providers": { body: { encryption_available: encryption, providers } },
  "GET /api/v1/ai/models": { body: [] },
  "GET /api/v1/ai/assignments": { body: assignments() },
  "GET /api/v1/ai/usage": { body: emptyUsage },
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("AiSettingsScreen", () => {
  it("no se muestra ni consulta nada a quien no es administrador", () => {
    const fetchMock = mockApi({});
    renderApp(<AiSettingsScreen />, { session: makeUser({ role: "RECLUTADOR" }) });
    expect(screen.getByRole("alert").textContent).toContain("solo para administradores");
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("registra una clave sin volver a mostrarla", async () => {
    let stored = false;
    const fetchMock = mockApi({
      ...base([makeProvider(), openai]),
      "GET /api/v1/ai/providers": () => ({
        body: { encryption_available: true, providers: [stored ? withKey : makeProvider(), openai] },
      }),
      "PUT /api/v1/ai/providers/ANTHROPIC/key": () => {
        stored = true;
        return { body: withKey };
      },
    });
    const user = userEvent.setup();
    renderApp(<AiSettingsScreen />, { session: makeUser() });
    const card = await screen.findByRole("region", { name: "Anthropic" });
    expect(within(card).getByText("Sin registrar")).toBeTruthy();
    expect((within(card).getByRole("button", { name: "Probar conexión" }) as HTMLButtonElement).disabled).toBe(true);

    await user.click(within(card).getByRole("button", { name: "Registrar clave" }));
    const dialog = screen.getByRole("dialog", { name: "Registrar clave de Anthropic" });
    const field = within(dialog).getByLabelText("API key") as HTMLInputElement;
    expect(field.type).toBe("password");
    await user.click(within(dialog).getByRole("button", { name: "Guardar clave" }));
    expect(within(dialog).getByRole("alert").textContent).toContain("Pega la API key completa");
    await user.type(field, FAKE_KEY);
    await user.click(within(dialog).getByRole("button", { name: "Guardar clave" }));

    expect(await within(card).findByText("••••ABCD")).toBeTruthy();
    expect(within(card).getByRole("status").textContent).toContain("Clave guardada y cifrada");
    expect(within(card).getByText(/por Administradora de Prueba/)).toBeTruthy();
    expect(document.body.textContent).not.toContain(FAKE_KEY);
    const put = fetchMock.mock.calls.find(([, init]) => init?.method === "PUT");
    expect(JSON.parse(String(put?.[1]?.body))).toEqual({ api_key: FAKE_KEY });
  });

  it("muestra el motivo cuando la prueba de conexión falla", async () => {
    mockApi({
      ...base([withKey, openai]),
      "POST /api/v1/ai/providers/ANTHROPIC/test": {
        body: {
          ok: false,
          error: "El proveedor rechazó la clave: no es válida o no tiene permisos.",
          models_found: 0,
          provider: { ...withKey, last_test_ok: false },
        },
      },
    });
    const user = userEvent.setup();
    renderApp(<AiSettingsScreen />, { session: makeUser() });
    const card = await screen.findByRole("region", { name: "Anthropic" });
    await user.click(within(card).getByRole("button", { name: "Probar conexión" }));
    expect((await within(card).findByRole("alert")).textContent).toContain("rechazó la clave");
  });

  it("habilita el proveedor y guarda el límite mensual", async () => {
    const fetchMock = mockApi({
      ...base([withKey, openai]),
      "PUT /api/v1/ai/providers/ANTHROPIC": { body: { ...withKey, enabled: true } },
    });
    const user = userEvent.setup();
    renderApp(<AiSettingsScreen />, { session: makeUser() });
    const card = await screen.findByRole("region", { name: "Anthropic" });
    await user.type(within(card).getByLabelText("Límite de gasto mensual (USD)"), "150");
    await user.click(within(card).getByRole("button", { name: "Habilitar" }));
    expect((await within(card).findByRole("status")).textContent).toContain("quedó habilitado");
    const put = fetchMock.mock.calls.find(([, init]) => init?.method === "PUT");
    expect(JSON.parse(String(put?.[1]?.body))).toEqual({ enabled: true, monthly_limit_usd: "150" });
  });

  it("una clave definida por Sistemas no se puede cambiar ni revocar", async () => {
    mockApi(base([makeProvider({ key_configured: true, key_source: "ENTORNO", key_mask: "••••ZZZZ" }), openai]));
    renderApp(<AiSettingsScreen />, { session: makeUser() });
    const card = await screen.findByRole("region", { name: "Anthropic" });
    expect(within(card).getByText("Definida por Sistemas en el servidor")).toBeTruthy();
    expect(within(card).queryByRole("button", { name: /clave/i })).toBeNull();
  });

  it("revoca la clave tras confirmarlo", async () => {
    const fetchMock = mockApi({
      ...base([withKey, openai]),
      "DELETE /api/v1/ai/providers/ANTHROPIC/key": { body: makeProvider() },
    });
    const user = userEvent.setup();
    renderApp(<AiSettingsScreen />, { session: makeUser() });
    const card = await screen.findByRole("region", { name: "Anthropic" });
    await user.click(within(card).getByRole("button", { name: "Revocar clave" }));
    expect(fetchMock.mock.calls.some(([, init]) => init?.method === "DELETE")).toBe(false);
    const dialog = screen.getByRole("dialog", { name: "Revocar clave de Anthropic" });
    await user.click(within(dialog).getByRole("button", { name: "Revocar clave" }));
    expect((await within(card).findByRole("status")).textContent).toContain("Clave revocada");
  });

  it("avisa cuando falta la clave maestra y no deja registrar claves", async () => {
    mockApi(base([makeProvider(), openai], false));
    renderApp(<AiSettingsScreen />, { session: makeUser() });
    expect((await screen.findByRole("alert")).textContent).toContain("clave maestra");
    const card = screen.getByRole("region", { name: "Anthropic" });
    expect((within(card).getByRole("button", { name: "Registrar clave" }) as HTMLButtonElement).disabled).toBe(true);
  });

  it("asigna a una operación un modelo de un proveedor habilitado", async () => {
    const fetchMock = mockApi({
      ...base([{ ...withKey, enabled: true, models_available: 1 }, openai]),
      "GET /api/v1/ai/models": {
        body: [model, { ...model, id: "40000000-0000-0000-0000-000000000002", display_name: "Retirado", is_available: false }],
      },
      "PUT /api/v1/ai/assignments/EXTRACCION_CV": {
        body: { operation: "EXTRACCION_CV", model, updated_at: "2026-11-11T18:00:00Z" },
      },
    });
    const user = userEvent.setup();
    renderApp(<AiSettingsScreen />, { session: makeUser() });
    const select = await screen.findByLabelText("Extracción de datos de CV");
    await within(select).findByRole("option", { name: "Modelo Grande 1" });
    expect(within(select).queryByRole("option", { name: "Retirado" })).toBeNull();
    await user.selectOptions(select, model.id);
    expect((await screen.findByText(/Modelo actualizado para «Extracción de datos de CV»/)).tagName).toBe("P");
    const put = fetchMock.mock.calls.find(([url]) => String(url).endsWith("/assignments/EXTRACCION_CV"));
    expect(JSON.parse(String(put?.[1]?.body))).toEqual({ model_id: model.id });
  });

  it("guarda el precio de un modelo, lo prueba y muestra el consumo del mes", async () => {
    const priced = { ...model, input_price: "3.0000", output_price: "15.0000" };
    let current = model;
    const fetchMock = mockApi({
      ...base([{ ...withKey, enabled: true, models_available: 1 }, openai]),
      "GET /api/v1/ai/models": () => ({ body: [current] }),
      [`PUT /api/v1/ai/models/${model.id}/prices`]: () => {
        current = priced;
        return { body: priced };
      },
      [`POST /api/v1/ai/models/${model.id}/test`]: {
        body: {
          ok: true,
          error: null,
          reply: "OK",
          input_tokens: 1000,
          output_tokens: 500,
          estimated_cost_usd: "0.010500",
          attempts: 1,
        },
      },
      "GET /api/v1/ai/usage": {
        body: {
          ...emptyUsage,
          rows: [
            {
              provider_code: "ANTHROPIC",
              provider_name: "Anthropic",
              model_id: "modelo-grande-1",
              operation: "PRUEBA",
              calls: 2,
              failures: 1,
              input_tokens: 1000,
              output_tokens: 500,
              estimated_cost_usd: "0.010500",
            },
          ],
          providers: [
            { code: "ANTHROPIC", name: "Anthropic", spent_usd: "0.010500", limit_usd: "200.00" },
            emptyUsage.providers[1],
          ],
        },
      },
    });
    const user = userEvent.setup();
    renderApp(<AiSettingsScreen />, { session: makeUser() });
    await user.type(await screen.findByLabelText("Precio de entrada de Modelo Grande 1"), "3");
    await user.type(screen.getByLabelText("Precio de salida de Modelo Grande 1"), "15");
    await user.click(screen.getByRole("button", { name: "Guardar precio de Modelo Grande 1" }));
    const prices = screen.getByRole("region", { name: "Modelos y precios" });
    expect((await within(prices).findByRole("status")).textContent).toContain("guardado");
    const put = fetchMock.mock.calls.find(([url]) => String(url).endsWith("/prices"));
    expect(JSON.parse(String(put?.[1]?.body))).toEqual({ input_price: "3", output_price: "15" });

    await user.click(screen.getByRole("button", { name: "Probar Modelo Grande 1" }));
    expect((await within(prices).findByText(/respondió/)).textContent).toContain(
      "Costo estimado: 0.010500 USD",
    );

    const usage = screen.getByRole("region", { name: "Consumo y costos de este mes" });
    expect(within(usage).getByText("Límite mensual: 200.00 USD")).toBeTruthy();
    expect(within(usage).getByRole("cell", { name: "Prueba de modelo" })).toBeTruthy();
    expect(within(usage).getByRole("cell", { name: "0.010500 USD" })).toBeTruthy();
  });

  it("muestra el error si la configuración no carga", async () => {
    mockApi({ "GET /api/v1/ai/providers": problem(503, "servicio_no_disponible", "Servicio no disponible.") });
    renderApp(<AiSettingsScreen />, { session: makeUser() });
    expect((await screen.findByRole("alert")).textContent).toContain("Servicio no disponible");
  });
});
