import { cleanup, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { ProfileVersion, PromptVersion } from "@/lib/api/evaluation";
import { makeUser, mockApi, problem, renderApp } from "@/test/helpers";
import { EvaluationWorkspace } from "./evaluation-workspace";

const VACANCY_ID = "10000000-0000-0000-0000-000000000001";
const PROFILE_URL = `/api/v1/vacancies/${VACANCY_ID}/profile-versions`;
const PROMPTS_URL = `/api/v1/vacancies/${VACANCY_ID}/prompts`;
const PROMPT_ID = "50000000-0000-0000-0000-000000000001";
const LEVELS = ["Insuficiente", "Mínima", "Parcial", "Suficiente", "Supera"];

function makeProfile(overrides: Partial<ProfileVersion> = {}): ProfileVersion {
  return {
    id: "60000000-0000-0000-0000-000000000001",
    version_number: 1,
    origin: "MANUAL",
    change_note: null,
    created_at: "2026-11-11T18:00:00Z",
    created_by_name: "Reclutadora de Prueba",
    objective: "Calcular la nómina.",
    experience: "",
    education: "",
    functions: [],
    responsibilities: [],
    knowledge: [],
    skills: [],
    certifications: [],
    must_have: ["Experiencia en nómina"],
    nice_to_have: [],
    ambiguities: [],
    ...overrides,
  };
}

function makePrompt(overrides: Partial<PromptVersion> = {}): PromptVersion {
  return {
    id: PROMPT_ID,
    vacancy_id: VACANCY_ID,
    version_number: 1,
    status: "BORRADOR",
    profile_version_number: 1,
    pass_threshold: "60.00",
    revision: 1,
    layers: [
      { key: "INSTRUCCIONES", title: "Instrucciones permanentes", content: "Evalúa con evidencia.", locked: false },
      { key: "RUBRICA", title: "Rúbrica", content: "C1. Experiencia en nómina", locked: true },
    ],
    criteria: [
      {
        id: "70000000-0000-0000-0000-000000000001",
        code: "C1",
        name: "Experiencia en nómina",
        description: "",
        kind: "INDISPENSABLE",
        weight: "3.00",
        levels: LEVELS,
        origin: "PERFIL",
      },
    ],
    rendered: "## 1. Instrucciones permanentes",
    length: 31,
    max_length: 24000,
    issues: [],
    duplicated_from: null,
    created_at: "2026-11-11T18:00:00Z",
    created_by_name: "Reclutadora de Prueba",
    updated_at: "2026-11-11T18:00:00Z",
    approved_at: null,
    approved_by_name: null,
    ...overrides,
  };
}

function renderWorkspace(props: { canEdit?: boolean; canApprove?: boolean } = {}) {
  return renderApp(
    <EvaluationWorkspace
      vacancyId={VACANCY_ID}
      vacancyName="Analista de Nómina"
      canEdit={props.canEdit ?? true}
      canApprove={props.canApprove ?? true}
      onBack={() => {}}
    />,
    { session: makeUser() },
  );
}
const sent = (fetchMock: ReturnType<typeof mockApi>, method: string) => {
  const call = fetchMock.mock.calls.find(([, init]) => init?.method === method);
  return { url: String(call?.[0]), body: JSON.parse(String(call?.[1]?.body ?? "null")) };
};

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("EvaluationWorkspace", () => {
  it("guarda el primer perfil convirtiendo cada línea en un requisito", async () => {
    let saved = false;
    const fetchMock = mockApi({
      [`GET ${PROFILE_URL}`]: () => ({ body: saved ? [makeProfile()] : [] }),
      [`POST ${PROFILE_URL}`]: () => {
        saved = true;
        return { status: 201, body: makeProfile() };
      },
    });
    const user = userEvent.setup();
    renderWorkspace();
    expect(await screen.findByText(/Todavía no hay perfil/)).toBeTruthy();
    await user.type(screen.getByLabelText("Objetivo del puesto"), "Calcular la nómina.");
    await user.type(
      screen.getByLabelText("Requisitos indispensables (uno por línea)"),
      "Experiencia en nómina{Enter}{Enter}  Excel intermedio  ",
    );
    await user.click(screen.getByRole("button", { name: "Guardar perfil" }));

    expect(await screen.findByText("Versión 1 (vigente)")).toBeTruthy();
    const { body } = sent(fetchMock, "POST");
    expect(body.objective).toBe("Calcular la nómina.");
    expect(body.must_have).toEqual(["Experiencia en nómina", "Excel intermedio"]);
    expect(body.nice_to_have).toEqual([]);
    expect(body.expected_version).toBe(0);
  });

  it("muestra el motivo si el perfil no se puede guardar", async () => {
    mockApi({
      [`GET ${PROFILE_URL}`]: { body: [makeProfile()] },
      [`POST ${PROFILE_URL}`]: problem(409, "conflicto", "Otra persona guardó una versión más reciente del perfil."),
    });
    const user = userEvent.setup();
    renderWorkspace();
    await user.type(await screen.findByLabelText("Experiencia"), "Dos años");
    await user.click(screen.getByRole("button", { name: "Guardar como versión nueva" }));
    expect((await screen.findByRole("alert")).textContent).toContain("versión más reciente");
  });

  it("con acceso de lectura el perfil y el prompt no se pueden cambiar", async () => {
    mockApi({
      [`GET ${PROFILE_URL}`]: { body: [makeProfile()] },
      [`GET ${PROMPTS_URL}`]: { body: [makePrompt()] },
    });
    const user = userEvent.setup();
    renderWorkspace({ canEdit: false, canApprove: false });
    const objective = (await screen.findByLabelText("Objetivo del puesto")) as HTMLTextAreaElement;
    expect(objective.readOnly).toBe(true);
    expect(screen.queryByRole("button", { name: /Guardar/ })).toBeNull();

    await user.click(screen.getByRole("button", { name: "Prompt de evaluación" }));
    expect(await screen.findByRole("heading", { name: "Versión 1" })).toBeTruthy();
    for (const name of [/Generar/, "Guardar cambios", "Enviar a revisión", "Duplicar", "Archivar"]) {
      expect(screen.queryByRole("button", { name })).toBeNull();
    }
    expect((screen.getByLabelText("Peso") as HTMLInputElement).readOnly).toBe(true);
  });

  it("genera el primer borrador y guarda los cambios de la rúbrica", async () => {
    let versions: PromptVersion[] = [];
    const edited = makePrompt({ revision: 2, pass_threshold: "70.00" });
    const fetchMock = mockApi({
      [`GET ${PROMPTS_URL}`]: () => ({ body: versions }),
      [`POST ${PROMPTS_URL}`]: () => {
        versions = [makePrompt()];
        return { status: 201, body: versions[0] };
      },
      [`PUT /api/v1/prompts/${PROMPT_ID}`]: () => {
        versions = [edited];
        return { body: edited };
      },
    });
    const user = userEvent.setup();
    renderWorkspace();
    await user.click(screen.getByRole("button", { name: "Prompt de evaluación" }));
    expect(await screen.findByText(/Todavía no hay prompt/)).toBeTruthy();
    await user.click(screen.getByRole("button", { name: "Generar borrador desde el perfil" }));
    expect((await screen.findByRole("status")).textContent).toContain("Se generó el borrador (versión 1)");

    // La capa del sistema no se edita; las demás sí.
    expect((screen.getByLabelText("2. Rúbrica (la escribe el sistema)") as HTMLTextAreaElement).readOnly).toBe(true);
    await user.type(screen.getByLabelText("1. Instrucciones permanentes"), " Sé breve.");
    const weight = screen.getByLabelText("Peso");
    await user.clear(weight);
    await user.type(weight, "5");
    const threshold = screen.getByLabelText("Umbral de aceptación (0 a 100)");
    await user.clear(threshold);
    await user.type(threshold, "70");
    await user.click(screen.getByRole("button", { name: "Agregar criterio" }));
    await user.type(screen.getByLabelText(/Criterio C2/), "Timbrado de CFDI");
    await user.click(screen.getByRole("button", { name: "Guardar cambios" }));

    expect((await screen.findByRole("status")).textContent).toContain("Cambios guardados");
    const { body } = sent(fetchMock, "PUT");
    expect(body.revision).toBe(1);
    expect(body.pass_threshold).toBe("70");
    expect(body.layers.INSTRUCCIONES).toBe("Evalúa con evidencia. Sé breve.");
    expect(body.criteria.map((c: { id: string | null; name: string; weight: string }) => [c.id, c.name, c.weight])).toEqual([
      ["70000000-0000-0000-0000-000000000001", "Experiencia en nómina", "5"],
      [null, "Timbrado de CFDI", "1"],
    ]);
    expect(body.criteria[1].levels).toHaveLength(5);
  });

  it("muestra lo que falta y solo quien puede aprueba una versión en revisión", async () => {
    const inReview = makePrompt({ status: "EN_REVISION", revision: 3 });
    const approved = makePrompt({
      status: "APROBADO",
      revision: 4,
      approved_at: "2026-11-11T19:00:00Z",
      approved_by_name: "Reclutadora de Prueba",
    });
    let versions = [inReview];
    const fetchMock = mockApi({
      [`GET ${PROFILE_URL}`]: { body: [makeProfile()] },
      [`GET ${PROMPTS_URL}`]: () => ({ body: versions }),
      [`POST /api/v1/prompts/${PROMPT_ID}/approve`]: () => {
        versions = [approved];
        return { body: approved };
      },
    });
    const user = userEvent.setup();
    const view = renderWorkspace({ canApprove: false });
    await user.click(screen.getByRole("button", { name: "Prompt de evaluación" }));
    expect(await screen.findByRole("button", { name: "Devolver a borrador" })).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Aprobar" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Guardar cambios" })).toBeNull();
    view.unmount();

    renderWorkspace({ canApprove: true });
    await user.click(screen.getByRole("button", { name: "Prompt de evaluación" }));
    await user.click(await screen.findByRole("button", { name: "Aprobar" }));
    expect((await screen.findByRole("status")).textContent).toContain("Ya no se puede modificar");
    expect(sent(fetchMock, "POST")).toEqual({
      url: `/api/v1/prompts/${PROMPT_ID}/approve`,
      body: { revision: 3 },
    });
    // Aprobada: inmutable, pero se puede duplicar.
    expect(screen.getByText(/está aprobada y no se modifica/)).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Guardar cambios" })).toBeNull();
    expect((screen.getByLabelText("Peso") as HTMLInputElement).readOnly).toBe(true);
    expect(screen.getByRole("button", { name: "Duplicar" })).toBeTruthy();
  });

  it("lista los problemas que impiden enviar a revisión", async () => {
    mockApi({
      [`GET ${PROFILE_URL}`]: { body: [makeProfile()] },
      [`GET ${PROMPTS_URL}`]: {
        body: [makePrompt({ issues: ["El criterio C1 debe tener un peso mayor que cero."] })],
      },
    });
    const user = userEvent.setup();
    renderWorkspace();
    await user.click(screen.getByRole("button", { name: "Prompt de evaluación" }));
    const alert = await screen.findByRole("alert");
    expect(within(alert).getByText("El criterio C1 debe tener un peso mayor que cero.")).toBeTruthy();
  });
});
