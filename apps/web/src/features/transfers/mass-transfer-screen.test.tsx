import { cleanup, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { makeUser, mockApi, problem, renderApp } from "@/test/helpers";
import { MassTransferScreen } from "./mass-transfer-screen";

const admin = makeUser();
const outgoing = {
  id: "00000000-0000-0000-0000-000000000002",
  full_name: "Reclutadora Saliente",
  email: "saliente@ejemplo.test",
};
const receiver = {
  id: "00000000-0000-0000-0000-000000000003",
  full_name: "Reclutador Receptor",
  email: "receptor@ejemplo.test",
};
const preview = {
  from_user: { ...outgoing, is_active: true },
  to_user: { ...receiver, is_active: true },
  vacancies: [
    { id: "10000000-0000-0000-0000-000000000001", name: "Analista de Nómina", status: "ABIERTA" },
    { id: "10000000-0000-0000-0000-000000000002", name: "Auxiliar Contable", status: "PAUSADA" },
  ],
  memberships_to_revoke: 1,
  grants_to_revoke: 0,
  preview_token: "huella-de-la-vista-previa",
};
const directory = ({ url }: { url: string }) => ({
  body: url.includes("search=sal") ? [outgoing] : [receiver],
});

async function choosePeople(user: ReturnType<typeof userEvent.setup>) {
  await user.type(screen.getByLabelText("Usuario saliente"), "sal");
  await user.click(await screen.findByRole("button", { name: /Reclutadora Saliente/ }));
  await user.type(screen.getByLabelText("Usuario receptor"), "rec");
  await user.click(await screen.findByRole("button", { name: /Reclutador Receptor/ }));
  await user.click(screen.getByRole("button", { name: "Ver vista previa" }));
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("MassTransferScreen", () => {
  it("un reclutador no puede usar la pantalla", () => {
    const fetchMock = mockApi({});
    renderApp(<MassTransferScreen />, { session: makeUser({ role: "RECLUTADOR" }) });
    expect(screen.getByRole("alert").textContent).toContain("solo para administradores");
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("muestra la vista previa y confirma con el mismo identificador de operación", async () => {
    const fetchMock = mockApi({
      "GET /api/v1/users/directory": directory,
      "POST /api/v1/vacancy-transfers/mass/preview": { body: preview },
      "POST /api/v1/vacancy-transfers/mass": {
        body: {
          operation_id: "ignorado",
          completed_at: "2026-11-11T18:00:00Z",
          vacancies_transferred: 2,
          memberships_revoked: 1,
          grants_revoked: 0,
          user_deactivated: true,
        },
      },
    });
    const user = userEvent.setup();
    renderApp(<MassTransferScreen />, { session: admin });
    await choosePeople(user);

    expect(await screen.findByText("Analista de Nómina")).toBeTruthy();
    expect(screen.getByText("Pausada")).toBeTruthy();

    // Sin motivo no se envía nada.
    await user.click(screen.getByRole("button", { name: "Dar de baja y transferir" }));
    expect(screen.getByRole("alert").textContent).toContain("motivo");
    expect(fetchMock.mock.calls.some(([url]) => String(url).endsWith("/mass"))).toBe(false);

    await user.type(screen.getByLabelText("Motivo de la baja"), "Termina su contrato");
    await user.click(screen.getByRole("button", { name: "Dar de baja y transferir" }));

    const summary = await screen.findByRole("status");
    expect(summary.textContent).toContain("Vacantes transferidas a Reclutador Receptor: 2");
    expect(summary.textContent).toContain("Reclutadora Saliente quedó dado de baja");
    const call = fetchMock.mock.calls.find(([url]) => String(url).endsWith("/mass"));
    const body = JSON.parse(String((call?.[1] as RequestInit).body));
    expect(body).toMatchObject({
      from_user_id: outgoing.id,
      to_user_id: receiver.id,
      reason: "Termina su contrato",
      preview_token: "huella-de-la-vista-previa",
    });
    expect(body.operation_id).toMatch(/^[0-9a-f-]{36}$/);
  });

  it("si la confirmación falla se puede reintentar sin duplicar la operación", async () => {
    let attempts = 0;
    const fetchMock = mockApi({
      "GET /api/v1/users/directory": directory,
      "POST /api/v1/vacancy-transfers/mass/preview": { body: preview },
      "POST /api/v1/vacancy-transfers/mass": () => {
        attempts += 1;
        return attempts === 1
          ? problem(409, "conflict", "Los datos cambiaron desde la vista previa.")
          : {
              body: {
                operation_id: "ignorado",
                completed_at: "2026-11-11T18:00:00Z",
                vacancies_transferred: 2,
                memberships_revoked: 1,
                grants_revoked: 0,
                user_deactivated: true,
              },
            };
      },
    });
    const user = userEvent.setup();
    renderApp(<MassTransferScreen />, { session: admin });
    await choosePeople(user);
    await user.type(await screen.findByLabelText("Motivo de la baja"), "Termina su contrato");
    await user.click(screen.getByRole("button", { name: "Dar de baja y transferir" }));
    expect((await screen.findByRole("alert")).textContent).toContain("cambiaron desde la vista previa");

    await user.click(screen.getByRole("button", { name: "Dar de baja y transferir" }));
    await screen.findByRole("status");
    const ids = fetchMock.mock.calls
      .filter(([url]) => String(url).endsWith("/mass"))
      .map(([, init]) => JSON.parse(String((init as RequestInit).body)).operation_id);
    expect(ids).toHaveLength(2);
    expect(ids[0]).toBe(ids[1]);
  });
});
