"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
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
  analyzeCall,
  type AnswerInput,
  type Call,
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
  const [bankId, setBankId] = useState("");
  const [openId, setOpenId] = useState<string | null>(null);
  const [feedback, setFeedback] = useState<Feedback>(null);
  const [busy, setBusy] = useState(false);
  const banksQuery = useQuery({
    queryKey: ["question-banks"],
    queryFn: ({ signal }) => listBanks(signal),
    enabled: choosing,
  });
  const banks = (banksQuery.data ?? []).filter((bank) => bank.status === "ACTIVO");

  async function start() {
    setBusy(true);
    setFeedback(null);
    try {
      const call = await openCall(applicationId, bankId || banks[0].id);
      await queryClient.invalidateQueries({ queryKey });
      setOpenId(call.id);
      setChoosing(false);
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
          {banksQuery.data && banks.length === 0 ? (
            <p>No tienes bancos de preguntas activos. Crea uno en «Bancos».</p>
          ) : (
            <div className="flex flex-col gap-2">
              <label htmlFor="call-bank" className="text-sm text-ink-muted">
                Banco de preguntas
              </label>
              <select
                id="call-bank"
                className={fieldClass}
                value={bankId || banks[0]?.id || ""}
                onChange={(event) => setBankId(event.target.value)}
              >
                {banks.map((bank) => (
                  <option key={bank.id} value={bank.id}>
                    {bank.name} · {bank.questions.length} preguntas
                  </option>
                ))}
              </select>
            </div>
          )}
          <FeedbackLine feedback={feedback} />
          <div className="flex flex-wrap gap-3">
            <button
              type="button"
              className={primaryButtonClass}
              disabled={busy || banks.length === 0}
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
                {dateTimeFormat.format(new Date(call.called_at))} · {call.bank_name} (v
                {call.bank_version})
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
  const [answers, setAnswers] = useState<AnswerInput[]>(() =>
    call.questions.map((question) => ({
      question_id: question.id,
      answer: question.answer,
      notes: question.notes,
      not_asked: question.not_asked,
    })),
  );
  const [notes, setNotes] = useState(call.notes);
  const [feedback, setFeedback] = useState<Feedback>(null);
  const [busy, setBusy] = useState(false);
  const change = (index: number, patch: Partial<AnswerInput>) =>
    setAnswers(answers.map((item, i) => (i === index ? { ...item, ...patch } : item)));

  async function run(action: () => Promise<unknown>, message: string) {
    setBusy(true);
    setFeedback(null);
    try {
      await action();
      await onChanged();
      setFeedback({ kind: "ok", text: message });
    } catch (caught) {
      setFeedback({ kind: "error", text: describeError(caught) });
    } finally {
      setBusy(false);
    }
  }
  const payload = (close: boolean) => ({
    answers: answers.filter((item) => item.answer.trim() || item.notes.trim() || item.not_asked),
    notes,
    close,
  });

  return (
    <div className="mt-4 flex flex-col gap-4 border-t border-line pt-4">
      <ol className="flex flex-col gap-4">
        {call.questions.map((question, index) => (
          <li key={question.id} className="flex flex-col gap-2">
            <p className="font-medium">
              {index + 1}. {question.text}
            </p>
            {(question.competency || question.guidance) && (
              <p className="text-sm text-ink-muted">
                {[question.competency, question.guidance].filter(Boolean).join(" · ")}
              </p>
            )}
            <label htmlFor={`answer-${call.id}-${index}`} className="sr-only">
              Respuesta a la pregunta {index + 1}
            </label>
            <textarea
              id={`answer-${call.id}-${index}`}
              rows={3}
              readOnly={!editable}
              disabled={answers[index].not_asked}
              placeholder="Lo que respondió la persona"
              value={answers[index].answer}
              onChange={(event) => change(index, { answer: event.target.value })}
              className={areaClass}
            />
            <div className="flex flex-wrap items-center gap-4">
              <label htmlFor={`notes-${call.id}-${index}`} className="sr-only">
                Observación sobre la pregunta {index + 1}
              </label>
              <input
                id={`notes-${call.id}-${index}`}
                readOnly={!editable}
                placeholder="Observación (opcional)"
                value={answers[index].notes}
                onChange={(event) => change(index, { notes: event.target.value })}
                className={`${fieldClass} flex-[1_1_260px]`}
              />
              <label className="flex items-center gap-2">
                <input
                  type="checkbox"
                  className="size-5 accent-ink"
                  disabled={!editable}
                  checked={answers[index].not_asked}
                  onChange={(event) => change(index, { not_asked: event.target.checked })}
                />
                No se realizó
              </label>
            </div>
          </li>
        ))}
      </ol>
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
                onClick={() => run(() => saveCall(call.id, payload(false)), "Llamada guardada.")}
              >
                Guardar
              </button>
              <button
                type="button"
                className={secondaryButtonClass}
                disabled={busy}
                onClick={() => run(() => saveCall(call.id, payload(true)), "Llamada cerrada.")}
              >
                Cerrar llamada
              </button>
            </>
          )}
          <button
            type="button"
            className={secondaryButtonClass}
            disabled={busy}
            onClick={() => run(() => analyzeCall(call.id), "Análisis listo.")}
          >
            {busy ? "Trabajando…" : "Analizar con IA"}
          </button>
        </div>
      )}
      {editable && (
        <p className="text-sm text-ink-muted">
          Guarda antes de analizar: la IA trabaja con lo último guardado. Al cerrar, la llamada ya
          no se puede modificar.
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
