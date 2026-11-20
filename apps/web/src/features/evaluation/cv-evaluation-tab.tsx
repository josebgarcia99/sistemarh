"use client";

import { keepPreviousData, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRef, useState } from "react";
import {
  cardClass,
  dangerButtonClass,
  primaryButtonClass,
  secondaryButtonClass,
} from "@/components/ui/styles";
import { describeError } from "@/lib/api/client";
import {
  BATCH_STATUS_LABELS,
  type BatchStatus,
  CLASSIFICATION_LABELS,
  type Classification,
  type CvBatch,
  cvBatchAction,
  type CvBatchDetail,
  type CvBatchItem,
  getCvBatch,
  getCvOverview,
  isActive,
  startCvBatch,
} from "@/lib/api/cv-batches";
import { ACCEPTED_EXTENSIONS, downloadUrl, MAX_UPLOAD_BYTES, uploadFile } from "@/lib/api/files";

type Feedback = { kind: "ok" | "error"; text: string } | null;

/** Cada cuánto se consulta el avance mientras un lote está en curso. */
const POLL_MS = 2000;
const dateFormat = new Intl.DateTimeFormat("es-MX", {
  timeZone: "America/Mexico_City",
  dateStyle: "medium",
  timeStyle: "short",
});
const STATUS_STYLES: Record<BatchStatus, string> = {
  PENDIENTE: "bg-neutral-soft text-neutral-ink",
  EN_COLA: "bg-neutral-soft text-neutral-ink",
  PROCESANDO: "bg-accent-blue-soft text-accent-blue-ink",
  COMPLETADO: "bg-ink text-white",
  COMPLETADO_CON_INCIDENCIAS: "bg-accent-red-soft text-accent-red-ink",
  FALLIDO: "bg-accent-red-soft text-accent-red-ink",
  CANCELADO: "bg-neutral-soft text-neutral-ink",
};
const CLASSIFICATION_STYLES: Record<Classification, string> = {
  ACEPTADO_IA: "bg-accent-blue-soft text-accent-blue-ink",
  RECHAZADO_IA: "bg-accent-red-soft text-accent-red-ink",
  NO_EVALUABLE: "bg-neutral-soft text-neutral-ink",
};
const QUALITY_LABELS: Record<string, string> = {
  redaccion: "Redacción",
  ortografia: "Ortografía",
  organizacion: "Organización",
  claridad: "Claridad",
  coherencia: "Coherencia",
  completitud: "Completitud",
};
const pillClass = "inline-flex items-center rounded-full px-3 py-1 text-sm";
const plural = (amount: number, one: string, many: string) =>
  `${amount} ${amount === 1 ? one : many}`;

