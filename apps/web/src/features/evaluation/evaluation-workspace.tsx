"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { type FormEvent, useState } from "react";
import {
  cardClass,
  dangerButtonClass,
  fieldClass,
  primaryButtonClass,
  secondaryButtonClass,
} from "@/components/ui/styles";
import { describeError } from "@/lib/api/client";
import {
  type CriteriaProposal,
  type CriterionInput,
  duplicatePrompt,
  extractProfile,
  generatePrompt,
  listProfileVersions,
  listPrompts,
  PROFILE_LABELS,
  PROFILE_LIST_FIELDS,
  PROFILE_TEXT_FIELDS,
  type ProfileInput,
  type ProfileProposal,
  type ProfileVersion,
  proposeCriteria,
  PROMPT_STATUS_LABELS,
  type PromptAction,
  promptAction,
  type PromptStatus,
  type PromptVersion,
  saveProfile,
  updatePrompt,
} from "@/lib/api/evaluation";
import { listFiles } from "@/lib/api/files";
import { CvEvaluationTab } from "./cv-evaluation-tab";

type Props = {
  vacancyId: string;
  vacancyName: string;
  /** Colaboración o más: edita el perfil y los borradores. */
  canEdit: boolean;
  /** Responsable o administrador: aprueba y archiva. */
  canApprove: boolean;
  onBack: () => void;
};
type Feedback = { kind: "ok" | "error"; text: string } | null;

const dateFormat = new Intl.DateTimeFormat("es-MX", {
  timeZone: "America/Mexico_City",
  dateStyle: "medium",
  timeStyle: "short",
});
const areaClass =
  "w-full rounded-3xl border border-ink/15 bg-surface px-5 py-3 text-ink outline-none " +
  "focus-visible:border-ink focus-visible:ring-2 focus-visible:ring-accent-blue";
const STATUS_STYLES: Record<PromptStatus, string> = {
  BORRADOR: "bg-neutral-soft text-neutral-ink",
  EN_REVISION: "bg-accent-blue-soft text-accent-blue-ink",
  APROBADO: "bg-ink text-white",
  ARCHIVADO: "bg-neutral-soft text-neutral-ink",
};

function FeedbackLine({ feedback }: { feedback: Feedback }) {
  if (!feedback) return null;
  const ok = feedback.kind === "ok";
  return (
    <p
      role={ok ? "status" : "alert"}
      className={`rounded-2xl px-4 py-3 ${
        ok ? "bg-accent-blue-soft text-accent-blue-ink" : "bg-accent-red-soft text-accent-red-ink"
      }`}
    >
      {feedback.text}
    </p>
  );
}

/** Perfil de puesto, prompt de evaluación y evaluación de CV de una vacante. */
export function EvaluationWorkspace({ vacancyId, vacancyName, canEdit, canApprove, onBack }: Props) {
  const [tab, setTab] = useState<"profile" | "prompt" | "cv">("profile");
  return (
    <>
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="text-sm text-ink-muted">{vacancyName}</p>
          <h1 className="text-4xl font-medium tracking-tight sm:text-5xl">Perfil y evaluación</h1>
          <p className="mt-2 max-w-3xl text-ink-muted">
            El perfil describe el puesto. De él sale el prompt con el que la IA hace la revisión
            inicial de los CV; solo se usa una versión aprobada.
          </p>
        </div>
        <button type="button" className={secondaryButtonClass} onClick={onBack}>
          Volver a vacantes
        </button>
      </div>
      <div role="group" aria-label="Sección" className="flex flex-wrap gap-1.5">
        {(
          [
            ["profile", "Perfil de puesto"],
            ["prompt", "Prompt de evaluación"],
            ["cv", "Evaluación de CV"],
          ] as const
        ).map(([value, label]) => (
          <button
            key={value}
            type="button"
            aria-pressed={tab === value}
            onClick={() => setTab(value)}
            className={`min-h-11 rounded-full px-5 ${
              tab === value ? "bg-ink text-white" : "border border-line bg-surface"
            }`}
          >
            {label}
          </button>
        ))}
      </div>
      {tab === "profile" && <ProfileTab vacancyId={vacancyId} canEdit={canEdit} />}
      {tab === "prompt" && (
        <PromptTab vacancyId={vacancyId} canEdit={canEdit} canApprove={canApprove} />
      )}
      {tab === "cv" && <CvEvaluationTab vacancyId={vacancyId} canEdit={canEdit} />}
    </>
  );
}

