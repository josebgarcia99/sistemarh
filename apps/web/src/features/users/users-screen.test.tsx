import { cleanup, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { makeUser, mockApi, problem, renderApp } from "@/test/helpers";
import { UsersScreen } from "./users-screen";

const admin = makeUser();
const recruiter = makeUser({
  id: "00000000-0000-0000-0000-000000000002",
  email: "reclutadora@ejemplo.test",
  full_name: "Reclutadora de Prueba",
  role: "RECLUTADOR",
  last_activity_at: null,
});
const page = (items: unknown[]) => ({ body: { items, total: items.length, page: 1, page_size: 10 } });

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("UsersScreen", () => {
  it("un reclutador ve que no tiene acceso y no se consulta la lista", () => {
    const fetchMock = mockApi({});
    renderApp(<UsersScreen />, { session: recruiter });
    expect(screen.getByRole("alert").textContent).toContain("solo para administradores");
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("lista los usuarios y no ofrece dar de baja la propia cuenta", async () => {
    mockApi({ "GET /api/v1/users": page([admin, recruiter]) });
    renderApp(<UsersScreen />, { session: admin });
    expect(await screen.findByText("reclutadora@ejemplo.test")).toBeTruthy();
    expect(screen.getByText("2 usuarios")).toBeTruthy();
    expect(screen.getByText("Sin actividad")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Dar de baja a Reclutadora de Prueba" })).toBeTruthy();
    expect(
      screen.queryByRole("button", { name: "Dar de baja a Administradora de Prueba" }),
    ).toBeNull();
  });

  it("crea un usuario enviando el token CSRF y avisa del resultado", async () => {
    const created = makeUser({
      id: "00000000-0000-0000-0000-000000000003",
      email: "nueva@ejemplo.test",
      full_name: "Nueva Persona",
      role: "RECLUTADOR",
    });
    const fetchMock = mockApi({
      "GET /api/v1/users": page([admin]),
      "POST /api/v1/users": { status: 201, body: created },
    });
    const user = userEvent.setup();
    renderApp(<UsersScreen />, { session: admin });

    await user.click(await screen.findByRole("button", { name: "Nuevo usuario" }));
    const dialog = screen.getByRole("dialog", { name: "Nuevo usuario" });
    await user.type(within(dialog).getByLabelText("Nombre completo"), "Nueva Persona");
    await user.type(within(dialog).getByLabelText("Correo"), "nueva@ejemplo.test");
    await user.type(within(dialog).getByLabelText("Contraseña"), "Clave-Inicial-2026");
    await user.click(within(dialog).getByRole("button", { name: "Crear usuario" }));

    expect((await screen.findByRole("status")).textContent).toContain("Nueva Persona");
    expect(screen.queryByRole("dialog")).toBeNull();
    const post = fetchMock.mock.calls.find(([, init]) => init?.method === "POST");
    const init = post?.[1] as RequestInit;
    expect((init.headers as Record<string, string>)["X-CSRF-Token"]).toBe("csrf-de-prueba");
    expect(JSON.parse(String(init.body))).toEqual({
      email: "nueva@ejemplo.test",
      full_name: "Nueva Persona",
      password: "Clave-Inicial-2026",
      role: "RECLUTADOR",
    });
  });

  it("no envía una contraseña de menos de 12 caracteres", async () => {
    const fetchMock = mockApi({ "GET /api/v1/users": page([admin]) });
    const user = userEvent.setup();
    renderApp(<UsersScreen />, { session: admin });

    await user.click(await screen.findByRole("button", { name: "Nuevo usuario" }));
    const dialog = screen.getByRole("dialog");
    await user.type(within(dialog).getByLabelText("Nombre completo"), "Nueva Persona");
    await user.type(within(dialog).getByLabelText("Correo"), "nueva@ejemplo.test");
    await user.type(within(dialog).getByLabelText("Contraseña"), "corta");
    await user.click(within(dialog).getByRole("button", { name: "Crear usuario" }));

    expect(await within(dialog).findByText(/al menos 12 caracteres/)).toBeTruthy();
    expect(fetchMock.mock.calls.every(([, init]) => (init?.method ?? "GET") === "GET")).toBe(true);
  });

  it("muestra el error de la API sin cerrar el diálogo", async () => {
    mockApi({
      "GET /api/v1/users": page([admin]),
      "POST /api/v1/users": problem(409, "conflicto", "Ya existe un usuario con ese correo."),
    });
    const user = userEvent.setup();
    renderApp(<UsersScreen />, { session: admin });

    await user.click(await screen.findByRole("button", { name: "Nuevo usuario" }));
    const dialog = screen.getByRole("dialog");
    await user.type(within(dialog).getByLabelText("Nombre completo"), "Nueva Persona");
    await user.type(within(dialog).getByLabelText("Correo"), "admin@ejemplo.test");
    await user.type(within(dialog).getByLabelText("Contraseña"), "Clave-Inicial-2026");
    await user.click(within(dialog).getByRole("button", { name: "Crear usuario" }));

    expect((await within(dialog).findByRole("alert")).textContent).toBe(
      "Ya existe un usuario con ese correo.",
    );
  });

  it("restablece una contraseña e informa cuántas sesiones se cerraron", async () => {
    const fetchMock = mockApi({
      "GET /api/v1/users": page([admin, recruiter]),
      [`POST /api/v1/users/${recruiter.id}/reset-password`]: { body: { sessions_closed: 1 } },
    });
    const user = userEvent.setup();
    renderApp(<UsersScreen />, { session: admin });

    await user.click(
      await screen.findByRole("button", {
        name: "Restablecer la contraseña de Reclutadora de Prueba",
      }),
    );
    const dialog = screen.getByRole("dialog", { name: "Restablecer contraseña" });
    await user.type(within(dialog).getByLabelText("Contraseña nueva"), "Clave-Nueva-2026!");
    await user.click(within(dialog).getByRole("button", { name: "Restablecer contraseña" }));

    expect((await screen.findByRole("status")).textContent).toContain("Se cerró 1 sesión abierta.");
    const post = fetchMock.mock.calls.find(([, init]) => init?.method === "POST");
    expect(JSON.parse(String((post?.[1] as RequestInit).body))).toEqual({
      new_password: "Clave-Nueva-2026!",
    });
  });
});
