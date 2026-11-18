"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { AiWaitNotice, useAiWait } from "@/components/ui/ai-wait";
import { cardClass, fieldClass, primaryButtonClass } from "@/components/ui/styles";
import { dateTimeFormat, type Feedback, FeedbackLine } from "@/features/recruitment/shared";
import {
  createSynthesis,
  getSyntheses,
  KIND_LABELS,
  listAssessments,
  STATUS_LABELS,
  SYNTHESIS_SECTIONS,
} from "@/lib/api/assessments";
import { listCalls } from "@/lib/api/calls";
import { describeError } from "@/lib/api/client";
import type { ApplicationDetail } from "@/lib/api/recruitment";

const STAGE_KINDS: Record<string, string> = {
  PSICOMETRIA: "PSICOMETRIA",
  ENTREVISTA: "ENTREVISTA",
  PRUEBA_TECNICA: "PRUEBA_TECNICA",
  ESTUDIO_SOCIOECONOMICO: "ESTUDIO_SOCIOECONOMICO",
};

/** Estados con los que una evaluación ya aporta un resultado al expediente. */
const SETTLED_STATUSES = new Set(["PRESENTADA", "VALIDADA", "REALIZADA", "COMPLETADO", "NO_APLICA"]);

/** Vista consolidada del expediente: cada etapa con sus fuentes, y la síntesis de IA. */
export function DossierSection({ detail, canEdit }: { detail: ApplicationDetail; canEdit: boolean }) {
  const queryClient = useQueryClient();
  const applicationId = detail.application.id;
  const calls = useQuery({
    queryKey: ["application", applicationId, "calls"],
    queryFn: ({ signal }) => listCalls(applicationId, signal),
  });
  const assessments = useQuery({
    queryKey: ["application", applicationId, "assessments"],
    queryFn: ({ signal }) => listAssessments(applicationId, signal),
  });
  const synthesisKey = ["application", applicationId, "syntheses"];
  const syntheses = useQuery({
    queryKey: synthesisKey,
    queryFn: ({ signal }) => getSyntheses(applicationId, signal),
  });
  const [feedback, setFeedback] = useState<Feedback>(null);
  const [busy, setBusy] = useState(false);
  // Síntesis anterior que se está consultando; vacío = la más reciente.
  const [shownId, setShownId] = useState("");

  const aiWait = useAiWait();
  async function synthesize(automatic = false) {
    setBusy(true);
    setFeedback(null);
    try {
      await aiWait.run(() => createSynthesis(applicationId));
      await queryClient.invalidateQueries({ queryKey: synthesisKey });
      setShownId("");
      setFeedback({
        kind: "ok",
        text: automatic
          ? "La síntesis se actualizó sola con lo que acabas de registrar."
          : "Síntesis lista.",
      });
    } catch (caught) {
      setFeedback({
        kind: "error",
        text: automatic
          ? `No se pudo actualizar la síntesis sola: ${describeError(caught)} Puedes generarla con el botón.`
          : describeError(caught),
      });
    } finally {
      setBusy(false);
    }
  }

  // Lo que ya quedó firme en el expediente: llamadas cerradas y evaluaciones con
  // resultado. Cuando aparece algo nuevo mientras la persona trabaja en esta
  // pantalla (cerró una llamada, completó una prueba), la síntesis se actualiza sola.
  const settled =
    calls.data && assessments.data
      ? [
          ...calls.data.filter((call) => call.status === "CERRADA").map((call) => `c:${call.id}`),
          ...assessments.data.items
            .filter((item) => SETTLED_STATUSES.has(item.status))
            .map((item) => `e:${item.id}:${item.status}`),
        ]
          .sort()
          .join("|")
      : null;
  const seen = useRef<string | null>(null);
  useEffect(() => {
    if (settled === null) return;
    const previous = seen.current;
    seen.current = settled;
    // La primera carga solo se anota: abrir un expediente no consulta a la IA.
    if (previous === null || previous === settled || !canEdit) return;
    const before = new Set(previous.split("|"));
    if (settled.split("|").some((entry) => entry && !before.has(entry))) void synthesize(true);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- solo reacciona a lo registrado
  }, [settled, canEdit]);

  const { pipeline, application, movements, evaluation } = detail;
  const current = pipeline.stages.find((stage) => stage.id === application.stage_id);
  const omitted = new Set(
    movements.filter((movement) => movement.kind === "OMISION").map((movement) => movement.from_stage),
  );
  function sources(kind: string): string[] {
    if (kind === "EVALUACION_CV") {
      return evaluation ? [`CV «${evaluation.file_name}» y su evaluación inicial`] : [];
    }
    if (kind === "LLAMADA") {
      return (calls.data ?? []).map(
        (call) =>
          `Llamada del ${dateTimeFormat.format(new Date(call.called_at))} (${call.status === "CERRADA" ? "cerrada" : "borrador"})`,
      );
    }
    const assessmentKind = STAGE_KINDS[kind];
    if (!assessmentKind) return [];
    const found = (assessments.data?.items ?? [])
      .filter((item) => item.kind === assessmentKind)
      .map(
        (item) =>
          `${KIND_LABELS[item.kind]}: ${STATUS_LABELS[item.status] ?? item.status}${item.file_id ? ", con documento" : ""}`,
      );
    if (assessments.data?.restricted.some((item) => item === assessmentKind)) {
      found.push("Existe, pero requiere un permiso adicional para consultarse");
    }
    return found;
  }
  const latest = syntheses.data?.latest;
  const history = syntheses.data?.history ?? [];
  const shown = history.find((item) => item.id === shownId) ?? latest;

  return (
    <section className={`${cardClass} flex flex-col gap-5`} aria-labelledby="dossier-title">
      <h2 id="dossier-title" className="text-xl font-medium">
        Expediente por etapas
      </h2>
      <ol aria-label="Etapas y fuentes" className="flex flex-col gap-2">
        {pipeline.stages.map((stage) => {
          const state =
            stage.id === current?.id
              ? "Etapa actual"
              : omitted.has(stage.name)
                ? "Omitida"
                : current && stage.position < current.position
                  ? "Cubierta"
                  : "Por venir";
          const found = sources(stage.kind);
          return (
            <li key={stage.id} className="rounded-2xl bg-surface px-4 py-3">
              <p className="font-medium">
                {stage.position}. {stage.name} <span className="font-normal text-ink-muted">· {state}</span>
              </p>
              {found.length > 0 ? (
                <ul className="list-disc pl-5 text-sm">
                  {found.map((source) => (
                    <li key={source}>{source}</li>
                  ))}
                </ul>
              ) : (
                <p className="text-sm text-ink-muted">Sin fuentes registradas.</p>
              )}
            </li>
          );
        })}
      </ol>

      <div className="flex flex-col gap-3 border-t border-line pt-4">
        <h3 className="text-lg font-medium">Síntesis del expediente con IA</h3>
        <p className="text-sm text-ink-muted">
          Ordena lo que hay en el expediente según de dónde viene, explica qué aportó cada etapa
          frente a las anteriores, en qué coinciden o difieren las fuentes, y propone qué
          preguntar en la siguiente. Razona con los datos, pero no valora ni decide: no calcula
          ninguna puntuación ni índice y no recomienda una decisión.
          Se actualiza sola cuando cierras una llamada o registras el resultado de una
          evaluación. La psicometría solo entra si un profesional la validó; del estudio
          socioeconómico solo entran las descripciones de sus fotografías.
        </p>
        {canEdit && (
          <button type="button" className={`${primaryButtonClass} self-start`} disabled={busy} onClick={() => synthesize()}>
            {busy ? "Consultando a la IA…" : latest ? "Generar una síntesis nueva" : "Generar síntesis"}
          </button>
        )}
        <AiWaitNotice wait={aiWait} />
        <FeedbackLine feedback={feedback} />
        {syntheses.data?.hidden && (
          <p className="rounded-2xl bg-surface px-4 py-3">
            Hay una síntesis más reciente que incluye psicometría o fotografías del estudio; verla requiere un permiso
            adicional sobre la vacante.
          </p>
        )}
        {history.length > 1 && (
          <div className="flex max-w-xl flex-col gap-2">
            <label htmlFor="synthesis-history" className="text-sm text-ink-muted">
              Síntesis guardadas ({history.length})
            </label>
            <select
              id="synthesis-history"
              className={fieldClass}
              value={shown?.id ?? ""}
              onChange={(event) => setShownId(event.target.value === latest?.id ? "" : event.target.value)}
            >
              {history.map((item, index) => (
                <option key={item.id} value={item.id}>
                  {dateTimeFormat.format(new Date(item.created_at))}
                  {index === 0 ? " (la más reciente)" : ""} · {item.created_by_name ?? "Sin datos"}
                </option>
              ))}
            </select>
          </div>
        )}
        {shown && (
          <div aria-label="Síntesis" role="region" className="flex flex-col gap-3 rounded-3xl bg-surface p-5">
            {shown !== latest && (
              <p className="rounded-2xl bg-white/60 px-4 py-2 text-sm">
                Estás viendo una síntesis anterior. Puede no incluir lo registrado después.
              </p>
            )}
            <p className="text-sm text-ink-muted">
              {dateTimeFormat.format(new Date(shown.created_at))} · {shown.created_by_name ?? "Sin datos"} ·
              fuentes: {shown.sources.join(", ")}
            </p>
            {SYNTHESIS_SECTIONS.map(([key, label]) => {
              const items = shown.result[key] ?? [];
              if (items.length === 0) return null;
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
          </div>
        )}
      </div>
    </section>
  );
}