/** Evaluación inicial de los CV de la vacante con el prompt aprobado. */
export function CvEvaluationTab({
  vacancyId,
  canEdit,
  onOpenPrompt,
  onOpenCandidates,
}: {
  vacancyId: string;
  canEdit: boolean;
  /** Lleva a la pestaña del prompt, cuando todavía no hay uno aprobado. */
  onOpenPrompt?: () => void;
  /** Lleva a los candidatos de la vacante. */
  onOpenCandidates?: () => void;
}) {
  const queryClient = useQueryClient();
  const overviewKey = ["vacancy", vacancyId, "cv-batches"];
  const { data: overview, error } = useQuery({
    queryKey: overviewKey,
    queryFn: ({ signal }) => getCvOverview(vacancyId, signal),
    refetchInterval: (query) => (query.state.data?.batches.some(isActive) ? POLL_MS : false),
  });
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [reevaluate, setReevaluate] = useState(false);
  const [feedback, setFeedback] = useState<Feedback>(null);
  const [busy, setBusy] = useState(false);

  if (error) {
    return (
      <p role="alert" className="rounded-tile bg-accent-red-soft px-5 py-4 text-accent-red-ink">
        {describeError(error)}
      </p>
    );
  }
  if (!overview) return <p className="text-ink-muted">Cargando evaluación de CV…</p>;

  const { approved_prompt: prompt, batches } = overview;
  const selected = batches.find((batch) => batch.id === selectedId) ?? batches[0];
  const running = batches.some(isActive);
  const amount = reevaluate ? overview.total_cvs : overview.pending_cvs;

  async function run(action: () => Promise<CvBatchDetail>, message: (d: CvBatchDetail) => string) {
    setBusy(true);
    setFeedback(null);
    try {
      const detail = await action();
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: overviewKey }),
        queryClient.invalidateQueries({ queryKey: ["cv-batch", detail.batch.id] }),
      ]);
      setSelectedId(detail.batch.id);
      setFeedback({ kind: "ok", text: message(detail) });
    } catch (caught) {
      setFeedback({ kind: "error", text: describeError(caught) });
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex flex-col gap-6">
      {canEdit && (
        <CvUpload
          vacancyId={vacancyId}
          onUploaded={() =>
            Promise.all([
              queryClient.invalidateQueries({ queryKey: overviewKey }),
              queryClient.invalidateQueries({ queryKey: ["vacancy", vacancyId, "files"] }),
            ])
          }
        />
      )}
      <section className={`${cardClass} flex flex-col gap-4`}>
        <h2 className="text-2xl font-medium">Evaluar CV</h2>
        {prompt ? (
          <>
            <dl className="grid gap-3 sm:grid-cols-3">
              <Fact
                label="Prompt aprobado"
                value={`Versión ${prompt.version_number} · ${plural(prompt.criteria, "criterio", "criterios")}`}
              />
              <Fact label="Umbral de aceptación" value={`${Number(prompt.pass_threshold)} de 100`} />
              <Fact
                label="CV cargados"
                value={`${overview.total_cvs} · ${overview.pending_cvs} sin evaluar con este prompt`}
              />
            </dl>
            <p className="text-ink-muted">
              La IA asigna un nivel a cada criterio de la rúbrica y el sistema calcula la
              puntuación. La clasificación es una sugerencia inicial: la decisión es de RH, que
              puede avanzar también a quien quedó como rechazado.
            </p>
            {prompt.instructions && (
              <details className="rounded-2xl bg-white/60 px-4 py-3">
                <summary className="cursor-pointer font-medium">
                  Ver el prompt con el que se evaluarán los CV
                </summary>
                <p className="mt-2 text-sm text-ink-muted">
                  Es el texto exacto que recibe la IA con cada currículum: las instrucciones de
                  la versión {prompt.version_number} aprobada, con su rúbrica, y el mensaje que
                  acompaña al CV. Para cambiarlo, edita el prompt en el paso anterior y aprueba
                  una versión nueva.
                </p>
                <p className="mt-3 font-medium">Instrucciones y rúbrica</p>
                <pre
                  aria-label="Instrucciones y rúbrica"
                  className="mt-2 max-h-[32rem] overflow-auto whitespace-pre-wrap rounded-2xl bg-surface p-4 text-sm"
                >
                  {prompt.instructions}
                </pre>
                <p className="mt-3 font-medium">Mensaje que acompaña a cada CV</p>
                <pre
                  aria-label="Mensaje que acompaña a cada CV"
                  className="mt-2 overflow-auto whitespace-pre-wrap rounded-2xl bg-surface p-4 text-sm"
                >
                  {prompt.cv_message}
                </pre>
              </details>
            )}
            {canEdit && (
              <div className="flex flex-wrap items-center gap-4">
                <button
                  type="button"
                  className={primaryButtonClass}
                  disabled={busy || running || amount === 0}
                  onClick={() =>
                    run(
                      () => startCvBatch(vacancyId, reevaluate),
                      (detail) =>
                        isActive(detail.batch)
                          ? "La evaluación está en marcha. Puedes cerrar esta pantalla y volver después."
                          : "La evaluación terminó.",
                    )
                  }
                >
                  {busy ? "Iniciando…" : `Evaluar ${plural(amount, "CV", "CV")}`}
                </button>
                <label className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    className="size-5 accent-ink"
                    checked={reevaluate}
                    onChange={(event) => setReevaluate(event.target.checked)}
                  />
                  Volver a evaluar también los ya evaluados
                </label>
              </div>
            )}
            {canEdit && !running && amount > 0 && (reevaluate || overview.batches.length > 0) && (
              <p className="text-sm text-ink-muted">
                Si un CV ya se había evaluado, el candidato mostrará el resultado nuevo y el
                anterior quedará anotado en su historial. Nadie cambia de etapa por esto.
              </p>
            )}
            {canEdit && running && (
              <p className="text-ink-muted">Hay un lote en curso; espera a que termine.</p>
            )}
            {canEdit && !running && overview.total_cvs === 0 && (
              <p className="text-ink-muted">Todavía no hay CV. Cárgalos arriba, en «Cargar CV».</p>
            )}
          </>
        ) : (
          <div className="flex flex-col items-start gap-3">
            <p className="text-ink-muted">
              Para evaluar CV hace falta un prompt aprobado.
              {overview.total_cvs > 0 &&
                ` Ya hay ${plural(overview.total_cvs, "CV cargado", "CV cargados")}, en espera.`}
            </p>
            {onOpenPrompt && (
              <button type="button" className={primaryButtonClass} onClick={onOpenPrompt}>
                Ir al prompt de evaluación
              </button>
            )}
          </div>
        )}
        {feedback && (
          <p
            role={feedback.kind === "ok" ? "status" : "alert"}
            className={`rounded-2xl px-4 py-3 ${
              feedback.kind === "ok"
                ? "bg-accent-blue-soft text-accent-blue-ink"
                : "bg-accent-red-soft text-accent-red-ink"
            }`}
          >
            {feedback.text}
          </p>
        )}
      </section>

      {batches.length > 0 && onOpenCandidates && (
        <section className={`${cardClass} flex flex-wrap items-center justify-between gap-4`}>
          <p className="max-w-2xl text-ink-muted">
            Las personas evaluadas ya están en «Candidatos y etapas», en la primera etapa. Ahí
            decides quién avanza a llamada y sigues el proceso.
          </p>
          <button type="button" className={primaryButtonClass} onClick={onOpenCandidates}>
            Ver candidatos y etapas
          </button>
        </section>
      )}

      {batches.length > 0 && selected && (
        <section className={`${cardClass} flex flex-col gap-5`}>
          <div className="flex flex-wrap items-end justify-between gap-4">
            <h2 className="text-2xl font-medium">Lotes</h2>
            {batches.length > 1 && (
              <div className="flex flex-col gap-1">
                <label htmlFor="cv-batch" className="text-sm text-ink-muted">
                  Lote
                </label>
                <select
                  id="cv-batch"
                  className="min-h-11 rounded-full border border-ink/15 bg-surface px-4"
                  value={selected.id}
                  onChange={(event) => setSelectedId(event.target.value)}
                >
                  {batches.map((batch) => (
                    <option key={batch.id} value={batch.id}>
                      {dateFormat.format(new Date(batch.created_at))} ·{" "}
                      {BATCH_STATUS_LABELS[batch.status]}
                    </option>
                  ))}
                </select>
              </div>
            )}
          </div>
          <BatchSummary
            batch={selected}
            canEdit={canEdit}
            busy={busy}
            onAction={(action) =>
              run(
                () => cvBatchAction(selected.id, action),
                () => (action === "cancel" ? "Lote cancelado." : "Se reanudó la evaluación."),
              )
            }
          />
          <BatchItems batch={selected} />
        </section>
      )}
    </div>
  );
}

