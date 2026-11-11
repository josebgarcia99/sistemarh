import { cleanup, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { StoredFile } from "@/lib/api/files";
import { makeUser, mockApi, problem, renderApp } from "@/test/helpers";
import { VacancyDocuments } from "./vacancy-documents";

const VACANCY_ID = "10000000-0000-0000-0000-000000000001";
const FILES_URL = `/api/v1/vacancies/${VACANCY_ID}/files`;

function makeFile(overrides: Partial<StoredFile> = {}): StoredFile {
  return {
    id: "30000000-0000-0000-0000-000000000001",
    vacancy_id: VACANCY_ID,
    document_type: "CV",
    sensitive: false,
    original_name: "CV Persona Ficticia.pdf",
    content_type: "application/pdf",
    size_bytes: 2 * 1024 * 1024,
    sha256: "a".repeat(64),
    malware_scan: "LIMPIO",
    encrypted: false,
    uploaded_by: "00000000-0000-0000-0000-000000000002",
    uploaded_by_name: "Reclutadora de Prueba",
    created_at: "2026-11-11T18:00:00Z",
    ...overrides,
  };
}
const pdf = () =>
  new File(["%PDF-1.4 ficticio %%EOF"], "cv nuevo.pdf", {
    type: "application/pdf",
  });

function renderDocuments(
  props: { canUpload?: boolean; canDelete?: boolean } = {},
) {
  return renderApp(
    <VacancyDocuments
      vacancyId={VACANCY_ID}
      canUpload={props.canUpload ?? true}
      canDelete={props.canDelete ?? false}
    />,
    { session: makeUser() },
  );
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("VacancyDocuments", () => {
  it("lista los documentos con un enlace de descarga que pasa por la API", async () => {
    mockApi({ [`GET ${FILES_URL}`]: { body: [makeFile()] } });
    renderDocuments();
    const link = await screen.findByRole("link", {
      name: "Descargar CV Persona Ficticia.pdf",
    });
    expect(link.getAttribute("href")).toBe(
      "/api/v1/files/30000000-0000-0000-0000-000000000001/download",
    );
    expect(
      screen.getByText(/Currículum · 2\.0 MB · Reclutadora de Prueba/),
    ).toBeTruthy();
    expect(screen.queryByRole("button", { name: /Eliminar/ })).toBeNull();
  });

  it("carga un archivo como cuerpo de la petición y avisa si está duplicado", async () => {
    const stored = makeFile({
      id: "30000000-0000-0000-0000-000000000002",
      original_name: "cv nuevo.pdf",
    });
    const fetchMock = mockApi({
      [`GET ${FILES_URL}`]: { body: [] },
      [`POST ${FILES_URL}`]: {
        status: 201,
        body: { file: stored, duplicates: [makeFile()] },
      },
    });
    const user = userEvent.setup();
    renderDocuments();
    expect(
      await screen.findByText("Todavía no hay documentos en esta vacante."),
    ).toBeTruthy();

    await user.selectOptions(
      screen.getByLabelText("Tipo de documento"),
      "PERFIL_PUESTO",
    );
    await user.upload(screen.getByLabelText(/^Archivo/), pdf());
    await user.click(screen.getByRole("button", { name: "Cargar documento" }));

    expect((await screen.findByRole("status")).textContent).toContain(
      "Ya estaba cargado en esta vacante como «CV Persona Ficticia.pdf»",
    );
    const [url, init] =
      fetchMock.mock.calls.find(([, i]) => i?.method === "POST") ?? [];
    expect(String(url)).toContain("document_type=PERFIL_PUESTO");
    expect(String(url)).toContain("filename=cv+nuevo.pdf");
    expect(init?.body).toBeInstanceOf(File);
    expect((init?.headers as Record<string, string>)["Content-Type"]).toBe(
      "application/octet-stream",
    );
    expect((init?.headers as Record<string, string>)["X-CSRF-Token"]).toBe(
      "csrf-de-prueba",
    );
  });

  it("avisa que los documentos sensibles se guardan cifrados", async () => {
    mockApi({
      [`GET ${FILES_URL}`]: {
        body: [makeFile({ document_type: "PSICOMETRIA", sensitive: true, encrypted: true })],
      },
    });
    const user = userEvent.setup();
    renderDocuments();
    expect(await screen.findByText(/Psicometría · .* · Sensible, cifrado/)).toBeTruthy();
    expect(screen.queryByText(/se guarda cifrado/)).toBeNull();
    await user.selectOptions(screen.getByLabelText("Tipo de documento"), "ESTUDIO_SOCIOECONOMICO");
    expect(screen.getByText(/se guarda cifrado y solo lo ven/)).toBeTruthy();
  });

  it("rechaza en pantalla un formato no permitido sin llamar a la API", async () => {
    const fetchMock = mockApi({ [`GET ${FILES_URL}`]: { body: [] } });
    const user = userEvent.setup({ applyAccept: false });
    renderDocuments();
    await screen.findByText("Todavía no hay documentos en esta vacante.");
    await user.click(screen.getByRole("button", { name: "Cargar documento" }));
    expect(screen.getByRole("alert").textContent).toContain("Elige un archivo");
    await user.upload(
      screen.getByLabelText(/^Archivo/),
      new File(["MZ"], "programa.exe"),
    );
    await user.click(screen.getByRole("button", { name: "Cargar documento" }));
    expect(screen.getByRole("alert").textContent).toContain(
      "Formato no permitido",
    );
    expect(
      fetchMock.mock.calls.every(
        ([, init]) => (init?.method ?? "GET") === "GET",
      ),
    ).toBe(true);
  });

  it("muestra el motivo cuando el servidor rechaza el archivo", async () => {
    mockApi({
      [`GET ${FILES_URL}`]: { body: [] },
      [`POST ${FILES_URL}`]: problem(
        422,
        "validacion",
        "El documento contiene macros y no se acepta.",
      ),
    });
    const user = userEvent.setup();
    renderDocuments();
    await screen.findByText("Todavía no hay documentos en esta vacante.");
    await user.upload(screen.getByLabelText(/^Archivo/), pdf());
    await user.click(screen.getByRole("button", { name: "Cargar documento" }));
    expect((await screen.findByRole("alert")).textContent).toContain(
      "contiene macros",
    );
  });

  it("con acceso de lectura solo permite descargar", async () => {
    mockApi({ [`GET ${FILES_URL}`]: { body: [makeFile()] } });
    renderDocuments({ canUpload: false });
    expect(await screen.findByRole("link", { name: /Descargar/ })).toBeTruthy();
    expect(
      screen.queryByRole("button", { name: "Cargar documento" }),
    ).toBeNull();
  });

  it("una administradora elimina un documento indicando el motivo", async () => {
    let deleted = false;
    const fetchMock = mockApi({
      [`GET ${FILES_URL}`]: () => ({ body: deleted ? [] : [makeFile()] }),
      "POST /api/v1/files/30000000-0000-0000-0000-000000000001/deletion":
        () => {
          deleted = true;
          return { status: 204 };
        },
    });
    const user = userEvent.setup();
    renderDocuments({ canDelete: true });
    await user.click(
      await screen.findByRole("button", {
        name: "Eliminar CV Persona Ficticia.pdf",
      }),
    );
    const dialog = screen.getByRole("dialog", { name: "Eliminar documento" });

    await user.click(
      within(dialog).getByRole("button", { name: "Eliminar documento" }),
    );
    expect(within(dialog).getByRole("alert").textContent).toContain("motivo");
    await user.type(
      within(dialog).getByLabelText("Motivo de la eliminación"),
      "Solicitud del titular",
    );
    await user.click(
      within(dialog).getByRole("button", { name: "Eliminar documento" }),
    );

    expect(
      await screen.findByText("Todavía no hay documentos en esta vacante."),
    ).toBeTruthy();
    expect(screen.getByRole("status").textContent).toContain(
      "La eliminación quedó registrada",
    );
    const call = fetchMock.mock.calls.find(([url]) =>
      String(url).endsWith("/deletion"),
    );
    expect(JSON.parse(String(call?.[1]?.body))).toEqual({
      reason: "Solicitud del titular",
    });
  });

  it("avisa cuando el almacenamiento no está configurado y no ofrece cargar", async () => {
    mockApi({
      [`GET ${FILES_URL}`]: problem(
        503,
        "servicio_no_disponible",
        "El almacenamiento documental no está configurado.",
      ),
    });
    renderDocuments();
    expect((await screen.findByRole("alert")).textContent).toContain(
      "no está configurado",
    );
    expect(
      screen.queryByRole("button", { name: "Cargar documento" }),
    ).toBeNull();
  });
});
