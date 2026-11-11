"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { type FormEvent, type ReactNode, useState } from "react";
import {
  cardClass,
  fieldClass,
  primaryButtonClass,
  secondaryButtonClass,
} from "@/components/ui/styles";
import { useSession } from "@/features/auth/use-session";
import {
  AI_STYLES,
  dateTimeFormat,
  type Feedback,
  FeedbackLine,
  formatDay,
  pillClass,
} from "@/features/recruitment/shared";
import { describeError } from "@/lib/api/client";
import { formatBytes } from "@/lib/api/files";
import { AI_LABELS, OUTCOME_KINDS, OUTCOME_LABELS } from "@/lib/api/recruitment";
import {
  createExport,
  DATE_KIND_LABELS,
  EMPTY_FILTERS,
  exportDownloadUrl,
  type ExportKind,
  getHistory,
  getOverview,
  getReportOptions,
  lastDays,
  listExports,
  type ReportExport,
  type ReportFilters,
  type ReportOptions,
  VACANCY_STATUS_LABELS,
} from "@/lib/api/reports";
import { DashboardView } from "./dashboard-view";

type Tab = "dashboard" | "history" | "exports";
const TABS: { value: Tab; label: string }[] = [
  { value: "dashboard", label: "Tablero" },
  { value: "history", label: "Histórico de candidatos" },
  { value: "exports", label: "Reportes generados" },
];
const PAGE_SIZE = 25;
const PRESETS: { label: string; range: () => { date_from: string; date_to: string } }[] = [
  { label: "30 días", range: () => lastDays(30) },
  { label: "90 días", range: () => lastDays(90) },
  { label: "12 meses", range: () => lastDays(365) },
  { label: "Todo", range: () => ({ date_from: "", date_to: "" }) },
];

