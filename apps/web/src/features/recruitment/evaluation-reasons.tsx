"use client";

import { useQuery } from "@tanstack/react-query";
import { describeError } from "@/lib/api/client";
import { type ApplicationDetail, getApplication } from "@/lib/api/recruitment";

type Evaluation = NonNullable<ApplicationDetail["evaluation"]>;

/** Por qué la IA clasificó así un CV: el nivel de cada criterio, la evidencia que citó
 * y su justificación. Es la misma explicación en la lista de candidatos y en el expediente. */
export function EvaluationReasons({ evaluation }: { evaluation: Evaluation }) {
  const criteria = evaluation.result.criterios ?? [];
  if (criteria.length === 0) {
    return evaluation.result.motivo ? null : (
      <p className="text-ink-muted">Esta evaluación no guardó el detalle por criterio.</p>
    );
  }
  return (
    <ul aria-label="Niveles por criterio" className="flex flex-col gap-2">
      {criteria.map((criterion) => {
        const name = evaluation.criteria_names[criterion.id];
        return (
          <li key={criterion.id} className="rounded-2xl bg-white/60 px-4 py-3">
            <p className="font-medium">
              {name ?? criterion.id}
              {name && <span className="font-normal text-ink-muted"> ({criterion.id})</span>}:{" "}
              {criterion.sin_evidencia ? "sin evidencia" : `nivel ${criterion.nivel} de 4`}
            </p>
            {criterion.evidencia && <p className="text-sm">«{criterion.evidencia}»</p>}
            <p className="text-sm text-ink-muted">{criterion.justificacion}</p>
          </li>
        );
      })}
    </ul>
  );
}

/** El porqué de una persona de la lista, sin salir de la lista. */
export function ReasonsPanel({ applicationId, onOpen }: { applicationId: string; onOpen: () => void }) {
  const { data, error } = useQuery({
    queryKey: ["application", applicationId],
    queryFn: ({ signal }) => getApplication(applicationId, signal),
  });
  if (error) {
    return (
      <p role="alert" className="rounded-2xl bg-accent-red-soft px-4 py-3 text-accent-red-ink">
        {describeError(error)}
      </p>
    );
  }
  if (!data) return <p className="text-ink-muted">Cargando el detalle…</p>;
  const evaluation = data.evaluation;
  if (!evaluation) {
    return <p className="text-ink-muted">Esta persona se dio de alta a mano; no tiene evaluación de CV.</p>;
  }
  return (
    <div className="flex flex-col gap-3">
      <p className="text-sm text-ink-muted">
        Evaluación más reciente de «{evaluation.file_name}». La puntuación sale del nivel de cada
        criterio y de su peso; es una sugerencia de la IA y la decisión es de RH.
      </p>
      {evaluation.result.motivo && <p>{evaluation.result.motivo}</p>}
      <EvaluationReasons evaluation={evaluation} />
      <button type="button" className="self-start text-ink-muted underline" onClick={onOpen}>
        Abrir el expediente completo
      </button>
    </div>
  );
}
