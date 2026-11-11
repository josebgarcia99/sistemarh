"use client";

import { useQuery } from "@tanstack/react-query";
import { ApiError } from "@/lib/api/client";
import { fetchReadiness, type ComponentStatus } from "@/lib/api/health";

const COMPONENT_LABELS: Record<string, string> = {
  sql_server: "SQL Server",
  redis: "Cola de tareas (Redis)",
  almacenamiento: "Almacenamiento documental",
};

const STATUS_LABELS: Record<ComponentStatus, string> = {
  ok: "Responde",
  fallo: "No responde",
  sin_configurar: "Sin configurar",
};

const STATUS_STYLES: Record<ComponentStatus, string> = {
  ok: "bg-accent-blue-soft text-accent-blue-ink",
  fallo: "bg-accent-red-soft text-accent-red-ink",
  sin_configurar: "bg-neutral-soft text-neutral-ink",
};

export function SystemStatus() {
  const { data, error, isPending, refetch, isFetching } = useQuery({
    queryKey: ["system", "readiness"],
    queryFn: ({ signal }) => fetchReadiness(signal),
    refetchInterval: 15_000,
  });

  return (
    <section
      aria-labelledby="estado-titulo"
      className="flex flex-col gap-5 rounded-card bg-white/60 p-7"
    >
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 id="estado-titulo" className="text-xl font-medium">
          Estado del sistema
        </h2>
        <button
          type="button"
          onClick={() => refetch()}
          disabled={isFetching}
          className="min-h-11 rounded-full border border-line bg-surface px-5 disabled:opacity-60"
        >
          {isFetching ? "Comprobando…" : "Comprobar de nuevo"}
        </button>
      </div>

      {isPending ? (
        <p role="status" className="text-ink-muted">
          Comprobando los servicios…
        </p>
      ) : error ? (
        <div role="alert" className="rounded-tile bg-accent-red-soft p-5 text-accent-red-ink">
          <p className="font-medium">No se pudo consultar la API.</p>
          <p className="text-sm">
            {error instanceof ApiError && error.correlationId
              ? `Identificador para soporte: ${error.correlationId}`
              : "Verifica que la API esté en ejecución."}
          </p>
        </div>
      ) : (
        <>
          <p className="text-ink-muted">
            {data.ready
              ? "Todos los servicios responden."
              : "Hay servicios que no responden o no están configurados."}
          </p>
          <ul className="flex flex-col gap-2">
            {data.components.map((component) => (
              <li
                key={component.name}
                className="flex flex-wrap items-center justify-between gap-3 rounded-tile bg-surface px-5 py-4"
              >
                <span className="font-medium">
                  {COMPONENT_LABELS[component.name] ?? component.name}
                </span>
                <span
                  className={`rounded-full px-3 py-1 text-sm ${STATUS_STYLES[component.status]}`}
                >
                  {STATUS_LABELS[component.status]}
                </span>
              </li>
            ))}
          </ul>
        </>
      )}
    </section>
  );
}