/** Indicadores, histórico de postulaciones y reportes en Excel. */
export function ReportsScreen() {
  const { user } = useSession();
  const isAdmin = user?.role === "ADMINISTRADOR";
  const queryClient = useQueryClient();
  const [tab, setTab] = useState<Tab>("dashboard");
  const [draft, setDraft] = useState<ReportFilters>(() => ({ ...EMPTY_FILTERS, ...lastDays(90) }));
  const [filters, setFilters] = useState<ReportFilters>(draft);
  const [page, setPage] = useState(0);
  const [feedback, setFeedback] = useState<Feedback>(null);
  const [created, setCreated] = useState<ReportExport | null>(null);
  const [busy, setBusy] = useState(false);

  const options = useQuery({
    queryKey: ["reports", "options"],
    queryFn: ({ signal }) => getReportOptions(signal),
  });

  function apply(next: ReportFilters) {
    setDraft(next);
    setFilters(next);
    setPage(0);
    setFeedback(null);
    setCreated(null);
  }

  async function download(kind: ExportKind) {
    setBusy(true);
    setFeedback(null);
    setCreated(null);
    try {
      const report = await createExport(kind, filters);
      setCreated(report);
      setFeedback({ kind: "ok", text: "Reporte generado y guardado en el servidor." });
      await queryClient.invalidateQueries({ queryKey: ["reports", "exports"] });
    } catch (caught) {
      setFeedback({ kind: "error", text: describeError(caught) });
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <div>
        <h1 className="text-4xl font-medium tracking-tight sm:text-5xl">Indicadores y reportes</h1>
        <p className="mt-2 max-w-3xl text-ink-muted">
          {isAdmin
            ? "Incluye todas las vacantes."
            : "Incluye tus vacantes y las que tienes compartidas hoy."}{" "}
          Las fechas se cuentan en la hora de Ciudad de México.
        </p>
      </div>

      <div role="group" aria-label="Sección" className="flex flex-wrap gap-1.5">
        {TABS.map(({ value, label }) => (
          <button
            key={value}
            type="button"
            aria-pressed={tab === value}
            onClick={() => setTab(value)}
            className={`min-h-11 rounded-full px-5 ${
              tab === value ? "bg-ink text-white" : "border border-line bg-surface"
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {tab !== "exports" && (
        <FiltersForm
          draft={draft}
          options={options.data}
          detailed={tab === "history"}
          onChange={setDraft}
          onApply={() => apply(draft)}
          onClear={() => apply({ ...EMPTY_FILTERS })}
          onPreset={(range) => apply({ ...draft, ...range })}
        >
          <button
            type="button"
            className={secondaryButtonClass}
            disabled={busy}
            onClick={() => download(tab === "history" ? "POSTULACIONES" : "INDICADORES")}
          >
            {busy ? "Generando…" : "Descargar en Excel"}
          </button>
        </FiltersForm>
      )}
      <FeedbackLine feedback={feedback} />
      {created && (
        <p>
          <a
            href={exportDownloadUrl(created.id)}
            download
            className={`${primaryButtonClass} inline-flex items-center`}
          >
            Descargar {created.name}
          </a>
        </p>
      )}

      {tab === "dashboard" && <DashboardTab filters={filters} />}
      {tab === "history" && <HistoryTab filters={filters} page={page} onPage={setPage} />}
      {tab === "exports" && <ExportsTab />}
    </>
  );
}

function Select({
  id,
  label,
  value,
  onChange,
  children,
}: {
  id: string;
  label: string;
  value: string;
  onChange: (value: string) => void;
  children: ReactNode;
}) {
  return (
    <div className="flex min-w-0 flex-col gap-2">
      <label htmlFor={id} className="text-sm text-ink-muted">
        {label}
      </label>
      <select id={id} className={fieldClass} value={value} onChange={(event) => onChange(event.target.value)}>
        <option value="">Todos</option>
        {children}
      </select>
    </div>
  );
}

function Input({
  id,
  label,
  value,
  onChange,
  type = "text",
}: {
  id: string;
  label: string;
  value: string;
  onChange: (value: string) => void;
  type?: string;
}) {
  return (
    <div className="flex min-w-0 flex-col gap-2">
      <label htmlFor={id} className="text-sm text-ink-muted">
        {label}
      </label>
      <input
        id={id}
        type={type}
        className={fieldClass}
        value={value}
        min={type === "number" ? 0 : undefined}
        max={type === "number" ? 100 : undefined}
        onChange={(event) => onChange(event.target.value)}
      />
    </div>
  );
}

function FiltersForm({
  draft,
  options,
  detailed,
  onChange,
  onApply,
  onClear,
  onPreset,
  children,
}: {
  draft: ReportFilters;
  options: ReportOptions | undefined;
  detailed: boolean;
  onChange: (next: ReportFilters) => void;
  onApply: () => void;
  onClear: () => void;
  onPreset: (range: { date_from: string; date_to: string }) => void;
  children: ReactNode;
}) {
  const set = (key: keyof ReportFilters) => (value: string) => onChange({ ...draft, [key]: value });
  function submit(event: FormEvent) {
    event.preventDefault();
    onApply();
  }
  const named = (items: { id: string; name: string }[] = []) =>
    items.map((item) => (
      <option key={item.id} value={item.id}>
        {item.name}
      </option>
    ));
  const plain = (items: string[] = [], labels: Record<string, string> = {}) =>
    items.map((item) => (
      <option key={item} value={item}>
        {labels[item] ?? item}
      </option>
    ));

  return (
    <form onSubmit={submit} noValidate aria-label="Filtros" className={`${cardClass} flex flex-col gap-4`}>
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-sm text-ink-muted">Periodo:</span>
        {PRESETS.map((preset) => (
          <button
            key={preset.label}
            type="button"
            className="min-h-9 rounded-full border border-line bg-surface px-4 text-sm"
            onClick={() => onPreset(preset.range())}
          >
            {preset.label}
          </button>
        ))}
      </div>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Input id="f-from" label="Desde" type="date" value={draft.date_from} onChange={set("date_from")} />
        <Input id="f-to" label="Hasta" type="date" value={draft.date_to} onChange={set("date_to")} />
        <Select id="f-vacancy" label="Vacante" value={draft.vacancy_id} onChange={set("vacancy_id")}>
          {named(options?.vacancies)}
        </Select>
        <Select id="f-department" label="Departamento" value={draft.department} onChange={set("department")}>
          {plain(options?.departments)}
        </Select>
        <Select id="f-owner" label="Responsable" value={draft.owner_id} onChange={set("owner_id")}>
          {named(options?.owners)}
        </Select>
        <Select id="f-collaborator" label="Colaborador" value={draft.collaborator_id} onChange={set("collaborator_id")}>
          {named(options?.collaborators)}
        </Select>
        <Select
          id="f-status"
          label="Estado de la vacante"
          value={draft.vacancy_status}
          onChange={set("vacancy_status")}
        >
          {plain(Object.keys(VACANCY_STATUS_LABELS), VACANCY_STATUS_LABELS)}
        </Select>
        {detailed && (
          <>
            <div className="flex min-w-0 flex-col gap-2">
              <label htmlFor="f-date-kind" className="text-sm text-ink-muted">
                Fecha que se compara
              </label>
              <select
                id="f-date-kind"
                className={fieldClass}
                value={draft.date_kind}
                onChange={(event) => set("date_kind")(event.target.value)}
              >
                {plain(Object.keys(DATE_KIND_LABELS), DATE_KIND_LABELS)}
              </select>
            </div>
            <Input id="f-candidate" label="Candidato" value={draft.candidate} onChange={set("candidate")} />
            <Select id="f-stage" label="Etapa" value={draft.stage} onChange={set("stage")}>
              {plain(options?.stages)}
            </Select>
            <Select id="f-outcome" label="Resultado final" value={draft.outcome} onChange={set("outcome")}>
              {plain(["EN_PROCESO", ...OUTCOME_KINDS], OUTCOME_LABELS)}
            </Select>
            <Select
              id="f-ai"
              label="Clasificación de la IA"
              value={draft.ai_classification}
              onChange={set("ai_classification")}
            >
              {plain(Object.keys(AI_LABELS), AI_LABELS)}
            </Select>
            <Input id="f-min" label="Calificación mínima" type="number" value={draft.score_min} onChange={set("score_min")} />
            <Input id="f-max" label="Calificación máxima" type="number" value={draft.score_max} onChange={set("score_max")} />
            <Select id="f-model" label="Modelo" value={draft.model} onChange={set("model")}>
              {plain(options?.models)}
            </Select>
            <Select
              id="f-prompt"
              label="Versión del prompt"
              value={draft.prompt_version_id}
              onChange={set("prompt_version_id")}
            >
              {named(options?.prompt_versions)}
            </Select>
            <Select id="f-bank" label="Banco de preguntas" value={draft.bank_id} onChange={set("bank_id")}>
              {named(options?.banks)}
            </Select>
          </>
        )}
      </div>
      <div className="flex flex-wrap items-center gap-3">
        <button type="submit" className={primaryButtonClass}>
          Aplicar filtros
        </button>
        <button type="button" className={secondaryButtonClass} onClick={onClear}>
          Quitar filtros
        </button>
        <span className="flex-1" />
        {children}
      </div>
    </form>
  );
}

function Problem({ error }: { error: unknown }) {
  return (
    <p role="alert" className="rounded-tile bg-accent-red-soft px-5 py-4 text-accent-red-ink">
      {describeError(error)}
    </p>
  );
}

function DashboardTab({ filters }: { filters: ReportFilters }) {
  const { data, error } = useQuery({
    queryKey: ["reports", "overview", filters],
    queryFn: ({ signal }) => getOverview(filters, signal),
  });
  if (error) return <Problem error={error} />;
  if (!data) return <p role="status" className="text-ink-muted">Calculando indicadores…</p>;
  return <DashboardView data={data} />;
}

function moment(value: string | null): string {
  return value ? dateTimeFormat.format(new Date(value)) : "—";
}

function HistoryTab({
  filters,
  page,
  onPage,
}: {
  filters: ReportFilters;
  page: number;
  onPage: (page: number) => void;
}) {
  const { data, error } = useQuery({
    queryKey: ["reports", "history", filters, page],
    queryFn: ({ signal }) => getHistory(filters, { limit: PAGE_SIZE, offset: page * PAGE_SIZE }, signal),
  });
  if (error) return <Problem error={error} />;
  if (!data) return <p role="status" className="text-ink-muted">Buscando postulaciones…</p>;
  const pages = Math.max(1, Math.ceil(data.total / PAGE_SIZE));
  const cell = "py-2 pr-4 align-top";
  const head = "py-2 pr-4 text-left text-sm font-normal text-ink-muted";
  return (
    <section className={`${cardClass} flex flex-col gap-4`} aria-label="Histórico de candidatos">
      <p className="text-ink-muted" role="status">
        {data.total === 1 ? "1 postulación" : `${data.total} postulaciones`}
      </p>
      {data.total > 0 && (
        <div className="overflow-x-auto">
          <table aria-label="Postulaciones" className="w-full min-w-[980px] border-collapse">
            <thead>
              <tr className="border-b border-line">
                {["Candidato", "Vacante", "Etapa", "Resultado final", "IA", "Carga del CV", "Último movimiento", "Cierre"].map(
                  (text) => (
                    <th key={text} scope="col" className={head}>
                      {text}
                    </th>
                  ),
                )}
              </tr>
            </thead>
            <tbody>
              {data.rows.map((row) => (
                <tr key={row.application_id} className="border-b border-line last:border-0">
                  <td className={cell}>{row.candidate}</td>
                  <td className={cell}>
                    {row.vacancy}
                    <span className="block text-sm text-ink-muted">
                      {row.department} · {row.owner_name}
                    </span>
                  </td>
                  <td className={cell}>{row.stage}</td>
                  <td className={cell}>
                    {OUTCOME_LABELS[row.outcome] ?? row.outcome}
                    {row.start_date && (
                      <span className="block text-sm text-ink-muted">Entra el {formatDay(row.start_date)}</span>
                    )}
                    {row.outcome_reason && (
                      <span className="block text-sm text-ink-muted">{row.outcome_reason}</span>
                    )}
                  </td>
                  <td className={cell}>
                    {row.ai_classification ? (
                      <>
                        <span className={`${pillClass} ${AI_STYLES[row.ai_classification] ?? ""}`}>
                          {AI_LABELS[row.ai_classification] ?? row.ai_classification}
                          {row.ai_score !== null ? ` · ${Number(row.ai_score)}` : ""}
                        </span>
                        {row.model && (
                          <span className="block text-sm text-ink-muted">
                            {row.model}
                            {row.prompt_version !== null ? ` · prompt v${row.prompt_version}` : ""}
                          </span>
                        )}
                      </>
                    ) : (
                      <span className="text-ink-muted">Alta manual</span>
                    )}
                  </td>
                  <td className={`${cell} whitespace-nowrap`}>{moment(row.cv_uploaded_at ?? row.created_at)}</td>
                  <td className={`${cell} whitespace-nowrap`}>{moment(row.last_movement_at)}</td>
                  <td className={`${cell} whitespace-nowrap`}>
                    {moment(row.closed_at)}
                    {row.closed_by_name && (
                      <span className="block text-sm text-ink-muted">{row.closed_by_name}</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {pages > 1 && (
        <div className="flex flex-wrap items-center gap-3">
          <button
            type="button"
            className={secondaryButtonClass}
            disabled={page === 0}
            onClick={() => onPage(page - 1)}
          >
            Anterior
          </button>
          <span className="text-ink-muted">
            Página {page + 1} de {pages}
          </span>
          <button
            type="button"
            className={secondaryButtonClass}
            disabled={page + 1 >= pages}
            onClick={() => onPage(page + 1)}
          >
            Siguiente
          </button>
        </div>
      )}
    </section>
  );
}

function ExportsTab() {
  const { data, error } = useQuery({
    queryKey: ["reports", "exports"],
    queryFn: ({ signal }) => listExports(signal),
  });
  if (error) return <Problem error={error} />;
  if (!data) return <p role="status" className="text-ink-muted">Cargando reportes…</p>;
  return (
    <section className={`${cardClass} flex flex-col gap-4`} aria-label="Reportes generados">
      <p className="text-ink-muted">
        Los Excel que generaste quedan guardados en el servidor. Si dejaste de tener acceso a
        alguna de las vacantes que contiene un reporte, ya no se puede descargar: genera uno nuevo.
      </p>
      {data.length === 0 ? (
        <p>Todavía no has generado reportes.</p>
      ) : (
        <ul aria-label="Reportes" className="flex flex-col gap-2">
          {data.map((report) => {
            const filters = Object.entries(report.filters);
            return (
              <li
                key={report.id}
                className="flex flex-wrap items-center justify-between gap-3 rounded-2xl bg-surface px-4 py-3"
              >
                <div className="min-w-0">
                  <p className="font-medium">{report.name}</p>
                  <p className="text-sm text-ink-muted">
                    {dateTimeFormat.format(new Date(report.created_at))} ·{" "}
                    {report.kind === "INDICADORES"
                      ? `${report.row_count} ${report.row_count === 1 ? "vacante" : "vacantes"}`
                      : `${report.row_count} ${report.row_count === 1 ? "postulación" : "postulaciones"}`}{" "}
                    · {formatBytes(report.size_bytes)}
                  </p>
                  <p className="text-sm text-ink-muted">
                    {filters.length === 0
                      ? "Sin filtros"
                      : filters.map(([name, value]) => `${name}: ${value}`).join(" · ")}
                  </p>
                  <p className="break-all text-xs text-ink-muted">SHA-256: {report.sha256}</p>
                </div>
                <a
                  href={exportDownloadUrl(report.id)}
                  download
                  className={`${secondaryButtonClass} inline-flex items-center`}
                >
                  Descargar
                </a>
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}
