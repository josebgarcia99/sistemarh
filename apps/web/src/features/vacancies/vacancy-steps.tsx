"use client";

import { useQuery } from "@tanstack/react-query";
import { getCvOverview } from "@/lib/api/cv-batches";
import { listProfileVersions, listPrompts, PROMPT_STATUS_LABELS } from "@/lib/api/evaluation";
import type { Vacancy } from "@/lib/api/vacancies";

export type EvaluationTab = "profile" | "prompt" | "cv";

type Step = {
  title: string;
  /** Para qué sirve el paso, en una línea. */
  hint: string;
  /** Cómo va: «Pendiente», «Listo · versión 2»… Vacío mientras se consulta. */
  status: string;
  done: boolean;
  open: () => void;
};

type Props = {
  vacancy: Vacancy;
  onOpenEvaluation: (vacancy: Vacancy, tab: EvaluationTab) => void;
  onOpenCandidates: (vacancy: Vacancy) => void;
};

const plural = (amount: number, one: string, many: string) =>
  `${amount} ${amount === 1 ? one : many}`;

/**
 * Guía de la vacante: los cuatro pasos en orden, cómo va cada uno y cuál sigue.
 * Cada paso abre directamente la pantalla donde se hace.
 */
export function VacancySteps({ vacancy, onOpenEvaluation, onOpenCandidates }: Props) {
  const profiles = useQuery({
    queryKey: ["vacancy", vacancy.id, "profile-versions"],
    queryFn: ({ signal }) => listProfileVersions(vacancy.id, signal),
  });
  const prompts = useQuery({
    queryKey: ["vacancy", vacancy.id, "prompts"],
    queryFn: ({ signal }) => listPrompts(vacancy.id, signal),
  });
  const overview = useQuery({
    queryKey: ["vacancy", vacancy.id, "cv-batches"],
    queryFn: ({ signal }) => getCvOverview(vacancy.id, signal),
  });

  const profile = profiles.data?.reduce(
    (latest, item) => (item.version_number > latest ? item.version_number : latest),
    0,
  );
  const approved = prompts.data?.find((item) => item.status === "APROBADO");
  const draft = prompts.data?.find((item) => item.status !== "ARCHIVADO");
  const cvs = overview.data;

  const steps: Step[] = [
    {
      title: "Perfil de puesto",
      hint: "Qué pide el puesto. Se captura o se sube el formato en Excel.",
      status: profile === undefined ? "" : profile > 0 ? `Listo · versión ${profile}` : "Pendiente",
      done: (profile ?? 0) > 0,
      open: () => onOpenEvaluation(vacancy, "profile"),
    },
    {
      title: "Prompt de evaluación",
      hint: "Los criterios con los que la IA califica cada CV. Aquí se ajusta y se aprueba.",
      status: !prompts.data
        ? ""
        : approved
          ? `Aprobado · versión ${approved.version_number}`
          : draft
            ? `${PROMPT_STATUS_LABELS[draft.status]} · falta aprobarlo`
            : "Pendiente",
      done: Boolean(approved),
      open: () => onOpenEvaluation(vacancy, "prompt"),
    },
    {
      title: "Cargar y evaluar CV",
      hint: "Sube los CV, lanza la evaluación y revisa la calificación de cada uno.",
      status: !cvs
        ? ""
        : cvs.total_cvs === 0
          ? "Sin CV cargados"
          : cvs.pending_cvs > 0
            ? `${plural(cvs.total_cvs, "CV cargado", "CV cargados")} · ${cvs.pending_cvs} sin evaluar`
            : `${plural(cvs.total_cvs, "CV evaluado", "CV evaluados")}`,
      done: Boolean(cvs && cvs.total_cvs > 0 && cvs.pending_cvs === 0),
      open: () => onOpenEvaluation(vacancy, "cv"),
    },
    {
      title: "Candidatos y etapas",
      hint: "Las personas evaluadas, su etapa, llamadas, entrevistas, estudio y expediente.",
      status: "",
      done: false,
      open: () => onOpenCandidates(vacancy),
    },
  ];
  // El paso que sigue: el primero sin terminar. Con todo listo, los candidatos.
  const loaded = profiles.data && prompts.data && cvs;
  const next = loaded ? steps.findIndex((step) => !step.done) : -1;

  return (
    <section aria-labelledby="steps-title" className="flex flex-col gap-3">
      <div>
        <h3 id="steps-title" className="text-lg font-medium">
          Pasos de la vacante
        </h3>
        <p className="text-sm text-ink-muted">
          Van en este orden. Pulsa un paso para abrirlo; el que sigue está resaltado.
        </p>
      </div>
      <ol className="flex flex-col gap-2">
        {steps.map((step, index) => {
          const current = index === next;
          return (
            <li key={step.title}>
              <button
                type="button"
                onClick={step.open}
                aria-current={current ? "step" : undefined}
                aria-label={`Paso ${index + 1}: ${step.title}.${step.status ? ` ${step.status}.` : ""}${
                  current ? " Es el paso que sigue." : ""
                }`}
                className={`flex min-h-11 w-full items-start gap-4 rounded-3xl px-5 py-4 text-left outline-none focus-visible:ring-2 focus-visible:ring-accent-blue ${
                  current ? "bg-ink text-white" : "border border-line bg-surface hover:border-ink/40"
                }`}
              >
                <span
                  aria-hidden="true"
                  className={`flex size-8 shrink-0 items-center justify-center rounded-full text-sm font-medium ${
                    current ? "bg-white text-ink" : "bg-neutral-soft text-neutral-ink"
                  }`}
                >
                  {step.done ? "✓" : index + 1}
                </span>
                <span className="flex min-w-0 flex-1 flex-col gap-0.5">
                  <span className="flex flex-wrap items-baseline justify-between gap-x-3">
                    <span className="font-medium">{step.title}</span>
                    {step.status && (
                      <span className={`text-sm ${current ? "text-white/80" : "text-ink-muted"}`}>
                        {step.status}
                      </span>
                    )}
                  </span>
                  <span className={`text-sm ${current ? "text-white/80" : "text-ink-muted"}`}>
                    {step.hint}
                  </span>
                </span>
              </button>
            </li>
          );
        })}
      </ol>
    </section>
  );
}
