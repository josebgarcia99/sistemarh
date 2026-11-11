import { cleanup, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { Vacancy } from "@/lib/api/vacancies";
import { makeUser, mockApi, problem, renderApp } from "@/test/helpers";
import { VacanciesScreen } from "./vacancies-screen";

const admin = makeUser();
const recruiter = makeUser({
  id: "00000000-0000-0000-0000-000000000002",
  email: "reclutadora@ejemplo.test",
  full_name: "Reclutadora de Prueba",
  role: "RECLUTADOR",
});
const person = (user: { id: string; full_name: string; email: string }) => ({
  id: user.id,
  full_name: user.full_name,
  email: user.email,
  is_active: true,
});
const colleague = {
  id: "00000000-0000-0000-0000-000000000009",
  full_name: "Colega de Prueba",
  email: "colega@ejemplo.test",
};

function makeVacancy(overrides: Partial<Vacancy> = {}): Vacancy {
  return {
    id: "10000000-0000-0000-0000-000000000001",
    name: "Analista de Nómina",
    department: "Finanzas",
    location: "Monterrey",
    work_mode: "PRESENCIAL",
    contract_type: "Tiempo completo",
    description: "Puesto de prueba.",
    positions: 2,
    notes: null,
    status: "BORRADOR",
    owner: person(recruiter),
    my_access: "RESPONSABLE",
    opened_at: null,
    closed_at: null,
    created_at: "2026-11-10T15:00:00Z",
    updated_at: "2026-11-10T15:00:00Z",
    version: 1,
    ...overrides,
  };
}
const page = (items: Vacancy[]) => ({
  body: { items, total: items.length, page: 1, page_size: 10 },
});
const initialHistory = {
  body: [
    {
      previous_owner: null,
      new_owner: person(recruiter),
      changed_at: "2026-11-10T15:00:00Z",
      reason: "Creación de la vacante",
      authorized_by: person(recruiter),
      part_of_mass_transfer: false,
    },
  ],
};
const VACANCY_URL = "/api/v1/vacancies/10000000-0000-0000-0000-000000000001";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("VacanciesScreen", () => {
  it("un reclutador empieza en «Mis vacantes» y puede pedir las compartidas", async () => {
    const fetchMock = mockApi({
      "GET /api/v1/vacancies": page([makeVacancy()]),
    });
    const user = userEvent.setup();
    renderApp(<VacanciesScreen />, { session: recruiter });

    expect(await screen.findByText("Analista de Nómina")).toBeTruthy();
    expect(screen.getByText("1 vacante")).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Todas" })).toBeNull();
    expect(String(fetchMock.mock.calls[0][0])).toContain("scope=mine");

    await user.click(
      screen.getByRole("button", { name: "Compartidas conmigo" }),
    );
    await vi.waitFor(() =>
      expect(
        fetchMock.mock.calls.some(([url]) =>
          String(url).includes("scope=shared"),
        ),
      ).toBe(true),
    );
  });

  it("una administradora empieza viendo todas las vacantes", async () => {
    const fetchMock = mockApi({
      "GET /api/v1/vacancies": page([
        makeVacancy({ my_access: "ADMINISTRADOR" }),
      ]),
    });
    renderApp(<VacanciesScreen />, { session: admin });
    expect(await screen.findByText("Analista de Nómina")).toBeTruthy();
    expect(String(fetchMock.mock.calls[0][0])).toContain("scope=all");
    expect(
      screen
        .getByRole("button", { name: "Todas" })
        .getAttribute("aria-pressed"),
    ).toBe("true");
  });

  it("explica cuando no hay vacantes compartidas", async () => {
    mockApi({ "GET /api/v1/vacancies": page([]) });
    const user = userEvent.setup();
    renderApp(<VacanciesScreen />, { session: recruiter });
    expect(await screen.findByText(/Todavía no hay vacantes/)).toBeTruthy();
    await user.click(
      screen.getByRole("button", { name: "Compartidas conmigo" }),
    );
    expect(
      await screen.findByText("Nadie ha compartido vacantes contigo."),
    ).toBeTruthy();
  });

  it("crea una vacante y abre su detalle", async () => {
    const created = makeVacancy();
    const fetchMock = mockApi({
      "GET /api/v1/vacancies": page([]),
      "POST /api/v1/vacancies": { status: 201, body: created },
      [`GET ${VACANCY_URL}`]: { body: created },
      [`GET ${VACANCY_URL}/members`]: { body: [] },
      [`GET ${VACANCY_URL}/files`]: { body: [] },
      [`GET ${VACANCY_URL}/ownership-history`]: initialHistory,
    });
    const user = userEvent.setup();
    renderApp(<VacanciesScreen />, { session: recruiter });

    await user.click(screen.getByRole("button", { name: "Nueva vacante" }));
    const dialog = screen.getByRole("dialog", { name: "Nueva vacante" });
    await user.type(
      within(dialog).getByLabelText("Nombre de la vacante"),
      "Analista de Nómina",
    );
    await user.type(within(dialog).getByLabelText("Departamento"), "Finanzas");
    await user.type(within(dialog).getByLabelText("Ubicación"), "Monterrey");
    await user.type(
      within(dialog).getByLabelText("Tipo de contratación"),
      "Tiempo completo",
    );
    await user.clear(within(dialog).getByLabelText("Número de posiciones"));
    await user.type(within(dialog).getByLabelText("Número de posiciones"), "2");
    await user.click(
      within(dialog).getByRole("button", { name: "Crear vacante" }),
    );

    const panel = await screen.findByRole("complementary", {
      name: "Detalle de Analista de Nómina",
    });
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(within(panel).getByRole("status").textContent).toContain(
      "Se creó la vacante",
    );
    expect(
      await within(panel).findByText(/Nadie más tiene acceso/),
    ).toBeTruthy();
    expect(
      await within(panel).findByText(
        /Responsable inicial: Reclutadora de Prueba/,
      ),
    ).toBeTruthy();
    const post = fetchMock.mock.calls.find(
      ([, init]) => init?.method === "POST",
    );
    expect(JSON.parse(String((post?.[1] as RequestInit).body))).toEqual({
      name: "Analista de Nómina",
      department: "Finanzas",
      location: "Monterrey",
      work_mode: "PRESENCIAL",
      contract_type: "Tiempo completo",
      positions: 2,
      description: "",
      notes: null,
    });
  });

  it("no envía una vacante sin nombre", async () => {
    const fetchMock = mockApi({ "GET /api/v1/vacancies": page([]) });
    const user = userEvent.setup();
    renderApp(<VacanciesScreen />, { session: recruiter });
    await user.click(screen.getByRole("button", { name: "Nueva vacante" }));
    const dialog = screen.getByRole("dialog", { name: "Nueva vacante" });
    await user.click(
      within(dialog).getByRole("button", { name: "Crear vacante" }),
    );
    expect(
      await within(dialog).findByText(/nombre/i, { selector: "p" }),
    ).toBeTruthy();
    expect(
      fetchMock.mock.calls.every(
        ([, init]) => (init?.method ?? "GET") === "GET",
      ),
    ).toBe(true);
  });

  it("la responsable comparte la vacante en modo lectura", async () => {
    const vacancy = makeVacancy({ status: "ABIERTA" });
    const fetchMock = mockApi({
      "GET /api/v1/vacancies": page([vacancy]),
      [`GET ${VACANCY_URL}`]: { body: vacancy },
      [`GET ${VACANCY_URL}/members`]: { body: [] },
      [`GET ${VACANCY_URL}/files`]: { body: [] },
      [`GET ${VACANCY_URL}/ownership-history`]: initialHistory,
      "GET /api/v1/users/directory": { body: [colleague] },
      [`PUT ${VACANCY_URL}/members/${colleague.id}`]: { status: 204 },
    });
    const user = userEvent.setup();
    renderApp(<VacanciesScreen />, { session: recruiter });

    await user.click(
      await screen.findByRole("button", { name: "Abrir Analista de Nómina" }),
    );
    const panel = await screen.findByRole("complementary", {
      name: "Detalle de Analista de Nómina",
    });
    await user.type(within(panel).getByLabelText("Compartir con"), "col");
    await user.click(
      await within(panel).findByRole("button", { name: /Colega de Prueba/ }),
    );
    await user.click(within(panel).getByRole("button", { name: "Compartir" }));

    expect(
      await within(panel).findByText(
        /Compartiste la vacante con Colega de Prueba/,
      ),
    ).toBeTruthy();
    const put = fetchMock.mock.calls.find(([, init]) => init?.method === "PUT");
    expect(JSON.parse(String((put?.[1] as RequestInit).body))).toEqual({
      access_type: "LECTURA",
    });
    // El buscador queda vacío para compartir con otra persona.
    expect(
      (within(panel).getByLabelText("Compartir con") as HTMLInputElement).value,
    ).toBe("");
    // Solo una administradora puede transferir la propiedad.
    expect(
      within(panel).queryByRole("button", { name: "Transferir responsable" }),
    ).toBeNull();
  });

  it("con acceso de lectura no ofrece editar, cambiar estado ni compartir", async () => {
    const vacancy = makeVacancy({
      status: "ABIERTA",
      owner: person(colleague),
      my_access: "LECTURA",
    });
    mockApi({
      "GET /api/v1/vacancies": page([vacancy]),
      [`GET ${VACANCY_URL}`]: { body: vacancy },
      [`GET ${VACANCY_URL}/members`]: { body: [] },
      [`GET ${VACANCY_URL}/files`]: { body: [] },
      [`GET ${VACANCY_URL}/ownership-history`]: { body: [] },
    });
    const user = userEvent.setup();
    renderApp(<VacanciesScreen />, { session: recruiter });
    await user.click(
      await screen.findByRole("button", { name: "Abrir Analista de Nómina" }),
    );
    const panel = await screen.findByRole("complementary", {
      name: "Detalle de Analista de Nómina",
    });
    expect(
      within(panel).queryByRole("button", { name: "Editar datos" }),
    ).toBeNull();
    expect(within(panel).queryByRole("button", { name: /Pasar a/ })).toBeNull();
    expect(within(panel).queryByLabelText("Compartir con")).toBeNull();
  });

  it("avisa cuando otra persona cambió la vacante antes", async () => {
    const vacancy = makeVacancy();
    mockApi({
      "GET /api/v1/vacancies": page([vacancy]),
      [`GET ${VACANCY_URL}`]: { body: vacancy },
      [`GET ${VACANCY_URL}/members`]: { body: [] },
      [`GET ${VACANCY_URL}/files`]: { body: [] },
      [`GET ${VACANCY_URL}/ownership-history`]: initialHistory,
      [`POST ${VACANCY_URL}/status`]: problem(
        409,
        "conflict",
        "Otra persona modificó la vacante. Vuelve a cargarla.",
      ),
    });
    const user = userEvent.setup();
    renderApp(<VacanciesScreen />, { session: recruiter });
    await user.click(
      await screen.findByRole("button", { name: "Abrir Analista de Nómina" }),
    );
    const panel = await screen.findByRole("complementary", {
      name: "Detalle de Analista de Nómina",
    });
    await user.click(
      await within(panel).findByRole("button", { name: "Pasar a abierta" }),
    );
    expect((await within(panel).findByRole("alert")).textContent).toContain(
      "Otra persona modificó",
    );
  });

  it("abre el perfil y el prompt de la vacante y permite volver a la lista", async () => {
    const vacancy = makeVacancy();
    mockApi({
      "GET /api/v1/vacancies": page([vacancy]),
      [`GET ${VACANCY_URL}`]: { body: vacancy },
      [`GET ${VACANCY_URL}/members`]: { body: [] },
      [`GET ${VACANCY_URL}/files`]: { body: [] },
      [`GET ${VACANCY_URL}/ownership-history`]: initialHistory,
      [`GET ${VACANCY_URL}/profile-versions`]: { body: [] },
    });
    const user = userEvent.setup();
    renderApp(<VacanciesScreen />, { session: recruiter });
    await user.click(await screen.findByRole("button", { name: "Abrir Analista de Nómina" }));
    await user.click(await screen.findByRole("button", { name: "Perfil y prompt de evaluación" }));
    expect(await screen.findByRole("heading", { name: "Perfil y prompt" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Guardar perfil" })).toBeTruthy();
    await user.click(screen.getByRole("button", { name: "Volver a vacantes" }));
    expect(await screen.findByRole("heading", { name: "Vacantes" })).toBeTruthy();
  });

  it("muestra el error cuando la lista no carga", async () => {
    mockApi({
      "GET /api/v1/vacancies": problem(
        503,
        "service_unavailable",
        "Servicio no disponible.",
      ),
    });
    renderApp(<VacanciesScreen />, { session: recruiter });
    expect((await screen.findByRole("alert")).textContent).toContain(
      "Servicio no disponible",
    );
  });
});
