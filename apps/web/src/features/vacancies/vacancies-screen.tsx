"use client";

import { keepPreviousData, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Modal } from "@/components/ui/modal";
import {
  cardClass,
  fieldClass,
  primaryButtonClass,
  secondaryButtonClass,
} from "@/components/ui/styles";
import { useSession } from "@/features/auth/use-session";
import { EvaluationWorkspace } from "@/features/evaluation/evaluation-workspace";
import { CandidatesWorkspace } from "@/features/recruitment/candidates-workspace";
import { describeError } from "@/lib/api/client";
import {
  listVacancies,
  MY_ACCESS_LABELS,
  type Scope,
  type Vacancy,
  STATUS_LABELS,
  type VacancyStatus,
  vacancyStatusSchema,
} from "@/lib/api/vacancies";
import { VacancyForm } from "./vacancy-form";
import { VacancyPanel } from "./vacancy-panel";

const PAGE_SIZE = 10;

const STATUS_STYLES: Record<VacancyStatus, string> = {
  BORRADOR: "bg-neutral-soft text-neutral-ink",
  ABIERTA: "bg-accent-blue-soft text-accent-blue-ink",
  PAUSADA: "bg-neutral-soft text-neutral-ink",
  CERRADA: "bg-ink text-white",
  CANCELADA: "bg-accent-red-soft text-accent-red-ink",
  ARCHIVADA: "bg-neutral-soft text-neutral-ink",
};

