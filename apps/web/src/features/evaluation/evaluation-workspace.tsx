"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { AiWaitNotice, useAiWait } from "@/components/ui/ai-wait";
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
  generatePrompt,
  listPrompts,
  proposeCriteria,
  PROMPT_STATUS_LABELS,
  type PromptAction,
  promptAction,
  type PromptStatus,
  type PromptVersion,
  updatePrompt,
} from "@/lib/api/evaluation";
import { CvEvaluationTab } from "./cv-evaluation-tab";
import { ProfileTab } from "./profile-tab";
import { areaClass, dateFormat, type Feedback, FeedbackLine } from "./shared";

type Props = {
  vacancyId: string;
  vacancyName: string;
  /** Colaboración o más: edita el perfil y los borradores. */
  canEdit: boolean;
  /** Responsable o administrador: aprueba y archiva. */
  canApprove: boolean;
  onBack: () => void;
  /** Pestaña con la que se abre. */
  initialTab?: "profile" | "prompt" | "cv";
  /** Lleva a los candidatos de la vacante, ya con los CV evaluados. */
  onOpenCandidates?: () => void;
};
const STATUS_STYLES: Record<PromptStatus, string> = {
  BORRADOR: "bg-neutral-soft text-neutral-ink",
  EN_REVISION: "bg-accent-blue-soft text-accent-blue-ink",
  APROBADO: "bg-ink text-white",
  ARCHIVADO: "bg-neutral-soft text-neutral-ink",
};

/** Perfil de puesto, prompt de evaluación y evaluación de CV de una vacante. */
export function EvaluationWorkspace({
  vacancyId,
  vacancyName,
  canEdit,
  canApprove,
  onBack,
  initialTab = "profile",
  onOpenCandidates,
}: Props) {
  const [tab, setTab] = useState<"profile" | "prompt" | "cv">(initialTab);
  return (
    <>
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="text-sm text-ink-muted">{vacancyName}</p>
          <h1 className="text-4xl font-medium tracking-tight sm:text-5xl">Perfil y evaluación</h1>
          <p className="mt-2 max-w-3xl text-ink-muted">
            Van en orden: 1) el perfil describe el puesto; 2) de él sale el prompt, que se ajusta
            y se aprueba; 3) con el prompt aprobado se cargan y se evalúan los CV.
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
        ).map(([value, label], index) => (
          <button
            key={value}
            type="button"
            aria-pressed={tab === value}
            onClick={() => setTab(value)}
            className={`min-h-11 rounded-full px-5 ${
              tab === value ? "bg-ink text-white" : "border border-line bg-surface"
            }`}
          >
            {/* El número orienta a la vista; el nombre del botón no cambia. */}
            <span aria-hidden="true">{index + 1}. </span>
            {label}
          </button>
        ))}
      </div>
      {tab === "profile" && <ProfileTab vacancyId={vacancyId} canEdit={canEdit} />}
      {tab === "prompt" && (
        <PromptTab vacancyId={vacancyId} canEdit={canEdit} canApprove={canApprove} />
      )}
      {tab === "cv" && (
        <CvEvaluationTab
          vacancyId={vacancyId}
          canEdit={canEdit}
          onOpenPrompt={() => setTab("prompt")}
          onOpenCandidates={onOpenCandidates}
        />
      )}
    </>
  );
}

