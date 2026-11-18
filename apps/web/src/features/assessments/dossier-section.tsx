"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { AiWaitNotice, useAiWait } from "@/components/ui/ai-wait";
import { cardClass, fieldClass, primaryButtonClass } from "@/components/ui/styles";
import { dateTimeFormat, type Feedback, FeedbackLine, pillClass } from "@/features/recruitment/shared";
import {
  createSynthesis,
  getSyntheses,
  KIND_LABELS,
  listAssessments,
  STATUS_LABELS,
  type Synthesis,
  SYNTHESIS_SECTIONS,
  VERDICT_LABELS,
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

const VERDICT_STYLES: Record<string, string> = {
  RECOMENDABLE: "bg-accent-blue-soft text-accent-blue-ink",
  RECOMENDABLE_CON_RESERVAS: "bg-neutral-soft text-neutral-ink",
  NO_RECOMENDABLE: "bg-accent-red-soft text-accent-red-ink",
};

const lines = (value: unknown): string[] =>
  Array.isArray(value) ? value.filter((item): item is string => typeof item === "string") : [];
const words = (value: unknown): string => (typeof value === "string" ? value : "");

function Listed({ title, items }: { title: string; items: string[] }) {
  if (items.length === 0) return null;
  return (
    <div>
      <p className="font-medium">{title}</p>
      <ul className="list-disc pl-5">
        {items.map((item) => (
          <li key={item}>{item}</li>
        ))}
      </ul>
    </div>
  );
}

function Paragraphs({ text }: { text: string }) {
  return (
    <>
      {text.split("\n\n").map((paragraph) => (
        <p key={paragraph}>{paragraph}</p>
      ))}
    </>
  );
}

/** La recomendación de la IA: veredicto en palabras, conclusión y razones con su fuente. */
function Recommendation({ result }: { result: Synthesis["result"] }) {
  const verdict = words(result.veredicto);
  return (
    <section aria-label="Recomendación de la IA" className="flex flex-col gap-2 rounded-2xl bg-white/60 p-4">
      <div className="flex flex-wrap items-center gap-3">
        <h4 className="text-lg font-medium">Recomendación de la IA</h4>
        {verdict ? (
          <span className={`${pillClass} ${VERDICT_STYLES[verdict] ?? ""}`}>
            {VERDICT_LABELS[verdict] ?? verdict}
          </span>
        ) : (
          <span className={`${pillClass} bg-neutral-soft text-neutral-ink`}>Sin veredicto</span>
        )}
      </div>
      <p className="text-sm text-ink-muted">
        Generado por IA. No es una decisión: no mueve ni cierra la postulación. Decide una
        persona, que puede no estar de acuerdo.
      </p>
      {!verdict && (
        <p>La IA no emitió un veredicto en esta síntesis. Genera una nueva para obtenerlo.</p>
      )}
      {words(result.conclusion) && <Paragraphs text={words(result.conclusion)} />}
      <Listed title="Razones" items={lines(result.razones)} />
    </section>
  );
}

/** El análisis de cierre que redactó la IA cuando una persona marcó «No viable». */
function ClosingAnalysis({ result }: { result: Synthesis["result"] }) {
  return (
    <section aria-label="Análisis de cierre" className="flex flex-col gap-2 rounded-2xl bg-white/60 p-4">
      <h4 className="text-lg font-medium">Análisis de cierre</h4>
      <p className="text-sm text-ink-muted">
        Generado por IA a partir del expediente. La decisión, la etapa y el motivo los
        registró una persona.
      </p>
      <dl className="grid gap-2 sm:grid-cols-3">
        <div>
          <dt className="text-sm text-ink-muted">Resultado</dt>
          <dd>{words(result.resultado)}</dd>
        </div>
        <div>
          <dt className="text-sm text-ink-muted">Etapa en la que se quedó</dt>
          <dd>{words(result.etapa)}</dd>
        </div>
        <div>
          <dt className="text-sm text-ink-muted">Motivo</dt>
          <dd>{words(result.motivo)}</dd>
        </div>
      </dl>
      <Paragraphs text={words(result.analisis_de_cierre)} />
    </section>
  );
}

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
  // Una postulación cerrada sin contratación recibe un análisis de cierre.
  const closed = !["ACTIVA", "CONTRATADA"].includes(detail.application.status);
  async function synthesize(automatic = false) {
    setBusy(true);
    setFeedback(null);
    try {
      await aiWait.run(() => createSynthesis(applicationId, closed));
      await queryClient.invalidateQueries({ queryKey: synthesisKey });
      setShownId("");
      setFeedback({
        kind: "ok",
        text: automatic
          ? "La síntesis se actualizó sola con lo que acabas de registrar."
          : closed
            ? "Análisis de cierre listo."
            : "Síntesis y recomendación listas.",
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
      found.push("Existe, pero tu acceso no permite consultarla");
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
        <h3 className="text-lg font-medium">Síntesis y recomendación de la IA</h3>
        <p className="text-sm text-ink-muted">
          Ordena lo que hay en el expediente según de dónde viene, señala los puntos de
          atención de cada etapa, contrasta las fuentes que no coinciden y da una
          recomendación en palabras (recomendable, con reservas o no recomendable) con sus
          razones. Es una opinión generada por IA: no calcula ninguna puntuación y no mueve ni
          cierra la postulación; la decisión es tuya. Se actualiza sola cuando cierras una
          llamada o registras el resultado de una evaluación. Entran la prueba psicométrica
          presentada, con las escalas que la IA leyó de su reporte, y del estudio
          socioeconómico solo las descripciones de sus fotografías, por lo que dicen de orden
          y organización.
        </p>
        {canEdit && (
          <button type="button" className={`${primaryButtonClass} self-start`} disabled={busy} onClick={() => synthesize()}>
            {busy
              ? "Consultando a la IA…"
              : closed
                ? "Generar análisis de cierre"
                : latest
                  ? "Generar una síntesis nueva"
                  : "Generar síntesis"}
          </button>
        )}
        <AiWaitNotice wait={aiWait} />
        <FeedbackLine feedback={feedback} />
        {syntheses.data?.hidden && (
          <p className="rounded-2xl bg-surface px-4 py-3">
            Hay una síntesis más reciente que tu acceso no permite consultar.
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
            {shown.result.tipo === "CIERRE" ? (
              <ClosingAnalysis result={shown.result} />
            ) : (
              <Recommendation result={shown.result} />
            )}
            {SYNTHESIS_SECTIONS.map(([key, label]) => (
              <Listed key={key} title={label} items={lines(shown.result[key])} />
            ))}
          </div>
        )}
      </div>
    </section>
  );
}
