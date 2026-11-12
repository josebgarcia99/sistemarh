import { cleanup, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { Assessment, AssessmentList } from "@/lib/api/assessments";
import type { ApplicationDetail } from "@/lib/api/recruitment";
import { makeUser, mockApi, renderApp } from "@/test/helpers";
import { AssessmentsSection } from "./assessments-section";
import { DossierSection } from "./dossier-section";

const LIST_URL = "/api/v1/applications/a1/assessments";
const FILES_URL = "/api/v1/vacancies/v1/files";
const file = (id: string, name: string, type: string) => ({
  id,
  vacancy_id: "v1",
  document_type: type,
  sensitive: true,
  original_name: name,
  content_type: null,
  size_bytes: 10,
  sha256: null,
  malware_scan: null,
  encrypted: true,
  uploaded_by: "u1",
  uploaded_by_name: "x",
  created_at: "2026-11-11T18:00:00Z",
});

function make(kind: Assessment["kind"], overrides: Partial<Assessment> = {}): Assessment {
  return {
    id: `e-${kind}`,
    application_id: "a1",
    kind,
    status: "PENDIENTE",
    statuses: ["PENDIENTE", "REALIZADA", "VALIDADA", "EN_PROCESO", "COMPLETADO"],
    event_date: null,
    file_id: null,
    data: {},
    score: null,
    ai_summary: null,
    ai_summary_at: null,
    form: null,
    version: 1,
    updated_at: "2026-11-11T18:00:00Z",
    updated_by_name: "Reclutadora de Prueba",
    ...overrides,
  };
}
const list = (items: Assessment[], extra: Partial<AssessmentList> = {}): AssessmentList => ({
  items,
  restricted: [],
  writable: ["ENTREVISTA", "PRUEBA_TECNICA", "PSICOMETRIA", "ESTUDIO_SOCIOECONOMICO"],
  ...extra,
});
const sent = (fetchMock: ReturnType<typeof mockApi>, method: string, ending: string) => {
  const call = fetchMock.mock.calls.find(([url, init]) => init?.method === method && String(url).endsWith(ending));
  return JSON.parse(String(call?.[1]?.body ?? "null"));
};
const renderSection = () =>
  renderApp(<AssessmentsSection applicationId="a1" vacancyId="v1" active />, { session: makeUser() });

const FIELD = {
  required: false,
  options: [] as string[],
  minimum: null,
  maximum: null,
  columns: [] as string[],
  manual_only: false,
};

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("AssessmentsSection", () => {
  it("registra una prueba técnica, captura la rúbrica y muestra la calificación calculada", async () => {
    let items: Assessment[] = [];
    const created = make("PRUEBA_TECNICA", { data: { test_type: "Excel", rubric: [] } });
    const graded = { ...created, version: 2, status: "REALIZADA", score: "75.00", data: { test_type: "Excel", passed: true, rubric: [{ criterion: "Fórmulas", max_points: "4", points: "3" }] } };
    const fetchMock = mockApi({
      [`GET ${LIST_URL}`]: () => ({ body: list(items) }),
      [`GET ${FILES_URL}`]: { body: [] },
      [`POST ${LIST_URL}`]: () => {
        items = [created];
        return { status: 201, body: created };
      },
      ["PUT /api/v1/assessments/e-PRUEBA_TECNICA"]: () => {
        items = [graded];
        return { body: graded };
      },
    });
    const user = userEvent.setup();
    renderSection();
    await user.click(await screen.findByRole("button", { name: "Registrar evaluación" }));
    await user.selectOptions(screen.getByLabelText("Tipo de evaluación"), "PRUEBA_TECNICA");
    await user.type(screen.getByLabelText("Tipo de prueba"), "Excel");
    await user.click(screen.getByRole("button", { name: "Registrar" }));
    expect(sent(fetchMock, "POST", LIST_URL)).toEqual({ kind: "PRUEBA_TECNICA", data: { test_type: "Excel" }, template_id: null });

    await user.click(await screen.findByRole("button", { name: "Agregar criterio" }));
    await user.type(screen.getByLabelText("Criterio 1"), "Fórmulas");
    await user.type(screen.getByLabelText("Puntos obtenidos del criterio 1"), "3");
    await user.type(screen.getByLabelText("Puntos posibles del criterio 1"), "4");
    await user.selectOptions(screen.getByLabelText("Estado"), "REALIZADA");
    await user.click(screen.getByRole("button", { name: "Guardar" }));

    expect(await screen.findByText(/Calificación calculada por el sistema/)).toBeTruthy();
    expect(screen.getByText(/alcanza el mínimo/)).toBeTruthy();
    const body = sent(fetchMock, "PUT", "/e-PRUEBA_TECNICA");
    expect(body.status).toBe("REALIZADA");
    expect(body.version).toBe(1);
    expect(body.data.rubric).toEqual([{ criterion: "Fórmulas", max_points: "4", points: "3" }]);
  });

  it("en el estudio, lo que lee la IA entra sin verificar y la persona lo marca", async () => {
    const study = make("ESTUDIO_SOCIOECONOMICO", {
      status: "EN_PROCESO",
      form: [{ title: "Datos de la visita", fields: [
        { ...FIELD, id: "visita", label: "Fecha de la visita", type: "FECHA", required: true },
        { ...FIELD, id: "domicilio", label: "Domicilio declarado", type: "PARRAFO" },
      ] }],
    });
    const fetchMock = mockApi({
      [`GET ${LIST_URL}`]: { body: list([study]) },
      [`GET ${FILES_URL}`]: { body: [file("f9", "estudio escaneado.pdf", "ESTUDIO_SOCIOECONOMICO"), file("f1", "cv.pdf", "CV")] },
      ["POST /api/v1/assessments/e-ESTUDIO_SOCIOECONOMICO/digitization"]: {
        body: { values: { visita: "2026-11-10", domicilio: "Calle Inventada 123" }, illegible: ["Persona que atendió"], missing: [] },
      },
      ["PUT /api/v1/assessments/e-ESTUDIO_SOCIOECONOMICO"]: { body: { ...study, version: 2 } },
    });
    const user = userEvent.setup();
    renderSection();
    await user.click(await screen.findByRole("button", { name: /Estudio socioeconómico/ }));
    expect(screen.getByText(/El sistema no lo puntúa/)).toBeTruthy();
    // Solo se ofrecen documentos del tipo que corresponde.
    const picker = await screen.findByLabelText("Formulario escaneado");
    await within(picker).findByRole("option", { name: "estudio escaneado.pdf" });
    expect(within(picker).queryByRole("option", { name: "cv.pdf" })).toBeNull();
    await user.selectOptions(picker, "f9");
    await user.click(screen.getByRole("button", { name: "Leer el formulario escaneado con IA" }));

    expect((await screen.findByRole("status")).textContent).toContain("todavía no se ha guardado");
    expect(screen.getByText("No se pudo leer: Persona que atendió.")).toBeTruthy();
    expect((screen.getByLabelText("Fecha de la visita (obligatorio)") as HTMLInputElement).value).toBe("2026-11-10");
    expect(screen.getAllByText("Leído por la IA")).toHaveLength(2);
    const verified = screen.getByRole("checkbox", { name: "Fecha de la visita: verificado" }) as HTMLInputElement;
    expect(verified.checked).toBe(false);
    await user.click(verified);
    await user.click(screen.getByRole("button", { name: "Guardar" }));
    await screen.findByText("Evaluación guardada.");
    expect(sent(fetchMock, "PUT", "/e-ESTUDIO_SOCIOECONOMICO").data.answers).toEqual({
      visita: { value: "2026-11-10", verified: true, source: "IA" },
      domicilio: { value: "Calle Inventada 123", verified: false, source: "IA" },
    });
  });

  it("captura las tablas del formato y marca lo que solo anota una persona", async () => {
    const study = make("ESTUDIO_SOCIOECONOMICO", {
      status: "EN_PROCESO",
      data: { answers: { familia: { value: [["Familiar Ficticio", "52", "Madre"]], verified: false, source: "IA" } } },
      form: [
        { title: "Datos familiares", fields: [
          { ...FIELD, id: "familia", label: "Datos familiares", type: "TABLA", columns: ["Nombre", "Edad", "Parentesco"] },
        ] },
        { title: "Dictamen", fields: [
          { ...FIELD, id: "dictamen", label: "Dictamen (observaciones)", type: "OBSERVACION", manual_only: true },
        ] },
      ],
    });
    const fetchMock = mockApi({
      [`GET ${LIST_URL}`]: { body: list([study]) },
      [`GET ${FILES_URL}`]: { body: [] },
      ["PUT /api/v1/assessments/e-ESTUDIO_SOCIOECONOMICO"]: { body: { ...study, version: 2 } },
    });
    const user = userEvent.setup();
    renderSection();
    await user.click(await screen.findByRole("button", { name: /Estudio socioeconómico/ }));
    const table = await screen.findByRole("table", { name: "Datos familiares" });
    expect(within(table).getAllByRole("columnheader").map((cell) => cell.textContent)).toEqual(["Nombre", "Edad", "Parentesco"]);
    expect((screen.getByLabelText("Datos familiares, fila 1: Nombre") as HTMLInputElement).value).toBe("Familiar Ficticio");
    expect(screen.getByText("Lo anota quien aplicó el estudio. La IA no lo llena.")).toBeTruthy();

    // Se agrega una fila, se quita la primera y se anota el dictamen.
    await user.click(screen.getByRole("button", { name: "Agregar fila a Datos familiares" }));
    await user.type(screen.getByLabelText("Datos familiares, fila 2: Nombre"), "Hermano Ficticio");
    await user.type(screen.getByLabelText("Datos familiares, fila 2: Parentesco"), "Hermano");
    await user.click(screen.getByRole("button", { name: "Quitar la fila 1 de Datos familiares" }));
    await user.type(screen.getByLabelText("Dictamen (observaciones)"), "Dictamen del aplicador.");
    await user.click(screen.getByRole("button", { name: "Guardar" }));
    await screen.findByText("Evaluación guardada.");
    expect(sent(fetchMock, "PUT", "/e-ESTUDIO_SOCIOECONOMICO").data.answers).toEqual({
      familia: { value: [["Hermano Ficticio", "", "Hermano"]], verified: false, source: "MANUAL" },
      dictamen: { value: "Dictamen del aplicador.", verified: false, source: "MANUAL" },
    });
  });

  it("avisa de lo que requiere permiso adicional y muestra el resumen de IA como tal", async () => {
    const interview = make("ENTREVISTA", {
      status: "REALIZADA",
      data: { interviewer: "Gerente Ficticio", conclusion: "Recomiendo continuar." },
      ai_summary: { resumen: "Describe cómo corrige errores.", competencias_observadas: ["Análisis"], evidencias: [] },
    });
    mockApi({ [`GET ${LIST_URL}`]: { body: list([interview], { restricted: ["PSICOMETRIA"], writable: [] }) } });
    const user = userEvent.setup();
    renderSection();
    expect(await screen.findByText(/prueba psicométrica, que requiere un permiso adicional/)).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Registrar evaluación" })).toBeNull();
    await user.click(screen.getByRole("button", { name: /Entrevista con gerente · Gerente Ficticio/ }));
    const summary = screen.getByRole("region", { name: "Resumen de la IA" });
    expect(within(summary).getByText("Competencias observadas")).toBeTruthy();
    expect(within(summary).getByText(/No es un diagnóstico ni una recomendación/)).toBeTruthy();
    expect((screen.getByLabelText("Conclusión de quien entrevistó") as HTMLTextAreaElement).readOnly).toBe(true);
    expect(screen.queryByRole("button", { name: /Guardar|Organizar con IA/ })).toBeNull();
  });
});

describe("DossierSection", () => {
  const stage = (position: number, name: string, kind: string) => ({ id: `s${position}`, position, name, kind, is_optional: false });
  const detail = {
    application: { id: "a1", candidate_id: "k1", full_name: "Ana Pérez", email: null, phone: null, stage_id: "s3", status: "ACTIVA", ai_classification: "ACEPTADO_IA", ai_score: "87.50", cv_file_id: "f1", due_at: null, created_at: "2026-11-11T18:00:00Z", updated_at: "2026-11-11T18:00:00Z" },
    campaign: { id: "c1", number: 1, name: "Convocatoria 1", status: "ABIERTA", opened_at: "2026-11-11T18:00:00Z", closed_at: null },
    pipeline: { id: "p1", version_number: 1, created_at: "2026-11-11T18:00:00Z", stages: [stage(1, "Evaluación de CV", "EVALUACION_CV"), stage(2, "Pruebas psicométricas", "PSICOMETRIA"), stage(3, "Entrevista con gerente", "ENTREVISTA"), stage(4, "Estudio socioeconómico", "ESTUDIO_SOCIOECONOMICO")] },
    movements: [{ id: "m1", kind: "OMISION", occurred_at: "2026-11-11T18:00:00Z", actor_name: "x", from_stage: "Pruebas psicométricas", to_stage: null, note: "Ya la tenía", due_at: null, mass: false }],
    evaluation: { classification: "ACEPTADO_IA", score: "87.50", file_name: "cv ana.pdf", result: {}, extraction: {} },
    tenure: null,
  } as ApplicationDetail;

  it("muestra cada etapa con sus fuentes y genera una síntesis sin puntuación", async () => {
    let created = false;
    const synthesis = {
      id: "x1",
      created_at: "2026-11-11T19:00:00Z",
      created_by_name: "Reclutadora de Prueba",
      result: { hechos_documentados: ["Analista en Uno SA (CV)"], discrepancias_verificables: ["CV: 2 años; llamada: 3 años"], informacion_pendiente: [] },
      sources: ["CV", "1 entrevistas"],
      includes_psychometrics: false,
    };
    const fetchMock = mockApi({
      ["GET /api/v1/applications/a1/calls"]: { body: [] },
      [`GET ${LIST_URL}`]: { body: list([make("ENTREVISTA", { status: "REALIZADA", data: { interviewer: "G" } })], { restricted: ["PSICOMETRIA"] }) },
      ["GET /api/v1/applications/a1/syntheses"]: () => ({ body: { latest: created ? synthesis : null, total: created ? 1 : 0, hidden: true } }),
      ["POST /api/v1/applications/a1/syntheses"]: () => {
        created = true;
        return { status: 201, body: synthesis };
      },
    });
    const user = userEvent.setup();
    renderApp(<DossierSection detail={detail} canEdit />, { session: makeUser() });
    const stages = within(screen.getByRole("list", { name: "Etapas y fuentes" }));
    expect(await stages.findByText(/Entrevista con gerente: Realizada/)).toBeTruthy();
    const rows = stages.getAllByRole("listitem").filter((item) => item.textContent?.match(/^\d\./));
    expect(rows[0].textContent).toContain("Cubierta");
    expect(rows[0].textContent).toContain("CV «cv ana.pdf»");
    expect(rows[1].textContent).toContain("Omitida");
    expect(rows[1].textContent).toContain("requiere un permiso adicional");
    expect(rows[2].textContent).toContain("Etapa actual");
    expect(rows[3].textContent).toContain("Por venir");
    expect(screen.getByText(/síntesis más reciente que incluye psicometría/)).toBeTruthy();

    await user.click(screen.getByRole("button", { name: "Generar síntesis" }));
    const panel = await screen.findByRole("region", { name: "Síntesis" });
    expect(within(panel).getByText("Hechos documentados")).toBeTruthy();
    expect(within(panel).getByText("Diferencias por aclarar entre fuentes")).toBeTruthy();
    expect(within(panel).queryByText("Información pendiente")).toBeNull();
    expect(within(panel).getByText(/fuentes: CV, 1 entrevistas/)).toBeTruthy();
    expect(fetchMock.mock.calls.some(([, init]) => init?.method === "POST")).toBe(true);
  });
});
