import { cleanup, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { HomeScreen } from "@/features/home/home-screen";
import { makeUser, mockApi, renderApp } from "@/test/helpers";
import { StudyQueueScreen } from "./study-queue-screen";

const QUEUE = "/api/v1/study-queue";
const row = (id: string, name: string, status: string | null, active = true) => ({
  application_id: id,
  vacancy_id: "v1",
  candidate_name: name,
  vacancy_name: "Analista de Nómina",
  active,
  study_status: status,
  study_updated_at: status ? "2026-11-12T18:00:00Z" : null,
});
const analyst = () => makeUser({ role: "ANALISTA_ESTUDIOS", full_name: "Analista Ficticia" });

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("StudyQueueScreen", () => {
  it("no se muestra ni consulta nada a un reclutador", () => {
    const fetchMock = mockApi({});
    renderApp(<StudyQueueScreen />, { session: makeUser({ role: "RECLUTADOR" }) });
    expect(screen.getByRole("alert").textContent).toContain("analista de estudios");
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("lista a las personas con el estado de su estudio y abre el estudio de una", async () => {
    const fetchMock = mockApi({
      [`GET ${QUEUE}`]: {
        body: [row("a1", "Ana Pérez Ficticia", "EN_PROCESO"), row("a2", "Beto López Ficticio", null, false)],
      },
      ["GET /api/v1/applications/a1/assessments"]: {
        body: { items: [], restricted: [], writable: ["ESTUDIO_SOCIOECONOMICO"] },
      },
    });
    const user = userEvent.setup();
    renderApp(<StudyQueueScreen />, { session: analyst() });
    const people = within(await screen.findByRole("list", { name: "Personas" }));
    expect(people.getByRole("button", { name: "Abrir el estudio de Ana Pérez Ficticia" }).textContent).toContain(
      "Estudio: En proceso",
    );
    expect(people.getByRole("button", { name: "Abrir el estudio de Beto López Ficticio" }).textContent).toContain(
      "Sin estudio · Proceso cerrado",
    );

    await user.click(people.getByRole("button", { name: "Abrir el estudio de Ana Pérez Ficticia" }));
    expect(await screen.findByRole("heading", { name: "Ana Pérez Ficticia" })).toBeTruthy();
    // Solo puede registrar lo que el servidor le permite: el estudio.
    expect(await screen.findByRole("button", { name: "Registrar evaluación" })).toBeTruthy();
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes("/applications/a1/assessments"))).toBe(true);
    await user.click(screen.getByRole("button", { name: "Volver a la lista" }));
    expect(await screen.findByRole("list", { name: "Personas" })).toBeTruthy();
  });

  it("busca por persona o vacante", async () => {
    const fetchMock = mockApi({ [`GET ${QUEUE}`]: { body: [] } });
    const user = userEvent.setup();
    renderApp(<StudyQueueScreen />, { session: analyst() });
    expect(await screen.findByText("No hay personas en proceso por ahora.")).toBeTruthy();
    await user.type(screen.getByLabelText("Buscar por persona o vacante"), "ana");
    expect(await screen.findByText("Nadie coincide con la búsqueda.")).toBeTruthy();
    expect(fetchMock.mock.calls.some(([url]) => String(url).endsWith("/study-queue?search=ana"))).toBe(true);
  });

  it("el inicio del analista es su lista de trabajo, sin pedir el tablero", async () => {
    const fetchMock = mockApi({ [`GET ${QUEUE}`]: { body: [row("a1", "Ana Pérez Ficticia", null)] } });
    renderApp(<HomeScreen />, { session: analyst() });
    expect(await screen.findByRole("heading", { name: "Estudios socioeconómicos" })).toBeTruthy();
    expect(fetchMock.mock.calls.every(([url]) => !String(url).includes("/reports/"))).toBe(true);
  });
});
