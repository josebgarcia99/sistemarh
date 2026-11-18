import { cleanup, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { ProfileVersion, PromptVersion } from "@/lib/api/evaluation";
import { makeUser, mockApi, problem, renderApp } from "@/test/helpers";
import { VacancySteps } from "@/features/vacancies/vacancy-steps";
import type { Vacancy } from "@/lib/api/vacancies";
import { EvaluationWorkspace } from "./evaluation-workspace";

const VACANCY_ID = "10000000-0000-0000-0000-000000000001";
const PROFILE_URL = `/api/v1/vacancies/${VACANCY_ID}/profile-versions`;
const PROMPTS_URL = `/api/v1/vacancies/${VACANCY_ID}/prompts`;
const PROMPT_ID = "50000000-0000-0000-0000-000000000001";
const LEVELS = ["Insuficiente", "Mínima", "Parcial", "Suficiente", "Supera"];

const EMPTY_PROFILE = {
  position_name: "",
  area: "",
  location: "",
  reports_to: "",
  supervises: "",
  contract_type: "",
  work_mode: "",
  schedule: "",
  offer: "",
  specialty: "",
  document_version: "",
  document_date: "",
  objective: "",
  internal_relations: "",
  external_relations: "",
  experience: "",
  education: "",
  education_levels: [] as string[],
  must_have: [] as string[],
  knowledge: [] as string[],
  skills: [] as string[],
  functions: [] as string[],
  nice_to_have: [] as string[],
  certifications: [] as string[],
  responsibilities: [] as string[],
  ambiguities: [] as string[],
  activities: [] as { description: string; frequency: string }[],
  kpis: [] as { name: string; goal: string; formula: string }[],
};

function makeProfile(overrides: Partial<ProfileVersion> = {}): ProfileVersion {
  return {
    id: "60000000-0000-0000-0000-000000000001",
    version_number: 1,
    origin: "MANUAL",
    change_note: null,
    created_at: "2026-11-11T18:00:00Z",
    created_by_name: "Reclutadora de Prueba",
    ...EMPTY_PROFILE,
    objective: "Calcular la nómina.",
    must_have: ["Experiencia en nómina"],
    ...overrides,
  };
}

function makeFile(id: string, name: string) {
  return {
    id,
    vacancy_id: VACANCY_ID,
    document_type: "PERFIL_PUESTO",
    sensitive: false,
    original_name: name,
    content_type: null,
    size_bytes: 1200,
    sha256: null,
    malware_scan: null,
    encrypted: false,
    uploaded_by: "u1",
    uploaded_by_name: "Reclutadora de Prueba",
    created_at: "2026-11-11T18:00:00Z",
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

const OVERVIEW_URL = `/api/v1/vacancies/${VACANCY_ID}/cv-batches`;
const overview = (total: number, pending: number, approved = false) => ({
  body: {
    approved_prompt: approved ? { id: PROMPT_ID, version_number: 1, pass_threshold: "60.00", criteria: 5 } : null,
    total_cvs: total,
    pending_cvs: pending,
    batches: [],
  },
});

describe("VacancySteps", () => {
  const vacancy = { id: VACANCY_ID, name: "Analista de Nómina" } as Vacancy;

  it("dice cómo va cada paso, resalta el que sigue y abre la pantalla de cada uno", async () => {
    mockApi({
      [`GET ${PROFILE_URL}`]: { body: [makeProfile({ version_number: 2 })] },
      [`GET ${PROMPTS_URL}`]: { body: [makePrompt()] },
      [`GET ${OVERVIEW_URL}`]: overview(0, 0),
    });
    const onOpenEvaluation = vi.fn();
    const onOpenCandidates = vi.fn();
    const user = userEvent.setup();
    renderApp(
      <VacancySteps vacancy={vacancy} onOpenEvaluation={onOpenEvaluation} onOpenCandidates={onOpenCandidates} />,
      { session: makeUser() },
    );
    // El perfil está listo; el prompt existe pero falta aprobarlo: es el paso que sigue.
    const next = await screen.findByRole("button", {
      name: "Paso 2: Prompt de evaluación. Borrador · falta aprobarlo. Es el paso que sigue.",
    });
    expect(next.getAttribute("aria-current")).toBe("step");
    const names = screen.getAllByRole("button").map((button) => button.getAttribute("aria-label"));
    expect(names).toEqual([
      "Paso 1: Perfil de puesto. Listo · versión 2.",
      "Paso 2: Prompt de evaluación. Borrador · falta aprobarlo. Es el paso que sigue.",
      "Paso 3: Cargar y evaluar CV. Sin CV cargados.",
      "Paso 4: Candidatos y etapas.",
    ]);
    for (const button of screen.getAllByRole("button")) await user.click(button);
    expect(onOpenEvaluation.mock.calls.map(([, tab]) => tab)).toEqual(["profile", "prompt", "cv"]);
    expect(onOpenCandidates).toHaveBeenCalledWith(vacancy);
  });

  it("con prompt aprobado y CV sin evaluar, el paso que sigue es evaluarlos", async () => {
    mockApi({
      [`GET ${PROFILE_URL}`]: { body: [makeProfile()] },
      [`GET ${PROMPTS_URL}`]: { body: [makePrompt({ status: "APROBADO" })] },
      [`GET ${OVERVIEW_URL}`]: overview(12, 5, true),
    });
    renderApp(<VacancySteps vacancy={vacancy} onOpenEvaluation={() => {}} onOpenCandidates={() => {}} />, {
      session: makeUser(),
    });
    expect(
      await screen.findByRole("button", {
        name: "Paso 3: Cargar y evaluar CV. 12 CV cargados · 5 sin evaluar. Es el paso que sigue.",
      }),
    ).toBeTruthy();
    expect(screen.getByRole("button", { name: "Paso 2: Prompt de evaluación. Aprobado · versión 1." })).toBeTruthy();
  });
});

describe("EvaluationWorkspace", () => {
  it("se abre en la pestaña pedida y, sin prompt aprobado, lleva a aprobarlo", async () => {
    mockApi({
      [`GET ${PROFILE_URL}`]: { body: [makeProfile()] },
      [`GET ${PROMPTS_URL}`]: { body: [makePrompt()] },
      [`GET ${OVERVIEW_URL}`]: overview(2, 2),
    });
    const user = userEvent.setup();
    renderApp(
      <EvaluationWorkspace
        vacancyId={VACANCY_ID}
        vacancyName="Analista de Nómina"
        canEdit
        canApprove
        initialTab="cv"
        onBack={() => {}}
      />,
      { session: makeUser() },
    );
    // Los CV se cargan aquí mismo, aunque el prompt todavía no esté aprobado.
    expect(await screen.findByRole("heading", { name: "Cargar CV" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Evaluación de CV" }).getAttribute("aria-pressed")).toBe("true");
    expect(screen.getByText(/Ya hay 2 CV cargados, en espera/)).toBeTruthy();
    await user.click(screen.getByRole("button", { name: "Ir al prompt de evaluación" }));
    expect(screen.getByRole("button", { name: "Prompt de evaluación" }).getAttribute("aria-pressed")).toBe("true");
  });

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
    await user.type(screen.getByLabelText("Propósito del puesto"), "Calcular la nómina.");
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
    await user.type(await screen.findByLabelText("Experiencia previa"), "Dos años");
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
    const objective = (await screen.findByLabelText("Propósito del puesto")) as HTMLTextAreaElement;
    expect(objective.readOnly).toBe(true);
    expect(screen.queryByRole("button", { name: /Guardar/ })).toBeNull();

    await user.click(screen.getByRole("button", { name: "Prompt de evaluación" }));
    expect(await screen.findByRole("heading", { name: "Versión 1" })).toBeTruthy();
    // La vista previa del prompt completo se puede consultar también con lectura.
    await user.click(screen.getByText("Vista previa: el prompt completo que recibirá la IA"));
    expect(screen.getByLabelText("Prompt completo").textContent).toContain("## 1. Instrucciones permanentes");
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
    const weight = screen.getAllByLabelText("Peso")[0];
    await user.clear(weight);
    await user.type(weight, "5");
    const threshold = screen.getByLabelText("Umbral de aceptación (0 a 100)");
    await user.clear(threshold);
    await user.type(threshold, "70");
    await user.click(screen.getByRole("button", { name: "Agregar criterio" }));
    await user.type(screen.getByLabelText(/Criterio C2/), "Timbrado de CFDI");
    // El peso sigue al tipo: un criterio deseable (peso 1) pasa a 3 al volverse
    // indispensable y regresa a 1 al volver a deseable.
    const [, kind] = screen.getAllByLabelText("Tipo");
    const [, second] = screen.getAllByLabelText("Peso") as HTMLInputElement[];
    await user.selectOptions(kind, "INDISPENSABLE");
    expect(second.value).toBe("3");
    await user.selectOptions(kind, "DESEABLE");
    expect(second.value).toBe("1");
    // Un peso puesto a mano se respeta aunque cambie el tipo.
    await user.selectOptions(screen.getAllByLabelText("Tipo")[0], "DESEABLE");
    expect((screen.getAllByLabelText("Peso")[0] as HTMLInputElement).value).toBe("5");
    await user.selectOptions(screen.getAllByLabelText("Tipo")[0], "INDISPENSABLE");
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
  it("llena el perfil con la propuesta de la IA y lo guarda marcado como originado con IA", async () => {
    const FILE_ID = "c0000000-0000-0000-0000-000000000001";
    const proposal = {
      ...makeProfile({ objective: "Pagar la nómina sin errores.", must_have: ["Dos años en nómina"] }),
      ambiguities: ["«Excel intermedio» no indica qué funciones"],
      truncated: true,
      source_file_id: FILE_ID,
      origin: "IA",
      notices: [],
    };
    const fetchMock = mockApi({
      [`GET ${PROFILE_URL}`]: { body: [] },
      [`GET /api/v1/vacancies/${VACANCY_ID}/files`]: {
        body: [makeFile(FILE_ID, "perfil analista.docx")],
      },
      [`POST /api/v1/vacancies/${VACANCY_ID}/profile-extractions`]: { body: proposal },
      [`POST ${PROFILE_URL}`]: { status: 201, body: makeProfile({ origin: "IA" }) },
    });
    const user = userEvent.setup();
    renderWorkspace();
    await user.click(
      await screen.findByRole("button", { name: "Usar un documento ya cargado o pegar texto" }),
    );
    // Sin documento ni texto no hay nada que leer.
    expect(screen.getByRole("button", { name: "Leer documento" }).hasAttribute("disabled")).toBe(true);
    await user.selectOptions(
      await screen.findByLabelText(/Documento de la vacante/),
      await screen.findByRole("option", { name: "perfil analista.docx" }),
    );
    await user.click(screen.getByRole("button", { name: "Leer documento" }));

    const status = await screen.findByRole("status");
    expect(status.textContent).toContain("todavía no se ha guardado");
    expect(status.textContent).toContain("solo se leyó el inicio");
    const extraction = fetchMock.mock.calls.find(([url]) => String(url).endsWith("/profile-extractions"));
    expect(JSON.parse(String(extraction?.[1]?.body))).toEqual({ file_id: FILE_ID });
    expect((screen.getByLabelText("Propósito del puesto") as HTMLTextAreaElement).value).toBe(
      "Pagar la nómina sin errores.",
    );
    expect(
      (screen.getByLabelText("Requisitos que no están claros (uno por línea)") as HTMLTextAreaElement).value,
    ).toContain("Excel intermedio");

    // La persona corrige y guarda: viaja el origen.
    await user.type(screen.getByLabelText("Requisitos indispensables (uno por línea)"), "\nExcel");
    await user.click(screen.getByRole("button", { name: "Guardar perfil" }));
    await screen.findByText(/Perfil guardado como versión 1/);
    const saved = fetchMock.mock.calls.find(
      ([url, init]) => String(url).endsWith("/profile-versions") && init?.method === "POST",
    );
    const body = JSON.parse(String(saved?.[1]?.body));
    expect(body.origin).toBe("IA");
    expect(body.source_file_id).toBe(FILE_ID);
    expect(body.must_have).toEqual(["Dos años en nómina", "Excel"]);
  });

  it("sube el formato de la empresa, llena los campos y lo guarda marcado como formato", async () => {
    const FILE_ID = "c0000000-0000-0000-0000-000000000002";
    const proposal = {
      ...EMPTY_PROFILE,
      position_name: "Analista de Nómina",
      area: "Recursos Humanos",
      document_date: "2026-10-05",
      objective: "Calcular y pagar la nómina.",
      education_levels: ["Licenciatura", "TSU"],
      must_have: ["Cálculo de nómina", "Cuotas IMSS"],
      skills: ["Atención al detalle"],
      functions: ["Calcular la nómina"],
      activities: [
        { description: "Registrar incidencias", frequency: "Diaria" },
        { description: "Calcular la nómina", frequency: "" },
      ],
      kpis: [{ name: "Nóminas a tiempo", goal: "100 %", formula: "A tiempo / total" }],
      truncated: false,
      source_file_id: FILE_ID,
      origin: "FORMATO",
      notices: ["El formato pide edad mínima 25. No se copió al perfil."],
    };
    const fetchMock = mockApi({
      [`GET ${PROFILE_URL}`]: { body: [] },
      [`POST /api/v1/vacancies/${VACANCY_ID}/files`]: {
        status: 201,
        body: { file: makeFile(FILE_ID, "SGC.F15.RH. Perfil de puesto.xlsx"), duplicates: [] },
      },
      [`POST /api/v1/vacancies/${VACANCY_ID}/profile-extractions`]: { body: proposal },
      [`POST ${PROFILE_URL}`]: { status: 201, body: makeProfile({ origin: "FORMATO" }) },
    });
    const user = userEvent.setup();
    renderWorkspace();
    const picker = await screen.findByLabelText("Formato del perfil");
    const file = new File(["libro"], "SGC.F15.RH. Perfil de puesto.xlsx");
    await user.upload(picker, file);

    const status = await screen.findByRole("status");
    expect(status.textContent).toContain("Se leyó el formato de la empresa");
    expect(status.textContent).toContain("todavía no se ha guardado");
    const upload = fetchMock.mock.calls.find(([url]) => String(url).includes("/files?"));
    expect(String(upload?.[0])).toContain("document_type=PERFIL_PUESTO");
    expect(within(screen.getByRole("list", { name: "Avisos de la lectura" })).getByText(/edad mínima 25/)).toBeTruthy();

    // Los campos del formato quedan llenos.
    expect((screen.getByLabelText("Nombre del puesto") as HTMLInputElement).value).toBe("Analista de Nómina");
    expect((screen.getByLabelText("Fecha de actualización") as HTMLInputElement).value).toBe("2026-10-05");
    const levels = within(screen.getByRole("group", { name: "Formación académica" }));
    expect((levels.getByLabelText("Licenciatura") as HTMLInputElement).checked).toBe(true);
    expect((levels.getByLabelText("Maestría") as HTMLInputElement).checked).toBe(false);
    expect((screen.getByLabelText("Actividad 1") as HTMLInputElement).value).toBe("Registrar incidencias");
    expect((screen.getByLabelText("Periodicidad de la actividad 1") as HTMLSelectElement).value).toBe("Diaria");
    expect((screen.getByLabelText("KPI 1") as HTMLInputElement).value).toBe("Nóminas a tiempo");

    // La persona corrige antes de guardar: marca un nivel, completa una periodicidad y quita el KPI.
    await user.click(levels.getByLabelText("Maestría"));
    await user.selectOptions(screen.getByLabelText("Periodicidad de la actividad 2"), "Semanal");
    await user.click(screen.getByRole("button", { name: "Agregar actividad" }));
    await user.click(screen.getByRole("button", { name: "Quitar fila 1 de indicadores" }));
    await user.click(screen.getByRole("button", { name: "Guardar perfil" }));
    await screen.findByText(/Perfil guardado como versión 1/);
    const saved = fetchMock.mock.calls.find(
      ([url, init]) => String(url).endsWith("/profile-versions") && init?.method === "POST",
    );
    const body = JSON.parse(String(saved?.[1]?.body));
    expect(body.origin).toBe("FORMATO");
    expect(body.source_file_id).toBe(FILE_ID);
    expect(body.position_name).toBe("Analista de Nómina");
    expect(body.education_levels).toEqual(["Licenciatura", "TSU", "Maestría"]);
    // La fila vacía que se agregó no viaja.
    expect(body.activities).toEqual([
      { description: "Registrar incidencias", frequency: "Diaria" },
      { description: "Calcular la nómina", frequency: "Semanal" },
    ]);
    expect(body.kpis).toEqual([]);
    expect(body.must_have).toEqual(["Cálculo de nómina", "Cuotas IMSS"]);
  });

  it("no sube un archivo que no es un formato aceptado para el perfil", async () => {
    const fetchMock = mockApi({ [`GET ${PROFILE_URL}`]: { body: [] } });
    const user = userEvent.setup({ applyAccept: false });
    renderWorkspace();
    await user.upload(await screen.findByLabelText("Formato del perfil"), new File(["x"], "perfil.zip"));
    expect((await screen.findByRole("alert")).textContent).toContain("Formato no permitido");
    expect(fetchMock.mock.calls.some(([, init]) => init?.method === "POST")).toBe(false);
  });

  it("si la IA no puede leer el perfil, muestra el motivo y no toca el formulario", async () => {
    const fetchMock = mockApi({
      [`GET ${PROFILE_URL}`]: { body: [makeProfile()] },
      [`GET /api/v1/vacancies/${VACANCY_ID}/files`]: { body: [] },
      [`POST /api/v1/vacancies/${VACANCY_ID}/profile-extractions`]: problem(
        422,
        "validacion",
        "Esta operación no tiene un modelo asignado.",
      ),
    });
    const user = userEvent.setup();
    renderWorkspace();
    await user.click(
      await screen.findByRole("button", { name: "Usar un documento ya cargado o pegar texto" }),
    );
    await user.type(screen.getByLabelText("Texto del perfil"), "Perfil de analista de nómina");
    await user.click(screen.getByRole("button", { name: "Leer documento" }));
    expect((await screen.findByRole("alert")).textContent).toContain("modelo asignado");
    const extraction = fetchMock.mock.calls.find(([url]) => String(url).endsWith("/profile-extractions"));
    expect(JSON.parse(String(extraction?.[1]?.body))).toEqual({ text: "Perfil de analista de nómina" });
    expect((screen.getByLabelText("Propósito del puesto") as HTMLTextAreaElement).value).toBe(
      "Calcular la nómina.",
    );
  });

  it("aplica al borrador la redacción que propone la IA y solo cambia al guardar", async () => {
    const levels = ["Sin evidencia", "Menos de un año", "Uno a dos años", "Dos a cuatro", "Más de cuatro"];
    const fetchMock = mockApi({
      [`GET ${PROMPTS_URL}`]: { body: [makePrompt()] },
      [`POST /api/v1/prompts/${PROMPT_ID}/criteria-proposals`]: {
        body: {
          suggestions: [
            {
              id: "70000000-0000-0000-0000-000000000001",
              code: "C1",
              name: "Experiencia en nómina",
              description: "Busca puestos de nómina con fechas.",
              levels,
            },
          ],
          observations: ["«Excel intermedio» es ambiguo"],
        },
      },
      [`PUT /api/v1/prompts/${PROMPT_ID}`]: { body: makePrompt({ revision: 2 }) },
    });
    const user = userEvent.setup();
    renderWorkspace();
    await user.click(screen.getByRole("button", { name: "Prompt de evaluación" }));
    await user.click(await screen.findByRole("button", { name: "Proponer mejoras con IA" }));

    const panel = await screen.findByRole("region", { name: "Mejoras propuestas por la IA" });
    expect(within(panel).getByText("«Excel intermedio» es ambiguo")).toBeTruthy();
    expect(within(panel).getByText("C1. Experiencia en nómina")).toBeTruthy();
    expect(fetchMock.mock.calls.some(([, init]) => init?.method === "PUT")).toBe(false);
    await user.click(within(panel).getByRole("button", { name: "Aplicar a C1" }));

    expect((await screen.findByRole("status")).textContent).toContain("Guardar cambios");
    expect(screen.queryByRole("region", { name: "Mejoras propuestas por la IA" })).toBeNull();
    expect((screen.getByLabelText("Descripción del criterio C1") as HTMLInputElement).value).toBe(
      "Busca puestos de nómina con fechas.",
    );
    await user.click(screen.getByRole("button", { name: "Guardar cambios" }));
    await screen.findByText(/Cambios guardados/);
    const { body } = sent(fetchMock, "PUT");
    expect(body.criteria).toHaveLength(1);
    expect(body.criteria[0].name).toBe("Experiencia en nómina");
    expect(body.criteria[0].weight).toBe("3.00");
    expect(body.criteria[0].levels).toEqual(levels);
  });

  it("avisa de los cambios sin guardar y «Enviar a revisión» los guarda antes de enviar", async () => {
    const fetchMock = mockApi({
      [`GET ${PROMPTS_URL}`]: { body: [makePrompt()] },
      [`PUT /api/v1/prompts/${PROMPT_ID}`]: { body: makePrompt({ revision: 2, pass_threshold: "70.00" }) },
      [`POST /api/v1/prompts/${PROMPT_ID}/submit`]: {
        body: makePrompt({ revision: 3, pass_threshold: "70.00", status: "EN_REVISION" }),
      },
    });
    const user = userEvent.setup();
    renderWorkspace();
    await user.click(screen.getByRole("button", { name: "Prompt de evaluación" }));
    await screen.findByRole("heading", { name: "Versión 1" });
    // Sin cambios no hay aviso.
    expect(screen.queryByRole("note")).toBeNull();
    const threshold = screen.getByLabelText(/Umbral/);
    await user.clear(threshold);
    await user.type(threshold, "70.00");
    expect(screen.getByRole("note").textContent).toContain("Tienes cambios sin guardar");
    // Con cambios pendientes no se pueden pedir mejoras a la IA: primero hay que guardar.
    const propose = screen.getByRole("button", { name: "Proponer mejoras con IA" }) as HTMLButtonElement;
    expect(propose.disabled).toBe(true);
    expect(screen.getByText(/Primero guarda los cambios: la IA trabaja sobre lo guardado/)).toBeTruthy();
    // La barra al pie trae su propio botón para guardar sin subir por la pantalla.
    expect(within(screen.getByRole("note")).getByRole("button", { name: "Guardar ahora" })).toBeTruthy();

    await user.click(screen.getByRole("button", { name: "Enviar a revisión" }));
    expect((await screen.findByRole("status")).textContent).toContain(
      "Cambios guardados. El borrador pasó a revisión.",
    );
    // Primero se guarda lo que estaba en pantalla y después se envía esa misma versión.
    const writes = fetchMock.mock.calls.filter(([, init]) => init?.method === "PUT" || init?.method === "POST");
    expect(writes.map(([url, init]) => `${init?.method} ${String(url).split("/").pop()}`)).toEqual([
      `PUT ${PROMPT_ID}`,
      "POST submit",
    ]);
    expect(JSON.parse(String(writes[0][1]?.body)).pass_threshold).toBe("70.00");
    expect(JSON.parse(String(writes[1][1]?.body))).toEqual({ revision: 2 });
  });

  it("la barra de cambios sin guardar guarda sin subir por la pantalla", async () => {
    const fetchMock = mockApi({
      [`GET ${PROMPTS_URL}`]: { body: [makePrompt()] },
      [`PUT /api/v1/prompts/${PROMPT_ID}`]: { body: makePrompt({ revision: 2, pass_threshold: "70.00" }) },
    });
    const user = userEvent.setup();
    renderWorkspace();
    await user.click(screen.getByRole("button", { name: "Prompt de evaluación" }));
    await screen.findByRole("heading", { name: "Versión 1" });
    const threshold = screen.getByLabelText(/Umbral/);
    await user.clear(threshold);
    await user.type(threshold, "70.00");
    await user.click(screen.getByRole("button", { name: "Guardar ahora" }));
    await screen.findByText(/Cambios guardados/);
    expect(sent(fetchMock, "PUT").body.pass_threshold).toBe("70.00");
    expect(fetchMock.mock.calls.some(([, init]) => init?.method === "POST")).toBe(false);
  });

  it("si se quitan criterios, las mejoras de la IA siguen a su criterio y no a su número", async () => {
    const criterion = (n: number, name: string) => ({
      id: `70000000-0000-0000-0000-00000000000${n}`,
      code: `C${n}`,
      name,
      description: "",
      kind: "INDISPENSABLE" as const,
      weight: "3.00",
      levels: LEVELS,
      origin: "PERFIL" as const,
    });
    const criteria = [criterion(1, "Experiencia en nómina"), criterion(2, "Excel"), criterion(3, "Informes")];
    const suggestion = (n: number, description: string) => ({
      id: criteria[n - 1].id,
      code: `C${n}`,
      name: criteria[n - 1].name,
      description,
      levels: LEVELS,
    });
    mockApi({
      [`GET ${PROMPTS_URL}`]: { body: [makePrompt({ criteria })] },
      [`POST /api/v1/prompts/${PROMPT_ID}/criteria-proposals`]: {
        body: {
          suggestions: [suggestion(1, "Busca nómina."), suggestion(2, "Busca Excel."), suggestion(3, "Busca informes.")],
          observations: [],
        },
      },
    });
    const user = userEvent.setup();
    renderWorkspace();
    await user.click(screen.getByRole("button", { name: "Prompt de evaluación" }));
    await user.click(await screen.findByRole("button", { name: "Proponer mejoras con IA" }));
    const panel = within(await screen.findByRole("region", { name: "Mejoras propuestas por la IA" }));
    expect(panel.getByRole("button", { name: "Aplicar a C3" })).toBeTruthy();

    // Al quitar el segundo criterio, «Informes» pasa a ser el C2 en la rúbrica…
    await user.click(screen.getByRole("button", { name: "Quitar criterio C2" }));
    // …y su mejora lo sigue: ya no dice C3, y la del criterio quitado no se muestra.
    expect(panel.getByText("C2. Informes")).toBeTruthy();
    expect(panel.queryByRole("button", { name: "Aplicar a C3" })).toBeNull();
    expect(panel.queryByText("Busca Excel.")).toBeNull();
    expect(panel.getByText("No se muestra 1 mejora porque era para un criterio que ya quitaste.")).toBeTruthy();

    await user.click(panel.getByRole("button", { name: "Aplicar a C2" }));
    expect((screen.getByLabelText("Descripción del criterio C2") as HTMLInputElement).value).toBe("Busca informes.");
    expect((screen.getByLabelText("Descripción del criterio C1") as HTMLInputElement).value).toBe("");
    // Queda solo la mejora del primer criterio; la del que se quitó no vuelve a aparecer.
    expect(panel.getByRole("button", { name: "Aplicar a C1" })).toBeTruthy();
    expect(panel.queryByText(/ya quitaste/)).toBeNull();
  });
});
