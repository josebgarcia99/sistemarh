import { cleanup, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { Application, ApplicationDetail, Board } from "@/lib/api/recruitment";
import { makeUser, mockApi, problem, renderApp } from "@/test/helpers";
import { CandidatesWorkspace } from "./candidates-workspace";

const VACANCY_ID = "10000000-0000-0000-0000-000000000001";
const BOARD_URL = `/api/v1/vacancies/${VACANCY_ID}/applications`;
const MOVES_URL = `/api/v1/vacancies/${VACANCY_ID}/application-moves`;
const STAGES = ["Evaluación de CV", "Revisión local RH", "Llamada telefónica", "Prueba técnica"].map(
  (name, index) => ({
    id: `s${index + 1}`,
    position: index + 1,
    name,
    kind: "OTRA",
    is_optional: index === 3,
  }),
);
const CAMPAIGN = {
  id: "c1",
  number: 1,
  name: "Convocatoria 1",
  status: "ABIERTA" as const,
  opened_at: "2026-11-11T18:00:00Z",
  closed_at: null,
};
const PIPELINE = { id: "p1", version_number: 1, created_at: "2026-11-11T18:00:00Z", stages: STAGES };

function makeApplication(overrides: Partial<Application> = {}): Application {
  return {
    id: "a1",
    candidate_id: "k1",
    full_name: "Ana Pérez",
    email: "ana@ejemplo.test",
    phone: null,
    stage_id: "s2",
    status: "ACTIVA",
    outcome: "EN_PROCESO",
    ai_classification: "ACEPTADO_IA",
    ai_score: "87.50",
    cv_file_id: "f1",
    due_at: null,
    created_at: "2026-11-11T18:00:00Z",
    updated_at: "2026-11-11T18:00:00Z",
    ...overrides,
  };
}
const BETO = makeApplication({
  id: "a2",
  candidate_id: "k2",
  full_name: "Beto López",
  ai_classification: "RECHAZADO_IA",
  ai_score: "25.00",
});

function makeBoard(overrides: Partial<Board> = {}): Board {
  return {
    campaigns: [CAMPAIGN],
    campaign: CAMPAIGN,
    pipeline: PIPELINE,
    applications: [makeApplication(), BETO],
    positions: 2,
    hires: 0,
    ...overrides,
  };
}

function makeDetail(overrides: Partial<ApplicationDetail> = {}): ApplicationDetail {
  return {
    application: makeApplication(),
    campaign: CAMPAIGN,
    pipeline: PIPELINE,
    movements: [
      { id: "m1", kind: "ALTA", occurred_at: "2026-11-11T18:00:00Z", actor_name: null, from_stage: null, to_stage: "Evaluación de CV", note: "Clasificación inicial de la IA: aceptado.", due_at: null, mass: false },
      { id: "m2", kind: "AVANCE", occurred_at: "2026-11-11T18:00:01Z", actor_name: "Reclutadora de Prueba", from_stage: "Evaluación de CV", to_stage: "Revisión local RH", note: null, due_at: null, mass: false },
    ],
    evaluation: {
      classification: "ACEPTADO_IA",
      score: "87.50",
      file_name: "cv ana.pdf",
      result: { criterios: [{ id: "C1", nivel: 4, sin_evidencia: false, evidencia: "5 años en nómina", justificacion: "Cumple" }] },
      extraction: { habilidades: ["Excel"], estudios: [{ titulo: "Contaduría", institucion: "UNAM", periodo: "2015" }] },
    },
    tenure: {
      jobs: [{ title: "Analista de nómina", company: "Uno SA", start: "2020-01", end: "2022-06", current: false, months: 30, approximate: false }],
      average_months: 30,
      median_months: 30,
      total_months: 30,
      overlaps: 0,
      incomplete: 0,
    },
    outcomes: [],
    ...overrides,
  };
}

function renderWorkspace(props: { canEdit?: boolean; canManage?: boolean } = {}) {
  return renderApp(
    <CandidatesWorkspace
      vacancyId={VACANCY_ID}
      vacancyName="Analista de Nómina"
      canEdit={props.canEdit ?? true}
      canManage={props.canManage ?? true}
      onBack={() => {}}
    />,
    { session: makeUser() },
  );
}
const body = (fetchMock: ReturnType<typeof mockApi>, ending: string) => {
  const call = fetchMock.mock.calls.find(
    ([url, init]) => String(url).endsWith(ending) && init?.method && init.method !== "GET",
  );
  return JSON.parse(String(call?.[1]?.body ?? "null"));
};

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("CandidatesWorkspace", () => {
  it("muestra a los candidatos por etapa con la clasificación inicial de la IA", async () => {
    mockApi({ [`GET ${BOARD_URL}`]: { body: makeBoard() } });
    const user = userEvent.setup();
    renderWorkspace();
    const rows = within(await screen.findByRole("list", { name: "Candidatos" })).getAllByRole("listitem");
    expect(rows).toHaveLength(2);
    expect(rows[0].textContent).toContain("Aceptado por IA · 87.5");
    expect(rows[1].textContent).toContain("Rechazado por IA · 25");
    expect(screen.getByRole("button", { name: "Revisión local RH (2)" })).toBeTruthy();
    await user.click(screen.getByRole("button", { name: "Llamada telefónica (0)" }));
    expect(screen.getByText("No hay candidatos en esta etapa.")).toBeTruthy();
  });

  it("mueve a los seleccionados y muestra el motivo cuando el servidor lo exige", async () => {
    let attempts = 0;
    const fetchMock = mockApi({
      [`GET ${BOARD_URL}`]: { body: makeBoard() },
      [`POST ${MOVES_URL}`]: () => {
        attempts += 1;
        return attempts === 1
          ? problem(422, "validacion", "Escribe el motivo de tu decisión de avanzarla.")
          : { body: [] };
      },
    });
    const user = userEvent.setup();
    renderWorkspace();
    await user.click(await screen.findByRole("checkbox", { name: "Seleccionar a Beto López" }));
    await user.click(screen.getByRole("button", { name: "Mover de etapa" }));
    const dialog = screen.getByRole("dialog");
    await user.selectOptions(within(dialog).getByLabelText("Etapa de destino"), "s3");
    await user.click(within(dialog).getByRole("button", { name: "Mover" }));
    expect((await within(dialog).findByRole("alert")).textContent).toContain("motivo de tu decisión");

    await user.type(within(dialog).getByLabelText("Motivo"), "Tiene experiencia que la IA no vio");
    await user.click(within(dialog).getByRole("button", { name: "Mover" }));
    expect((await screen.findByRole("status")).textContent).toContain("Candidatos movidos");
    expect(screen.queryByRole("dialog")).toBeNull();
    const last = fetchMock.mock.calls.filter(([, init]) => init?.method === "POST").at(-1);
    expect(JSON.parse(String(last?.[1]?.body))).toEqual({
      application_ids: ["a2"],
      to_stage_id: "s3",
      note: "Tiene experiencia que la IA no vio",
    });
  });

  it("agrega un candidato a mano y cierra la convocatoria", async () => {
    const fetchMock = mockApi({
      [`GET ${BOARD_URL}`]: { body: makeBoard() },
      [`POST ${BOARD_URL}`]: { status: 201, body: makeDetail() },
      ["POST /api/v1/campaigns/c1/close"]: { body: { ...CAMPAIGN, status: "CERRADA" } },
    });
    const user = userEvent.setup();
    renderWorkspace();
    await user.click(await screen.findByRole("button", { name: "Agregar candidato" }));
    const dialog = screen.getByRole("dialog");
    await user.type(within(dialog).getByLabelText("Nombre completo"), "Carla Ruiz");
    await user.type(within(dialog).getByLabelText("Correo (opcional)"), "carla@ejemplo.test");
    await user.click(within(dialog).getByRole("button", { name: "Agregar" }));
    expect((await screen.findByRole("status")).textContent).toContain("Candidato agregado");
    expect(body(fetchMock, "/applications")).toEqual({
      full_name: "Carla Ruiz",
      email: "carla@ejemplo.test",
      phone: null,
    });
    await user.click(screen.getByRole("button", { name: "Cerrar convocatoria" }));
    expect((await screen.findByRole("status")).textContent).toContain("Convocatoria cerrada");
  });

  it("una convocatoria cerrada o un acceso de lectura no permiten operar", async () => {
    const closed = { ...CAMPAIGN, status: "CERRADA" as const };
    mockApi({ [`GET ${BOARD_URL}`]: { body: makeBoard({ campaign: closed, campaigns: [closed] }) } });
    renderWorkspace({ canEdit: false, canManage: false });
    expect(await screen.findByText(/ya no admite movimientos/)).toBeTruthy();
    expect(screen.queryByRole("checkbox")).toBeNull();
    expect(screen.queryByRole("button", { name: /Agregar|Cerrar convocatoria|Abrir convocatoria/ })).toBeNull();
  });

  it("abre el expediente con historial, evaluación y permanencia", async () => {
    mockApi({
      [`GET ${BOARD_URL}`]: { body: makeBoard() },
      ["GET /api/v1/applications/a1"]: { body: makeDetail() },
      ["GET /api/v1/applications/a1/calls"]: { body: [] },
      ["GET /api/v1/applications/a1/assessments"]: { body: { items: [], restricted: [], writable: [] } },
      ["GET /api/v1/applications/a1/syntheses"]: { body: { latest: null, total: 0, hidden: false } },
    });
    const user = userEvent.setup();
    renderWorkspace();
    await user.click(await screen.findByRole("button", { name: "Ana Pérez" }));

    expect(await screen.findByRole("heading", { name: "Ana Pérez" })).toBeTruthy();
    const history = within(screen.getByRole("list", { name: "Historial de movimientos" })).getAllByRole("listitem");
    // Lo más reciente primero; lo que hizo el sistema se indica como tal.
    expect(history[0].textContent).toContain("Avance: Revisión local RH");
    expect(history[0].textContent).toContain("Reclutadora de Prueba");
    expect(history[1].textContent).toContain("Sistema");
    expect(screen.getByText(/Aceptado por IA · 87.5 de 100/)).toBeTruthy();
    const jobs = within(screen.getByRole("list", { name: "Experiencia" })).getAllByRole("listitem");
    expect(jobs[0].textContent).toContain("2 años 6 meses");
    expect(screen.getByText(/una permanencia breve no es motivo de rechazo/)).toBeTruthy();
    expect(screen.getByRole("link", { name: "Descargar CV" }).getAttribute("href")).toBe(
      "/api/v1/files/f1/download",
    );
    expect(await screen.findByText("Todavía no hay llamadas registradas.")).toBeTruthy();

    expect(within(screen.getByRole("region", { name: "Resultado final" })).getByText(/En proceso/)).toBeTruthy();
  });

  it("registra una contratación con fecha de incorporación y permite reabrir el proceso", async () => {
    const hired = makeDetail({
      application: makeApplication({ status: "CONTRATADA", outcome: "CONTRATADO" }),
      outcomes: [
        {
          id: "o1",
          outcome: "CONTRATADO",
          reason: null,
          notes: "Acepta la oferta.",
          start_date: "2026-12-01",
          recorded_at: "2026-11-13T18:00:00Z",
          recorded_by_name: "Reclutadora de Prueba",
          voided_at: null,
          voided_by_name: null,
          void_reason: null,
        },
      ],
    });
    const reopened = makeDetail({
      outcomes: [
        { ...hired.outcomes[0], voided_at: "2026-11-14T18:00:00Z", voided_by_name: "Reclutadora de Prueba", void_reason: "No se presentó" },
      ],
    });
    let current = makeDetail();
    const fetchMock = mockApi({
      [`GET ${BOARD_URL}`]: { body: makeBoard({ hires: 1 }) },
      ["GET /api/v1/applications/a1"]: () => ({ body: current }),
      ["GET /api/v1/applications/a1/calls"]: { body: [] },
      ["GET /api/v1/applications/a1/assessments"]: { body: { items: [], restricted: [], writable: [] } },
      ["GET /api/v1/applications/a1/syntheses"]: { body: { latest: null, total: 0, hidden: false } },
      ["POST /api/v1/applications/a1/outcome"]: () => {
        current = hired;
        return { body: hired };
      },
      ["POST /api/v1/applications/a1/reopening"]: () => {
        current = reopened;
        return { body: reopened };
      },
    });
    const user = userEvent.setup();
    renderWorkspace();
    expect(await screen.findByText("Plazas cubiertas: 1 de 2")).toBeTruthy();
    await user.click(await screen.findByRole("button", { name: "Ana Pérez" }));

    await user.click(await screen.findByRole("button", { name: "Registrar resultado final" }));
    let dialog = screen.getByRole("dialog");
    // La fecha de incorporación solo se pide en una contratación.
    await user.selectOptions(within(dialog).getByLabelText("Resultado"), "DESISTIO");
    expect(within(dialog).queryByLabelText(/Fecha de incorporación/)).toBeNull();
    await user.selectOptions(within(dialog).getByLabelText("Resultado"), "CONTRATADO");
    await user.type(within(dialog).getByLabelText(/Fecha de incorporación/), "2026-12-01");
    await user.type(within(dialog).getByLabelText(/Observaciones/), "Acepta la oferta.");
    await user.click(within(dialog).getByRole("button", { name: "Registrar resultado" }));
    expect((await screen.findByRole("status")).textContent).toContain("Resultado final registrado");
    expect(body(fetchMock, "/outcome")).toEqual({
      outcome: "CONTRATADO",
      reason: null,
      notes: "Acepta la oferta.",
      start_date: "2026-12-01",
    });
    const result = screen.getByRole("region", { name: "Resultado final" });
    expect(within(result).getByText("Contratado")).toBeTruthy();
    expect(within(result).getByText(/Fecha de incorporación: 1 dic 2026/)).toBeTruthy();
    // Con resultado final ya no se mueve de etapa; solo se puede reabrir.
    expect(screen.queryByRole("button", { name: "Mover de etapa" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Registrar resultado final" })).toBeNull();

    await user.click(screen.getByRole("button", { name: "Reabrir proceso" }));
    dialog = screen.getByRole("dialog");
    await user.type(within(dialog).getByLabelText("Motivo"), "No se presentó");
    await user.click(within(dialog).getByRole("button", { name: "Confirmar" }));
    expect((await screen.findByRole("status")).textContent).toContain("Proceso reabierto");
    expect(body(fetchMock, "/reopening")).toEqual({ reason: "No se presentó" });
    const voided = within(screen.getByRole("list", { name: "Resultados anulados" })).getAllByRole("listitem");
    expect(voided[0].textContent).toContain("Contratado");
    expect(voided[0].textContent).toContain("No se presentó");
  });
});
