"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";
import { cardClass, secondaryButtonClass } from "@/components/ui/styles";
import { useSession } from "@/features/auth/use-session";
import { ActivityList, StatGroup, StatTile } from "@/features/reports/dashboard-view";
import { SystemStatus } from "@/features/system/system-status";
import { describeError } from "@/lib/api/client";
import { getOverview, lastDays } from "@/lib/api/reports";

const DAYS = 30;

/** Inicio: el tablero de la persona, con sus vacantes y las compartidas. */
export function HomeScreen() {
  const { user } = useSession();
  const firstName = user?.full_name.split(" ")[0] ?? "";
  const isAdmin = user?.role === "ADMINISTRADOR";
  const [range] = useState(() => lastDays(DAYS));
  const { data, error } = useQuery({
    queryKey: ["reports", "overview", "home", range],
    queryFn: ({ signal }) => getOverview(range, signal),
  });

  return (
    <>
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-4xl font-medium tracking-tight sm:text-5xl">Hola, {firstName}</h1>
          <p className="mt-2 max-w-2xl text-ink-muted">
            {isAdmin
              ? "Así va el reclutamiento en todas las vacantes."
              : "Así van tus vacantes y las que te compartieron."}
          </p>
        </div>
        <Link href="/indicadores" className={`${secondaryButtonClass} inline-flex items-center`}>
          Ver indicadores y reportes
        </Link>
      </div>

      {error ? (
        <p role="alert" className="rounded-tile bg-accent-red-soft px-5 py-4 text-accent-red-ink">
          {describeError(error)}
        </p>
      ) : !data ? (
        <p role="status" className="text-ink-muted">
          Cargando tu tablero…
        </p>
      ) : (
        <>
          <StatGroup title="Hoy">
            {isAdmin ? (
              <StatTile
                label="Vacantes"
                value={data.snapshot.vacancies}
                hint={`${data.snapshot.vacancies_open} ${data.snapshot.vacancies_open === 1 ? "abierta" : "abiertas"}`}
              />
            ) : (
              <>
                <StatTile label="Vacantes propias" value={data.snapshot.own} />
                <StatTile label="Vacantes compartidas" value={data.snapshot.shared} />
              </>
            )}
            <StatTile label="Procesos pendientes" value={data.snapshot.active_applications} />
            <StatTile label="Candidatos en llamada" value={data.snapshot.in_calls} />
            <StatTile label="Pruebas pendientes" value={data.snapshot.tests_pending} />
            <StatTile label="Entrevistas pendientes" value={data.snapshot.interviews_pending} />
          </StatGroup>
          <StatGroup title={`Últimos ${DAYS} días`}>
            <StatTile label="CV analizados" value={data.totals.cv_analyzed} />
            <StatTile label="Aceptados por IA" value={data.totals.ai_accepted} />
            <StatTile label="Rechazados por IA" value={data.totals.ai_rejected} />
            <StatTile label="Procesos cerrados" value={data.totals.closed} />
            <StatTile label="Contrataciones" value={data.totals.hires} />
          </StatGroup>
          <section className={`${cardClass} flex flex-col gap-4`}>
            <h2 className="text-xl font-medium">Actividad reciente</h2>
            <ActivityList items={data.recent} />
          </section>
        </>
      )}
      {isAdmin && <SystemStatus />}
    </>
  );
}