/** Peso que el sistema pone por omisión a cada tipo de criterio. */
const USUAL_WEIGHT = { INDISPENSABLE: "3", DESEABLE: "1" } as const;

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
  const aiWait = useAiWait();

  async function propose() {
    setProposing(true);
    setProposalFeedback(null);
    try {
      setProposal(await aiWait.run(() => proposeCriteria(version.id)));
    } catch (caught) {
      setProposalFeedback({ kind: "error", text: describeError(caught) });
    } finally {
      setProposing(false);
    }
  }
  // Cada mejora se empareja con su criterio por identidad, no por número: si se quitan
  // criterios, los que quedan cambian de número en pantalla (el antiguo C10 puede ser
  // ahora el C7) y las mejoras de criterios que ya no están dejan de mostrarse.
  const matched = (proposal?.suggestions ?? [])
    .map((item) => ({ item, index: criteria.findIndex((criterion) => criterion.id === item.id) }))
    .filter(({ index }) => index >= 0)
    .sort((a, b) => a.index - b.index);
  const orphaned = (proposal?.suggestions.length ?? 0) - matched.length;

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
    // Lo aplicado se retira, y también lo que era para criterios que ya no están.
    const rest = proposal.suggestions.filter(
      (item) => !ids.includes(item.id) && criteria.some((criterion) => criterion.id === item.id),
    );
    setProposal(rest.length > 0 ? { ...proposal, suggestions: rest } : null);
    setProposalFeedback({
      kind: "ok",
      text: "Redacción aplicada al borrador. Revísala y pulsa «Guardar cambios» para conservarla.",
    });
  }

  // Hay cambios en pantalla que todavía no se guardaron.
  const dirty =
    editable &&
    (threshold !== version.pass_threshold ||
      version.layers.some((layer) => layers[layer.key] !== layer.content) ||
      JSON.stringify(criteria) !==
        JSON.stringify(
          version.criteria.map(({ id, name, description, kind, weight, levels }) => ({
            id,
            name,
            description,
            kind,
            weight,
            levels,
          })),
        ));
  const save = () =>
    updatePrompt(version.id, { layers, criteria, pass_threshold: threshold, revision: version.revision });
  const act = (action: PromptAction) =>
    run(() => promptAction(version.id, action, version.revision), () => ACTION_MESSAGES[action]);
  /** Enviar a revisión guarda antes lo que haya en pantalla: lo que se revisa y se aprueba
   * es lo que la persona está viendo, no una versión anterior. */
  const submit = () =>
    run(
      async () => {
        const saved = dirty ? await save() : version;
        return promptAction(saved.id, "submit", saved.revision);
      },
      () => (dirty ? "Cambios guardados. El borrador pasó a revisión." : ACTION_MESSAGES.submit),
    );
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
        <details className="rounded-2xl bg-surface px-4 py-3">
          <summary className="cursor-pointer font-medium">
            Vista previa: el prompt completo que recibirá la IA
          </summary>
          <p className="mt-2 text-sm text-ink-muted">
            Es el texto exacto de esta versión, con las partes fijas del sistema y la rúbrica,
            tal como está guardada. Si acabas de cambiar algo, pulsa «Guardar cambios» para
            verlo aquí.
          </p>
          <pre
            aria-label="Prompt completo"
            className="mt-3 max-h-[32rem] overflow-auto whitespace-pre-wrap rounded-2xl bg-white/60 p-4 text-sm"
          >
            {version.rendered}
          </pre>
        </details>
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
        {dirty && (
          <p role="note" className="rounded-2xl bg-accent-red-soft px-4 py-3 text-accent-red-ink">
            Tienes cambios sin guardar. Mientras no pulses «Guardar cambios», el prompt sigue
            siendo el anterior. «Enviar a revisión» los guarda antes de enviar.
          </p>
        )}
        <div className="flex flex-wrap gap-2">
          {editable && (
            <button
              type="button"
              className={primaryButtonClass}
              disabled={busy}
              onClick={() => run(save, () => "Cambios guardados.")}
            >
              Guardar cambios
            </button>
          )}
          {editable && (
            <button type="button" className={secondaryButtonClass} disabled={busy} onClick={submit}>
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
              100) como promedio ponderado; la IA no calcula porcentajes. Para la puntuación cuenta
              el peso de cada criterio: al cambiar el tipo, el peso pasa a 3 (indispensable) o a 1
              (deseable), salvo que ya le hayas puesto uno propio. La IA solo califica lo que está
              en esta rúbrica.
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
                    onChange={(event) => {
                      const kind = event.target.value === "DESEABLE" ? "DESEABLE" : "INDISPENSABLE";
                      // El peso sigue al tipo mientras sea el de costumbre; si la
                      // persona ya puso uno propio, se respeta.
                      const usual = Number(criterion.weight) === Number(USUAL_WEIGHT[criterion.kind]);
                      change(index, usual ? { kind, weight: USUAL_WEIGHT[kind] } : { kind });
                    }}
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
                Trabaja sobre lo último guardado: si quitaste o cambiaste criterios, pulsa antes
                «Guardar cambios».
              </p>
            </div>
            <AiWaitNotice wait={aiWait} />
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
                {orphaned > 0 && (
                  <p className="rounded-2xl bg-surface px-4 py-3">
                    {orphaned === 1
                      ? "No se muestra 1 mejora porque era para un criterio que ya quitaste."
                      : `No se muestran ${orphaned} mejoras porque eran para criterios que ya quitaste.`}
                  </p>
                )}
                <ul className="flex flex-col gap-3">
                  {matched.map(({ item, index }) => (
                    <li key={item.id} className="flex flex-col gap-2 rounded-3xl bg-surface p-4">
                      <p className="font-medium">
                        C{index + 1}. {criteria[index].name || item.name}
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
                        Aplicar a C{index + 1}
                      </button>
                    </li>
                  ))}
                </ul>
                <div className="flex flex-wrap gap-3">
                  {matched.length > 0 && (
                    <button
                      type="button"
                      className={primaryButtonClass}
                      onClick={() => applySuggestions(matched.map(({ item }) => item.id))}
                    >
                      Aplicar todas
                    </button>
                  )}
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
