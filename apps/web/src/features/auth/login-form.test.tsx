import { cleanup, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { makeUser, mockApi, problem, renderApp } from "@/test/helpers";
import { LoginForm } from "./login-form";

const replace = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ replace }) }));

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  replace.mockReset();
});

async function fillAndSubmit(email: string, password: string) {
  const user = userEvent.setup();
  if (email) await user.type(screen.getByLabelText("Correo"), email);
  if (password) await user.type(screen.getByLabelText("Contraseña"), password);
  await user.click(screen.getByRole("button", { name: "Entrar" }));
}

describe("LoginForm", () => {
  it("no llama a la API si faltan datos y explica qué falta", async () => {
    const fetchMock = mockApi({});
    renderApp(<LoginForm />);
    await fillAndSubmit("", "");
    expect(await screen.findByText("Escribe tu correo.")).toBeTruthy();
    expect(screen.getByText("Escribe tu contraseña.")).toBeTruthy();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("muestra el mensaje de la API cuando las credenciales no valen", async () => {
    mockApi({
      "POST /api/v1/auth/login": problem(
        401,
        "credenciales_invalidas",
        "Correo o contraseña incorrectos",
      ),
    });
    renderApp(<LoginForm />);
    await fillAndSubmit("admin@ejemplo.test", "incorrecta-000000");
    expect((await screen.findByRole("alert")).textContent).toBe("Correo o contraseña incorrectos");
    expect(replace).not.toHaveBeenCalled();
  });

  it("envía las credenciales y lleva al inicio cuando son correctas", async () => {
    const fetchMock = mockApi({
      "POST /api/v1/auth/login": { body: { user: makeUser(), csrf_token: "csrf-nuevo" } },
    });
    renderApp(<LoginForm />);
    await fillAndSubmit("admin@ejemplo.test", "Clave-Maestra-2026");
    await vi.waitFor(() => expect(replace).toHaveBeenCalledWith("/"));
    const init = fetchMock.mock.calls[0][1] as RequestInit;
    expect(JSON.parse(String(init.body))).toEqual({
      email: "admin@ejemplo.test",
      password: "Clave-Maestra-2026",
    });
  });
});
