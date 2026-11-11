"use client";

import type { ReactNode } from "react";
import { cardClass } from "@/components/ui/styles";
import { dateTimeFormat } from "@/features/recruitment/shared";
import { MOVEMENT_LABELS } from "@/lib/api/recruitment";
import {
  type Activity,
  OPERATION_LABELS,
  type Overview,
  type StageRow,
  VACANCY_STATUS_LABELS,
} from "@/lib/api/reports";

const numberFormat = new Intl.NumberFormat("es-MX", { maximumFractionDigits: 1 });
const moneyFormat = new Intl.NumberFormat("es-MX", {
  style: "currency",
  currency: "USD",
  maximumFractionDigits: 2,
});
const monthFormat = new Intl.DateTimeFormat("es-MX", {
  timeZone: "UTC",
  month: "long",
  year: "numeric",
});

export function formatDays(days: number | null): string {
  if (days === null) return "—";
  return `${numberFormat.format(days)} ${days === 1 ? "día" : "días"}`;
}

/** Una cifra con su nombre. El valor va en tinta normal; no depende del color. */
export function StatTile({ label, value, hint }: { label: string; value: ReactNode; hint?: string }) {
  return (
    <div className="flex min-w-0 flex-col gap-1 rounded-tile bg-surface px-5 py-4">
      <dt className="text-sm text-ink-muted">{label}</dt>
      <dd className="text-3xl font-medium tracking-tight">{value}</dd>
      {hint && <dd className="text-sm text-ink-muted">{hint}</dd>}
    </div>
  );
}

export function StatGroup({ title, note, children }: { title: string; note?: string; children: ReactNode }) {
  return (
    <section className={`${cardClass} flex flex-col gap-4`} aria-label={title}>
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="text-xl font-medium">{title}</h2>
        {note && <p className="text-sm text-ink-muted">{note}</p>}
      </div>
      <dl className="grid grid-cols-2 gap-3 md:grid-cols-4">{children}</dl>
    </section>
  );
}

/** Embudo: una barra por etapa, del mismo tono, con la cifra escrita al lado. */
export function FunnelBars({ stages, hired }: { stages: StageRow[]; hired: number }) {
  const steps = [
    ...stages.map((stage) => ({ name: stage.name, value: stage.reached, conversion: stage.conversion })),
    { name: "Contratadas", value: hired, conversion: null },
  ];
  const max = Math.max(1, ...steps.map((step) => step.value));
  return (
    <ol aria-label="Embudo por etapa" className="flex flex-col gap-2">
      {steps.map((step) => (
        <li
          key={step.name}
          className="grid grid-cols-[minmax(0,13rem)_minmax(0,1fr)_auto] items-center gap-3"
          title={`${step.name}: ${step.value}`}
        >
          <span className="truncate">{step.name}</span>
          <span aria-hidden="true" className="h-3 rounded-[4px] bg-surface">
            <span
              className="block h-3 rounded-[4px] bg-accent-blue"
              style={{ width: `${(step.value / max) * 100}%` }}
            />
          </span>
          <span className="min-w-28 text-right tabular-nums">
            {step.value}
            {step.conversion !== null && (
              <span className="text-sm text-ink-muted"> · pasa {numberFormat.format(step.conversion)} %</span>
            )}
          </span>
        </li>
      ))}
    </ol>
  );
}

export function ActivityList({ items }: { items: Activity[] }) {
  if (items.length === 0) return <p className="text-ink-muted">Todavía no hay movimientos.</p>;
  return (
    <ol aria-label="Actividad reciente" className="flex flex-col gap-2">
      {items.map((item, index) => (
        <li key={`${item.occurred_at}-${index}`} className="rounded-2xl bg-surface px-4 py-3">
          <p>
            <span className="font-medium">{item.candidate}</span> ·{" "}
            {MOVEMENT_LABELS[item.kind] ?? item.kind}
            {item.stage ? ` (${item.stage})` : ""}
          </p>
          <p className="text-sm text-ink-muted">
            {item.vacancy} · {dateTimeFormat.format(new Date(item.occurred_at))} ·{" "}
            {item.actor_name ?? "Sistema"}
          </p>
        </li>
      ))}
    </ol>
  );
}

const thClass = "py-2 pr-4 text-left text-sm font-normal text-ink-muted";
const tdClass = "py-2 pr-4 align-top";
const numClass = `${tdClass} text-right tabular-nums`;
const numHeadClass = `${thClass} text-right`;

