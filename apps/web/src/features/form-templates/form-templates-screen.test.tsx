import { cleanup, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { FormTemplate } from "@/lib/api/assessments";
import { makeUser, mockApi, problem, renderApp } from "@/test/helpers";
import { FormTemplatesScreen } from "./form-templates-screen";

const URL = "/api/v1/form-templates";
const BASIC: FormTemplate = {
  id: "t1",
  name: "Estudio socioeconómico básico",
  description: null,
  status: "ACTIVA",
  version_number: 1,
  sections: [{ title: "Datos de la visita", fields: [{ id: "visita", label: "Fecha de la visita", type: "FECHA", required: true, options: [], minimum: null, maximum: null, columns: [], manual_only: false }] }],
};

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("FormTemplatesScreen", () => {
  it("crea un formulario con una sección y campos de distintos tipos", async () => {
    let templates = [BASIC];
    const created: FormTemplate = { ...BASIC, id: "t2", name: "Estudio de confianza" };
    const fetchMock = mockApi({
      [`GET ${URL}`]: () => ({ body: templates }),
      [`POST ${URL}`]: () => {
        templates = [BASIC, created];
        return { status: 201, body: created };
      },
    });
    const user = userEvent.setup();
    renderApp(<FormTemplatesScreen />, { session: makeUser() });
    expect(await screen.findByText("versión 1 · 1 campos")).toBeTruthy();
    await user.click(screen.getByRole("button", { name: "Nuevo formulario" }));
    await user.type(screen.getByLabelText("Nombre"), "Estudio de confianza");
    await user.type(screen.getByLabelText("Sección 1"), "Referencias");
    await user.type(screen.getByLabelText("Nombre del campo 1 de la sección 1"), "Resultado");
    await user.selectOptions(screen.getByLabelText("Tipo del campo 1 de la sección 1"), "OPCIONES");
    await user.type(screen.getByLabelText("Opciones del campo 1 de la sección 1"), "Confirmadas, No contactadas");
    await user.click(screen.getByRole("checkbox", { name: "Obligatorio" }));
    await user.click(screen.getByRole("button", { name: "Crear formulario" }));

    expect((await screen.findByRole("status")).textContent).toContain("Formulario guardado");
    const post = fetchMock.mock.calls.find(([, init]) => init?.method === "POST");
    expect(JSON.parse(String(post?.[1]?.body))).toEqual({
      name: "Estudio de confianza",
      description: null,
      sections: [{ title: "Referencias", fields: [{ id: null, label: "Resultado", type: "OPCIONES", required: true, options: ["Confirmadas", "No contactadas"], minimum: null, maximum: null, columns: [], manual_only: false }] }],
      expected_version: 0,
    });
  });

  it("guarda una versión nueva conservando el identificador de los campos y muestra errores", async () => {
    const fetchMock = mockApi({
      [`GET ${URL}`]: { body: [BASIC] },
      [`PUT ${URL}/t1`]: problem(409, "conflicto", "Otra persona guardó una versión más reciente."),
    });
    const user = userEvent.setup();
    renderApp(<FormTemplatesScreen />, { session: makeUser() });
    await user.click(await screen.findByRole("button", { name: "Estudio socioeconómico básico" }));
    await user.click(screen.getByRole("button", { name: "Agregar campo" }));
    await user.type(screen.getByLabelText("Nombre del campo 2 de la sección 1"), "Datos familiares");
    await user.selectOptions(screen.getByLabelText("Tipo del campo 2 de la sección 1"), "TABLA");
    await user.type(screen.getByLabelText("Columnas del campo 2 de la sección 1"), "Nombre, Edad ,,Parentesco");
    await user.click(screen.getAllByLabelText("Solo captura manual")[1]);
    await user.click(screen.getByRole("button", { name: "Guardar cambios" }));
    expect((await screen.findByRole("alert")).textContent).toContain("versión más reciente");
    const put = fetchMock.mock.calls.find(([, init]) => init?.method === "PUT");
    const body = JSON.parse(String(put?.[1]?.body));
    expect(body.expected_version).toBe(1);
    expect(body.sections[0].fields.map((field: { id: string | null }) => field.id)).toEqual(["visita", null]);
    expect(body.sections[0].fields[1]).toMatchObject({
      type: "TABLA",
      columns: ["Nombre", "Edad", "Parentesco"],
      manual_only: true,
    });
    expect(body.sections[0].fields[0].manual_only).toBe(false);
  });
});
