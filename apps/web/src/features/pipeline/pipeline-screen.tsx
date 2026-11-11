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
import { type Feedback, FeedbackLine } from "@/features/recruitment/shared";
import { describeError } from "@/lib/api/client";
import {
  getPipeline,
  type Pipeline,
  savePipeline,
  STAGE_KIND_LABELS,
  type StageInput,
} from "@/lib/api/recruitment";

/** Etapas del proceso de reclutamiento (solo administradores). */
export function PipelineScreen() {
  const queryClient = useQueryClient();
  const { data: pipeline, error } = useQuery({
    queryKey: ["pipeline"],
    queryFn: ({ signal }) => getPipeline(signal),
  });
  return (
    <>
      <div>
        <h1 className="text-4xl font-medium tracking-tight sm:text-5xl">Etapas del proceso</h1>
        <p className="mt-2 max-w-3xl text-ink-muted">
          Las etapas por las que pasa una persona candidata. Al guardar se crea una versión nueva,
          que se usa en las convocatorias que se abran después; las que ya están abiertas
          conservan sus etapas.
        </p>
      </div>
      {error && (
        <p role="alert" className="rounded-tile bg-accent-red-soft px-5 py-4 text-accent-red-ink">
          {describeError(error)}
        </p>
      )}
      {pipeline && (
        <PipelineEditor
          key={pipeline.version_number}
          pipeline={pipeline}
          onSaved={() => queryClient.invalidateQueries({ queryKey: ["pipeline"] })}
        />
      )}
    </>
  );
}

function PipelineEditor({ pipeline, onSaved }: { pipeline: Pipeline; onSaved: () => Promise<void> }) {
  const [stages, setStages] = useState<StageInput[]>(() =>
    pipeline.stages.map(({ name, kind, is_optional }) => ({ name, kind, is_optional })),
  );
  const [feedback, setFeedback] = useState<Feedback>(null);
  const [busy, setBusy] = useState(false);
  const change = (index: number, patch: Partial<StageInput>) =>
    setStages(stages.map((item, i) => (i === index ? { ...item, ...patch } : item)));
  function shift(index: number, delta: number) {
    const next = [...stages];
    const [moved] = next.splice(index, 1);
    next.splice(index + delta, 0, moved);
    setStages(next);
  }
  async function save() {
    setBusy(true);
    setFeedback(null);
    try {
      const saved = await savePipeline(stages, pipeline.version_number);
      setFeedback({ kind: "ok", text: `Etapas guardadas como versión ${saved.version_number}.` });
      await onSaved();
    } catch (caught) {
      setFeedback({ kind: "error", text: describeError(caught) });
    } finally {
      setBusy(false);
    }
  }
  return (
    <section className={`${cardClass} flex flex-col gap-4`}>
      <h2 className="text-xl font-medium">Versión {pipeline.version_number}</h2>
      <ol aria-label="Etapas" className="flex flex-col gap-3">
        {stages.map((stage, index) => (
          <li key={index} className="flex flex-wrap items-end gap-3 rounded-3xl bg-surface p-4">
            <div className="flex flex-[3_1_240px] flex-col gap-2">
              <label htmlFor={`stage-name-${index}`} className="text-sm text-ink-muted">
                Etapa {index + 1}
              </label>
              <input id={`stage-name-${index}`} className={fieldClass} value={stage.name} onChange={(event) => change(index, { name: event.target.value })} />
            </div>
            <div className="flex flex-[2_1_200px] flex-col gap-2">
              <label htmlFor={`stage-kind-${index}`} className="text-sm text-ink-muted">
                Tipo
              </label>
              <select id={`stage-kind-${index}`} className={fieldClass} value={stage.kind} onChange={(event) => change(index, { kind: event.target.value })}>
                {Object.entries(STAGE_KIND_LABELS).map(([value, label]) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))}
              </select>
            </div>
            <label className="flex min-h-12 items-center gap-2">
              <input type="checkbox" className="size-5 accent-ink" checked={stage.is_optional} onChange={(event) => change(index, { is_optional: event.target.checked })} />
              Opcional
            </label>
            <div className="flex flex-wrap gap-2">
              <button type="button" className={secondaryButtonClass} disabled={index === 0} aria-label={`Subir la etapa ${index + 1}`} onClick={() => shift(index, -1)}>
                Subir
              </button>
              <button type="button" className={secondaryButtonClass} disabled={index === stages.length - 1} aria-label={`Bajar la etapa ${index + 1}`} onClick={() => shift(index, 1)}>
                Bajar
              </button>
              <button type="button" className={dangerButtonClass} aria-label={`Quitar la etapa ${index + 1}`} onClick={() => setStages(stages.filter((_, i) => i !== index))}>
                Quitar
              </button>
            </div>
          </li>
        ))}
      </ol>
      <p className="text-sm text-ink-muted">
        Una etapa opcional se puede omitir sin escribir un motivo. Omitir cualquier otra exige
        motivo.
      </p>
      <FeedbackLine feedback={feedback} />
      <div className="flex flex-wrap gap-3">
        <button type="button" className={secondaryButtonClass} onClick={() => setStages([...stages, { name: "", kind: "OTRA", is_optional: false }])}>
          Agregar etapa
        </button>
        <button type="button" className={primaryButtonClass} disabled={busy} onClick={save}>
          {busy ? "Guardando…" : "Guardar como versión nueva"}
        </button>
      </div>
    </section>
  );
}