function DataTable({
  label,
  head,
  children,
}: {
  label: string;
  head: { text: string; numeric?: boolean }[];
  children: ReactNode;
}) {
  return (
    <div className="overflow-x-auto">
      <table aria-label={label} className="w-full min-w-[640px] border-collapse">
        <thead>
          <tr className="border-b border-line">
            {head.map((column) => (
              <th key={column.text} scope="col" className={column.numeric ? numHeadClass : thClass}>
                {column.text}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>{children}</tbody>
      </table>
    </div>
  );
}

function monthLabel(month: string): string {
  const label = monthFormat.format(new Date(`${month}-01T00:00:00Z`));
  return label.charAt(0).toUpperCase() + label.slice(1);
}

/** Tablero completo. Lo que es solo de administradores llega vacío a los demás. */
export function DashboardView({ data }: { data: Overview }) {
  const { snapshot, totals } = data;
  return (
    <>
      <StatGroup title="Hoy" note="Fotografía del momento; no depende del periodo.">
        <StatTile
          label="Vacantes"
          value={snapshot.vacancies}
          hint={`${snapshot.vacancies_open} ${snapshot.vacancies_open === 1 ? "abierta" : "abiertas"}`}
        />
        <StatTile label="Procesos pendientes" value={snapshot.active_applications} hint="Postulaciones activas" />
        <StatTile label="Candidatos en llamada" value={snapshot.in_calls} />
        <StatTile label="Pruebas pendientes" value={snapshot.tests_pending} hint="Psicométricas y técnicas" />
        <StatTile label="Entrevistas pendientes" value={snapshot.interviews_pending} />
      </StatGroup>

      <StatGroup title="En el periodo">
        <StatTile
          label="CV analizados"
          value={totals.cv_analyzed}
          hint={`Aceptados: ${totals.ai_accepted} · rechazados: ${totals.ai_rejected} · no evaluables: ${totals.ai_unevaluable}`}
        />
        <StatTile label="Postulaciones nuevas" value={totals.applications} />
        <StatTile label="Procesos cerrados" value={totals.closed} />
        <StatTile label="Contrataciones" value={totals.hires} />
        <StatTile label="Desistimientos" value={totals.withdrawals} />
        <StatTile label="No contratados" value={totals.not_hired} />
        <StatTile
          label="Otros cierres"
          value={totals.not_located + totals.cancelled + totals.other_closures}
          hint={`No localizados: ${totals.not_located} · vacante cancelada: ${totals.cancelled}`}
        />
        <StatTile
          label="Tiempo de cobertura"
          value={formatDays(totals.coverage_days)}
          hint="De abrir la convocatoria a contratar"
        />
      </StatGroup>

      <section className={`${cardClass} flex flex-col gap-4`} aria-label="Etapas">
        <h2 className="text-xl font-medium">Embudo y tiempos por etapa</h2>
        <p className="text-sm text-ink-muted">
          De las postulaciones dadas de alta en el periodo, cuántas llegaron a cada etapa o más
          allá. Los días son el promedio de las estancias que terminaron en el periodo.
        </p>
        <FunnelBars stages={data.stages} hired={data.funnel_hired} />
        <DataTable
          label="Etapas"
          head={[
            { text: "Etapa" },
            { text: "Activas hoy", numeric: true },
            { text: "Llegaron", numeric: true },
            { text: "Pasan a la siguiente", numeric: true },
            { text: "Tiempo promedio", numeric: true },
          ]}
        >
          {data.stages.map((stage) => (
            <tr key={`${stage.kind}-${stage.name}`} className="border-b border-line last:border-0">
              <td className={tdClass}>{stage.name}</td>
              <td className={numClass}>{stage.active}</td>
              <td className={numClass}>{stage.reached}</td>
              <td className={numClass}>
                {stage.conversion === null ? "—" : `${numberFormat.format(stage.conversion)} %`}
              </td>
              <td className={numClass}>{formatDays(stage.average_days)}</td>
            </tr>
          ))}
        </DataTable>
      </section>

      <section className={`${cardClass} flex flex-col gap-4`} aria-label="Vacantes">
        <h2 className="text-xl font-medium">Por vacante</h2>
        {data.vacancies.length === 0 ? (
          <p className="text-ink-muted">No hay vacantes con estos filtros.</p>
        ) : (
          <DataTable
            label="Vacantes"
            head={[
              { text: "Vacante" },
              { text: "Responsable" },
              { text: "Estado" },
              { text: "Plazas cubiertas", numeric: true },
              { text: "Activas hoy", numeric: true },
              { text: "CV analizados", numeric: true },
              { text: "Cerrados", numeric: true },
              { text: "Contrataciones", numeric: true },
              { text: "Cobertura", numeric: true },
            ]}
          >
            {data.vacancies.map((vacancy) => (
              <tr key={vacancy.id} className="border-b border-line last:border-0">
                <td className={tdClass}>
                  {vacancy.name}
                  <span className="block text-sm text-ink-muted">{vacancy.department}</span>
                </td>
                <td className={tdClass}>{vacancy.owner_name}</td>
                <td className={tdClass}>{VACANCY_STATUS_LABELS[vacancy.status] ?? vacancy.status}</td>
                <td className={numClass}>
                  {vacancy.hires_total} de {vacancy.positions}
                </td>
                <td className={numClass}>{vacancy.active}</td>
                <td className={numClass}>{vacancy.cv_analyzed}</td>
                <td className={numClass}>{vacancy.closed}</td>
                <td className={numClass}>{vacancy.hires}</td>
                <td className={numClass}>{formatDays(vacancy.coverage_days)}</td>
              </tr>
            ))}
          </DataTable>
        )}
      </section>

      {data.recruiters && (
        <section className={`${cardClass} flex flex-col gap-4`} aria-label="Reclutadores">
          <h2 className="text-xl font-medium">Carga de trabajo por responsable</h2>
          <p className="text-sm text-ink-muted">
            Cada contratación se cuenta una sola vez, a nombre de la persona responsable de la
            vacante; colaborar en una vacante ajena no la duplica.
          </p>
          <DataTable
            label="Reclutadores"
            head={[
              { text: "Responsable" },
              { text: "Vacantes", numeric: true },
              { text: "Abiertas", numeric: true },
              { text: "Colabora en", numeric: true },
              { text: "Postulaciones activas", numeric: true },
              { text: "Cerrados", numeric: true },
              { text: "Contrataciones", numeric: true },
            ]}
          >
            {data.recruiters.map((row) => (
              <tr key={row.user_id} className="border-b border-line last:border-0">
                <td className={tdClass}>{row.name}</td>
                <td className={numClass}>{row.vacancies}</td>
                <td className={numClass}>{row.vacancies_open}</td>
                <td className={numClass}>{row.collaborating}</td>
                <td className={numClass}>{row.active}</td>
                <td className={numClass}>{row.closed}</td>
                <td className={numClass}>{row.hires}</td>
              </tr>
            ))}
          </DataTable>
        </section>
      )}

      <section className={`${cardClass} flex flex-col gap-4`} aria-label="Histórico mensual">
        <h2 className="text-xl font-medium">Histórico por mes</h2>
        {data.months.length === 0 ? (
          <p className="text-ink-muted">No hay actividad en el periodo.</p>
        ) : (
          <DataTable
            label="Histórico mensual"
            head={[
              { text: "Mes" },
              { text: "CV analizados", numeric: true },
              { text: "Postulaciones nuevas", numeric: true },
              { text: "Cerrados", numeric: true },
              { text: "Contrataciones", numeric: true },
              { text: "Desistimientos", numeric: true },
            ]}
          >
            {data.months.map((month) => (
              <tr key={month.month} className="border-b border-line last:border-0">
                <td className={tdClass}>{monthLabel(month.month)}</td>
                <td className={numClass}>{month.cv_analyzed}</td>
                <td className={numClass}>{month.applications}</td>
                <td className={numClass}>{month.closed}</td>
                <td className={numClass}>{month.hires}</td>
                <td className={numClass}>{month.withdrawals}</td>
              </tr>
            ))}
          </DataTable>
        )}
      </section>

      {data.ai && (
        <section className={`${cardClass} flex flex-col gap-4`} aria-label="Uso de IA">
          <h2 className="text-xl font-medium">Uso de IA y errores técnicos</h2>
          <dl className="grid grid-cols-2 gap-3 md:grid-cols-4">
            <StatTile label="Llamadas a la IA" value={data.ai.calls} />
            <StatTile label="Costo estimado" value={moneyFormat.format(Number(data.ai.cost_usd))} />
            <StatTile label="Fallos de IA" value={data.ai.failures} />
            <StatTile label="CV sin poder evaluarse" value={data.cv_failures ?? 0} />
          </dl>
          {data.ai.operations.length > 0 && (
            <DataTable
              label="Uso de IA por operación"
              head={[
                { text: "Operación" },
                { text: "Llamadas", numeric: true },
                { text: "Fallos", numeric: true },
                { text: "Costo estimado", numeric: true },
              ]}
            >
              {data.ai.operations.map((row) => (
                <tr key={row.operation} className="border-b border-line last:border-0">
                  <td className={tdClass}>{OPERATION_LABELS[row.operation] ?? row.operation}</td>
                  <td className={numClass}>{row.calls}</td>
                  <td className={numClass}>{row.failures}</td>
                  <td className={numClass}>{moneyFormat.format(Number(row.cost_usd))}</td>
                </tr>
              ))}
            </DataTable>
          )}
        </section>
      )}
    </>
  );
}