export function VacanciesScreen() {
  const { user } = useSession();
  const queryClient = useQueryClient();
  const isAdmin = user?.role === "ADMINISTRADOR";
  const scopes: { value: Scope; label: string }[] = isAdmin
    ? [
        { value: "all", label: "Todas" },
        { value: "mine", label: "Mis vacantes" },
      ]
    : [
        { value: "mine", label: "Mis vacantes" },
        { value: "shared", label: "Compartidas conmigo" },
      ];

  const [scope, setScope] = useState<Scope>(isAdmin ? "all" : "mine");
  const [status, setStatus] = useState<VacancyStatus | "">("");
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  // Aviso de alta: se muestra dentro del panel de la vacante recién creada.
  const [created, setCreated] = useState<{ id: string; message: string } | null>(null);
  // Vacante cuyo perfil y prompt se están editando; ocupa toda la pantalla.
  const [evaluating, setEvaluating] = useState<Vacancy | null>(null);
  // Vacante cuyos candidatos se están gestionando; también ocupa toda la pantalla.
  const [recruiting, setRecruiting] = useState<Vacancy | null>(null);

  const { data, error, isPending } = useQuery({
    queryKey: ["vacancies", { scope, status, search, page }],
    queryFn: ({ signal }) =>
      listVacancies({ scope, status, search, page, pageSize: PAGE_SIZE }, signal),
    placeholderData: keepPreviousData,
  });
  const total = data?.total ?? 0;
  const pageCount = Math.max(1, Math.ceil(total / PAGE_SIZE));

  if (recruiting) {
    return (
      <CandidatesWorkspace
        vacancyId={recruiting.id}
        vacancyName={recruiting.name}
        canEdit={recruiting.my_access !== "LECTURA"}
        canManage={
          recruiting.my_access === "RESPONSABLE" || recruiting.my_access === "ADMINISTRADOR"
        }
        onBack={() => setRecruiting(null)}
      />
    );
  }
  if (evaluating) {
    return (
      <EvaluationWorkspace
        vacancyId={evaluating.id}
        vacancyName={evaluating.name}
        canEdit={evaluating.my_access !== "LECTURA"}
        canApprove={
          evaluating.my_access === "RESPONSABLE" || evaluating.my_access === "ADMINISTRADOR"
        }
        onBack={() => setEvaluating(null)}
      />
    );
  }

  return (
    <>
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-4xl font-medium tracking-tight sm:text-5xl">Vacantes</h1>
          <p className="mt-2 text-ink-muted">
            Privadas por defecto. Compartir una vacante no transfiere su propiedad.
          </p>
        </div>
        <button type="button" className={primaryButtonClass} onClick={() => setCreating(true)}>
          Nueva vacante
        </button>
      </div>

      <div className="flex flex-wrap items-start gap-6">
        <section className={`${cardClass} flex min-w-0 flex-[3_1_560px] flex-col gap-5`}>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div role="group" aria-label="Qué vacantes mostrar" className="flex flex-wrap gap-1.5">
              {scopes.map((option) => (
                <button
                  key={option.value}
                  type="button"
                  aria-pressed={scope === option.value}
                  onClick={() => {
                    setScope(option.value);
                    setPage(1);
                  }}
                  className={`min-h-11 rounded-full px-5 ${
                    scope === option.value ? "bg-ink text-white" : "border border-line bg-surface"
                  }`}
                >
                  {option.label}
                </button>
              ))}
            </div>
            <p className="text-sm text-ink-muted">
              {total === 1 ? "1 vacante" : `${total} vacantes`}
            </p>
          </div>

          <div className="flex flex-wrap gap-3">
            <label htmlFor="vacancy-search" className="sr-only">
              Buscar por nombre o departamento
            </label>
            <input
              id="vacancy-search"
              type="search"
              placeholder="Buscar por nombre o departamento"
              value={search}
              onChange={(event) => {
                setSearch(event.target.value);
                setPage(1);
              }}
              className={`${fieldClass} flex-[2_1_240px]`}
            />
            <select
              aria-label="Filtrar por estado"
              value={status}
              onChange={(event) => {
                setStatus(event.target.value ? vacancyStatusSchema.parse(event.target.value) : "");
                setPage(1);
              }}
              className={`${fieldClass} flex-[1_1_160px]`}
            >
              <option value="">Todos los estados</option>
              {vacancyStatusSchema.options.map((option) => (
                <option key={option} value={option}>
                  {STATUS_LABELS[option]}
                </option>
              ))}
            </select>
          </div>

          {error ? (
            <p role="alert" className="rounded-tile bg-accent-red-soft px-5 py-4 text-accent-red-ink">
              {describeError(error)}
            </p>
          ) : isPending ? (
            <p role="status" className="text-ink-muted">
              Cargando vacantes…
            </p>
          ) : total === 0 ? (
            <p className="text-ink-muted">
              {search || status
                ? "Ninguna vacante coincide con los filtros."
                : scope === "shared"
                  ? "Nadie ha compartido vacantes contigo."
                  : "Todavía no hay vacantes. Crea la primera con «Nueva vacante»."}
            </p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[540px] border-separate border-spacing-y-1.5 text-left">
                <thead>
                  <tr className="text-sm text-ink-muted">
                    <th scope="col" className="px-4 pb-1 font-normal">
                      Vacante
                    </th>
                    <th scope="col" className="px-4 pb-1 font-normal">
                      Responsable
                    </th>
                    <th scope="col" className="px-4 pb-1 font-normal">
                      Estado
                    </th>
                    <th scope="col" className="px-4 pb-1 font-normal">
                      Mi acceso
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {data.items.map((vacancy) => {
                    const selected = vacancy.id === selectedId;
                    const cell = `px-4 py-3 first:rounded-l-3xl last:rounded-r-3xl ${
                      selected ? "bg-ink text-white" : "bg-surface"
                    }`;
                    return (
                      <tr key={vacancy.id}>
                        <td className={cell}>
                          <button
                            type="button"
                            aria-label={`Abrir ${vacancy.name}`}
                            aria-pressed={selected}
                            onClick={() => setSelectedId(vacancy.id)}
                            className="flex min-h-11 flex-col text-left"
                          >
                            <span className="font-medium underline-offset-4 hover:underline">
                              {vacancy.name}
                            </span>
                            <span className={`text-sm ${selected ? "text-white/80" : "text-ink-muted"}`}>
                              {vacancy.department} · {vacancy.location}
                            </span>
                          </button>
                        </td>
                        <td className={cell}>{vacancy.owner?.full_name ?? "Sin datos"}</td>
                        <td className={cell}>
                          <span
                            className={`rounded-full px-3 py-1 text-sm ${
                              selected ? "bg-white text-ink" : STATUS_STYLES[vacancy.status]
                            }`}
                          >
                            {STATUS_LABELS[vacancy.status]}
                          </span>
                        </td>
                        <td className={cell}>{MY_ACCESS_LABELS[vacancy.my_access]}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}

          {pageCount > 1 && (
            <nav aria-label="Paginación" className="flex flex-wrap items-center justify-end gap-3">
              <button
                type="button"
                className={secondaryButtonClass}
                disabled={page <= 1}
                onClick={() => setPage((p) => p - 1)}
              >
                Anterior
              </button>
              <span className="text-sm text-ink-muted">
                Página {page} de {pageCount}
              </span>
              <button
                type="button"
                className={secondaryButtonClass}
                disabled={page >= pageCount}
                onClick={() => setPage((p) => p + 1)}
              >
                Siguiente
              </button>
            </nav>
          )}
        </section>

        {selectedId && (
          <div className="min-w-0 flex-[2_1_380px]">
            <VacancyPanel
              key={selectedId}
              vacancyId={selectedId}
              initialNotice={created?.id === selectedId ? created.message : undefined}
              onOpenEvaluation={setEvaluating}
              onOpenCandidates={setRecruiting}
              onClose={() => setSelectedId(null)}
            />
          </div>
        )}
      </div>

      {creating && (
        <Modal title="Nueva vacante" onClose={() => setCreating(false)}>
          <VacancyForm
            onCancel={() => setCreating(false)}
            onDone={(vacancy, message) => {
              setCreating(false);
              setCreated({ id: vacancy.id, message });
              setSelectedId(vacancy.id);
              void queryClient.invalidateQueries({ queryKey: ["vacancies"] });
            }}
          />
        </Modal>
      )}
    </>
  );
}
