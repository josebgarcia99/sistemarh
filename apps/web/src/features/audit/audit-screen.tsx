"use client";

import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { cardClass, fieldClass, secondaryButtonClass } from "@/components/ui/styles";
import { useSession } from "@/features/auth/use-session";
import { AUDIT_ACTION_LABELS, type AuditEvent, listAuditEvents } from "@/lib/api/audit";
import { describeError } from "@/lib/api/client";

const PAGE_SIZE = 20;

const dateFormat = new Intl.DateTimeFormat("es-MX", {
  timeZone: "America/Mexico_City",
  dateStyle: "medium",
  timeStyle: "medium",
});

const RESULT_STYLES: Record<AuditEvent["result"], string> = {
  PERMITIDO: "bg-accent-blue-soft text-accent-blue-ink",
  DENEGADO: "bg-accent-red-soft text-accent-red-ink",
  FALLIDO: "bg-accent-red-soft text-accent-red-ink",
};
const RESULT_LABELS: Record<AuditEvent["result"], string> = {
  PERMITIDO: "Permitido",
  DENEGADO: "Denegado",
  FALLIDO: "Fallido",
};

function describeDetails(details: AuditEvent["details"]): string {
  return Object.entries(details)
    .map(([key, value]) => `${key}: ${typeof value === "object" ? JSON.stringify(value) : value}`)
    .join(" · ");
}

export function AuditScreen() {
  const { user } = useSession();
  const [action, setAction] = useState("");
  const [page, setPage] = useState(1);
  const isAdmin = user?.role === "ADMINISTRADOR";

  const { data, error, isPending } = useQuery({
    queryKey: ["audit", { action, page }],
    queryFn: ({ signal }) => listAuditEvents({ action, page, pageSize: PAGE_SIZE }, signal),
    placeholderData: keepPreviousData,
    enabled: isAdmin,
  });

  if (!isAdmin) {
    return (
      <div role="alert" className={cardClass}>
        <h1 className="text-2xl font-medium">Sin acceso</h1>
        <p className="mt-1 text-ink-muted">La auditoría es solo para administradores.</p>
      </div>
    );
  }

  const total = data?.total ?? 0;
  const pageCount = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <>
      <div>
        <h1 className="text-4xl font-medium tracking-tight sm:text-5xl">Auditoría</h1>
        <p className="mt-2 text-ink-muted">
          Registro de accesos y cambios. Los eventos no se pueden modificar ni borrar. Horario
          America/Mexico_City.
        </p>
      </div>

      <section className={`${cardClass} flex flex-col gap-5`}>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <select
            aria-label="Filtrar por tipo de evento"
            value={action}
            onChange={(event) => {
              setAction(event.target.value);
              setPage(1);
            }}
            className={`${fieldClass} max-w-sm`}
          >
            <option value="">Todos los eventos</option>
            {Object.entries(AUDIT_ACTION_LABELS).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
          <p className="text-sm text-ink-muted">{total === 1 ? "1 evento" : `${total} eventos`}</p>
        </div>

        {error ? (
          <p role="alert" className="rounded-tile bg-accent-red-soft px-5 py-4 text-accent-red-ink">
            {describeError(error)}
          </p>
        ) : isPending ? (
          <p role="status" className="text-ink-muted">
            Cargando eventos…
          </p>
        ) : total === 0 ? (
          <p className="text-ink-muted">No hay eventos con ese filtro.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[860px] border-separate border-spacing-y-1.5 text-left text-sm">
              <thead>
                <tr className="text-ink-muted">
                  <th scope="col" className="px-4 pb-1 font-normal">
                    Fecha
                  </th>
                  <th scope="col" className="px-4 pb-1 font-normal">
                    Evento
                  </th>
                  <th scope="col" className="px-4 pb-1 font-normal">
                    Resultado
                  </th>
                  <th scope="col" className="px-4 pb-1 font-normal">
                    Quién
                  </th>
                  <th scope="col" className="px-4 pb-1 font-normal">
                    Detalle
                  </th>
                  <th scope="col" className="px-4 pb-1 font-normal">
                    IP
                  </th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((event) => (
                  <tr key={event.id}>
                    <td className="rounded-l-3xl bg-surface px-4 py-3 whitespace-nowrap">
                      {dateFormat.format(new Date(event.occurred_at))}
                    </td>
                    <td className="bg-surface px-4 py-3 font-medium">
                      {AUDIT_ACTION_LABELS[event.action] ?? event.action}
                    </td>
                    <td className="bg-surface px-4 py-3">
                      <span className={`rounded-full px-3 py-1 ${RESULT_STYLES[event.result]}`}>
                        {RESULT_LABELS[event.result]}
                      </span>
                    </td>
                    <td className="bg-surface px-4 py-3">{event.actor_name ?? "Sin identificar"}</td>
                    <td className="bg-surface px-4 py-3 text-ink-muted">
                      {describeDetails(event.details) || "Sin detalle"}
                    </td>
                    <td className="rounded-r-3xl bg-surface px-4 py-3 text-ink-muted">
                      {event.ip ?? ""}
                    </td>
                  </tr>
                ))}
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
    </>
  );
}
