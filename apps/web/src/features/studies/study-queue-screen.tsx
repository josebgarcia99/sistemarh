"use client";

import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { cardClass, fieldClass, secondaryButtonClass } from "@/components/ui/styles";
import { AssessmentsSection } from "@/features/assessments/assessments-section";
import { useSession } from "@/features/auth/use-session";
import { listStudyQueue, STATUS_LABELS, type StudyQueueItem } from "@/lib/api/assessments";
import { describeError } from "@/lib/api/client";

const dateFormat = new Intl.DateTimeFormat("es-MX", {
  timeZone: "America/Mexico_City",
  dateStyle: "medium",
});

/**
 * Lista de trabajo de estudios socioeconómicos: las personas en proceso de
 * cualquier vacante y el estado de su estudio. Para el analista de estudios y
 * los administradores.
 */
export function StudyQueueScreen() {
  const { user } = useSession();
  const allowed = user?.role === "ANALISTA_ESTUDIOS" || user?.role === "ADMINISTRADOR";
  const [search, setSearch] = useState("");
  const [open, setOpen] = useState<StudyQueueItem | null>(null);
  const { data, error } = useQuery({
    queryKey: ["study-queue", search],
    queryFn: ({ signal }) => listStudyQueue(search, signal),
    enabled: allowed,
  });

  if (!allowed) {
    return (
      <p role="alert" className="rounded-tile bg-accent-red-soft px-5 py-4 text-accent-red-ink">
        Esta sección es para el analista de estudios socioeconómicos y los administradores.
      </p>
    );
  }
  if (open) {
    return (
      <>
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <p className="text-sm text-ink-muted">{open.vacancy_name}</p>
            <h1 className="text-4xl font-medium tracking-tight sm:text-5xl">{open.candidate_name}</h1>
            <p className="mt-2 max-w-3xl text-ink-muted">
              Estudio socioeconómico. Aquí cargas el formato y las fotografías, capturas el
              estudio y usas las ayudas de IA.
            </p>
          </div>
          <button type="button" className={secondaryButtonClass} onClick={() => setOpen(null)}>
            Volver a la lista
          </button>
        </div>
        <AssessmentsSection
          applicationId={open.application_id}
          vacancyId={open.vacancy_id}
          active={open.active}
        />
      </>
    );
  }
  return (
    <>
      <div>
        <h1 className="text-4xl font-medium tracking-tight sm:text-5xl">Estudios socioeconómicos</h1>
        <p className="mt-2 max-w-3xl text-ink-muted">
          Personas en proceso en todas las vacantes y el estado de su estudio. Abre a una persona
          para registrar o continuar su estudio.
        </p>
      </div>
      <section className={`${cardClass} flex flex-col gap-4`}>
        <div className="flex max-w-xl flex-col gap-2">
          <label htmlFor="study-search" className="text-sm text-ink-muted">
            Buscar por persona o vacante
          </label>
          <input
            id="study-search"
            type="search"
            maxLength={100}
            className={fieldClass}
            value={search}
            onChange={(event) => setSearch(event.target.value)}
          />
        </div>
        {error && (
          <p role="alert" className="rounded-2xl bg-accent-red-soft px-4 py-3 text-accent-red-ink">
            {describeError(error)}
          </p>
        )}
        {!data && !error && <p className="text-ink-muted">Cargando…</p>}
        {data && data.length === 0 && (
          <p className="text-ink-muted">
            {search ? "Nadie coincide con la búsqueda." : "No hay personas en proceso por ahora."}
          </p>
        )}
        {data && data.length > 0 && (
          <ul aria-label="Personas" className="flex flex-col gap-1.5">
            {data.map((item) => (
              <li key={item.application_id}>
                <button
                  type="button"
                  aria-label={`Abrir el estudio de ${item.candidate_name}`}
                  className="flex min-h-14 w-full flex-wrap items-center justify-between gap-x-6 gap-y-1 rounded-2xl bg-surface px-5 py-3 text-left hover:bg-surface-soft focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent-blue-ink"
                  onClick={() => setOpen(item)}
                >
                  <span>
                    <span className="block font-medium">{item.candidate_name}</span>
                    <span className="block text-sm text-ink-muted">{item.vacancy_name}</span>
                  </span>
                  <span className="text-sm text-ink-muted">
                    {item.study_status
                      ? `Estudio: ${STATUS_LABELS[item.study_status] ?? item.study_status}` +
                        (item.study_updated_at
                          ? ` · ${dateFormat.format(new Date(item.study_updated_at))}`
                          : "")
                      : "Sin estudio"}
                    {!item.active && " · Proceso cerrado"}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </section>
    </>
  );
}
