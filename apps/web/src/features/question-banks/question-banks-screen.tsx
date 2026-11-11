"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import {
  cardClass,
  dangerButtonClass,
  fieldClass,
  primaryButtonClass,
  secondaryButtonClass,
} from "@/components/ui/styles";
import { useSession } from "@/features/auth/use-session";
import {
  dateTimeFormat,
  type Feedback,
  FeedbackLine,
  pillClass,
} from "@/features/recruitment/shared";
import {
  type Bank,
  bankAction,
  createBank,
  getBank,
  listBanks,
  proposeQuestions,
  type ProposedQuestion,
  type QuestionInput,
  updateBank,
} from "@/lib/api/calls";
import { describeError } from "@/lib/api/client";
import { listVacancies } from "@/lib/api/vacancies";

const emptyQuestion = (): QuestionInput => ({
  id: null,
  text: "",
  competency: "",
  guidance: "",
  origin: "MANUAL",
});

/** Bancos de preguntas para las llamadas telefónicas. */
export function QuestionBanksScreen() {
  const queryClient = useQueryClient();
  const { data: banks, error } = useQuery({
    queryKey: ["question-banks"],
    queryFn: ({ signal }) => listBanks(signal),
  });
  // "new" = banco nuevo; un identificador = banco abierto; null = lista.
  const [openId, setOpenId] = useState<string | null>(null);
  const [notice, setNotice] = useState<Feedback>(null);

  const refresh = () => queryClient.invalidateQueries({ queryKey: ["question-banks"] });
  const selected = banks?.find((bank) => bank.id === openId);

  return (
    <>
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-4xl font-medium tracking-tight sm:text-5xl">Bancos de preguntas</h1>
          <p className="mt-2 max-w-3xl text-ink-muted">
            Las preguntas de tus llamadas telefónicas. Un banco es privado hasta que lo compartes;
            cada cambio en sus preguntas crea una versión nueva y las llamadas ya hechas conservan
            la suya.
          </p>
        </div>
        {openId === null ? (
          <button type="button" className={primaryButtonClass} onClick={() => setOpenId("new")}>
            Nuevo banco
          </button>
        ) : (
          <button type="button" className={secondaryButtonClass} onClick={() => setOpenId(null)}>
            Volver a la lista
          </button>
        )}
      </div>
      <FeedbackLine feedback={notice} />
      {error && (
        <p role="alert" className="rounded-tile bg-accent-red-soft px-5 py-4 text-accent-red-ink">
          {describeError(error)}
        </p>
      )}
      {openId === null && banks && (
        <section className={`${cardClass} flex flex-col gap-3`}>
          {banks.length === 0 ? (
            <p className="text-ink-muted">Todavía no hay bancos. Crea el primero.</p>
          ) : (
            <ul aria-label="Bancos" className="flex flex-col gap-2">
              {banks.map((bank) => (
                <li key={bank.id} className="flex flex-wrap items-center gap-x-4 gap-y-2 rounded-tile bg-surface px-5 py-3">
                  <button
                    type="button"
                    className="min-w-0 flex-[1_1_220px] break-words text-left font-medium underline-offset-4 hover:underline"
                    onClick={() => {
                      setNotice(null);
                      setOpenId(bank.id);
                    }}
                  >
                    {bank.name}
                  </button>
                  <span className="text-ink-muted">
                    {bank.questions.length} preguntas · versión {bank.version_number}
                  </span>
                  <span className={`${pillClass} bg-neutral-soft text-neutral-ink`}>
                    {bank.mine ? (bank.shared ? "Mío, compartido" : "Mío, privado") : `De ${bank.owner_name ?? "otra persona"}`}
                  </span>
                  {bank.status === "ARCHIVADO" && (
                    <span className={`${pillClass} bg-accent-red-soft text-accent-red-ink`}>Archivado</span>
                  )}
                </li>
              ))}
            </ul>
          )}
        </section>
      )}
      {openId !== null && (openId === "new" || selected) && (
        <BankEditor
          key={openId === "new" ? "new" : `${selected?.id}-${selected?.version_number}-${selected?.status}`}
          bank={selected}
          onSaved={async (bank, message) => {
            await refresh();
            setOpenId(bank.id);
            setNotice({ kind: "ok", text: message });
          }}
        />
      )}
    </>
  );
}

