import { cleanup, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { makeUser, mockApi, problem, renderApp } from "@/test/helpers";
import { PipelineScreen } from "./pipeline-screen";

const stage = (position: number, name: string, kind: string, is_optional = false) => ({
  id: `s${position}`,
  position,
  name,
  kind,
  is_optional,
});
const V1 = {
  id: "p1",
  version_number: 1,
  created_at: "2026-11-11T18:00:00Z",
  stages: [stage(1, "Evaluación de CV", "EVALUACION_CV"), stage(2, "Revisión local RH", "REVISION_RH")],
};

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("PipelineScreen", () => {
  it("guarda las etapas como una versión nueva", async () => {
    let saved = false;
    const v2 = { ...V1, id: "p2", version_number: 2, stages: [...V1.stages, stage(3, "Entrevista con RH", "OTRA", true)] };
    const fetchMock = mockApi({
      ["GET /api/v1/pipeline"]: () => ({ body: saved ? v2 : V1 }),
      ["PUT /api/v1/pipeline"]: () => {
        saved = true;
        return { body: v2 };
      },
    });
    const user = userEvent.setup();
    renderApp(<PipelineScreen />, { session: makeUser() });
    expect(await screen.findByRole("heading", { name: "Versión 1" })).toBeTruthy();
    await user.click(screen.getByRole("button", { name: "Agregar etapa" }));
    await user.type(screen.getByLabelText("Etapa 3"), "Entrevista con RH");
    await user.click(screen.getAllByRole("checkbox", { name: "Opcional" })[2]);
    await user.click(screen.getByRole("button", { name: "Subir la etapa 3" }));
    await user.click(screen.getByRole("button", { name: "Guardar como versión nueva" }));

    expect(await screen.findByRole("heading", { name: "Versión 2" })).toBeTruthy();
    const put = fetchMock.mock.calls.find(([, init]) => init?.method === "PUT");
    expect(JSON.parse(String(put?.[1]?.body))).toEqual({
      stages: [
        { name: "Evaluación de CV", kind: "EVALUACION_CV", is_optional: false },
        { name: "Entrevista con RH", kind: "OTRA", is_optional: true },
        { name: "Revisión local RH", kind: "REVISION_RH", is_optional: false },
      ],
      expected_version: 1,
    });
  });

  it("muestra el motivo si no se pueden guardar", async () => {
    mockApi({
      ["GET /api/v1/pipeline"]: { body: V1 },
      ["PUT /api/v1/pipeline"]: problem(422, "validacion", "Las etapas no tienen cambios."),
    });
    const user = userEvent.setup();
    renderApp(<PipelineScreen />, { session: makeUser() });
    await user.click(await screen.findByRole("button", { name: "Guardar como versión nueva" }));
    expect((await screen.findByRole("alert")).textContent).toContain("no tienen cambios");
  });
});
