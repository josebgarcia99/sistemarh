import { cleanup, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { Assessment, AssessmentList } from "@/lib/api/assessments";
import type { ApplicationDetail } from "@/lib/api/recruitment";
import { makeUser, mockApi, renderApp, problem } from "@/test/helpers";
import { AssessmentsSection } from "./assessments-section";
import { DossierSection } from "./dossier-section";

const LIST_URL = "/api/v1/applications/a1/assessments";
/** Cuerpo de la última solicitud de escritura a una ruta que termina así. */
const body = (fetchMock: ReturnType<typeof mockApi>, ending: string) => {
  const calls = fetchMock.mock.calls.filter(
    ([url, init]) => String(url).endsWith(ending) && init?.method && init.method !== "GET",
  );
  return JSON.parse(String(calls.at(-1)?.[1]?.body ?? "null"));
};
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

  it("registra referencias, anota lo que dijo cada una y muestra el análisis de la IA", async () => {
    let items: Assessment[] = [];
    const statuses = ["PENDIENTE", "EN_PROCESO", "COMPLETADO", "NO_APLICA", "ANULADO"];
    const created = make("REFERENCIAS", { statuses, data: { references: [], notes: "" } });
    const reference = {
      type: "PERSONAL",
      name: "Vecina Ficticia",
      relation: "Vecina",
      position: "",
      phone: "",
      period: "",
      contacted_by: "",
      contacted_on: "",
      result: "CONTACTADA",
      comments: "La conoce desde hace diez años.",
    };
    const saved = { ...created, version: 2, status: "EN_PROCESO", data: { references: [reference], notes: "" } };
    const analyzed = {
      ...saved,
      version: 3,
      ai_summary: {
        resumen: "Una referencia personal contactada.",
        referencias_laborales: [],
        referencias_personales: ["Vecina Ficticia indicó que la conoce desde hace diez años."],
        coincidencias_con_cv: [],
        discrepancias_verificables: [],
        sin_confirmar: ["Ninguna referencia confirma el último empleo del CV."],
      },
      ai_summary_at: "2026-11-15T18:00:00Z",
    };
    const fetchMock = mockApi({
      [`GET ${LIST_URL}`]: () => ({ body: list(items, { writable: ["ESTUDIO_SOCIOECONOMICO", "REFERENCIAS"] }) }),
      [`GET ${FILES_URL}`]: { body: [] },
      ["GET /api/v1/form-templates"]: { body: [] },
      [`POST ${LIST_URL}`]: () => {
        items = [created];
        return { status: 201, body: created };
      },
      ["PUT /api/v1/assessments/e-REFERENCIAS"]: () => {
        items = [saved];
        return { body: saved };
      },
      ["POST /api/v1/assessments/e-REFERENCIAS/summary"]: () => {
        items = [analyzed];
        return { body: analyzed };
      },
    });
    const user = userEvent.setup();
    renderSection();
    await user.click(await screen.findByRole("button", { name: "Registrar evaluación" }));
    await user.selectOptions(screen.getByLabelText("Tipo de evaluación"), "REFERENCIAS");
    expect(screen.getByText(/antes o después del estudio socioeconómico/)).toBeTruthy();
    await user.click(screen.getByRole("button", { name: "Registrar" }));
    expect(sent(fetchMock, "POST", LIST_URL)).toEqual({ kind: "REFERENCIAS", data: {}, template_id: null });

    // No lleva documento adjunto y avisa que lo dicho es una opinión.
    expect(await screen.findByText("Todavía no hay referencias registradas.")).toBeTruthy();
    expect(screen.queryByLabelText("Documento")).toBeNull();
    expect(screen.getByText(/Es la opinión de un tercero/)).toBeTruthy();
    await user.click(screen.getByRole("button", { name: "Agregar referencia" }));
    await user.selectOptions(screen.getByLabelText("Tipo de la referencia 1"), "PERSONAL");
    await user.type(screen.getByLabelText("Nombre de la referencia 1"), "Vecina Ficticia");
    await user.type(screen.getByLabelText("Empresa o relación con la persona 1"), "Vecina");
    await user.selectOptions(screen.getByLabelText("Resultado del contacto 1"), "CONTACTADA");
    await user.type(screen.getByLabelText("Lo que dijo la referencia 1"), "La conoce desde hace diez años.");
    await user.selectOptions(screen.getByLabelText("Estado"), "EN_PROCESO");
    await user.click(screen.getByRole("button", { name: "Guardar" }));
    expect((await screen.findByRole("status")).textContent).toContain("Evaluación guardada");
    const body = sent(fetchMock, "PUT", "/e-REFERENCIAS");
    expect(body.status).toBe("EN_PROCESO");
    expect(body.file_id).toBeNull();
    expect(body.data).toEqual({ notes: "", references: [reference] });

    await user.click(screen.getByRole("button", { name: "Analizar con IA" }));
    const panel = within(await screen.findByRole("region", { name: "Resumen de la IA" }));
    expect(panel.getByText("Lo que dijeron las referencias personales")).toBeTruthy();
    expect(panel.getByText("Sin confirmar")).toBeTruthy();
    expect(panel.queryByText("Lo que dijeron las referencias laborales")).toBeNull();
    expect(panel.getByText(/es su opinión, no un hecho comprobado/)).toBeTruthy();
  });

  it("en el estudio, lo que lee la IA entra sin verificar y la persona lo marca", async () => {
    const study = make("ESTUDIO_SOCIOECONOMICO", {
      status: "EN_PROCESO",
      form: [{ title: "Datos de la visita", fields: [
        { ...FIELD, id: "visita", label: "Fecha de la visita", type: "FECHA", required: true },
        { ...FIELD, id: "domicilio", label: "Domicilio declarado", type: "PARRAFO" },
      ] }],
    });
    let stored = [file("f9", "estudio escaneado.pdf", "ESTUDIO_SOCIOECONOMICO"), file("f1", "cv.pdf", "CV")];
    const fetchMock = mockApi({
      [`GET ${LIST_URL}`]: { body: list([study]) },
      [`GET ${FILES_URL}`]: () => ({ body: stored }),
      [`POST ${FILES_URL}`]: () => {
        const format = file("f12", "estudio lleno.xlsx", "ESTUDIO_SOCIOECONOMICO");
        stored = [...stored, format];
        return { status: 201, body: { file: format, duplicates: [] } };
      },
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
    const picker = (await screen.findByLabelText("Formato del estudio (Excel, PDF, Word o escaneado)")) as HTMLSelectElement;
    await within(picker).findByRole("option", { name: "estudio escaneado.pdf" });
    expect(within(picker).queryByRole("option", { name: "cv.pdf" })).toBeNull();
    // El formato lleno se adjunta aquí mismo y queda elegido para leerlo.
    await user.upload(screen.getByLabelText("Adjuntar el formato del estudio"), new File(["xlsx"], "estudio lleno.xlsx"));
    expect((await screen.findByRole("status")).textContent).toContain("Archivo adjuntado");
    const upload = fetchMock.mock.calls.find(([url, init]) => String(url).includes("/files?") && init?.method === "POST");
    expect(String(upload?.[0])).toContain("document_type=ESTUDIO_SOCIOECONOMICO");
    expect(picker.value).toBe("f12");
    await user.click(screen.getByRole("button", { name: "Leer el formato con IA" }));
    expect(sent(fetchMock, "POST", "/digitization")).toEqual({ file_id: "f12" });

    expect(await screen.findByText(/todavía no se ha guardado/)).toBeTruthy();
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

  it("descarga el estudio en el formato de la empresa y avisa de lo que no cupo o falta", async () => {
    const study = make("ESTUDIO_SOCIOECONOMICO", {
      status: "EN_PROCESO",
      form: [{ title: "Datos de la visita", fields: [{ ...FIELD, id: "visita", label: "Fecha de la visita", type: "FECHA" }] }],
    });
    const DOWNLOAD = "GET /api/v1/assessments/e-ESTUDIO_SOCIOECONOMICO/study-format";
    let attempt = 0;
    mockApi({
      [`GET ${LIST_URL}`]: { body: list([study]) },
      [`GET ${FILES_URL}`]: { body: [] },
      [DOWNLOAD]: () => {
        attempt += 1;
        if (attempt === 1) return problem(422, "validacion", "Todavía no se ha cargado el formato en blanco de la empresa.");
        return {
          body: "xlsx",
          headers: {
            "Content-Disposition": "attachment; filename*=UTF-8''Estudio%20socioeconomico%20-%20Ana%20P%C3%A9rez.xlsx",
            "X-Unplaced": attempt === 2 ? encodeURIComponent(JSON.stringify(["Datos familiares: solo caben 8 filas; faltan 2"])) : "%5B%5D",
          },
        };
      },
    });
    const saved: string[] = [];
    vi.stubGlobal("URL", Object.assign(URL, { createObjectURL: () => "blob:prueba", revokeObjectURL: () => undefined }));
    const click = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(function (this: HTMLAnchorElement) {
      saved.push(this.download);
    });
    const user = userEvent.setup();
    renderSection();
    await user.click(await screen.findByRole("button", { name: /Estudio socioeconómico/ }));
    const button = await screen.findByRole("button", { name: "Descargar en el formato de la empresa (Excel)" });

    await user.click(button);
    expect((await screen.findByRole("alert")).textContent).toContain("Todavía no se ha cargado el formato");
    expect(saved).toEqual([]);

    await user.click(button);
    await screen.findByText(/no encontraron lugar en él: Datos familiares: solo caben 8 filas; faltan 2\./);
    expect(saved).toEqual(["Estudio socioeconomico - Ana Pérez.xlsx"]);

    await user.click(button);
    expect((await screen.findByRole("status")).textContent).toContain("Formato descargado");
    expect(saved).toHaveLength(2);
    click.mockRestore();
  });

  it("agrega fotografías adicionales al estudio, la IA las describe y se guardan con su título", async () => {
    const study = make("ESTUDIO_SOCIOECONOMICO", { status: "EN_PROCESO", form: [] });
    let count = 0;
    let stored: ReturnType<typeof file>[] = [];
    const fetchMock = mockApi({
      [`GET ${LIST_URL}`]: { body: list([study]) },
      [`GET ${FILES_URL}`]: () => ({ body: stored }),
      [`POST ${FILES_URL}`]: ({ url }) => {
        count += 1;
        const name = new URL(url, "http://prueba").searchParams.get("filename") ?? "";
        const photo = file(`p${count}`, name, "ESTUDIO_SOCIOECONOMICO");
        stored = [...stored, photo];
        return { status: 201, body: { file: photo, duplicates: [] } };
      },
      ["POST /api/v1/assessments/e-ESTUDIO_SOCIOECONOMICO/photo-descriptions"]: {
        body: { description: "Patio con piso de cemento y un lavadero.", unclear: [] },
      },
      ["PUT /api/v1/assessments/e-ESTUDIO_SOCIOECONOMICO"]: { body: { ...study, version: 2 } },
    });
    const user = userEvent.setup({ applyAccept: false });
    renderSection();
    await user.click(await screen.findByRole("button", { name: /Estudio socioeconómico/ }));
    const extra = within(await screen.findByRole("group", { name: "Fotografías adicionales" }));
    // Varias de una vez; lo que no es foto se rechaza y se avisa.
    await user.upload(extra.getByLabelText("Agregar fotografías adicionales"), [
      new File(["a"], "patio.jpg"),
      new File(["b"], "cocina.png"),
      new File(["c"], "notas.pdf"),
    ]);
    expect((await extra.findByRole("alert")).textContent).toContain("notas.pdf: solo se aceptan fotos JPG o PNG.");
    expect(extra.getAllByRole("listitem")).toHaveLength(2);
    expect(extra.getByRole("link", { name: "1. patio.jpg" })).toBeTruthy();

    await user.type(extra.getByLabelText("Título de la fotografía adicional 1"), "Patio");
    await user.click(extra.getByRole("button", { name: "Describir con IA: fotografía adicional 1" }));
    const description = (await extra.findByLabelText(
      "Descripción de lo que se observa: fotografía adicional 1",
    )) as HTMLTextAreaElement;
    await waitFor(() => expect(description.value).toBe("Patio con piso de cemento y un lavadero."));
    expect(sent(fetchMock, "POST", "/photo-descriptions")).toEqual({ file_id: "p1", field_id: null, title: "Patio" });
    expect(extra.getByText("Descripción propuesta por la IA")).toBeTruthy();
    // La segunda se describe a mano y la primera se conserva como propuesta de la IA.
    await user.type(extra.getByLabelText("Descripción de lo que se observa: fotografía adicional 2"), "Cocina con estufa.");
    await user.click(screen.getByRole("button", { name: "Guardar" }));
    await screen.findByText("Evaluación guardada.");
    expect(sent(fetchMock, "PUT", "/e-ESTUDIO_SOCIOECONOMICO").data.extra_photos).toEqual([
      { file_id: "p1", title: "Patio", description: "Patio con piso de cemento y un lavadero.", description_source: "IA" },
      { file_id: "p2", title: "", description: "Cocina con estufa.", description_source: "MANUAL" },
    ]);
    await user.click(extra.getByRole("button", { name: "Quitar la fotografía adicional 2" }));
    expect(extra.getAllByRole("listitem")).toHaveLength(1);
  });

  it("en psicometría la IA resume, explica lo que dice el reporte y propone preguntas", async () => {
    const test = make("PSICOMETRIA", {
      status: "PRESENTADA",
      file_id: "f3",
      data: { instrument: "Prueba Inventada" },
      ai_summary: {
        resumen: "El reporte documenta dos escalas.",
        escalas: ["Soborno: 3 de 5 · «Tendencia media a presentar la conducta» · lectura intermedia"],
        revisar_en_el_reporte: ["Fraude: la gráfica se leyó como 4 de 5, pero el texto dice «Tendencia baja»."],
        puntos_de_atencion: ["Soborno: el reporte la ubica en 3 de 5 (lectura intermedia)."],
        resultados_documentados: ["Razonamiento: percentil 70"],
        interpretacion: ["Razonamiento, percentil 70: el reporte lo describe como por encima del promedio."],
        datos_no_legibles: [],
        advertencias: [],
        preguntas_para_la_siguiente_etapa: ["Cuéntame de un problema de nómina que resolviste paso a paso."],
      },
      ai_summary_at: "2026-11-15T18:00:00Z",
    });
    mockApi({
      [`GET ${LIST_URL}`]: { body: list([test]) },
      [`GET ${FILES_URL}`]: { body: [file("f3", "reporte.pdf", "PSICOMETRIA")] },
    });
    const user = userEvent.setup();
    renderSection();
    await user.click(await screen.findByRole("button", { name: /Prueba psicométrica/ }));
    expect(screen.getByRole("button", { name: "Resumir e interpretar con IA" })).toBeTruthy();
    expect(screen.getByLabelText("Adjuntar el documento")).toBeTruthy();
    const panel = within(screen.getByRole("region", { name: "Resumen de la IA" }));
    expect(panel.getByText("Qué significa, según el reporte")).toBeTruthy();
    expect(panel.getByText(/por encima del promedio/)).toBeTruthy();
    expect(panel.getByText("Preguntas para la siguiente etapa")).toBeTruthy();
    // Las escalas leídas de la gráfica, lo que pide atención y lo que hay que revisar.
    expect(panel.getByText("Escalas leídas del reporte")).toBeTruthy();
    expect(panel.getByText("Puntos de atención (generado por IA)")).toBeTruthy();
    expect(panel.getByText(/Soborno: el reporte la ubica en 3 de 5/)).toBeTruthy();
    expect(panel.getByText("Revisar en el reporte: el número y el texto no coinciden")).toBeTruthy();
    expect(panel.getByText(/Generado por IA .*No es un diagnóstico ni una decisión/)).toBeTruthy();
    expect(panel.getByText(/se lee de la gráfica del reporte: compruébalo contra el documento/)).toBeTruthy();
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

  it("adjunta una foto al estudio y la IA propone una descripción que la persona revisa", async () => {
    const study = make("ESTUDIO_SOCIOECONOMICO", {
      status: "EN_PROCESO",
      form: [{ title: "Soporte fotográfico", fields: [
        { ...FIELD, id: "fachada", label: "Fotografía: fachada de la vivienda", type: "DOCUMENTO" },
        { ...FIELD, id: "firmado", label: "Formato firmado (escaneado)", type: "DOCUMENTO" },
      ] }],
    });
    let files = [file("f9", "estudio escaneado.pdf", "ESTUDIO_SOCIOECONOMICO")];
    const fetchMock = mockApi({
      [`GET ${LIST_URL}`]: { body: list([study]) },
      [`GET ${FILES_URL}`]: () => ({ body: files }),
      [`POST ${FILES_URL}`]: () => {
        const photo = file("f10", "fachada.jpg", "ESTUDIO_SOCIOECONOMICO");
        files = [...files, photo];
        return { status: 201, body: { file: photo, duplicates: [] } };
      },
      ["POST /api/v1/assessments/e-ESTUDIO_SOCIOECONOMICO/photo-descriptions"]: {
        body: { description: "Fachada de dos niveles con portón metálico.", unclear: ["El número exterior"] },
      },
      ["PUT /api/v1/assessments/e-ESTUDIO_SOCIOECONOMICO"]: { body: { ...study, version: 2 } },
    });
    const user = userEvent.setup();
    renderSection();
    await user.click(await screen.findByRole("button", { name: /Estudio socioeconómico/ }));
    // Sin fotografía elegida no hay nada que describir.
    expect(screen.queryByRole("button", { name: /Describir con IA/ })).toBeNull();
    // Un PDF elegido como documento tampoco ofrece la descripción.
    await user.selectOptions(await screen.findByLabelText("Formato firmado (escaneado)"), "f9");
    expect(screen.queryByRole("button", { name: /Describir con IA/ })).toBeNull();

    const picker = screen.getByLabelText("Adjuntar archivo: Fotografía: fachada de la vivienda");
    await user.upload(picker, new File(["foto"], "fachada.jpg", { type: "image/jpeg" }));
    expect(await screen.findByText(/Archivo adjuntado/)).toBeTruthy();
    const upload = fetchMock.mock.calls.find(([url, init]) => String(url).includes("/files?") && init?.method === "POST");
    expect(String(upload?.[0])).toContain("document_type=ESTUDIO_SOCIOECONOMICO");
    expect((screen.getByLabelText("Fotografía: fachada de la vivienda") as HTMLSelectElement).value).toBe("f10");

    await user.click(screen.getByRole("button", { name: "Describir con IA: Fotografía: fachada de la vivienda" }));
    const description = (await screen.findByLabelText(
      "Descripción de lo que se observa: Fotografía: fachada de la vivienda",
    )) as HTMLTextAreaElement;
    expect(description.value).toBe("Fachada de dos niveles con portón metálico.");
    expect(screen.getByText("Descripción propuesta por la IA")).toBeTruthy();
    expect(screen.getByText("La IA no distingue: El número exterior.")).toBeTruthy();
    expect(sent(fetchMock, "POST", "/photo-descriptions")).toEqual({ file_id: "f10", field_id: "fachada", title: null });
    expect(fetchMock.mock.calls.some(([, init]) => init?.method === "PUT")).toBe(false);

    // La persona corrige el texto: deja de contar como propuesto por la IA.
    await user.type(description, " Pintura clara.");
    expect(screen.queryByText("Descripción propuesta por la IA")).toBeNull();
    await user.click(screen.getByRole("button", { name: "Guardar" }));
    await screen.findByText("Evaluación guardada.");
    expect(sent(fetchMock, "PUT", "/e-ESTUDIO_SOCIOECONOMICO").data.answers).toEqual({
      fachada: {
        value: "f10",
        verified: false,
        source: "MANUAL",
        description: "Fachada de dos niveles con portón metálico. Pintura clara.",
        description_source: "MANUAL",
      },
      firmado: { value: "f9", verified: false, source: "MANUAL" },
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
    expect(await screen.findByText(/prueba psicométrica, que tu acceso no permite consultar/)).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Registrar evaluación" })).toBeNull();
    await user.click(screen.getByRole("button", { name: /Entrevista con gerente · Gerente Ficticio/ }));
    const summary = screen.getByRole("region", { name: "Resumen de la IA" });
    expect(within(summary).getByText("Competencias observadas")).toBeTruthy();
    expect(within(summary).getByText(/No es un diagnóstico ni una decisión/)).toBeTruthy();
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
      result: {
        hechos_documentados: ["Analista en Uno SA (CV)"],
        discrepancias_verificables: ["CV: 2 años; llamada: 3 años"],
        informacion_pendiente: [],
        puntos_de_atencion: ["CV: criterio C2 en nivel 1 (CV)"],
        contrastes: ["Antigüedad: 2 años (CV); 3 años (llamada 1). Conclusión: pesa más el CV."],
        veredicto: "RECOMENDABLE_CON_RESERVAS",
        razones: ["Cumple la experiencia (CV)", "Antigüedad por aclarar (llamada 1)"],
        conclusion: "Cumple lo indispensable.\n\nConviene aclarar la antigüedad.",
      },
      sources: ["CV", "1 entrevistas"],
      includes_psychometrics: false,
      includes_study: false,
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
    expect(rows[1].textContent).toContain("tu acceso no permite consultarla");
    expect(rows[2].textContent).toContain("Etapa actual");
    expect(rows[3].textContent).toContain("Por venir");
    expect(screen.getByText(/síntesis más reciente que tu acceso no permite consultar/)).toBeTruthy();

    await user.click(screen.getByRole("button", { name: "Generar síntesis" }));
    const panel = await screen.findByRole("region", { name: "Síntesis" });
    // La recomendación va primero, en palabras y marcada como generada por IA.
    const advice = within(within(panel).getByRole("region", { name: "Recomendación de la IA" }));
    expect(advice.getByText("Recomendable con reservas")).toBeTruthy();
    expect(advice.getByText(/Generado por IA\. No es una decisión/)).toBeTruthy();
    expect(advice.getByText("Conviene aclarar la antigüedad.")).toBeTruthy();
    expect(advice.getByText("Antigüedad por aclarar (llamada 1)")).toBeTruthy();
    expect(within(panel).getByText("Puntos de atención")).toBeTruthy();
    expect(within(panel).getByText("Contrastes entre fuentes y conclusión de la IA")).toBeTruthy();
    expect(within(panel).getByText(/Conclusión: pesa más el CV/)).toBeTruthy();
    expect(within(panel).queryByText(/\d+ de 100/)).toBeNull(); // sin puntuación global
    expect(body(fetchMock, "/syntheses")).toEqual({ closing: false });
    expect(within(panel).getByText("Hechos documentados")).toBeTruthy();
    expect(within(panel).getByText("Diferencias por aclarar entre fuentes")).toBeTruthy();
    expect(within(panel).queryByText("Información pendiente")).toBeNull();
    expect(within(panel).getByText(/fuentes: CV, 1 entrevistas/)).toBeTruthy();
    expect(fetchMock.mock.calls.some(([, init]) => init?.method === "POST")).toBe(true);
  });

  it("en una postulación cerrada pide y muestra el análisis de cierre", async () => {
    const closing = {
      id: "x9",
      created_at: "2026-11-12T19:00:00Z",
      created_by_name: "Reclutadora de Prueba",
      result: {
        tipo: "CIERRE",
        etapa: "Entrevista con gerente",
        resultado: "No contratado",
        motivo: "No viable: no acepta el horario",
        analisis_de_cierre: "Llegó hasta la entrevista.\n\nEl expediente no documenta este motivo.",
        avance_por_etapa: ["CV: tres años en nómina."],
        puntos_de_atencion: ["CV: sin evidencia de finiquitos (CV)"],
        informacion_pendiente: [],
      },
      sources: ["CV"],
      includes_psychometrics: false,
      includes_study: false,
    };
    let created = false;
    const fetchMock = mockApi({
      ["GET /api/v1/applications/a1/calls"]: { body: [] },
      [`GET ${LIST_URL}`]: { body: list([]) },
      ["GET /api/v1/applications/a1/syntheses"]: () => ({ body: { latest: created ? closing : null, total: created ? 1 : 0, hidden: false } }),
      ["POST /api/v1/applications/a1/syntheses"]: () => {
        created = true;
        return { status: 201, body: closing };
      },
    });
    const closed = { ...detail, application: { ...detail.application, status: "DESCARTADA" } } as ApplicationDetail;
    const user = userEvent.setup();
    renderApp(<DossierSection detail={closed} canEdit />, { session: makeUser() });
    await user.click(await screen.findByRole("button", { name: "Generar análisis de cierre" }));
    const panel = await screen.findByRole("region", { name: "Síntesis" });
    const analysis = within(within(panel).getByRole("region", { name: "Análisis de cierre" }));
    expect(analysis.getByText("Entrevista con gerente")).toBeTruthy();
    expect(analysis.getByText("No viable: no acepta el horario")).toBeTruthy();
    expect(analysis.getByText("El expediente no documenta este motivo.")).toBeTruthy();
    expect(analysis.getByText(/La decisión, la etapa y el motivo los registró una persona/)).toBeTruthy();
    // Un cierre no lleva recomendación: la decisión ya está tomada.
    expect(within(panel).queryByRole("region", { name: "Recomendación de la IA" })).toBeNull();
    expect(within(panel).getByText("Puntos de atención")).toBeTruthy();
    expect(body(fetchMock, "/syntheses")).toEqual({ closing: true });
  });

  const makeSynthesis = (id: string, at: string, result: Record<string, string | string[]>) => ({
    id,
    created_at: at,
    created_by_name: "Reclutadora de Prueba",
    result,
    sources: ["CV"],
    includes_psychometrics: false,
    includes_study: false,
  });

  it("muestra las preguntas sugeridas y deja consultar las síntesis anteriores", async () => {
    const recent = makeSynthesis("x2", "2026-11-12T19:00:00Z", {
      hechos_documentados: ["Confirmó su motivo de salida"],
      preguntas_sugeridas: ["¿Qué sistema de nómina usabas a diario?"],
      coincidencias_entre_fuentes: ["El CV y la llamada coinciden en los años en nómina (CV, llamada 1)"],
      avance_por_etapa: ["Llamada: confirma los años del CV y añade el tamaño de la nómina."],
    });
    const older = makeSynthesis("x1", "2026-11-11T19:00:00Z", { hechos_documentados: ["Analista en Uno SA (CV)"] });
    const fetchMock = mockApi({
      ["GET /api/v1/applications/a1/calls"]: { body: [] },
      [`GET ${LIST_URL}`]: { body: list([]) },
      ["GET /api/v1/applications/a1/syntheses"]: { body: { latest: recent, total: 2, history: [recent, older], hidden: false } },
    });
    const user = userEvent.setup();
    renderApp(<DossierSection detail={detail} canEdit />, { session: makeUser() });
    const panel = await screen.findByRole("region", { name: "Síntesis" });
    expect(within(panel).getByText("Preguntas sugeridas para la siguiente etapa")).toBeTruthy();
    expect(within(panel).getByText("¿Qué sistema de nómina usabas a diario?")).toBeTruthy();
    // La relación entre etapas: primero qué aportó cada una, y las coincidencias junto a las diferencias.
    const titles = Array.from(panel.querySelectorAll("p.font-medium")).map((node) => node.textContent);
    expect(titles).toEqual([
      "Qué aportó cada etapa frente a las anteriores",
      "Hechos documentados",
      "Coincidencias entre fuentes",
      "Preguntas sugeridas para la siguiente etapa",
    ]);
    expect(within(panel).getByText(/confirma los años del CV/)).toBeTruthy();

    const picker = screen.getByLabelText("Síntesis guardadas (2)") as HTMLSelectElement;
    expect(picker.options[0].textContent).toContain("(la más reciente)");
    await user.selectOptions(picker, "x1");
    expect(within(panel).getByText("Analista en Uno SA (CV)")).toBeTruthy();
    expect(within(panel).getByText(/Estás viendo una síntesis anterior/)).toBeTruthy();
    expect(within(panel).queryByText("Preguntas sugeridas para la siguiente etapa")).toBeNull();
    await user.selectOptions(picker, "x2");
    expect(within(panel).queryByText(/Estás viendo una síntesis anterior/)).toBeNull();
    // Abrir el expediente y consultar el historial no pide nada a la IA.
    expect(fetchMock.mock.calls.some(([, init]) => init?.method === "POST")).toBe(false);
  });

  it("actualiza la síntesis sola cuando se registra un resultado, no al abrir el expediente", async () => {
    let interview = make("ENTREVISTA", { status: "PROGRAMADA", data: { interviewer: "G" } });
    let latest: ReturnType<typeof makeSynthesis> | null = null;
    let fail = false;
    const fetchMock = mockApi({
      ["GET /api/v1/applications/a1/calls"]: { body: [] },
      [`GET ${LIST_URL}`]: () => ({ body: list([interview]) }),
      ["GET /api/v1/applications/a1/syntheses"]: () => ({
        body: { latest, total: latest ? 1 : 0, history: latest ? [latest] : [], hidden: false },
      }),
      ["POST /api/v1/applications/a1/syntheses"]: () => {
        if (fail) return { status: 422, body: { detail: "No hay un modelo asignado a la síntesis." } };
        latest = makeSynthesis("x1", "2026-11-12T19:00:00Z", { observaciones_humanas: ["Entrevista realizada"] });
        return { status: 201, body: latest };
      },
    });
    const posts = () => fetchMock.mock.calls.filter(([url, init]) => String(url).endsWith("/syntheses") && init?.method === "POST").length;
    const { queryClient } = renderApp(<DossierSection detail={detail} canEdit />, { session: makeUser() });
    const stages = within(screen.getByRole("list", { name: "Etapas y fuentes" }));
    expect(await stages.findByText(/Entrevista con gerente: Programada/)).toBeTruthy();
    expect(posts()).toBe(0);

    // Guardar un borrador o reprogramar no cuenta: la entrevista sigue sin resultado.
    interview = { ...interview, version: 2 };
    await queryClient.invalidateQueries({ queryKey: ["application", "a1", "assessments"] });
    expect(posts()).toBe(0);

    // La entrevista queda realizada: la síntesis se genera sola.
    interview = { ...interview, status: "REALIZADA" };
    await queryClient.invalidateQueries({ queryKey: ["application", "a1", "assessments"] });
    expect(await screen.findByText("La síntesis se actualizó sola con lo que acabas de registrar.")).toBeTruthy();
    expect(within(await screen.findByRole("region", { name: "Síntesis" })).getByText("Entrevista realizada")).toBeTruthy();
    expect(posts()).toBe(1);

    // Si la IA no está disponible, se avisa sin estorbar y queda el botón.
    fail = true;
    interview = { ...interview, status: "NO_APLICA" };
    await queryClient.invalidateQueries({ queryKey: ["application", "a1", "assessments"] });
    expect((await screen.findByRole("alert")).textContent).toContain("No se pudo actualizar la síntesis sola");
    expect(posts()).toBe(2);
    expect(screen.getByRole("button", { name: "Generar una síntesis nueva" })).toBeTruthy();
  });

  it("no actualiza la síntesis sola para quien solo puede leer", async () => {
    let interview = make("ENTREVISTA", { status: "PROGRAMADA", data: { interviewer: "G" } });
    const fetchMock = mockApi({
      ["GET /api/v1/applications/a1/calls"]: { body: [] },
      [`GET ${LIST_URL}`]: () => ({ body: list([interview]) }),
      ["GET /api/v1/applications/a1/syntheses"]: { body: { latest: null, total: 0, history: [], hidden: false } },
    });
    const { queryClient } = renderApp(<DossierSection detail={detail} canEdit={false} />, { session: makeUser() });
    const stages = within(screen.getByRole("list", { name: "Etapas y fuentes" }));
    expect(await stages.findByText(/Entrevista con gerente: Programada/)).toBeTruthy();
    interview = { ...interview, status: "REALIZADA" };
    await queryClient.invalidateQueries({ queryKey: ["application", "a1", "assessments"] });
    expect(await stages.findByText(/Entrevista con gerente: Realizada/)).toBeTruthy();
    expect(fetchMock.mock.calls.some(([, init]) => init?.method === "POST")).toBe(false);
  });
});