/** Cuántos CV se pueden elegir de una vez. */
const MAX_FILES = 100;

/** Carga de CV: varios archivos de una vez, sin salir de la evaluación. */
function CvUpload({
  vacancyId,
  onUploaded,
}: {
  vacancyId: string;
  onUploaded: () => Promise<unknown>;
}) {
  const input = useRef<HTMLInputElement>(null);
  const [progress, setProgress] = useState<string | null>(null);
  const [done, setDone] = useState<string | null>(null);
  const [problems, setProblems] = useState<string[]>([]);

  async function upload(files: File[]) {
    if (files.length === 0) return;
    setDone(null);
    setProblems([]);
    if (files.length > MAX_FILES) {
      setProblems([`Elige como máximo ${MAX_FILES} archivos por carga.`]);
      return;
    }
    const failed: string[] = [];
    let saved = 0;
    let repeated = 0;
    for (const [index, file] of files.entries()) {
      setProgress(`Cargando ${index + 1} de ${files.length}…`);
      const extension = file.name.slice(file.name.lastIndexOf(".")).toLowerCase();
      if (!ACCEPTED_EXTENSIONS.includes(extension)) {
        failed.push(`${file.name}: formato no permitido (se aceptan PDF, DOCX, DOC, JPG y PNG).`);
        continue;
      }
      if (file.size > MAX_UPLOAD_BYTES) {
        failed.push(`${file.name}: supera el límite de 20 MB.`);
        continue;
      }
      try {
        const result = await uploadFile(vacancyId, file, "CV");
        saved += 1;
        if (result.duplicates.length > 0) repeated += 1;
      } catch (caught) {
        failed.push(`${file.name}: ${describeError(caught)}`);
      }
    }
    if (input.current) input.current.value = "";
    await onUploaded();
    setProgress(null);
    setProblems(failed);
    if (saved > 0) {
      setDone(
        `Se ${saved === 1 ? "cargó" : "cargaron"} ${plural(saved, "CV", "CV")}.` +
          (repeated > 0
            ? ` ${repeated === 1 ? "Uno ya estaba" : `${repeated} ya estaban`} en esta vacante; no se evalúan dos veces.`
            : ""),
      );
    }
  }

  return (
    <section className={`${cardClass} flex flex-col gap-3`}>
      <h2 className="text-2xl font-medium">Cargar CV</h2>
      <p className="text-ink-muted">
        Puedes elegir varios archivos a la vez (PDF, DOCX, DOC, JPG o PNG, de hasta 20 MB cada
        uno). Se guardan en los documentos de la vacante.
      </p>
      <div className="flex flex-wrap items-center gap-3">
        <label htmlFor="cv-files" className="sr-only">
          Archivos de CV
        </label>
        <input
          id="cv-files"
          ref={input}
          type="file"
          multiple
          accept={ACCEPTED_EXTENSIONS.join(",")}
          disabled={progress !== null}
          className="min-h-11 max-w-full rounded-full border border-ink/15 bg-surface px-4 py-2"
          onChange={(event) => upload(Array.from(event.target.files ?? []))}
        />
        {progress && (
          <p role="status" className="text-ink-muted">
            {progress}
          </p>
        )}
      </div>
      {done && (
        <p role="status" className="rounded-2xl bg-accent-blue-soft px-4 py-3 text-accent-blue-ink">
          {done}
        </p>
      )}
      {problems.length > 0 && (
        <div role="alert" className="rounded-2xl bg-accent-red-soft px-4 py-3 text-accent-red-ink">
          <p>No se cargaron:</p>
          <ul className="list-disc pl-5">
            {problems.map((problem) => (
              <li key={problem}>{problem}</li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}

function Fact({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-tile bg-surface px-5 py-4">
      <dt className="text-sm text-ink-muted">{label}</dt>
      <dd className="text-lg">{value}</dd>
    </div>
  );
}

function BatchSummary({
  batch,
  canEdit,
  busy,
  onAction,
}: {
  batch: CvBatch;
  canEdit: boolean;
  busy: boolean;
  onAction: (action: "retry" | "cancel") => void;
}) {
  const active = isActive(batch);
  const done = batch.evaluated + batch.failed;
  const canResume =
    batch.stalled ||
    batch.status === "FALLIDO" ||
    batch.status === "CANCELADO" ||
    batch.status === "COMPLETADO_CON_INCIDENCIAS";
  const downloads = [
    ["Reporte_Evaluacion.xlsx", batch.report_file_id],
    ["Aceptados.zip", batch.accepted_zip_file_id],
    ["Rechazados.zip", batch.rejected_zip_file_id],
    ["No_Evaluables.zip", batch.unevaluable_zip_file_id],
  ] as const;
  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center gap-3">
        <span className={`${pillClass} ${STATUS_STYLES[batch.status]}`}>
          {BATCH_STATUS_LABELS[batch.status]}
        </span>
        <span className="text-ink-muted">
          {dateFormat.format(new Date(batch.created_at))}
          {batch.created_by_name ? ` · ${batch.created_by_name}` : ""}
        </span>
      </div>
      <div>
        <div
          role="progressbar"
          aria-label="Avance del lote"
          aria-valuemin={0}
          aria-valuemax={batch.total}
          aria-valuenow={done}
          className="h-2.5 overflow-hidden rounded-full bg-neutral-soft"
        >
          <div className="h-full bg-accent-blue" style={{ width: `${(done / batch.total) * 100}%` }} />
        </div>
        <p className="mt-2 text-ink-muted">
          {done} de {plural(batch.total, "CV procesado", "CV procesados")} ·{" "}
          {plural(batch.accepted, "aceptado", "aceptados")} ·{" "}
          {plural(batch.rejected, "rechazado", "rechazados")} ·{" "}
          {plural(batch.unevaluable, "no evaluable", "no evaluables")}
          {batch.failed > 0 ? ` · ${batch.failed} con error` : ""}
        </p>
      </div>
      {batch.stalled && (
        <p role="alert" className="rounded-2xl bg-accent-red-soft px-4 py-3 text-accent-red-ink">
          El lote se quedó detenido. Lo ya evaluado está guardado; usa «Reanudar».
        </p>
      )}
      {batch.error && (
        <p role="alert" className="rounded-2xl bg-accent-red-soft px-4 py-3 text-accent-red-ink">
          {batch.error}
        </p>
      )}
      <div className="flex flex-wrap gap-3">
        {downloads.map(([name, fileId]) =>
          fileId ? (
            <a
              key={name}
              href={downloadUrl(fileId)}
              download
              className={`${secondaryButtonClass} inline-flex items-center`}
            >
              Descargar {name}
            </a>
          ) : null,
        )}
        {canEdit && canResume && (
          <button
            type="button"
            className={secondaryButtonClass}
            disabled={busy}
            onClick={() => onAction("retry")}
          >
            {batch.failed > 0 && !batch.stalled ? "Reintentar" : "Reanudar"}
          </button>
        )}
        {canEdit && active && (
          <button
            type="button"
            className={dangerButtonClass}
            disabled={busy}
            onClick={() => onAction("cancel")}
          >
            Cancelar lote
          </button>
        )}
      </div>
    </div>
  );
}

function BatchItems({ batch }: { batch: CvBatch }) {
  // La clave incluye el avance: cuando el resumen cambia, el detalle se vuelve a pedir.
  const { data, error } = useQuery({
    queryKey: ["cv-batch", batch.id, batch.status, batch.evaluated, batch.failed],
    queryFn: ({ signal }) => getCvBatch(batch.id, signal),
    placeholderData: keepPreviousData,
  });

  if (error) {
    return (
      <p role="alert" className="rounded-2xl bg-accent-red-soft px-4 py-3 text-accent-red-ink">
        {describeError(error)}
      </p>
    );
  }
  if (!data) return <p className="text-ink-muted">Cargando resultados…</p>;
  return (
    <ul aria-label="CV del lote" className="flex flex-col gap-2">
      {data.items.map((item) => (
        <li key={item.id}>
          <ItemRow item={item} names={data.criteria_names} />
        </li>
      ))}
    </ul>
  );
}

function itemState(item: CvBatchItem): { label: string; style: string } {
  if (item.classification) {
    return {
      label: CLASSIFICATION_LABELS[item.classification],
      style: CLASSIFICATION_STYLES[item.classification],
    };
  }
  if (item.status === "FALLIDO") {
    return { label: "Error", style: "bg-accent-red-soft text-accent-red-ink" };
  }
  return { label: "Pendiente", style: "bg-neutral-soft text-neutral-ink" };
}

function ItemRow({ item, names }: { item: CvBatchItem; names: Record<string, string> }) {
  const state = itemState(item);
  const missing = item.criteria.filter((criterion) => criterion.no_evidence).length;
  const hasDetail = item.criteria.length > 0 || Boolean(item.reason || item.error_message);
  const summary = (
    <span className="flex flex-wrap items-center gap-x-4 gap-y-1">
      <span className="min-w-0 flex-[1_1_220px] break-words font-medium">{item.file_name}</span>
      <span className={`${pillClass} ${state.style}`}>{state.label}</span>
      <span className="w-24 text-right tabular-nums">
        {item.score !== null ? `${Number(item.score)} / 100` : "—"}
      </span>
      {hasDetail && <span className="text-sm text-ink-muted underline">Ver detalle</span>}
    </span>
  );
  if (!hasDetail) return <div className="rounded-tile bg-surface px-5 py-3">{summary}</div>;
  return (
    <details className="rounded-tile bg-surface px-5 py-3">
      <summary className="cursor-pointer list-none">{summary}</summary>
      <div className="mt-4 flex flex-col gap-3 border-t border-line pt-4">
        {item.error_message && <p className="text-accent-red-ink">{item.error_message}</p>}
        {item.reason && <p>{item.reason}</p>}
        {item.duplicate && (
          <p className="text-ink-muted">
            Tiene el mismo contenido que otro CV del lote; se usó la misma evaluación.
          </p>
        )}
        {item.truncated && (
          <p className="text-ink-muted">El CV era muy largo y se evaluó solo el inicio.</p>
        )}
        {missing > 0 && (
          <p className="text-ink-muted">
            {plural(missing, "criterio", "criterios")} sin evidencia en el CV: cuentan como 0
            puntos, pero no significan que la persona no cumpla.
          </p>
        )}
        {item.criteria.length > 0 && (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[560px] text-left">
              <thead className="text-sm text-ink-muted">
                <tr>
                  <th className="py-1 pr-3 font-normal">Criterio</th>
                  <th className="py-1 pr-3 font-normal">Nivel</th>
                  <th className="py-1 pr-3 font-normal">Evidencia</th>
                  <th className="py-1 font-normal">Justificación</th>
                </tr>
              </thead>
              <tbody>
                {item.criteria.map((criterion) => (
                  <tr key={criterion.code} className="border-t border-line align-top">
                    <td className="py-2 pr-3">
                      {names[criterion.code] ?? criterion.code}
                      {names[criterion.code] && (
                        <span className="text-sm text-ink-muted"> ({criterion.code})</span>
                      )}
                    </td>
                    <td className="py-2 pr-3 whitespace-nowrap">
                      {criterion.no_evidence ? "Sin evidencia" : `${criterion.level} de 4`}
                    </td>
                    <td className="py-2 pr-3">{criterion.evidence}</td>
                    <td className="py-2">{criterion.justification}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {item.quality && (
          <p className="text-ink-muted">
            Calidad del documento (0 a 4, no cambia la puntuación):{" "}
            {Object.entries(item.quality)
              .map(([aspect, level]) => `${QUALITY_LABELS[aspect] ?? aspect} ${level}`)
              .join(" · ")}
            {item.digitization_suspect ? " · posible error de digitalización" : ""}
          </p>
        )}
        {item.notes && <p className="text-ink-muted">{item.notes}</p>}
      </div>
    </details>
  );
}