// --- Perfil ----------------------------------------------------------------------------

type ProfileDraft = Record<(typeof PROFILE_TEXT_FIELDS)[number], string> &
  Record<(typeof PROFILE_LIST_FIELDS)[number], string>;

function toDraft(version: ProfileVersion | ProfileProposal | undefined): ProfileDraft {
  const draft = {} as ProfileDraft;
  for (const field of PROFILE_TEXT_FIELDS) draft[field] = version?.[field] ?? "";
  for (const field of PROFILE_LIST_FIELDS) draft[field] = (version?.[field] ?? []).join("\n");
  return draft;
}

function ProfileTab({ vacancyId, canEdit }: { vacancyId: string; canEdit: boolean }) {
  const queryClient = useQueryClient();
  const queryKey = ["vacancy", vacancyId, "profile"];
  const { data: versions, error } = useQuery({
    queryKey,
    queryFn: ({ signal }) => listProfileVersions(vacancyId, signal),
  });

  if (error) {
    return (
      <p role="alert" className="rounded-tile bg-accent-red-soft px-5 py-4 text-accent-red-ink">
        {describeError(error)}
      </p>
    );
  }
  if (!versions) return <p className="text-ink-muted">Cargando perfil…</p>;
  const current = versions[0];
  return (
    <div className="flex flex-wrap items-start gap-6">
      <ProfileForm
        key={current?.id ?? "nuevo"}
        vacancyId={vacancyId}
        current={current}
        canEdit={canEdit}
        onSaved={() => queryClient.invalidateQueries({ queryKey })}
      />
      <section className={`${cardClass} flex min-w-0 flex-[1_1_280px] flex-col gap-3`}>
        <h2 className="text-xl font-medium">Versiones del perfil</h2>
        {versions.length === 0 ? (
          <p className="text-ink-muted">Todavía no hay perfil. Al guardarlo se crea la versión 1.</p>
        ) : (
          <ul aria-label="Versiones del perfil" className="flex flex-col gap-1.5">
            {versions.map((version) => (
              <li key={version.id} className="rounded-2xl bg-surface px-4 py-3">
                <p className="font-medium">
                  Versión {version.version_number}
                  {version === current && " (vigente)"}
                </p>
                <p className="text-sm text-ink-muted">
                  {dateFormat.format(new Date(version.created_at))} ·{" "}
                  {version.created_by_name ?? "Sin datos"}
                </p>
                {version.change_note && <p className="text-sm">{version.change_note}</p>}
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}

function ProfileForm({
  vacancyId,
  current,
  canEdit,
  onSaved,
}: {
  vacancyId: string;
  current: ProfileVersion | undefined;
  canEdit: boolean;
  onSaved: () => Promise<void>;
}) {
  const [draft, setDraft] = useState<ProfileDraft>(() => toDraft(current));
  const [note, setNote] = useState("");
  const [feedback, setFeedback] = useState<Feedback>(null);
  const [busy, setBusy] = useState(false);
  // Si el formulario se llenó con una propuesta de la IA, y de qué documento salió.
  const [aiSource, setAiSource] = useState<{ fileId: string | null } | null>(null);

  async function submit(event: FormEvent) {
    event.preventDefault();
    const input = {
      change_note: note.trim() || null,
      expected_version: current?.version_number ?? 0,
      from_ai: aiSource !== null,
      source_file_id: aiSource?.fileId ?? null,
    } as ProfileInput;
    for (const field of PROFILE_TEXT_FIELDS) input[field] = draft[field];
    for (const field of PROFILE_LIST_FIELDS) {
      input[field] = draft[field].split("\n").map((line) => line.trim()).filter(Boolean);
    }
    setBusy(true);
    setFeedback(null);
    try {
      const saved = await saveProfile(vacancyId, input);
      setNote("");
      setFeedback({ kind: "ok", text: `Perfil guardado como versión ${saved.version_number}.` });
      await onSaved();
    } catch (caught) {
      setFeedback({ kind: "error", text: describeError(caught) });
    } finally {
      setBusy(false);
    }
  }

  return (
    <form
      onSubmit={submit}
      noValidate
      className={`${cardClass} flex min-w-0 flex-[3_1_520px] flex-col gap-5`}
    >
      <h2 className="text-xl font-medium">
        {current ? `Perfil vigente (versión ${current.version_number})` : "Nuevo perfil de puesto"}
      </h2>
      {canEdit && (
        <ProfileAssistant
          vacancyId={vacancyId}
          onProposal={(proposal) => {
            setDraft(toDraft(proposal));
            setAiSource({ fileId: proposal.source_file_id });
            setFeedback(null);
          }}
        />
      )}
      {PROFILE_TEXT_FIELDS.map((field) => (
        <div key={field} className="flex flex-col gap-2">
          <label htmlFor={`profile-${field}`} className="text-sm text-ink-muted">
            {PROFILE_LABELS[field]}
          </label>
          <textarea
            id={`profile-${field}`}
            rows={field === "objective" ? 3 : 2}
            readOnly={!canEdit}
            value={draft[field]}
            onChange={(event) => setDraft({ ...draft, [field]: event.target.value })}
            className={areaClass}
          />
        </div>
      ))}
      <div className="grid gap-5 md:grid-cols-2">
        {PROFILE_LIST_FIELDS.map((field) => (
          <div key={field} className="flex flex-col gap-2">
            <label htmlFor={`profile-${field}`} className="text-sm text-ink-muted">
              {PROFILE_LABELS[field]} (uno por línea)
            </label>
            <textarea
              id={`profile-${field}`}
              rows={4}
              readOnly={!canEdit}
              value={draft[field]}
              onChange={(event) => setDraft({ ...draft, [field]: event.target.value })}
              className={areaClass}
            />
          </div>
        ))}
      </div>
      <p className="text-sm text-ink-muted">
        De cada requisito indispensable o deseable sale un criterio de la rúbrica. Si un requisito
        del perfil original es ambiguo, anótalo en «Requisitos que no están claros».
      </p>
      <FeedbackLine feedback={feedback} />
      {canEdit ? (
        <div className="flex flex-wrap items-end gap-3">
          <div className="flex flex-[1_1_260px] flex-col gap-2">
            <label htmlFor="profile-note" className="text-sm text-ink-muted">
              Qué cambió (opcional)
            </label>
            <input
              id="profile-note"
              value={note}
              maxLength={300}
              onChange={(event) => setNote(event.target.value)}
              className={fieldClass}
            />
          </div>
          <button type="submit" className={primaryButtonClass} disabled={busy}>
            {busy ? "Guardando…" : current ? "Guardar como versión nueva" : "Guardar perfil"}
          </button>
        </div>
      ) : (
        <p className="text-sm text-ink-muted">Tu acceso a esta vacante es de solo lectura.</p>
      )}
    </form>
  );
}

/** Llena el formulario del perfil con lo que la IA lee de un documento o de un texto. */
function ProfileAssistant({
  vacancyId,
  onProposal,
}: {
  vacancyId: string;
  onProposal: (proposal: ProfileProposal) => void;
}) {
  const [open, setOpen] = useState(false);
  const [fileId, setFileId] = useState("");
  const [text, setText] = useState("");
  const [feedback, setFeedback] = useState<Feedback>(null);
  const [busy, setBusy] = useState(false);
  // Los documentos se piden solo al abrir el panel.
  const { data: files, error } = useQuery({
    queryKey: ["vacancy", vacancyId, "files"],
    queryFn: ({ signal }) => listFiles(vacancyId, signal),
    enabled: open,
  });
  const documents = (files ?? []).filter((file) => file.document_type === "PERFIL_PUESTO");

  async function read() {
    setBusy(true);
    setFeedback(null);
    try {
      const proposal = await extractProfile(vacancyId, fileId ? { fileId } : { text });
      onProposal(proposal);
      setFeedback({
        kind: "ok",
        text:
          "La IA llenó el formulario. Revísalo y corrígelo: todavía no se ha guardado." +
          (proposal.truncated ? " El documento era muy largo y solo se leyó el inicio." : ""),
      });
    } catch (caught) {
      setFeedback({ kind: "error", text: describeError(caught) });
    } finally {
      setBusy(false);
    }
  }

  if (!open) {
    return (
      <button
        type="button"
        className={`${secondaryButtonClass} self-start`}
        onClick={() => setOpen(true)}
      >
        Llenar con IA desde un documento
      </button>
    );
  }
  return (
    <div className="flex flex-col gap-3 rounded-3xl bg-surface p-5">
      <p className="text-ink-muted">
        La IA lee el perfil y llena este formulario con lo que el documento dice, sin añadir
        nada. Después lo revisas y lo guardas tú.
      </p>
      {error && (
        <p role="alert" className="text-accent-red-ink">
          {describeError(error)}
        </p>
      )}
      <div className="flex flex-col gap-2">
        <label htmlFor="profile-source-file" className="text-sm text-ink-muted">
          Documento de la vacante (tipo «Perfil de puesto»)
        </label>
        <select
          id="profile-source-file"
          className={fieldClass}
          value={fileId}
          onChange={(event) => setFileId(event.target.value)}
        >
          <option value="">Ninguno: pegaré el texto</option>
          {documents.map((file) => (
            <option key={file.id} value={file.id}>
              {file.original_name}
            </option>
          ))}
        </select>
      </div>
      {!fileId && (
        <div className="flex flex-col gap-2">
          <label htmlFor="profile-source-text" className="text-sm text-ink-muted">
            Texto del perfil
          </label>
          <textarea
            id="profile-source-text"
            rows={5}
            value={text}
            onChange={(event) => setText(event.target.value)}
            className={areaClass}
          />
        </div>
      )}
      <FeedbackLine feedback={feedback} />
      <div className="flex flex-wrap gap-3">
        <button
          type="button"
          className={primaryButtonClass}
          disabled={busy || (!fileId && text.trim().length === 0)}
          onClick={read}
        >
          {busy ? "Leyendo…" : "Leer con IA"}
        </button>
        <button type="button" className={secondaryButtonClass} onClick={() => setOpen(false)}>
          Cerrar
        </button>
      </div>
    </div>
  );
}

// --- Prompt ----------------------------------------------------------------------------

function PromptTab({
  vacancyId,
  canEdit,
  canApprove,
}: {
  vacancyId: string;
  canEdit: boolean;
  canApprove: boolean;
}) {
  const queryClient = useQueryClient();
  const queryKey = ["vacancy", vacancyId, "prompts"];
  const { data: versions, error } = useQuery({
    queryKey,
    queryFn: ({ signal }) => listPrompts(vacancyId, signal),
  });
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [feedback, setFeedback] = useState<Feedback>(null);
  const [busy, setBusy] = useState(false);

  if (error) {
    return (
      <p role="alert" className="rounded-tile bg-accent-red-soft px-5 py-4 text-accent-red-ink">
        {describeError(error)}
      </p>
    );
  }
  if (!versions) return <p className="text-ink-muted">Cargando prompts…</p>;
  const selected = versions.find((version) => version.id === selectedId) ?? versions[0];

  /** Ejecuta una acción que devuelve la versión resultante y la deja seleccionada. */
  async function run(action: () => Promise<PromptVersion>, message: (v: PromptVersion) => string) {
    setBusy(true);
    setFeedback(null);
    try {
      const result = await action();
      await queryClient.invalidateQueries({ queryKey });
      setSelectedId(result.id);
      setFeedback({ kind: "ok", text: message(result) });
    } catch (caught) {
      setFeedback({ kind: "error", text: describeError(caught) });
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <section className={`${cardClass} flex flex-wrap items-end justify-between gap-4`}>
        <div className="flex flex-[1_1_260px] flex-col gap-2">
          <label htmlFor="prompt-version" className="text-sm text-ink-muted">
            Versión
          </label>
          <select
            id="prompt-version"
            value={selected?.id ?? ""}
            onChange={(event) => {
              setSelectedId(event.target.value);
              setFeedback(null);
            }}
            disabled={versions.length === 0}
            className={fieldClass}
          >
            {versions.length === 0 && <option value="">Sin versiones</option>}
            {versions.map((version) => (
              <option key={version.id} value={version.id}>
                Versión {version.version_number} · {PROMPT_STATUS_LABELS[version.status]}
              </option>
            ))}
          </select>
        </div>
        {canEdit && (
          <button
            type="button"
            className={secondaryButtonClass}
            disabled={busy}
            onClick={() =>
              run(
                () => generatePrompt(vacancyId),
                (v) => `Se generó el borrador (versión ${v.version_number}) a partir del perfil.`,
              )
            }
          >
            Generar borrador desde el perfil
          </button>
        )}
      </section>
      <FeedbackLine feedback={feedback} />
      {selected ? (
        <PromptEditor
          key={`${selected.id}-${selected.revision}`}
          version={selected}
          canEdit={canEdit}
          canApprove={canApprove}
          busy={busy}
          run={run}
        />
      ) : (
        <p className="text-ink-muted">
          Todavía no hay prompt. Guarda el perfil de puesto y genera el primer borrador.
        </p>
      )}
    </div>
  );
}

const ACTION_MESSAGES: Record<PromptAction, string> = {
  submit: "El borrador pasó a revisión.",
  return: "La versión volvió a borrador para corregirla.",
  approve: "Versión aprobada. Ya no se puede modificar.",
  archive: "Versión archivada.",
};

function PromptEditor({
  version,
  canEdit,
  canApprove,
  busy,
  run,
}: {
  version: PromptVersion;
  canEdit: boolean;
  canApprove: boolean;
  busy: boolean;
  run: (action: () => Promise<PromptVersion>, message: (v: PromptVersion) => string) => Promise<void>;
}) {
  const editable = canEdit && version.status === "BORRADOR";
  const [threshold, setThreshold] = useState(version.pass_threshold);
  const [layers, setLayers] = useState<Record<string, string>>(() =>
    Object.fromEntries(version.layers.map((layer) => [layer.key, layer.content])),
  );
  const [criteria, setCriteria] = useState<CriterionInput[]>(() =>
    version.criteria.map(({ id, name, description, kind, weight, levels }) => ({
      id,
      name,
      description,
      kind,
      weight,
      levels: [...levels],
    })),
  );

  const [proposal, setProposal] = useState<CriteriaProposal | null>(null);
  const [proposalFeedback, setProposalFeedback] = useState<Feedback>(null);
  const [proposing, setProposing] = useState(false);

  async function propose() {
    setProposing(true);
    setProposalFeedback(null);
    try {
      setProposal(await proposeCriteria(version.id));
    } catch (caught) {
      setProposalFeedback({ kind: "error", text: describeError(caught) });
    } finally {
      setProposing(false);
    }
  }
  /** Copia al borrador la redacción propuesta. No guarda: eso lo hace «Guardar cambios». */
  function applySuggestions(ids: string[]) {
    if (!proposal) return;
    const chosen = proposal.suggestions.filter((item) => ids.includes(item.id));
    setCriteria(
      criteria.map((item) => {
        const suggestion = chosen.find((candidate) => candidate.id === item.id);
        return suggestion
          ? { ...item, description: suggestion.description, levels: [...suggestion.levels] }
          : item;
      }),
    );
    const rest = proposal.suggestions.filter((item) => !ids.includes(item.id));
    setProposal(rest.length > 0 ? { ...proposal, suggestions: rest } : null);
    setProposalFeedback({
      kind: "ok",
      text: "Redacción aplicada al borrador. Revísala y pulsa «Guardar cambios» para conservarla.",
    });
  }

  const act = (action: PromptAction) =>
    run(() => promptAction(version.id, action, version.revision), () => ACTION_MESSAGES[action]);
  const change = (index: number, patch: Partial<CriterionInput>) =>
    setCriteria(criteria.map((item, i) => (i === index ? { ...item, ...patch } : item)));

  return (
    <>
      <section className={`${cardClass} flex flex-col gap-4`}>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h2 className="text-xl font-medium">Versión {version.version_number}</h2>
          <span className={`rounded-full px-3 py-1 text-sm ${STATUS_STYLES[version.status]}`}>
            {PROMPT_STATUS_LABELS[version.status]}
          </span>
        </div>
        <p className="text-sm text-ink-muted">
          Basada en la versión {version.profile_version_number ?? "?"} del perfil · creada por{" "}
          {version.created_by_name ?? "Sin datos"}
          {version.approved_at &&
            ` · aprobada el ${dateFormat.format(new Date(version.approved_at))} por ${
              version.approved_by_name ?? "Sin datos"
            }`}
          {" · "}
          {version.length} de {version.max_length} caracteres
        </p>
        {version.status === "APROBADO" && (
          <p className="rounded-2xl bg-surface px-4 py-3">
            Esta versión está aprobada y no se modifica. Para cambiarla, duplícala: se crea un
            borrador nuevo con el mismo contenido.
          </p>
        )}
        {version.issues.length > 0 && (
          <div role="alert" className="rounded-2xl bg-accent-red-soft px-4 py-3 text-accent-red-ink">
            <p className="font-medium">Falta para poder enviarla a revisión:</p>
            <ul className="list-disc pl-5">
              {version.issues.map((issue) => (
                <li key={issue}>{issue}</li>
              ))}
            </ul>
          </div>
        )}
        <div className="flex flex-wrap gap-2">
          {editable && (
            <button
              type="button"
              className={primaryButtonClass}
              disabled={busy}
              onClick={() =>
                run(
                  () =>
                    updatePrompt(version.id, {
                      layers,
                      criteria,
                      pass_threshold: threshold,
                      revision: version.revision,
                    }),
                  () => "Cambios guardados.",
                )
              }
            >
              Guardar cambios
            </button>
          )}
          {editable && (
            <button type="button" className={secondaryButtonClass} disabled={busy} onClick={() => act("submit")}>
              Enviar a revisión
            </button>
          )}
          {canEdit && version.status === "EN_REVISION" && (
            <button type="button" className={secondaryButtonClass} disabled={busy} onClick={() => act("return")}>
              Devolver a borrador
            </button>
          )}
          {canApprove && version.status === "EN_REVISION" && (
            <button type="button" className={primaryButtonClass} disabled={busy} onClick={() => act("approve")}>
              Aprobar
            </button>
          )}
          {canEdit && (
            <button
              type="button"
              className={secondaryButtonClass}
              disabled={busy}
              onClick={() =>
                run(
                  () => duplicatePrompt(version.id),
                  (v) => `Se creó el borrador (versión ${v.version_number}) como copia.`,
                )
              }
            >
              Duplicar
            </button>
          )}
          {canApprove && version.status !== "ARCHIVADO" && (
            <button type="button" className={dangerButtonClass} disabled={busy} onClick={() => act("archive")}>
              Archivar
            </button>
          )}
        </div>
        {editable && (
          <p className="text-sm text-ink-muted">
            Guarda los cambios antes de enviar a revisión: se envía lo último guardado.
          </p>
        )}
      </section>

      <section aria-labelledby="rubric-title" className={`${cardClass} flex flex-col gap-4`}>
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <h2 id="rubric-title" className="text-xl font-medium">
              Rúbrica
            </h2>
            <p className="mt-1 max-w-3xl text-ink-muted">
              La IA asigna a cada criterio un nivel de 0 a 4. El sistema calcula la puntuación (0 a
              100) como promedio ponderado; la IA no calcula porcentajes.
            </p>
          </div>
          <div className="flex flex-col gap-2">
            <label htmlFor="threshold" className="text-sm text-ink-muted">
              Umbral de aceptación (0 a 100)
            </label>
            <input
              id="threshold"
              inputMode="decimal"
              readOnly={!editable}
              value={threshold}
              onChange={(event) => setThreshold(event.target.value)}
              className={`${fieldClass} max-w-40`}
            />
          </div>
        </div>
        <ul aria-label="Criterios" className="flex flex-col gap-3">
          {criteria.map((criterion, index) => (
            <li key={criterion.id ?? `nuevo-${index}`} className="flex flex-col gap-3 rounded-3xl bg-surface p-4">
              <div className="flex flex-wrap items-end gap-3">
                <div className="flex flex-[3_1_260px] flex-col gap-2">
                  <label htmlFor={`criterion-name-${index}`} className="text-sm text-ink-muted">
                    Criterio C{index + 1}
                    {version.criteria[index]?.origin === "PERFIL" ? " · del perfil" : " · añadido a mano"}
                  </label>
                  <input
                    id={`criterion-name-${index}`}
                    readOnly={!editable}
                    value={criterion.name}
                    onChange={(event) => change(index, { name: event.target.value })}
                    className={fieldClass}
                  />
                </div>
                <div className="flex flex-[1_1_150px] flex-col gap-2">
                  <label htmlFor={`criterion-kind-${index}`} className="text-sm text-ink-muted">
                    Tipo
                  </label>
                  <select
                    id={`criterion-kind-${index}`}
                    disabled={!editable}
                    value={criterion.kind}
                    onChange={(event) =>
                      change(index, { kind: event.target.value === "DESEABLE" ? "DESEABLE" : "INDISPENSABLE" })
                    }
                    className={fieldClass}
                  >
                    <option value="INDISPENSABLE">Indispensable</option>
                    <option value="DESEABLE">Deseable</option>
                  </select>
                </div>
                <div className="flex flex-[1_1_100px] flex-col gap-2">
                  <label htmlFor={`criterion-weight-${index}`} className="text-sm text-ink-muted">
                    Peso
                  </label>
                  <input
                    id={`criterion-weight-${index}`}
                    inputMode="decimal"
                    readOnly={!editable}
                    value={criterion.weight}
                    onChange={(event) => change(index, { weight: event.target.value })}
                    className={fieldClass}
                  />
                </div>
                {editable && (
                  <button
                    type="button"
                    className={dangerButtonClass}
                    aria-label={`Quitar criterio C${index + 1}`}
                    onClick={() => setCriteria(criteria.filter((_, i) => i !== index))}
                  >
                    Quitar
                  </button>
                )}
              </div>
              <details>
                <summary className="cursor-pointer text-sm text-ink-muted">
                  Descripción y niveles 0 a 4
                </summary>
                <div className="mt-3 flex flex-col gap-2">
                  <label htmlFor={`criterion-description-${index}`} className="sr-only">
                    Descripción del criterio C{index + 1}
                  </label>
                  <input
                    id={`criterion-description-${index}`}
                    placeholder="Descripción (opcional)"
                    readOnly={!editable}
                    value={criterion.description}
                    onChange={(event) => change(index, { description: event.target.value })}
                    className={fieldClass}
                  />
                  {criterion.levels.map((level, levelIndex) => (
                    <div key={levelIndex} className="flex items-center gap-3">
                      <label htmlFor={`criterion-${index}-level-${levelIndex}`} className="w-16 text-sm text-ink-muted">
                        Nivel {levelIndex}
                      </label>
                      <input
                        id={`criterion-${index}-level-${levelIndex}`}
                        readOnly={!editable}
                        value={level}
                        onChange={(event) =>
                          change(index, {
                            levels: criterion.levels.map((item, i) =>
                              i === levelIndex ? event.target.value : item,
                            ),
                          })
                        }
                        className={fieldClass}
                      />
                    </div>
                  ))}
                </div>
              </details>
            </li>
          ))}
        </ul>
        {editable && (
          <button
            type="button"
            className={`${secondaryButtonClass} self-start`}
            onClick={() =>
              setCriteria([
                ...criteria,
                {
                  id: null,
                  name: "",
                  description: "",
                  kind: "DESEABLE",
                  weight: "1",
                  levels: [
                    "La evidencia del CV contradice el requisito o es claramente insuficiente.",
                    "Evidencia mínima o indirecta.",
                    "Cumple en parte: evidencia directa pero incompleta.",
                    "Cumple: evidencia directa y suficiente.",
                    "Supera el requisito con evidencia clara y verificable.",
                  ],
                },
              ])
            }
          >
            Agregar criterio
          </button>
        )}
        {editable && (
          <div className="flex flex-col gap-3 border-t border-line pt-4">
            <div className="flex flex-wrap items-center gap-3">
              <button
                type="button"
                className={secondaryButtonClass}
                disabled={proposing}
                onClick={propose}
              >
                {proposing ? "Consultando a la IA…" : "Proponer mejoras con IA"}
              </button>
              <p className="flex-[1_1_300px] text-sm text-ink-muted">
                La IA sugiere una redacción más clara para la descripción y los niveles de cada
                criterio. No añade criterios ni requisitos, y nada cambia hasta que lo apliques.
              </p>
            </div>
            <FeedbackLine feedback={proposalFeedback} />
            {proposal && (
              <section aria-label="Mejoras propuestas por la IA" className="flex flex-col gap-3">
                {proposal.observations.length > 0 && (
                  <div className="rounded-2xl bg-surface px-4 py-3">
                    <p className="font-medium">Avisos de la IA</p>
                    <ul className="list-disc pl-5">
                      {proposal.observations.map((note) => (
                        <li key={note}>{note}</li>
                      ))}
                    </ul>
                  </div>
                )}
                <ul className="flex flex-col gap-3">
                  {proposal.suggestions.map((item) => (
                    <li key={item.id} className="flex flex-col gap-2 rounded-3xl bg-surface p-4">
                      <p className="font-medium">
                        {item.code}. {item.name}
                      </p>
                      {item.description && <p>{item.description}</p>}
                      <ol start={0} className="list-decimal pl-6 text-ink-muted">
                        {item.levels.map((level, index) => (
                          <li key={index}>{level}</li>
                        ))}
                      </ol>
                      <button
                        type="button"
                        className={`${secondaryButtonClass} self-start`}
                        onClick={() => applySuggestions([item.id])}
                      >
                        Aplicar a {item.code}
                      </button>
                    </li>
                  ))}
                </ul>
                <div className="flex flex-wrap gap-3">
                  <button
                    type="button"
                    className={primaryButtonClass}
                    onClick={() => applySuggestions(proposal.suggestions.map((item) => item.id))}
                  >
                    Aplicar todas
                  </button>
                  <button
                    type="button"
                    className={secondaryButtonClass}
                    onClick={() => setProposal(null)}
                  >
                    Descartar
                  </button>
                </div>
              </section>
            )}
          </div>
        )}
      </section>

      <section aria-labelledby="layers-title" className={`${cardClass} flex flex-col gap-4`}>
        <h2 id="layers-title" className="text-xl font-medium">
          Capas del prompt
        </h2>
        {version.layers.map((layer, index) => (
          <div key={layer.key} className="flex flex-col gap-2">
            <label htmlFor={`layer-${layer.key}`} className="text-sm text-ink-muted">
              {index + 1}. {layer.title}
              {layer.locked && " (la escribe el sistema)"}
            </label>
            <textarea
              id={`layer-${layer.key}`}
              rows={layer.locked ? 4 : 5}
              readOnly={!editable || layer.locked}
              value={layer.locked ? layer.content : (layers[layer.key] ?? "")}
              onChange={(event) => setLayers({ ...layers, [layer.key]: event.target.value })}
              className={`${areaClass} ${layer.locked ? "text-ink-muted" : ""}`}
            />
          </div>
        ))}
      </section>
    </>
  );
}
