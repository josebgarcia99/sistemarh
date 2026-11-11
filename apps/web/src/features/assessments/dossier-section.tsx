"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { cardClass, primaryButtonClass } from "@/components/ui/styles";
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

  async function synthesize() {
    setBusy(true);
    setFeedback(null);
    try {
      await createSynthesis(applicationId);
      await queryClient.invalidateQueries({ queryKey: synthesisKey });
      setFeedback({ kind: "ok", text: "Síntesis lista." });
    } catch (caught) {
      setFeedback({ kind: "error", text: describeError(caught) });
    } finally {
      setBusy(false);
    }
  }

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
          Ordena lo que hay en el expediente según de dónde viene. No calcula ninguna puntuación
          ni índice y no recomienda una decisión. La psicometría solo entra si un profesional la
          validó; el estudio socioeconómico nunca entra.
        </p>
        {canEdit && (
          <button type="button" className={`${primaryButtonClass} self-start`} disabled={busy} onClick={synthesize}>
            {busy ? "Consultando a la IA…" : latest ? "Generar una síntesis nueva" : "Generar síntesis"}
          </button>
        )}
        <FeedbackLine feedback={feedback} />
        {syntheses.data?.hidden && (
          <p className="rounded-2xl bg-surface px-4 py-3">
            Hay una síntesis más reciente que incluye psicometría; verla requiere un permiso
            adicional sobre la vacante.
          </p>
        )}
        {latest && (
          <div aria-label="Síntesis" role="region" className="flex flex-col gap-3 rounded-3xl bg-surface p-5">
            <p className="text-sm text-ink-muted">
              {dateTimeFormat.format(new Date(latest.created_at))} · {latest.created_by_name ?? "Sin datos"} ·
              fuentes: {latest.sources.join(", ")}
            </p>
            {SYNTHESIS_SECTIONS.map(([key, label]) => {
              const items = latest.result[key] ?? [];
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