function BankEditor({
  bank,
  onSaved,
}: {
  bank: Bank | undefined;
  onSaved: (bank: Bank, message: string) => Promise<void>;
}) {
  const editable = !bank || (bank.can_edit && bank.status === "ACTIVO");
  const [name, setName] = useState(bank?.name ?? "");
  const [description, setDescription] = useState(bank?.description ?? "");
  const [shared, setShared] = useState(bank?.shared ?? false);
  const [questions, setQuestions] = useState<QuestionInput[]>(() =>
    bank ? bank.questions.map((question) => ({ ...question })) : [emptyQuestion()],
  );
  const [note, setNote] = useState("");
  const [feedback, setFeedback] = useState<Feedback>(null);
  const [busy, setBusy] = useState(false);
  const versions = useQuery({
    queryKey: ["question-banks", bank?.id, "detail", bank?.version_number],
    queryFn: ({ signal }) => getBank(bank?.id ?? "", signal),
    enabled: Boolean(bank),
  });

  const change = (index: number, patch: Partial<QuestionInput>) =>
    setQuestions(questions.map((item, i) => (i === index ? { ...item, ...patch } : item)));
  function shift(index: number, delta: number) {
    const next = [...questions];
    const [moved] = next.splice(index, 1);
    next.splice(index + delta, 0, moved);
    setQuestions(next);
  }

  async function run(action: () => Promise<Bank>, message: string) {
    setBusy(true);
    setFeedback(null);
    try {
      await onSaved(await action(), message);
    } catch (caught) {
      setFeedback({ kind: "error", text: describeError(caught) });
    } finally {
      setBusy(false);
    }
  }
  const input = { name, description: description.trim() || null, shared, questions };

  return (
    <div className="flex flex-wrap items-start gap-6">
      <section className={`${cardClass} flex min-w-0 flex-[3_1_520px] flex-col gap-5`}>
        <h2 className="text-xl font-medium">
          {bank ? `${bank.name} · versión ${bank.version_number}` : "Nuevo banco de preguntas"}
        </h2>
        {bank && !bank.can_edit && (
          <p className="rounded-2xl bg-surface px-4 py-3">
            Este banco es de {bank.owner_name ?? "otra persona"}. Puedes usarlo en tus llamadas o
            duplicarlo para tener tu propia copia.
          </p>
        )}
        {bank?.status === "ARCHIVADO" && (
          <p className="rounded-2xl bg-surface px-4 py-3">
            Este banco está archivado: no se usa en llamadas nuevas.
          </p>
        )}
        <div className="grid gap-4 md:grid-cols-2">
          <div className="flex flex-col gap-2">
            <label htmlFor="bank-name" className="text-sm text-ink-muted">
              Nombre
            </label>
            <input id="bank-name" className={fieldClass} readOnly={!editable} value={name} onChange={(event) => setName(event.target.value)} />
          </div>
          <div className="flex flex-col gap-2">
            <label htmlFor="bank-description" className="text-sm text-ink-muted">
              Descripción (opcional)
            </label>
            <input id="bank-description" className={fieldClass} readOnly={!editable} value={description} onChange={(event) => setDescription(event.target.value)} />
          </div>
        </div>
        <label className="flex items-center gap-2">
          <input
            type="checkbox"
            className="size-5 accent-ink"
            disabled={!editable}
            checked={shared}
            onChange={(event) => setShared(event.target.checked)}
          />
          Compartir con todo el equipo (los demás lo usan y lo duplican, pero no lo modifican)
        </label>
        <ol aria-label="Preguntas" className="flex flex-col gap-3">
          {questions.map((question, index) => (
            <li key={question.id ?? `nueva-${index}`} className="flex flex-col gap-2 rounded-3xl bg-surface p-4">
              <label htmlFor={`question-${index}`} className="text-sm text-ink-muted">
                Pregunta {index + 1}
                {question.origin === "IA" ? " · propuesta por la IA" : ""}
              </label>
              <input
                id={`question-${index}`}
                className={fieldClass}
                readOnly={!editable}
                value={question.text}
                onChange={(event) => change(index, { text: event.target.value })}
              />
              <div className="grid gap-2 md:grid-cols-2">
                <input
                  aria-label={`Competencia de la pregunta ${index + 1}`}
                  placeholder="Competencia que explora (opcional)"
                  className={fieldClass}
                  readOnly={!editable}
                  value={question.competency}
                  onChange={(event) => change(index, { competency: event.target.value })}
                />
                <input
                  aria-label={`Qué escuchar en la pregunta ${index + 1}`}
                  placeholder="Qué escuchar en la respuesta (opcional)"
                  className={fieldClass}
                  readOnly={!editable}
                  value={question.guidance}
                  onChange={(event) => change(index, { guidance: event.target.value })}
                />
              </div>
              {editable && (
                <div className="flex flex-wrap gap-2">
                  <button type="button" className={secondaryButtonClass} disabled={index === 0} aria-label={`Subir la pregunta ${index + 1}`} onClick={() => shift(index, -1)}>
                    Subir
                  </button>
                  <button type="button" className={secondaryButtonClass} disabled={index === questions.length - 1} aria-label={`Bajar la pregunta ${index + 1}`} onClick={() => shift(index, 1)}>
                    Bajar
                  </button>
                  <button type="button" className={dangerButtonClass} aria-label={`Quitar la pregunta ${index + 1}`} onClick={() => setQuestions(questions.filter((_, i) => i !== index))}>
                    Quitar
                  </button>
                </div>
              )}
            </li>
          ))}
        </ol>
        {editable && (
          <button type="button" className={`${secondaryButtonClass} self-start`} onClick={() => setQuestions([...questions, emptyQuestion()])}>
            Agregar pregunta
          </button>
        )}
        {editable && (
          <QuestionAssistant
            onAdd={(proposed) =>
              setQuestions([
                ...questions.filter((item) => item.text.trim()),
                { id: null, ...proposed, origin: "IA" },
              ])
            }
          />
        )}
        <FeedbackLine feedback={feedback} />
        <div className="flex flex-wrap items-end gap-3">
          {editable && bank && (
            <div className="flex flex-[1_1_260px] flex-col gap-2">
              <label htmlFor="bank-note" className="text-sm text-ink-muted">
                Qué cambió (opcional)
              </label>
              <input id="bank-note" className={fieldClass} maxLength={300} value={note} onChange={(event) => setNote(event.target.value)} />
            </div>
          )}
          {editable && (
            <button
              type="button"
              className={primaryButtonClass}
              disabled={busy}
              onClick={() =>
                run(
                  () =>
                    bank
                      ? updateBank(bank.id, { ...input, change_note: note.trim() || null, expected_version: bank.version_number })
                      : createBank(input),
                  "Banco guardado.",
                )
              }
            >
              {busy ? "Guardando…" : bank ? "Guardar cambios" : "Crear banco"}
            </button>
          )}
          {bank && (
            <button type="button" className={secondaryButtonClass} disabled={busy} onClick={() => run(() => bankAction(bank.id, "duplicate"), "Se creó tu copia del banco.")}>
              Duplicar
            </button>
          )}
          {bank?.can_edit && (
            <button
              type="button"
              className={bank.status === "ACTIVO" ? dangerButtonClass : secondaryButtonClass}
              disabled={busy}
              onClick={() =>
                run(
                  () => bankAction(bank.id, bank.status === "ACTIVO" ? "archive" : "restore"),
                  bank.status === "ACTIVO" ? "Banco archivado." : "Banco restaurado.",
                )
              }
            >
              {bank.status === "ACTIVO" ? "Archivar" : "Restaurar"}
            </button>
          )}
        </div>
      </section>
      {bank && (
        <section className={`${cardClass} flex min-w-0 flex-[1_1_280px] flex-col gap-3`}>
          <h2 className="text-xl font-medium">Versiones</h2>
          <ul aria-label="Versiones del banco" className="flex flex-col gap-1.5">
            {(versions.data?.versions ?? []).map((version) => (
              <li key={version.version_number} className="rounded-2xl bg-surface px-4 py-3">
                <p className="font-medium">
                  Versión {version.version_number} · {version.questions} preguntas
                </p>
                <p className="text-sm text-ink-muted">
                  {dateTimeFormat.format(new Date(version.created_at))} ·{" "}
                  {version.created_by_name ?? "Sin datos"}
                </p>
                {version.change_note && <p className="text-sm">{version.change_note}</p>}
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}

/** Propuestas de preguntas de la IA a partir del perfil de una vacante. */
function QuestionAssistant({ onAdd }: { onAdd: (question: ProposedQuestion) => void }) {
  const { data: session } = useSession();
  const [open, setOpen] = useState(false);
  const [vacancyId, setVacancyId] = useState("");
  const [proposals, setProposals] = useState<ProposedQuestion[]>([]);
  const [feedback, setFeedback] = useState<Feedback>(null);
  const [busy, setBusy] = useState(false);
  const isAdmin = session?.user.role === "ADMINISTRADOR";
  const vacancies = useQuery({
    queryKey: ["vacancies", "for-questions", isAdmin],
    queryFn: ({ signal }) =>
      listVacancies({ scope: isAdmin ? "all" : "mine", page: 1, pageSize: 50 }, signal),
    enabled: open,
  });
  const options = vacancies.data?.items ?? [];

  async function propose() {
    setBusy(true);
    setFeedback(null);
    try {
      setProposals(await proposeQuestions(vacancyId || options[0].id, 8));
    } catch (caught) {
      setFeedback({ kind: "error", text: describeError(caught) });
    } finally {
      setBusy(false);
    }
  }

  if (!open) {
    return (
      <button type="button" className={`${secondaryButtonClass} self-start`} onClick={() => setOpen(true)}>
        Proponer preguntas con IA
      </button>
    );
  }
  return (
    <div className="flex flex-col gap-3 rounded-3xl bg-surface p-5">
      <p className="text-ink-muted">
        La IA propone preguntas a partir del perfil de puesto de una vacante. Tú eliges cuáles
        añades; ninguna entra al banco sin que la revises.
      </p>
      <div className="flex flex-col gap-2">
        <label htmlFor="proposal-vacancy" className="text-sm text-ink-muted">
          Vacante
        </label>
        <select id="proposal-vacancy" className={fieldClass} value={vacancyId || options[0]?.id || ""} onChange={(event) => setVacancyId(event.target.value)}>
          {options.map((vacancy) => (
            <option key={vacancy.id} value={vacancy.id}>
              {vacancy.name}
            </option>
          ))}
        </select>
      </div>
      <FeedbackLine feedback={feedback} />
      <div className="flex flex-wrap gap-3">
        <button type="button" className={primaryButtonClass} disabled={busy || options.length === 0} onClick={propose}>
          {busy ? "Consultando a la IA…" : "Proponer"}
        </button>
        <button type="button" className={secondaryButtonClass} onClick={() => setOpen(false)}>
          Cerrar
        </button>
      </div>
      {proposals.length > 0 && (
        <ul aria-label="Preguntas propuestas" className="flex flex-col gap-2">
          {proposals.map((proposal) => (
            <li key={proposal.text} className="flex flex-wrap items-center gap-3 rounded-2xl bg-white/70 px-4 py-3">
              <div className="min-w-0 flex-[1_1_260px]">
                <p>{proposal.text}</p>
                <p className="text-sm text-ink-muted">
                  {[proposal.competency, proposal.guidance].filter(Boolean).join(" · ")}
                </p>
              </div>
              <button
                type="button"
                className={secondaryButtonClass}
                onClick={() => {
                  onAdd(proposal);
                  setProposals(proposals.filter((item) => item !== proposal));
                }}
              >
                Añadir
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
