"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { type FormEvent, type ReactNode, useRef, useState } from "react";
import {
  cardClass,
  fieldClass,
  primaryButtonClass,
  secondaryButtonClass,
} from "@/components/ui/styles";
import { describeError } from "@/lib/api/client";
import {
  EDUCATION_LEVELS,
  extractProfile,
  FREQUENCIES,
  listProfileVersions,
  PROFILE_LABELS,
  PROFILE_LINE_FIELDS,
  PROFILE_LIST_FIELDS,
  PROFILE_TEXT_FIELDS,
  type ProfileActivity,
  type ProfileInput,
  type ProfileKpi,
  type ProfileLineField,
  type ProfileListField,
  type ProfileOrigin,
  type ProfileProposal,
  type ProfileTextField,
  type ProfileVersion,
  saveProfile,
} from "@/lib/api/evaluation";
import { acceptedExtensions, listFiles, MAX_UPLOAD_BYTES, uploadFile } from "@/lib/api/files";
import { areaClass, dateFormat, type Feedback, FeedbackLine } from "./shared";

const ORIGIN_LABELS: Record<ProfileOrigin, string> = {
  MANUAL: "Captura manual",
  IA: "Propuesta de la IA, revisada",
  FORMATO: "Formato de la empresa",
};
const PROFILE_EXTENSIONS = acceptedExtensions("PERFIL_PUESTO");

type ProfileDraft = Record<ProfileLineField | ProfileTextField | ProfileListField, string> & {
  education_levels: string[];
  activities: ProfileActivity[];
  kpis: ProfileKpi[];
};
/** De dónde salió lo que hay en el formulario, si no se capturó a mano. */
type DraftSource = { origin: ProfileOrigin; fileId: string | null; notices: string[] };

function toDraft(version: ProfileVersion | ProfileProposal | undefined): ProfileDraft {
  const draft = {
    education_levels: [...(version?.education_levels ?? [])],
    activities: (version?.activities ?? []).map((row) => ({ ...row })),
    kpis: (version?.kpis ?? []).map((row) => ({ ...row })),
  } as ProfileDraft;
  for (const field of PROFILE_LINE_FIELDS) draft[field] = version?.[field] ?? "";
  for (const field of PROFILE_TEXT_FIELDS) draft[field] = version?.[field] ?? "";
  for (const field of PROFILE_LIST_FIELDS) draft[field] = (version?.[field] ?? []).join("\n");
  return draft;
}

