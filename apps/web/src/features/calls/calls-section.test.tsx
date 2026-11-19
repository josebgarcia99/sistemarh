import { cleanup, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { Bank, Call, CallQuestion } from "@/lib/api/calls";
import { makeUser, mockApi, renderApp } from "@/test/helpers";
import { CallsSection } from "./calls-section";

const CALLS_URL = "/api/v1/applications/a1/calls";
const BANK: Bank = {
  id: "b1",
  name: "Banco de nómina",
  description: null,
  owner_name: "Reclutadora de Prueba",
  mine: true,
  can_edit: true,
  shared: false,
  general: false,
  status: "ACTIVO",
  version_number: 1,
  questions: [],
  updated_at: "2026-11-11T18:00:00Z",
};

const GENERAL_BANK: Bank = {
  ...BANK,
  id: "g1",
  name: "Preguntas generales",
  general: true,
  questions: [{ id: "q1", text: "¿Qué nóminas has calculado?", competency: "Nómina", guidance: "Tamaño y periodicidad", origin: "MANUAL" }],
};
const SYSTEMS_BANK: Bank = {
  ...BANK,
  id: "b3",
  name: "Banco de sistemas",
  questions: [
    { id: "q2", text: "¿Cómo validas el IMSS?", competency: "", guidance: "", origin: "MANUAL" },
    { id: "q7", text: "¿Has usado CONTPAQi Nóminas?", competency: "Sistemas", guidance: "Sí o no", origin: "MANUAL" },
  ],
};

function question(id: string, text: string, changes: Partial<CallQuestion> = {}): CallQuestion {
  return {
    id,
    text,
    competency: "",
    guidance: "",
    origin: "MANUAL",
    source: "BANCO",
    general: false,
    bank_id: "b1",
    bank_name: "Banco de nómina",
    original_text: null,
    omitted: false,
    answer: "",
    notes: "",
    not_asked: false,
    ...changes,
  };
}

function makeCall(overrides: Partial<Call> = {}): Call {
  return {
    id: "l1",
    application_id: "a1",
    status: "BORRADOR",
    sources: ["Preguntas generales", "Banco de nómina"],
    called_at: "2026-11-11T18:00:00Z",
    created_by_name: "Reclutadora de Prueba",
    notes: "",
    questions: [
      question("q1", "¿Qué nóminas has calculado?", { competency: "Nómina", guidance: "Tamaño y periodicidad", source: "GENERAL", general: true, bank_id: "g1", bank_name: "Preguntas generales" }),
      question("q2", "¿Cómo validas el IMSS?"),
    ],
    analysis: null,
    analysis_at: null,
    closed_at: null,
    ...overrides,
  };
}

/** Lo que la pantalla envía de cada pregunta al guardar. */
const sent = (id: string, text: string, changes: Record<string, unknown> = {}) => ({
  id,
  text,
  competency: "",
  guidance: "",
  omitted: false,
  bank_id: "b1",
  ...changes,
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("CallsSection", () => {
  it("abre una llamada con las generales y los bancos elegidos, captura respuestas y la cierra", async () => {
    let calls: Call[] = [];
    const fetchMock = mockApi({
      [`GET ${CALLS_URL}`]: () => ({ body: calls }),
      ["GET /api/v1/question-banks"]: { body: [BANK, GENERAL_BANK, { ...BANK, id: "b2", name: "Archivado", status: "ARCHIVADO" }] },
      [`POST ${CALLS_URL}`]: () => {
        calls = [makeCall()];
        return { status: 201, body: calls[0] };
      },
      ["PUT /api/v1/calls/l1"]: ({ init }) => {
        const sent = JSON.parse(String(init.body));
        calls = [makeCall({ status: sent.close ? "CERRADA" : "BORRADOR" })];
        return { body: calls[0] };
      },
    });
    const user = userEvent.setup();
    renderApp(<CallsSection applicationId="a1" canEdit active />, { session: makeUser() });
    await user.click(await screen.findByRole("button", { name: "Nueva llamada" }));
    // Las generales entran solas; solo se eligen los demás bancos activos.
    expect(await screen.findByText(/Las 1 preguntas generales de la empresa entran solas/)).toBeTruthy();
    const optional = screen.getByRole("group", { name: "Suma también las preguntas de estos bancos (opcional)" });
    expect(within(optional).getAllByRole("checkbox")).toHaveLength(1);
    await user.click(within(optional).getByRole("checkbox", { name: "Banco de nómina · 0 preguntas" }));
    await user.click(screen.getByRole("button", { name: "Abrir llamada" }));
    const post = fetchMock.mock.calls.find(([, init]) => init?.method === "POST");
    expect(JSON.parse(String(post?.[1]?.body))).toEqual({ bank_ids: ["b1"] });

    await user.type(await screen.findByLabelText("Respuesta a la pregunta 1"), "Nómina quincenal de 200 personas");
    await user.click(screen.getAllByRole("checkbox", { name: "No se realizó" })[1]);
    await user.type(screen.getByLabelText("Observaciones generales"), "Llamada de 15 minutos");
    await user.click(screen.getByRole("button", { name: "Cerrar llamada" }));

    expect(await screen.findByText("Cerrada")).toBeTruthy();
    const put = fetchMock.mock.calls.find(([, init]) => init?.method === "PUT");
    expect(JSON.parse(String(put?.[1]?.body))).toEqual({
      answers: [
        { question_id: "q1", answer: "Nómina quincenal de 200 personas", notes: "", not_asked: false },
        { question_id: "q2", answer: "", notes: "", not_asked: true },
      ],
      questions: [
        sent("q1", "¿Qué nóminas has calculado?", { competency: "Nómina", guidance: "Tamaño y periodicidad", bank_id: "g1" }),
        sent("q2", "¿Cómo validas el IMSS?"),
      ],
      notes: "Llamada de 15 minutos",
      close: true,
    });
    // Cerrada: ya no se puede guardar ni cerrar otra vez.
    expect(screen.queryByRole("button", { name: /^Guardar$|Cerrar llamada/ })).toBeNull();
  });

  it("en la llamada se quitan, se redactan distinto y se agregan preguntas, sin tocar los bancos", async () => {
    const analysis = { resumen: "Resumen anterior." };
    let calls: Call[] = [
      makeCall({
        analysis,
        questions: [
          question("q1", "¿Qué nóminas has calculado?", { source: "GENERAL", general: true, bank_id: "g1", bank_name: "Preguntas generales", answer: "Quincenal" }),
          question("q2", "¿Cómo validas el IMSS?"),
          question("q3", "¿Cuál es tu expectativa de sueldo?", { source: "GENERAL", general: true, bank_id: "g1", bank_name: "Preguntas generales", omitted: true }),
        ],
      }),
    ];
    const fetchMock = mockApi({
      [`GET ${CALLS_URL}`]: () => ({ body: calls }),
      ["GET /api/v1/question-banks"]: { body: [GENERAL_BANK, SYSTEMS_BANK] },
      ["PUT /api/v1/calls/l1"]: () => {
        calls = [{ ...calls[0], analysis: null }];
        return { body: calls[0] };
      },
    });
    const user = userEvent.setup();
    renderApp(<CallsSection applicationId="a1" canEdit active />, { session: makeUser() });
    await user.click(await screen.findByRole("button", { name: /Preguntas generales \+ Banco de nómina/ }));

    // Quitar: deja de numerarse y pasa a la lista de quitadas, de donde se puede recuperar.
    const removed = () => within(screen.getByRole("group", { name: "Preguntas quitadas de esta llamada" }));
    expect(removed().getByText("¿Cuál es tu expectativa de sueldo?")).toBeTruthy();
    await user.click(screen.getByRole("button", { name: "Quitar de esta llamada la pregunta 1" }));
    expect(screen.getByText("1. ¿Cómo validas el IMSS?")).toBeTruthy();
    expect(removed().getByText("Quitadas de esta llamada (2)")).toBeTruthy();
    await user.click(removed().getByRole("button", { name: "Volver a incluir: ¿Cuál es tu expectativa de sueldo?" }));
    expect(screen.getByText("2. ¿Cuál es tu expectativa de sueldo?")).toBeTruthy();

    // Cambiar la redacción solo para esta llamada, y poder volver a la del banco.
    await user.click(screen.getByRole("button", { name: "Cambiar la redacción de la pregunta 1" }));
    const wording = screen.getByLabelText("Redacción de la pregunta 1 para esta llamada");
    await user.clear(wording);
    await user.type(wording, "¿Cómo validas IMSS e ISR?");
    expect(screen.getByText("Redacción cambiada")).toBeTruthy();
    expect(screen.getByText("Redacción del banco: «¿Cómo validas el IMSS?»")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Volver a la redacción del banco" })).toBeTruthy();
    await user.click(screen.getByRole("button", { name: "Listo" }));

    // Escribir una pregunta nueva y responderla en el mismo guardado.
    const adding = within(screen.getByRole("group", { name: "Agregar preguntas a esta llamada" }));
    await user.click(adding.getByRole("button", { name: "Escribir una pregunta" }));
    await user.type(adding.getByLabelText("Pregunta nueva"), "¿Puedes trabajar en sitio?");
    await user.type(adding.getByLabelText("Qué se espera de la respuesta (opcional)"), "Sí o no");
    await user.click(adding.getByRole("button", { name: "Agregar a la llamada" }));
    expect(screen.getByText("3. ¿Puedes trabajar en sitio?")).toBeTruthy();
    expect(screen.getByText("Solo de esta llamada")).toBeTruthy();
    await user.type(screen.getByLabelText("Respuesta a la pregunta 3"), "Sí");

    // Tomar preguntas de otro banco: las que ya están no se pueden repetir.
    await user.click(adding.getByRole("button", { name: "Tomar de un banco" }));
    await user.selectOptions(await adding.findByLabelText("Banco"), "b3");
    const offered = within(adding.getByRole("list", { name: "Preguntas de Banco de sistemas" }));
    expect((offered.getByRole("checkbox", { name: "¿Cómo validas el IMSS? (ya está en la llamada)" }) as HTMLInputElement).disabled).toBe(true);
    await user.click(offered.getByRole("checkbox", { name: "¿Has usado CONTPAQi Nóminas?" }));
    await user.click(adding.getByRole("button", { name: "Agregar las elegidas" }));
    expect(screen.getByText("4. ¿Has usado CONTPAQi Nóminas?")).toBeTruthy();
    expect(screen.getByText("Banco de sistemas")).toBeTruthy();

    await user.click(screen.getByRole("button", { name: "Guardar" }));
    // Como cambiaron las preguntas, el análisis anterior se retira y se avisa.
    expect((await screen.findByRole("status")).textContent).toContain("el análisis anterior se retiró");
    const put = fetchMock.mock.calls.find(([, init]) => init?.method === "PUT");
    const body = JSON.parse(String(put?.[1]?.body));
    const written = body.questions[3].id;
    expect(written).toMatch(/^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/);
    expect(body.questions).toEqual([
      sent("q1", "¿Qué nóminas has calculado?", { bank_id: "g1", omitted: true }),
      sent("q2", "¿Cómo validas IMSS e ISR?"),
      sent("q3", "¿Cuál es tu expectativa de sueldo?", { bank_id: "g1" }),
      sent(written, "¿Puedes trabajar en sitio?", { guidance: "Sí o no", bank_id: null }),
      sent("q7", "¿Has usado CONTPAQi Nóminas?", { competency: "Sistemas", guidance: "Sí o no", bank_id: "b3" }),
    ]);
    // Lo anotado en una pregunta quitada se conserva mientras es borrador.
    expect(body.answers).toEqual([
      { question_id: "q1", answer: "Quincenal", notes: "", not_asked: false },
      { question_id: written, answer: "Sí", notes: "", not_asked: false },
    ]);
  });

  it("una llamada cerrada muestra qué preguntas no se usaron, sin poder cambiarlas", async () => {
    const closed = makeCall({
      status: "CERRADA",
      questions: [
        question("q1", "¿Qué nóminas has calculado y con qué sistema?", { original_text: "¿Qué nóminas has calculado?", answer: "Quincenal" }),
        question("q9", "¿Puedes trabajar en sitio?", { source: "LLAMADA", bank_id: null, bank_name: "", answer: "Sí" }),
        question("q3", "¿Cuál es tu expectativa de sueldo?", { source: "GENERAL", general: true, omitted: true }),
      ],
    });
    mockApi({ [`GET ${CALLS_URL}`]: { body: [closed] } });
    const user = userEvent.setup();
    renderApp(<CallsSection applicationId="a1" canEdit active />, { session: makeUser() });
    await user.click(await screen.findByRole("button", { name: /Banco de nómina/ }));
    expect(screen.getByText("1. ¿Qué nóminas has calculado y con qué sistema?")).toBeTruthy();
    expect(screen.getByText("Redacción cambiada")).toBeTruthy();
    expect(screen.getByText("Solo de esta llamada")).toBeTruthy();
    const unused = within(screen.getByRole("group", { name: "Preguntas quitadas de esta llamada" }));
    expect(unused.getByText("No se usaron en esta llamada (1)")).toBeTruthy();
    expect(unused.getByText("¿Cuál es tu expectativa de sueldo?")).toBeTruthy();
    expect(screen.queryByRole("button", { name: /Quitar|Cambiar la redacción|Volver a incluir|Escribir una pregunta/ })).toBeNull();
  });

  it("muestra el análisis de la IA como resumen, sin recomendación", async () => {
    const analysis = {
      resumen: "Describe tres años calculando nómina.",
      evidencias: ["Nómina de 200 personas"],
      discrepancias_verificables: ["El CV indica 2020 a 2022; en la llamada dijo tres años"],
      preguntas_de_seguimiento: [],
      medicion: {
        score: 50,
        valoradas: 1,
        sin_valorar: 0,
        items: [{ question_id: "q1", numero: 1, nivel: "PARCIAL", evidencia: "Nómina de 200 personas" }],
      },
    };
    const closed = makeCall({ status: "CERRADA" });
    let analyzed = false;
    mockApi({
      [`GET ${CALLS_URL}`]: () => ({ body: [analyzed ? { ...closed, analysis } : closed] }),
      ["POST /api/v1/calls/l1/analysis"]: () => {
        analyzed = true;
        return { body: { ...closed, analysis } };
      },
    });
    const user = userEvent.setup();
    renderApp(<CallsSection applicationId="a1" canEdit active />, { session: makeUser() });
    await user.click(await screen.findByRole("button", { name: /Banco de nómina/ }));
    await user.click(screen.getByRole("button", { name: "Analizar con IA" }));
    const panel = await screen.findByRole("region", { name: "Análisis de la IA" });
    expect(within(panel).getByText("Describe tres años calculando nómina.")).toBeTruthy();
    expect(within(panel).getByText("Diferencias por aclarar con el CV")).toBeTruthy();
    expect(within(panel).queryByText("Preguntas de seguimiento")).toBeNull();
    expect(within(panel).getByText(/esa decisión es tuya/)).toBeTruthy();
    // La cobertura: el número lo calcula el sistema y no califica a la persona.
    const coverage = within(within(panel).getByRole("group", { name: "Cobertura de la llamada" }));
    expect(coverage.getByText("Cobertura de la llamada: 50 de 100")).toBeTruthy();
    expect(coverage.getByText(/Pregunta 1: Lo cubre en parte — «Nómina de 200 personas»/)).toBeTruthy();
    expect(coverage.getByText(/No califica a la persona/)).toBeTruthy();
    // Las preguntas generales de la empresa se distinguen de las del banco.
    expect(screen.getAllByText("General")).toHaveLength(1);
  });

  it("con acceso de lectura se consultan las llamadas sin poder abrir ni analizar", async () => {
    mockApi({ [`GET ${CALLS_URL}`]: { body: [makeCall({ status: "CERRADA" })] } });
    const user = userEvent.setup();
    renderApp(<CallsSection applicationId="a1" canEdit={false} active />, { session: makeUser() });
    await user.click(await screen.findByRole("button", { name: /Banco de nómina/ }));
    expect(screen.getByText("1. ¿Qué nóminas has calculado?")).toBeTruthy();
    expect(screen.queryByRole("button", { name: /Nueva llamada|Analizar con IA|Guardar/ })).toBeNull();
  });

  /** Las escrituras a la llamada, en orden, con lo esencial de cada una. */
  const writes = (fetchMock: ReturnType<typeof mockApi>) =>
    fetchMock.mock.calls
      .filter(([, init]) => init?.method === "PUT" || init?.method === "POST")
      .map(([url, init]) => {
        const body = init?.body ? JSON.parse(String(init.body)) : {};
        return {
          route: `${init?.method} ${String(url).split("/").pop()}`,
          autosave: body.autosave === true,
          answer: body.answers?.[0]?.answer as string | undefined,
        };
      });

  /** La llamada tal como queda en el servidor después de recibir un guardado. */
  const stored = (sent: { notes: string; answers: { question_id: string; answer: string }[] }) => {
    const base = makeCall();
    return makeCall({
      notes: sent.notes,
      questions: base.questions.map((item) => ({
        ...item,
        answer: sent.answers.find((answer) => answer.question_id === item.id)?.answer ?? "",
      })),
    });
  };

  it("guarda sola lo que se escribe y comprueba contra el servidor que quedó guardado", async () => {
    let calls = [makeCall()];
    const fetchMock = mockApi({
      [`GET ${CALLS_URL}`]: () => ({ body: calls }),
      ["PUT /api/v1/calls/l1"]: ({ init }) => {
        // El servidor recorta los espacios sobrantes: eso no cuenta como diferencia.
        const sent = JSON.parse(String(init.body));
        calls = [stored({ ...sent, answers: sent.answers.map((a: { answer: string }) => ({ ...a, answer: a.answer.trim() })) })];
        return { body: calls[0] };
      },
    });
    const user = userEvent.setup();
    renderApp(<CallsSection applicationId="a1" canEdit active />, { session: makeUser() });
    await user.click(await screen.findByRole("button", { name: /Banco de nómina/ }));
    const state = await screen.findByLabelText("Estado del guardado");
    expect(state.textContent).toBe("Lo que escribas se guarda solo.");

    await user.type(screen.getByLabelText("Respuesta a la pregunta 1"), "Nómina quincenal ");
    expect(state.textContent).toContain("Cambios sin guardar");
    // A los pocos segundos de dejar de escribir se guarda, marcado como automático, y la
    // pantalla vuelve a leer la llamada del servidor antes de darla por guardada.
    await waitFor(() => expect(state.textContent).toMatch(/^Guardado y comprobado a las /), { timeout: 4000 });
    expect(screen.getByText(/volvió a leer la llamada del servidor y es igual a lo que ves/)).toBeTruthy();
    expect(writes(fetchMock)).toEqual([{ route: "PUT l1", autosave: true, answer: "Nómina quincenal " }]);
    const reads = fetchMock.mock.calls.filter(
      ([url, init]) => String(url).endsWith(CALLS_URL) && (init?.method ?? "GET") === "GET",
    );
    expect(reads.length).toBeGreaterThanOrEqual(2); // la carga inicial y la relectura
  });

  it("si el servidor contesta que guardó pero al releer no coincide, no lo da por guardado", async () => {
    mockApi({
      // El envío «sale bien», pero la llamada que se vuelve a leer sigue sin la respuesta.
      [`GET ${CALLS_URL}`]: { body: [makeCall()] },
      ["PUT /api/v1/calls/l1"]: { body: makeCall() },
    });
    const user = userEvent.setup();
    renderApp(<CallsSection applicationId="a1" canEdit active />, { session: makeUser() });
    await user.click(await screen.findByRole("button", { name: /Banco de nómina/ }));
    const answer = await screen.findByLabelText<HTMLTextAreaElement>("Respuesta a la pregunta 2");
    await user.type(answer, "Concilio contra el SUA");
    const state = screen.getByLabelText("Estado del guardado");
    await waitFor(() => expect(state.textContent).toContain("No se pudo confirmar el guardado"), {
      timeout: 4000,
    });
    expect(state.textContent).toContain("la pregunta 2 no coincide con lo que ves en pantalla");
    expect(state.textContent).toContain("pulsa «Guardar»");
    expect(state.textContent).not.toContain("Guardado y comprobado");
    expect(answer.value).toBe("Concilio contra el SUA");
  });

  it("al plegar la llamada guarda lo que faltaba, y «Analizar con IA» guarda antes de analizar", async () => {
    const fetchMock = mockApi({
      [`GET ${CALLS_URL}`]: { body: [makeCall()] },
      ["PUT /api/v1/calls/l1"]: { body: makeCall() },
      ["POST /api/v1/calls/l1/analysis"]: { body: makeCall() },
    });
    const user = userEvent.setup();
    renderApp(<CallsSection applicationId="a1" canEdit active />, { session: makeUser() });
    const header = await screen.findByRole("button", { name: /Banco de nómina/ });
    await user.click(header);
    await user.type(await screen.findByLabelText("Respuesta a la pregunta 1"), "Uno");
    // La IA analiza lo guardado: primero se guarda lo que hay en pantalla.
    await user.click(screen.getByRole("button", { name: "Analizar con IA" }));
    await screen.findByText("Análisis listo.");
    expect(writes(fetchMock)).toEqual([
      { route: "PUT l1", autosave: false, answer: "Uno" },
      { route: "POST analysis", autosave: false, answer: undefined },
    ]);

    // Se escribe algo más y se pliega la llamada de inmediato: no se pierde.
    await user.type(screen.getByLabelText("Respuesta a la pregunta 1"), " dos");
    await user.click(header);
    await waitFor(() => expect(writes(fetchMock)).toHaveLength(3));
    expect(writes(fetchMock)[2]).toEqual({ route: "PUT l1", autosave: true, answer: "Uno dos" });
    // Al volver a abrirla se ve lo que se escribió, aunque la lista del servidor vaya un
    // paso atrás (aquí siempre responde con la llamada vacía).
    await user.click(header);
    expect((await screen.findByLabelText<HTMLTextAreaElement>("Respuesta a la pregunta 1")).value).toBe("Uno dos");
  });

  it("si el guardado automático falla, lo dice y no borra lo escrito", async () => {
    mockApi({
      [`GET ${CALLS_URL}`]: { body: [makeCall()] },
      ["PUT /api/v1/calls/l1"]: {
        status: 503,
        body: { title: "Sin servicio", status: 503, detail: "El servidor no está disponible.", code: "sin_servicio" },
      },
    });
    const user = userEvent.setup();
    renderApp(<CallsSection applicationId="a1" canEdit active />, { session: makeUser() });
    await user.click(await screen.findByRole("button", { name: /Banco de nómina/ }));
    const answer = (await screen.findByLabelText("Respuesta a la pregunta 1")) as HTMLTextAreaElement;
    await user.type(answer, "Nómina quincenal");
    const state = screen.getByLabelText("Estado del guardado");
    await waitFor(() => expect(state.textContent).toContain("No se pudo guardar automáticamente"), {
      timeout: 4000,
    });
    expect(state.textContent).toContain("El servidor no está disponible.");
    expect(state.textContent).toContain("pulsa «Guardar»");
    expect(answer.value).toBe("Nómina quincenal");
  });
});
