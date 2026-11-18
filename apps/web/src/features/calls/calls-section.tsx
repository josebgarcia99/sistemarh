"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { AiWaitNotice, useAiWait } from "@/components/ui/ai-wait";
import { cardClass, fieldClass, primaryButtonClass, secondaryButtonClass } from "@/components/ui/styles";
import {
  areaClass,
  dateTimeFormat,
  type Feedback,
  FeedbackLine,
  pillClass,
} from "@/features/recruitment/shared";
import {
  ANALYSIS_SECTIONS,
  COVERAGE_LABELS,
  analyzeCall,
  type Bank,
  type Call,
  type CallQuestion,
  listBanks,
  listCalls,
  openCall,
  saveCall,
} from "@/lib/api/calls";
import { describeError } from "@/lib/api/client";

type Props = { applicationId: string; canEdit: boolean; active: boolean };

/** Llamadas telefónicas de una postulación. */
export function CallsSection({ applicationId, canEdit, active }: Props) {
  const queryClient = useQueryClient();
  const queryKey = ["application", applicationId, "calls"];
  const { data: calls, error } = useQuery({
    queryKey,
    queryFn: ({ signal }) => listCalls(applicationId, signal),
  });
  const [choosing, setChoosing] = useState(false);
  const [bankIds, setBankIds] = useState<string[]>([]);
  const [openId, setOpenId] = useState<string | null>(null);
  const [feedback, setFeedback] = useState<Feedback>(null);
  const [busy, setBusy] = useState(false);
  const banksQuery = useQuery({
    queryKey: ["question-banks"],
    queryFn: ({ signal }) => listBanks(signal),
    enabled: choosing,
  });
  const banks = (banksQuery.data ?? []).filter((bank) => bank.status === "ACTIVO");
  // Las generales de la empresa entran solas; los demás bancos se eligen.
  const generalCount = banks
    .filter((bank) => bank.general)
    .reduce((total, bank) => total + bank.questions.length, 0);
  const optional = banks.filter((bank) => !bank.general);

  async function start() {
    setBusy(true);
    setFeedback(null);
    try {
      const call = await openCall(applicationId, bankIds);
      await queryClient.invalidateQueries({ queryKey });
      setOpenId(call.id);
      setChoosing(false);
      setBankIds([]);
    } catch (caught) {
      setFeedback({ kind: "error", text: describeError(caught) });
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className={`${cardClass} flex flex-col gap-4`} aria-labelledby="calls-title">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 id="calls-title" className="text-xl font-medium">
          Llamadas telefónicas
        </h2>
        {canEdit && active && !choosing && (
          <button type="button" className={secondaryButtonClass} onClick={() => setChoosing(true)}>
            Nueva llamada
          </button>
        )}
      </div>
      {error && (
        <p role="alert" className="text-accent-red-ink">
          {describeError(error)}
        </p>
      )}
      {choosing && (
        <div className="flex flex-col gap-3 rounded-3xl bg-surface p-5">
          <p>
            {generalCount > 0
              ? `Las ${generalCount} preguntas generales de la empresa entran solas.`
              : "Todavía no hay preguntas generales de la empresa (se crean en «Bancos»)."}{" "}
            Ya en la llamada podrás quitar las que no apliquen, cambiar su redacción, sumar
            preguntas de otros bancos o escribir nuevas.
          </p>
          <fieldset className="flex flex-col gap-2">
            <legend className="text-sm text-ink-muted">
              Suma también las preguntas de estos bancos (opcional)
            </legend>
            {banksQuery.data && optional.length === 0 && (
              <p className="text-ink-muted">No tienes otros bancos activos. Se crean en «Bancos».</p>
            )}
            {optional.map((bank) => (
              <label key={bank.id} className="flex items-center gap-2">
                <input
                  type="checkbox"
                  className="size-5 accent-ink"
                  checked={bankIds.includes(bank.id)}
                  onChange={(event) =>
                    setBankIds(
                      event.target.checked
                        ? [...bankIds, bank.id]
                        : bankIds.filter((id) => id !== bank.id),
                    )
                  }
                />
                {bank.name} · {bank.questions.length} preguntas
              </label>
            ))}
          </fieldset>
          <FeedbackLine feedback={feedback} />
          <div className="flex flex-wrap gap-3">
            <button
              type="button"
              className={primaryButtonClass}
              disabled={busy || !banksQuery.data}
              onClick={start}
            >
              Abrir llamada
            </button>
            <button type="button" className={secondaryButtonClass} onClick={() => setChoosing(false)}>
              Cancelar
            </button>
          </div>
        </div>
      )}
      {calls && calls.length === 0 && !choosing && (
        <p className="text-ink-muted">Todavía no hay llamadas registradas.</p>
      )}
      <ul aria-label="Llamadas" className="flex flex-col gap-3">
        {(calls ?? []).map((call) => (
          <li key={call.id} className="rounded-3xl bg-surface p-5">
            <button
              type="button"
              aria-expanded={openId === call.id}
              className="flex w-full flex-wrap items-center gap-3 text-left"
              onClick={() => setOpenId(openId === call.id ? null : call.id)}
            >
              <span className="flex-[1_1_200px] font-medium">
                {dateTimeFormat.format(new Date(call.called_at))} ·{" "}
                {call.sources.join(" + ") || "Sin preguntas todavía"}
              </span>
              <span
                className={`${pillClass} ${
                  call.status === "CERRADA" ? "bg-ink text-white" : "bg-neutral-soft text-neutral-ink"
                }`}
              >
                {call.status === "CERRADA" ? "Cerrada" : "Borrador"}
              </span>
              <span className="text-sm text-ink-muted">{call.created_by_name ?? ""}</span>
            </button>
            {openId === call.id && (
              <CallEditor
                key={`${call.id}-${call.status}`}
                call={call}
                canEdit={canEdit}
                onChanged={() => queryClient.invalidateQueries({ queryKey })}
              />
            )}
          </li>
        ))}
      </ul>
    </section>
  );
}

/** Tope de preguntas de una llamada, contando las quitadas (lo valida también el servidor). */
const MAX_CALL_QUESTIONS = 80;
const smallButtonClass = `${secondaryButtonClass} text-sm`;

/** Una pregunta de la llamada mientras se edita, con lo capturado en ella. */
type Item = {
  id: string;
  text: string;
  competency: string;
  guidance: string;
  source: CallQuestion["source"];
  bankId: string | null;
  bankName: string;
  /** Redacción con la que vino del banco; sirve para marcar el cambio y deshacerlo. */
  base: string | null;
  omitted: boolean;
  answer: string;
  notes: string;
  notAsked: boolean;
};

function toItem(question: CallQuestion): Item {
  return {
    id: question.id,
    text: question.text,
    competency: question.competency,
    guidance: question.guidance,
    source: question.source,
    bankId: question.bank_id,
    bankName: question.bank_name,
    base: question.source === "LLAMADA" ? null : (question.original_text ?? question.text),
    omitted: question.omitted,
    answer: question.answer,
    notes: question.notes,
    notAsked: question.not_asked,
  };
}

/** Identificador para una pregunta escrita aquí: así su respuesta viaja en el mismo guardado. */
function newId(): string {
  if (typeof crypto.randomUUID === "function") return crypto.randomUUID();
  const bytes = crypto.getRandomValues(new Uint8Array(16));
  bytes[6] = (bytes[6] & 0x0f) | 0x40;
  bytes[8] = (bytes[8] & 0x3f) | 0x80;
  const hex = [...bytes].map((value) => value.toString(16).padStart(2, "0")).join("");
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
}

const reworded = (item: Item) => item.base !== null && item.text.trim() !== item.base;

function SourcePills({ item }: { item: Item }) {
  return (
    <>
      <span className={`${pillClass} ml-2 bg-neutral-soft text-neutral-ink`}>
        {item.source === "GENERAL" ? "General" : item.source === "LLAMADA" ? "Solo de esta llamada" : item.bankName}
      </span>
      {reworded(item) && (
        <span className={`${pillClass} ml-2 bg-accent-blue-soft text-accent-blue-ink`}>
          Redacción cambiada
        </span>
      )}
    </>
  );
}

function CallEditor({
  call,
  canEdit,
  onChanged,
}: {
  call: Call;
  canEdit: boolean;
  onChanged: () => Promise<void>;
}) {
  const editable = canEdit && call.status === "BORRADOR";
  const [items, setItems] = useState<Item[]>(() => call.questions.map(toItem));
  const [editingId, setEditingId] = useState<string | null>(null);
  const [notes, setNotes] = useState(call.notes);
  const [feedback, setFeedback] = useState<Feedback>(null);
  const [busy, setBusy] = useState(false);
  const aiWait = useAiWait();
  const active = items.filter((item) => !item.omitted);
  const removed = items.filter((item) => item.omitted);
  const change = (id: string, patch: Partial<Item>) =>
    setItems(items.map((item) => (item.id === id ? { ...item, ...patch } : item)));

  async function run(action: () => Promise<string | void>, message: string) {
    setBusy(true);
    setFeedback(null);
    try {
      const other = await action();
      await onChanged();
      setFeedback({ kind: "ok", text: other || message });
    } catch (caught) {
      setFeedback({ kind: "error", text: describeError(caught) });
    } finally {
      setBusy(false);
    }
  }
  async function save(close: boolean) {
    const saved = await saveCall(call.id, {
      answers: items
        .filter((item) => item.answer.trim() || item.notes.trim() || item.notAsked)
        .map((item) => ({
          question_id: item.id,
          answer: item.answer,
          notes: item.notes,
          not_asked: item.notAsked,
        })),
      questions: items.map((item) => ({
        id: item.id,
        text: item.text,
        competency: item.competency,
        guidance: item.guidance,
        omitted: item.omitted,
        bank_id: item.bankId,
      })),
      notes,
      close,
    });
    setEditingId(null);
    // El análisis numera las preguntas: si cambiaron, el servidor lo retira.
    if (call.analysis && !saved.analysis) {
      return "Llamada guardada. Como cambiaron las preguntas, el análisis anterior se retiró: vuelve a pedirlo.";
    }
  }
  function add(extra: Item[]) {
    if (items.length + extra.length > MAX_CALL_QUESTIONS) {
      return setFeedback({
        kind: "error",
        text: `Una llamada admite como máximo ${MAX_CALL_QUESTIONS} preguntas, contando las quitadas.`,
      });
    }
    setFeedback(null);
    setItems([...items, ...extra]);
  }

  return (
    <div className="mt-4 flex flex-col gap-4 border-t border-line pt-4">
      {active.length === 0 && (
        <p className="text-ink-muted">
          {editable
            ? "Esta llamada todavía no tiene preguntas. Agrégalas aquí abajo."
            : "Esta llamada no tiene preguntas."}
        </p>
      )}
      <ol className="flex flex-col gap-4">
        {active.map((item, index) => (
          <li key={item.id} className="flex flex-col gap-2">
            <div className="flex flex-wrap items-start gap-2">
              <p className="flex-[1_1_320px] font-medium">
                {index + 1}. {item.text}
                <SourcePills item={item} />
              </p>
              {editable && (
                <div className="flex flex-wrap gap-2">
                  <button
                    type="button"
                    className={smallButtonClass}
                    aria-label={`Cambiar la redacción de la pregunta ${index + 1}`}
                    aria-expanded={editingId === item.id}
                    onClick={() => setEditingId(editingId === item.id ? null : item.id)}
                  >
                    Cambiar redacción
                  </button>
                  <button
                    type="button"
                    className={smallButtonClass}
                    aria-label={`Quitar de esta llamada la pregunta ${index + 1}`}
                    onClick={() => change(item.id, { omitted: true })}
                  >
                    Quitar
                  </button>
                </div>
              )}
            </div>
            {editable && editingId === item.id && (
              <div className="flex flex-col gap-2 rounded-2xl bg-white/60 p-4">
                <label htmlFor={`text-${call.id}-${item.id}`} className="text-sm text-ink-muted">
                  Redacción de la pregunta {index + 1} para esta llamada
                </label>
                <textarea
                  id={`text-${call.id}-${item.id}`}
                  rows={2}
                  maxLength={1000}
                  value={item.text}
                  onChange={(event) => change(item.id, { text: event.target.value })}
                  className={areaClass}
                />
                {item.source === "LLAMADA" && (
                  <>
                    <label htmlFor={`guidance-${call.id}-${item.id}`} className="text-sm text-ink-muted">
                      Qué se espera de la respuesta a la pregunta {index + 1} (opcional)
                    </label>
                    <input
                      id={`guidance-${call.id}-${item.id}`}
                      maxLength={1000}
                      value={item.guidance}
                      onChange={(event) => change(item.id, { guidance: event.target.value })}
                      className={fieldClass}
                    />
                  </>
                )}
                {reworded(item) && (
                  <p className="text-sm text-ink-muted">Redacción del banco: «{item.base}»</p>
                )}
                <div className="flex flex-wrap gap-2">
                  {reworded(item) && (
                    <button
                      type="button"
                      className={smallButtonClass}
                      onClick={() => change(item.id, { text: item.base ?? item.text })}
                    >
                      Volver a la redacción del banco
                    </button>
                  )}
                  <button type="button" className={smallButtonClass} onClick={() => setEditingId(null)}>
                    Listo
                  </button>
                </div>
                <p className="text-sm text-ink-muted">
                  El cambio vale solo para esta llamada; {item.source === "LLAMADA" ? "la pregunta no está en ningún banco" : "el banco queda igual"}.
                </p>
              </div>
            )}
            {(item.competency || item.guidance) && (
              <p className="text-sm text-ink-muted">
                {[item.competency, item.guidance].filter(Boolean).join(" · ")}
              </p>
            )}
            <label htmlFor={`answer-${call.id}-${item.id}`} className="sr-only">
              Respuesta a la pregunta {index + 1}
            </label>
            <textarea
              id={`answer-${call.id}-${item.id}`}
              rows={3}
              readOnly={!editable}
              disabled={item.notAsked}
              placeholder="Lo que respondió la persona"
              value={item.answer}
              onChange={(event) => change(item.id, { answer: event.target.value })}
              className={areaClass}
            />
            <div className="flex flex-wrap items-center gap-4">
              <label htmlFor={`notes-${call.id}-${item.id}`} className="sr-only">
                Observación sobre la pregunta {index + 1}
              </label>
              <input
                id={`notes-${call.id}-${item.id}`}
                readOnly={!editable}
                placeholder="Observación (opcional)"
                value={item.notes}
                onChange={(event) => change(item.id, { notes: event.target.value })}
                className={`${fieldClass} flex-[1_1_260px]`}
              />
              <label className="flex items-center gap-2">
                <input
                  type="checkbox"
                  className="size-5 accent-ink"
                  disabled={!editable}
                  checked={item.notAsked}
                  onChange={(event) => change(item.id, { notAsked: event.target.checked })}
                />
                No se realizó
              </label>
            </div>
          </li>
        ))}
      </ol>
      {editable && <AddQuestions items={items} onAdd={add} />}
      {removed.length > 0 && (
        <div
          role="group"
          aria-label="Preguntas quitadas de esta llamada"
          className="flex flex-col gap-2 rounded-2xl bg-white/60 p-4"
        >
          <p className="font-medium">
            {editable ? "Quitadas de esta llamada" : "No se usaron en esta llamada"} ({removed.length})
          </p>
          <p className="text-sm text-ink-muted">
            No se preguntan, no se analizan y no cuentan para cerrar la llamada. Los bancos quedan
            igual.
          </p>
          <ul className="flex flex-col gap-2">
            {removed.map((item) => (
              <li key={item.id} className="flex flex-wrap items-center gap-3">
                <span className="flex-[1_1_320px]">
                  {item.text}
                  <SourcePills item={item} />
                </span>
                {editable && (
                  <button
                    type="button"
                    className={smallButtonClass}
                    aria-label={`Volver a incluir: ${item.text}`}
                    onClick={() => change(item.id, { omitted: false })}
                  >
                    Volver a incluir
                  </button>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}
      <div className="flex flex-col gap-2">
        <label htmlFor={`call-notes-${call.id}`} className="text-sm text-ink-muted">
          Observaciones generales
        </label>
        <textarea
          id={`call-notes-${call.id}`}
          rows={2}
          readOnly={!editable}
          value={notes}
          onChange={(event) => setNotes(event.target.value)}
          className={areaClass}
        />
      </div>
      <FeedbackLine feedback={feedback} />
      {canEdit && (
        <div className="flex flex-wrap gap-3">
          {editable && (
            <>
              <button
                type="button"
                className={primaryButtonClass}
                disabled={busy}
                onClick={() => run(() => save(false), "Llamada guardada.")}
              >
                Guardar
              </button>
              <button
                type="button"
                className={secondaryButtonClass}
                disabled={busy}
                onClick={() => run(() => save(true), "Llamada cerrada.")}
              >
                Cerrar llamada
              </button>
            </>
          )}
          <button
            type="button"
            className={secondaryButtonClass}
            disabled={busy}
            onClick={() =>
              run(async () => {
                await aiWait.run(() => analyzeCall(call.id));
              }, "Análisis listo.")
            }
          >
            {busy ? "Trabajando…" : "Analizar con IA"}
          </button>
        </div>
      )}
      <AiWaitNotice wait={aiWait} />
      {editable && (
        <p className="text-sm text-ink-muted">
          Guarda antes de analizar: la IA trabaja con lo último guardado, también en las preguntas
          que quitaste, cambiaste o agregaste. Al cerrar, la llamada ya no se puede modificar.
        </p>
      )}
      {call.analysis && (
        <section aria-label="Análisis de la IA" className="flex flex-col gap-3 rounded-3xl bg-white/60 p-5">
          <h3 className="text-lg font-medium">Análisis de la IA</h3>
          <p className="text-sm text-ink-muted">
            Resume lo anotado en la llamada. No evalúa el tono ni la sinceridad y no recomienda
            avanzar o descartar: esa decisión es tuya.
          </p>
          {call.analysis.resumen && <p>{call.analysis.resumen}</p>}
          {call.analysis.medicion && (
            <div aria-label="Cobertura de la llamada" role="group" className="flex flex-col gap-2 rounded-2xl bg-surface p-4">
              <p className="font-medium">
                Cobertura de la llamada:{" "}
                {call.analysis.medicion.score === null
                  ? "sin calcular"
                  : `${call.analysis.medicion.score} de 100`}
              </p>
              <p className="text-sm text-ink-muted">
                Mide qué tanto cubrieron las respuestas lo que se esperaba en{" "}
                {call.analysis.medicion.valoradas} preguntas. La IA propone el nivel de cada una y
                el sistema calcula el número. No califica a la persona.
                {call.analysis.medicion.sin_valorar > 0 &&
                  ` ${call.analysis.medicion.sin_valorar} quedaron sin valorar.`}
              </p>
              <ul className="flex flex-col gap-1 text-sm">
                {call.analysis.medicion.items.map((item) => (
                  <li key={item.question_id}>
                    Pregunta {item.numero}: {COVERAGE_LABELS[item.nivel] ?? item.nivel}
                    {item.evidencia && ` — «${item.evidencia}»`}
                  </li>
                ))}
              </ul>
            </div>
          )}
          {ANALYSIS_SECTIONS.map(([key, label]) => {
            const items = call.analysis?.[key];
            if (!Array.isArray(items) || items.length === 0) return null;
            return (
              <div key={key}>
                <p className="font-medium">{label}</p>
                <ul className="list-disc pl-5">
                  {items.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              </div>
            );
          })}
        </section>
      )}
    </div>
  );
}

/** Sumar preguntas a la llamada: escritas aquí mismo o tomadas de un banco. */
function AddQuestions({ items, onAdd }: { items: Item[]; onAdd: (extra: Item[]) => void }) {
  const [mode, setMode] = useState<"write" | "bank" | null>(null);
  const [text, setText] = useState("");
  const [guidance, setGuidance] = useState("");
  const [bankId, setBankId] = useState("");
  const [chosen, setChosen] = useState<string[]>([]);
  const banksQuery = useQuery({
    queryKey: ["question-banks"],
    queryFn: ({ signal }) => listBanks(signal),
    enabled: mode === "bank",
  });
  const banks = (banksQuery.data ?? []).filter((bank) => bank.status === "ACTIVO");
  const bank: Bank | undefined = banks.find((item) => item.id === bankId) ?? banks[0];
  const inCall = new Map(items.map((item) => [item.id, item]));
  const blank: Pick<Item, "omitted" | "answer" | "notes" | "notAsked"> = {
    omitted: false,
    answer: "",
    notes: "",
    notAsked: false,
  };

  return (
    <div
      role="group"
      aria-label="Agregar preguntas a esta llamada"
      className="flex flex-col gap-3 rounded-2xl bg-white/60 p-4"
    >
      <p className="font-medium">Agregar preguntas a esta llamada</p>
      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          className={smallButtonClass}
          aria-expanded={mode === "write"}
          onClick={() => setMode(mode === "write" ? null : "write")}
        >
          Escribir una pregunta
        </button>
        <button
          type="button"
          className={smallButtonClass}
          aria-expanded={mode === "bank"}
          onClick={() => setMode(mode === "bank" ? null : "bank")}
        >
          Tomar de un banco
        </button>
      </div>
      {mode === "write" && (
        <div className="flex flex-col gap-2">
          <label htmlFor="new-question-text" className="text-sm text-ink-muted">
            Pregunta nueva
          </label>
          <textarea
            id="new-question-text"
            rows={2}
            maxLength={1000}
            value={text}
            onChange={(event) => setText(event.target.value)}
            className={areaClass}
          />
          <label htmlFor="new-question-guidance" className="text-sm text-ink-muted">
            Qué se espera de la respuesta (opcional)
          </label>
          <input
            id="new-question-guidance"
            maxLength={1000}
            value={guidance}
            onChange={(event) => setGuidance(event.target.value)}
            className={fieldClass}
          />
          <div>
            <button
              type="button"
              className={smallButtonClass}
              disabled={!text.trim()}
              onClick={() => {
                onAdd([
                  {
                    ...blank,
                    id: newId(),
                    text: text.trim(),
                    competency: "",
                    guidance: guidance.trim(),
                    source: "LLAMADA",
                    bankId: null,
                    bankName: "",
                    base: null,
                  },
                ]);
                setText("");
                setGuidance("");
              }}
            >
              Agregar a la llamada
            </button>
          </div>
        </div>
      )}
      {mode === "bank" && (
        <div className="flex flex-col gap-2">
          {banksQuery.error && (
            <p role="alert" className="text-accent-red-ink">
              {describeError(banksQuery.error)}
            </p>
          )}
          {banksQuery.data && banks.length === 0 && (
            <p className="text-ink-muted">No tienes bancos activos. Se crean en «Bancos».</p>
          )}
          {bank && (
            <>
              <label htmlFor="add-from-bank" className="text-sm text-ink-muted">
                Banco
              </label>
              <select
                id="add-from-bank"
                className={fieldClass}
                value={bank.id}
                onChange={(event) => {
                  setBankId(event.target.value);
                  setChosen([]);
                }}
              >
                {banks.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.name} · {item.questions.length} preguntas
                  </option>
                ))}
              </select>
              <ul aria-label={`Preguntas de ${bank.name}`} className="flex flex-col gap-2">
                {bank.questions.map((question) => {
                  const present = inCall.get(question.id);
                  return (
                    <li key={question.id}>
                      <label className="flex items-start gap-2">
                        <input
                          type="checkbox"
                          className="mt-1 size-5 shrink-0 accent-ink"
                          disabled={present !== undefined}
                          checked={chosen.includes(question.id)}
                          onChange={(event) =>
                            setChosen(
                              event.target.checked
                                ? [...chosen, question.id]
                                : chosen.filter((id) => id !== question.id),
                            )
                          }
                        />
                        <span>
                          {question.text}
                          {present && (
                            <>
                              {" "}
                              <span className="text-sm text-ink-muted">
                                {present.omitted
                                  ? "(está quitada: vuelve a incluirla abajo)"
                                  : "(ya está en la llamada)"}
                              </span>
                            </>
                          )}
                        </span>
                      </label>
                    </li>
                  );
                })}
              </ul>
              <div>
                <button
                  type="button"
                  className={smallButtonClass}
                  disabled={chosen.length === 0}
                  onClick={() => {
                    onAdd(
                      bank.questions
                        .filter((question) => chosen.includes(question.id))
                        .map((question) => ({
                          ...blank,
                          id: question.id,
                          text: question.text,
                          competency: question.competency,
                          guidance: question.guidance,
                          source: bank.general ? "GENERAL" : "BANCO",
                          bankId: bank.id,
                          bankName: bank.name,
                          base: question.text,
                        })),
                    );
                    setChosen([]);
                  }}
                >
                  Agregar las elegidas
                </button>
              </div>
            </>
          )}
        </div>
      )}
      <p className="text-sm text-ink-muted">
        Lo que agregues, quites o cambies vale solo para esta llamada (los bancos quedan igual) y
        se guarda al pulsar «Guardar».
      </p>
    </div>
  );
}