export function ProfileTab({ vacancyId, canEdit }: { vacancyId: string; canEdit: boolean }) {
  const queryClient = useQueryClient();
  const queryKey = ["vacancy", vacancyId, "profile"];
  const { data: versions, error } = useQuery({
    queryKey,
    queryFn: ({ signal }) => listProfileVersions(vacancyId, signal),
  });
  // El aviso de «guardado» vive aquí: al guardar, el formulario se vuelve a
  // crear con la versión nueva y perdería su propio estado.
  const [saved, setSaved] = useState<Feedback>(null);

  if (error) {
    return (
      <p role="alert" className="rounded-tile bg-accent-red-soft px-5 py-4 text-accent-red-ink">
        {describeError(error)}
      </p>
    );
  }
  if (!versions) return <p className="text-ink-muted">Cargando perfil…</p>;
  const current = versions[0];
  return (
    <div className="flex flex-wrap items-start gap-6">
      <ProfileForm
        key={current?.id ?? "nuevo"}
        vacancyId={vacancyId}
        current={current}
        canEdit={canEdit}
        saved={saved}
        onSaved={async (notice) => {
          setSaved(notice);
          if (notice) await queryClient.invalidateQueries({ queryKey });
        }}
      />
      <section className={`${cardClass} flex min-w-0 flex-[1_1_280px] flex-col gap-3`}>
        <h2 className="text-xl font-medium">Versiones del perfil</h2>
        {versions.length === 0 ? (
          <p className="text-ink-muted">Todavía no hay perfil. Al guardarlo se crea la versión 1.</p>
        ) : (
          <ul aria-label="Versiones del perfil" className="flex flex-col gap-1.5">
            {versions.map((version) => (
              <li key={version.id} className="rounded-2xl bg-surface px-4 py-3">
                <p className="font-medium">
                  Versión {version.version_number}
                  {version === current && " (vigente)"}
                </p>
                <p className="text-sm text-ink-muted">
                  {dateFormat.format(new Date(version.created_at))} ·{" "}
                  {version.created_by_name ?? "Sin datos"}
                </p>
                <p className="text-sm text-ink-muted">{ORIGIN_LABELS[version.origin]}</p>
                {version.change_note && <p className="text-sm">{version.change_note}</p>}
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}

function Section({ title, hint, children }: { title: string; hint?: string; children: ReactNode }) {
  return (
    <fieldset className="flex min-w-0 flex-col gap-4 rounded-3xl border border-line p-5">
      <legend className="px-2 font-medium">{title}</legend>
      {hint && <p className="text-sm text-ink-muted">{hint}</p>}
      {children}
    </fieldset>
  );
}

function ProfileForm({
  vacancyId,
  current,
  canEdit,
  saved,
  onSaved,
}: {
  vacancyId: string;
  current: ProfileVersion | undefined;
  canEdit: boolean;
  saved: Feedback;
  onSaved: (notice: Feedback) => Promise<void>;
}) {
  const [draft, setDraft] = useState<ProfileDraft>(() => toDraft(current));
  const [note, setNote] = useState("");
  const [feedback, setFeedback] = useState<Feedback>(null);
  const [busy, setBusy] = useState(false);
  // Si el formulario se llenó con el formato de la empresa o con una propuesta de la IA.
  const [source, setSource] = useState<DraftSource | null>(null);

  async function submit(event: FormEvent) {
    event.preventDefault();
    const input = {
      education_levels: draft.education_levels,
      activities: draft.activities.filter((row) => row.description.trim() || row.frequency),
      kpis: draft.kpis.filter((row) => row.name.trim() || row.goal.trim() || row.formula.trim()),
      change_note: note.trim() || null,
      expected_version: current?.version_number ?? 0,
      origin: source?.origin ?? "MANUAL",
      source_file_id: source?.fileId ?? null,
    } as ProfileInput;
    for (const field of PROFILE_LINE_FIELDS) input[field] = draft[field];
    for (const field of PROFILE_TEXT_FIELDS) input[field] = draft[field];
    for (const field of PROFILE_LIST_FIELDS) {
      input[field] = draft[field]
        .split("\n")
        .map((line) => line.trim())
        .filter(Boolean);
    }
    setBusy(true);
    setFeedback(null);
    await onSaved(null);
    try {
      const version = await saveProfile(vacancyId, input);
      setNote("");
      await onSaved({
        kind: "ok",
        text: `Perfil guardado como versión ${version.version_number}.`,
      });
    } catch (caught) {
      setFeedback({ kind: "error", text: describeError(caught) });
    } finally {
      setBusy(false);
    }
  }

  const line = (field: ProfileLineField, type: "text" | "date" = "text") => (
    <div key={field} className="flex flex-col gap-2">
      <label htmlFor={`profile-${field}`} className="text-sm text-ink-muted">
        {PROFILE_LABELS[field]}
      </label>
      <input
        id={`profile-${field}`}
        type={type}
        maxLength={300}
        readOnly={!canEdit}
        value={draft[field]}
        onChange={(event) => setDraft({ ...draft, [field]: event.target.value })}
        className={fieldClass}
      />
    </div>
  );
  const area = (field: ProfileTextField | ProfileListField, rows: number) => (
    <div key={field} className="flex flex-col gap-2">
      <label htmlFor={`profile-${field}`} className="text-sm text-ink-muted">
        {PROFILE_LABELS[field]}
        {(PROFILE_LIST_FIELDS as readonly string[]).includes(field) && " (uno por línea)"}
      </label>
      <textarea
        id={`profile-${field}`}
        rows={rows}
        readOnly={!canEdit}
        value={draft[field]}
        onChange={(event) => setDraft({ ...draft, [field]: event.target.value })}
        className={areaClass}
      />
    </div>
  );
  const grid = "grid gap-4 md:grid-cols-2";

  return (
    <form
      onSubmit={submit}
      noValidate
      className={`${cardClass} flex min-w-0 flex-[3_1_520px] flex-col gap-5`}
    >
      <div>
        <h2 className="text-xl font-medium">
          {current
            ? `Perfil vigente (versión ${current.version_number})`
            : "Nuevo perfil de puesto"}
        </h2>
        <p className="text-sm text-ink-muted">
          Sigue el formato de la empresa «SGC.F15.RH. Perfil de puesto».
        </p>
      </div>
      {canEdit && (
        <ProfileSource
          vacancyId={vacancyId}
          onProposal={(proposal) => {
            setDraft(toDraft(proposal));
            setSource({
              origin: proposal.origin,
              fileId: proposal.source_file_id,
              notices: proposal.notices,
            });
            setFeedback(null);
          }}
        />
      )}
      {source && source.notices.length > 0 && (
        <ul
          aria-label="Avisos de la lectura"
          className="flex flex-col gap-1 rounded-2xl bg-surface px-5 py-4 text-sm"
        >
          {source.notices.map((notice) => (
            <li key={notice}>{notice}</li>
          ))}
        </ul>
      )}

      <Section title="Identificación del puesto">
        <div className={grid}>
          {(
            [
              "position_name",
              "area",
              "location",
              "reports_to",
              "supervises",
              "contract_type",
              "work_mode",
              "schedule",
              "offer",
              "document_version",
            ] as const
          ).map((field) => line(field))}
          {line("document_date", "date")}
        </div>
      </Section>

      <Section title="Propósito del puesto">{area("objective", 3)}</Section>

      <Section title="Alcance y relaciones clave">
        <div className={grid}>
          {area("internal_relations", 2)}
          {area("external_relations", 2)}
        </div>
      </Section>

      <Section
        title="Requisitos del puesto"
        hint="De cada requisito indispensable sale un criterio de la rúbrica con la que se revisan los CV."
      >
        <div role="group" aria-label="Formación académica" className="flex flex-col gap-2">
          <p className="text-sm text-ink-muted">Formación académica</p>
          <div className="flex flex-wrap gap-x-5 gap-y-2">
            {EDUCATION_LEVELS.map((level) => (
              <label key={level} className="flex min-h-11 items-center gap-2">
                <input
                  type="checkbox"
                  className="size-5"
                  disabled={!canEdit}
                  checked={draft.education_levels.includes(level)}
                  onChange={(event) =>
                    setDraft({
                      ...draft,
                      education_levels: event.target.checked
                        ? [...draft.education_levels, level]
                        : draft.education_levels.filter((item) => item !== level),
                    })
                  }
                />
                {level}
              </label>
            ))}
          </div>
        </div>
        <div className={grid}>
          {line("specialty")}
          {area("experience", 2)}
        </div>
        {area("must_have", 6)}
        <div className={grid}>
          {area("knowledge", 4)}
          {area("skills", 4)}
        </div>
      </Section>

      <Section title="Funciones y actividades principales">
        {area("functions", 6)}
        <Rows
          title="Actividades del puesto"
          addLabel="Agregar actividad"
          canEdit={canEdit}
          rows={draft.activities}
          empty={{ description: "", frequency: "" }}
          onChange={(activities) => setDraft({ ...draft, activities })}
          render={(row, index, update) => (
            <>
              <input
                aria-label={`Actividad ${index + 1}`}
                value={row.description}
                maxLength={500}
                readOnly={!canEdit}
                onChange={(event) => update({ ...row, description: event.target.value })}
                className={`${fieldClass} flex-[3_1_260px]`}
              />
              <select
                aria-label={`Periodicidad de la actividad ${index + 1}`}
                value={row.frequency}
                disabled={!canEdit}
                onChange={(event) => update({ ...row, frequency: event.target.value })}
                className={`${fieldClass} flex-[1_1_150px]`}
              >
                <option value="">Sin periodicidad</option>
                {FREQUENCIES.map((frequency) => (
                  <option key={frequency} value={frequency}>
                    {frequency}
                  </option>
                ))}
              </select>
            </>
          )}
        />
      </Section>

      <Section title="KPI y medición de desempeño">
        <Rows
          title="Indicadores"
          addLabel="Agregar KPI"
          canEdit={canEdit}
          rows={draft.kpis}
          empty={{ name: "", goal: "", formula: "" }}
          onChange={(kpis) => setDraft({ ...draft, kpis })}
          render={(row, index, update) => (
            <>
              {(
                [
                  ["name", "KPI"],
                  ["goal", "Meta del KPI"],
                  ["formula", "Fórmula del KPI"],
                ] as const
              ).map(([key, label]) => (
                <input
                  key={key}
                  aria-label={`${label} ${index + 1}`}
                  placeholder={label.replace(" del KPI", "")}
                  value={row[key]}
                  maxLength={500}
                  readOnly={!canEdit}
                  onChange={(event) => update({ ...row, [key]: event.target.value })}
                  className={`${fieldClass} ${key === "name" ? "flex-[1_1_100%]" : "flex-[1_1_180px]"}`}
                />
              ))}
            </>
          )}
        />
      </Section>

      <Section
        title="Complementos para la evaluación"
        hint="Estos datos no vienen en el formato de la empresa. Son opcionales y ayudan a precisar la revisión de los CV."
      >
        <div className={grid}>
          {area("nice_to_have", 3)}
          {area("certifications", 3)}
          {area("responsibilities", 3)}
          {area("ambiguities", 3)}
        </div>
        {area("education", 2)}
      </Section>

      <FeedbackLine feedback={feedback ?? saved} />
      {canEdit ? (
        <div className="flex flex-wrap items-end gap-3">
          <div className="flex flex-[1_1_260px] flex-col gap-2">
            <label htmlFor="profile-note" className="text-sm text-ink-muted">
              Qué cambió (opcional)
            </label>
            <input
              id="profile-note"
              value={note}
              maxLength={300}
              onChange={(event) => setNote(event.target.value)}
              className={fieldClass}
            />
          </div>
          <button type="submit" className={primaryButtonClass} disabled={busy}>
            {busy ? "Guardando…" : current ? "Guardar como versión nueva" : "Guardar perfil"}
          </button>
        </div>
      ) : (
        <p className="text-sm text-ink-muted">Tu acceso a esta vacante es de solo lectura.</p>
      )}
    </form>
  );
}

/** Filas que se agregan y se quitan: actividades con su periodicidad, o indicadores. */
function Rows<Row>({
  title,
  addLabel,
  canEdit,
  rows,
  empty,
  onChange,
  render,
}: {
  title: string;
  addLabel: string;
  canEdit: boolean;
  rows: Row[];
  empty: Row;
  onChange: (rows: Row[]) => void;
  render: (row: Row, index: number, update: (row: Row) => void) => ReactNode;
}) {
  return (
    <div role="group" aria-label={title} className="flex flex-col gap-2">
      <p className="text-sm text-ink-muted">{title}</p>
      {rows.length === 0 && <p className="text-sm text-ink-muted">Sin registros.</p>}
      {rows.map((row, index) => (
        // Las filas no tienen identificador propio: su posición es estable mientras se editan.
        <div key={index} className="flex flex-wrap items-center gap-2 rounded-2xl bg-surface p-2">
          {render(row, index, (changed) =>
            onChange(rows.map((item, position) => (position === index ? changed : item))),
          )}
          {canEdit && (
            <button
              type="button"
              className={secondaryButtonClass}
              aria-label={`Quitar fila ${index + 1} de ${title.toLowerCase()}`}
              onClick={() => onChange(rows.filter((_, position) => position !== index))}
            >
              Quitar
            </button>
          )}
        </div>
      ))}
      {canEdit && rows.length < 30 && (
        <button
          type="button"
          className={`${secondaryButtonClass} self-start`}
          onClick={() => onChange([...rows, { ...empty }])}
        >
          {addLabel}
        </button>
      )}
    </div>
  );
}

/**
 * Llena el formulario desde un documento: el formato de la empresa en Excel se
 * lee directamente; otros documentos y los textos pegados los lee la IA.
 */
function ProfileSource({
  vacancyId,
  onProposal,
}: {
  vacancyId: string;
  onProposal: (proposal: ProfileProposal) => void;
}) {
  const queryClient = useQueryClient();
  const picker = useRef<HTMLInputElement>(null);
  const [open, setOpen] = useState(false);
  const [fileId, setFileId] = useState("");
  const [text, setText] = useState("");
  const [feedback, setFeedback] = useState<Feedback>(null);
  const [busy, setBusy] = useState(false);
  // Los documentos ya cargados se piden solo al abrir el panel.
  const { data: files, error } = useQuery({
    queryKey: ["vacancy", vacancyId, "files"],
    queryFn: ({ signal }) => listFiles(vacancyId, signal),
    enabled: open,
  });
  const documents = (files ?? []).filter((file) => file.document_type === "PERFIL_PUESTO");

  async function read(from: { fileId: string } | { text: string }) {
    const proposal = await extractProfile(vacancyId, from);
    onProposal(proposal);
    setFeedback({
      kind: "ok",
      text:
        (proposal.origin === "FORMATO"
          ? "Se leyó el formato de la empresa y se llenó el formulario."
          : "La IA llenó el formulario.") +
        " Revísalo y corrígelo: todavía no se ha guardado." +
        (proposal.truncated ? " El documento era muy largo y solo se leyó el inicio." : ""),
    });
  }

  async function run(action: () => Promise<void>) {
    setBusy(true);
    setFeedback(null);
    try {
      await action();
    } catch (caught) {
      setFeedback({ kind: "error", text: describeError(caught) });
    } finally {
      setBusy(false);
    }
  }

  async function uploadAndRead(file: File) {
    const extension = file.name.slice(file.name.lastIndexOf(".")).toLowerCase();
    if (!PROFILE_EXTENSIONS.includes(extension)) {
      return setFeedback({
        kind: "error",
        text: "Formato no permitido. Sube el formato en Excel (XLSX), o un PDF, DOCX, DOC, JPG o PNG.",
      });
    }
    if (file.size > MAX_UPLOAD_BYTES) {
      return setFeedback({ kind: "error", text: "El archivo supera el límite de 20 MB." });
    }
    await run(async () => {
      const uploaded = await uploadFile(vacancyId, file, "PERFIL_PUESTO");
      await queryClient.invalidateQueries({ queryKey: ["vacancy", vacancyId, "files"] });
      await read({ fileId: uploaded.file.id });
    });
  }

  return (
    <div className="flex flex-col gap-3 rounded-3xl bg-surface p-5">
      <p className="text-ink-muted">
        Sube el formato del perfil en Excel y el formulario se llena con sus datos. También
        puedes subir un PDF o un Word: esos los lee la IA. En ambos casos lo revisas y lo guardas
        tú.
      </p>
      <div className="flex flex-wrap gap-3">
        <input
          ref={picker}
          type="file"
          aria-label="Formato del perfil"
          accept={PROFILE_EXTENSIONS.join(",")}
          className="sr-only"
          tabIndex={-1}
          onChange={async (event) => {
            const file = event.target.files?.[0];
            event.target.value = "";
            if (file) await uploadAndRead(file);
          }}
        />
        <button
          type="button"
          className={primaryButtonClass}
          disabled={busy}
          onClick={() => picker.current?.click()}
        >
          {busy ? "Leyendo…" : "Subir formato del perfil"}
        </button>
        <button
          type="button"
          className={secondaryButtonClass}
          aria-expanded={open}
          onClick={() => setOpen(!open)}
        >
          Usar un documento ya cargado o pegar texto
        </button>
      </div>
      {open && (
        <>
          {error && (
            <p role="alert" className="text-accent-red-ink">
              {describeError(error)}
            </p>
          )}
          <div className="flex flex-col gap-2">
            <label htmlFor="profile-source-file" className="text-sm text-ink-muted">
              Documento de la vacante (tipo «Perfil de puesto»)
            </label>
            <select
              id="profile-source-file"
              className={fieldClass}
              value={fileId}
              onChange={(event) => setFileId(event.target.value)}
            >
              <option value="">Ninguno: pegaré el texto</option>
              {documents.map((file) => (
                <option key={file.id} value={file.id}>
                  {file.original_name}
                </option>
              ))}
            </select>
          </div>
          {!fileId && (
            <div className="flex flex-col gap-2">
              <label htmlFor="profile-source-text" className="text-sm text-ink-muted">
                Texto del perfil
              </label>
              <textarea
                id="profile-source-text"
                rows={5}
                value={text}
                onChange={(event) => setText(event.target.value)}
                className={areaClass}
              />
            </div>
          )}
          <button
            type="button"
            className={`${secondaryButtonClass} self-start`}
            disabled={busy || (!fileId && text.trim().length === 0)}
            onClick={() => run(() => read(fileId ? { fileId } : { text }))}
          >
            {busy ? "Leyendo…" : "Leer documento"}
          </button>
        </>
      )}
      <FeedbackLine feedback={feedback} />
    </div>
  );
}
