"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useRef, useState } from "react";
import {
  cardClass,
  dangerButtonClass,
  fieldClass,
  primaryButtonClass,
  secondaryButtonClass,
} from "@/components/ui/styles";
import {
  areaClass,
  dateTimeFormat,
  type Feedback,
  FeedbackLine,
  pillClass,
} from "@/features/recruitment/shared";
import {
  type Assessment,
  type AssessmentData,
  createAssessment,
  describePhoto,
  type Digitization,
  digitizeStudy,
  type FormField,
  KIND_DOCUMENT,
  KIND_LABELS,
  type Kind,
  listAssessments,
  listTemplates,
  STATUS_LABELS,
  summarizeAssessment,
  updateAssessment,
} from "@/lib/api/assessments";
import { describeError } from "@/lib/api/client";
import {
  acceptedExtensions,
  downloadUrl,
  listFiles,
  MAX_UPLOAD_BYTES,
  uploadFile,
} from "@/lib/api/files";

type Props = { applicationId: string; vacancyId: string; active: boolean };
type Row = Record<string, string>;
type Answer = {
  value: string | boolean | string[][];
  verified: boolean;
  source: string;
  /** Descripción anotada junto a una fotografía, y si la propuso la IA. */
  description?: string;
  description_source?: string;
};
const PHOTO_NAME = /\.(jpe?g|png)$/i;
const STUDY_EXTENSIONS = acceptedExtensions("ESTUDIO_SOCIOECONOMICO");

/** Dato obligatorio para dar de alta cada tipo; el resto se captura después. */
const FIRST_FIELD: Record<Kind, { key: string; label: string } | null> = {
  PSICOMETRIA: { key: "instrument", label: "Instrumento" },
  ENTREVISTA: { key: "interviewer", label: "Quién entrevista" },
  PRUEBA_TECNICA: { key: "test_type", label: "Tipo de prueba" },
  ESTUDIO_SOCIOECONOMICO: null,
};
const TEXT_FIELDS: Record<Kind, { key: string; label: string; area?: boolean }[]> = {
  PSICOMETRIA: [
    { key: "instrument", label: "Instrumento" },
    { key: "instrument_version", label: "Versión" },
    { key: "provider", label: "Proveedor" },
    { key: "result", label: "Resultado documentado", area: true },
    { key: "notes", label: "Observaciones", area: true },
    { key: "professional_name", label: "Profesional que la interpretó" },
    { key: "professional_license", label: "Cédula profesional" },
    { key: "validation_note", label: "Interpretación del profesional", area: true },
  ],
  ENTREVISTA: [
    { key: "interviewer", label: "Quién entrevistó" },
    { key: "feedback", label: "Retroalimentación del gerente", area: true },
    { key: "evidence", label: "Evidencias", area: true },
    { key: "notes", label: "Observaciones", area: true },
    { key: "conclusion", label: "Conclusión de quien entrevistó", area: true },
  ],
  PRUEBA_TECNICA: [
    { key: "test_type", label: "Tipo de prueba" },
    { key: "competency", label: "Competencia" },
    { key: "responsible", label: "Responsable" },
    { key: "result", label: "Resultado", area: true },
    { key: "evidence", label: "Evidencias", area: true },
    { key: "comments", label: "Comentarios", area: true },
  ],
  ESTUDIO_SOCIOECONOMICO: [
    { key: "performed_by", label: "Quién realizó el estudio" },
    { key: "notes", label: "Observaciones generales", area: true },
  ],
};
const SUMMARY_LABELS: Record<string, string> = {
  resultados_documentados: "Resultados que constan en el documento",
  datos_no_legibles: "Datos que no se pudieron leer",
  advertencias: "Avisos",
  competencias_observadas: "Competencias observadas",
  evidencias: "Evidencias",
  informacion_faltante: "Información que faltó",
  preguntas_de_seguimiento: "Preguntas de seguimiento",
};
const text = (value: unknown) => (typeof value === "string" ? value : "");

/** Psicometría, entrevistas, pruebas técnicas y estudios de una postulación. */
export function AssessmentsSection({ applicationId, vacancyId, active }: Props) {
  const queryClient = useQueryClient();
  const queryKey = ["application", applicationId, "assessments"];
  const { data, error } = useQuery({
    queryKey,
    queryFn: ({ signal }) => listAssessments(applicationId, signal),
  });
  const [openId, setOpenId] = useState<string | null>(null);
  const [adding, setAdding] = useState(false);
  // Aviso de la última operación sobre una evaluación. Vive aquí porque el
  // editor se vuelve a crear cuando llega la versión guardada.
  const [notice, setNotice] = useState<{ id: string; text: string } | null>(null);
  const refresh = () => queryClient.invalidateQueries({ queryKey });

  return (
    <section className={`${cardClass} flex flex-col gap-4`} aria-labelledby="assessments-title">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 id="assessments-title" className="text-xl font-medium">
          Evaluaciones posteriores
        </h2>
        {data && data.writable.length > 0 && active && !adding && (
          <button type="button" className={secondaryButtonClass} onClick={() => setAdding(true)}>
            Registrar evaluación
          </button>
        )}
      </div>
      <p className="text-sm text-ink-muted">
        Psicometría, entrevista con gerente, prueba técnica y estudio socioeconómico. Registrar
        una evaluación no mueve de etapa a nadie: avanzar sigue siendo tu decisión.
      </p>
      {error && (
        <p role="alert" className="text-accent-red-ink">
          {describeError(error)}
        </p>
      )}
      {data && data.restricted.length > 0 && (
        <p className="rounded-2xl bg-surface px-4 py-3">
          Esta postulación tiene {data.restricted.map((kind) => KIND_LABELS[kind].toLowerCase()).join(" y ")}
          , que requiere un permiso adicional sobre la vacante para consultarse.
        </p>
      )}
      {adding && data && (
        <NewAssessment
          applicationId={applicationId}
          kinds={data.writable}
          onCancel={() => setAdding(false)}
          onCreated={async (created) => {
            await refresh();
            setAdding(false);
            setOpenId(created.id);
          }}
        />
      )}
      {data && data.items.length === 0 && !adding && (
        <p className="text-ink-muted">Todavía no hay evaluaciones registradas.</p>
      )}
      <ul aria-label="Evaluaciones" className="flex flex-col gap-3">
        {(data?.items ?? []).map((item) => (
          <li key={item.id} className="rounded-3xl bg-surface p-5">
            <button
              type="button"
              aria-expanded={openId === item.id}
              className="flex w-full flex-wrap items-center gap-3 text-left"
              onClick={() => setOpenId(openId === item.id ? null : item.id)}
            >
              <span className="flex-[1_1_220px] font-medium">
                {KIND_LABELS[item.kind]}
                {titleOf(item) ? ` · ${titleOf(item)}` : ""}
              </span>
              {item.score !== null && (
                <span className={`${pillClass} bg-accent-blue-soft text-accent-blue-ink`}>
                  {Number(item.score)} de 100
                </span>
              )}
              <span className={`${pillClass} bg-neutral-soft text-neutral-ink`}>
                {STATUS_LABELS[item.status] ?? item.status}
              </span>
            </button>
            {openId === item.id && (
              <AssessmentEditor
                key={`${item.id}-${item.version}`}
                item={item}
                vacancyId={vacancyId}
                canEdit={data?.writable.includes(item.kind) ?? false}
                notice={notice?.id === item.id ? notice.text : null}
                onChanged={async (message) => {
                  setNotice({ id: item.id, text: message });
                  await refresh();
                }}
              />
            )}
          </li>
        ))}
      </ul>
    </section>
  );
}

function titleOf(item: Assessment): string {
  const first = FIRST_FIELD[item.kind];
  return first ? text(item.data[first.key]) : "";
}

function NewAssessment({
  applicationId,
  kinds,
  onCancel,
  onCreated,
}: {
  applicationId: string;
  kinds: Kind[];
  onCancel: () => void;
  onCreated: (item: Assessment) => Promise<void>;
}) {
  const [kind, setKind] = useState<Kind>(kinds[0]);
  const [first, setFirst] = useState("");
  const [templateId, setTemplateId] = useState("");
  const [feedback, setFeedback] = useState<Feedback>(null);
  const [busy, setBusy] = useState(false);
  const isStudy = kind === "ESTUDIO_SOCIOECONOMICO";
  const templates = useQuery({
    queryKey: ["form-templates"],
    queryFn: ({ signal }) => listTemplates(signal),
    enabled: isStudy,
  });
  const options = (templates.data ?? []).filter((template) => template.status === "ACTIVA");
  const field = FIRST_FIELD[kind];

  async function submit() {
    setBusy(true);
    setFeedback(null);
    try {
      await onCreated(
        await createAssessment(applicationId, {
          kind,
          data: field ? { [field.key]: first } : {},
          template_id: isStudy ? templateId || options[0]?.id : null,
        }),
      );
    } catch (caught) {
      setFeedback({ kind: "error", text: describeError(caught) });
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="flex flex-col gap-3 rounded-3xl bg-surface p-5">
      <div className="grid gap-3 md:grid-cols-2">
        <div className="flex flex-col gap-2">
          <label htmlFor="new-kind" className="text-sm text-ink-muted">
            Tipo de evaluación
          </label>
          <select id="new-kind" className={fieldClass} value={kind} onChange={(event) => setKind(event.target.value as Kind)}>
            {kinds.map((option) => (
              <option key={option} value={option}>
                {KIND_LABELS[option]}
              </option>
            ))}
          </select>
        </div>
        {field ? (
          <div className="flex flex-col gap-2">
            <label htmlFor="new-first" className="text-sm text-ink-muted">
              {field.label}
            </label>
            <input id="new-first" className={fieldClass} value={first} onChange={(event) => setFirst(event.target.value)} />
          </div>
        ) : (
          <div className="flex flex-col gap-2">
            <label htmlFor="new-template" className="text-sm text-ink-muted">
              Formulario
            </label>
            <select id="new-template" className={fieldClass} value={templateId || options[0]?.id || ""} onChange={(event) => setTemplateId(event.target.value)}>
              {options.map((template) => (
                <option key={template.id} value={template.id}>
                  {template.name}
                </option>
              ))}
            </select>
          </div>
        )}
      </div>
      <FeedbackLine feedback={feedback} />
      <div className="flex flex-wrap gap-3">
        <button type="button" className={primaryButtonClass} disabled={busy} onClick={submit}>
          Registrar
        </button>
        <button type="button" className={secondaryButtonClass} onClick={onCancel}>
          Cancelar
        </button>
      </div>
    </div>
  );
}

function AssessmentEditor({
  item,
  vacancyId,
  canEdit,
  notice,
  onChanged,
}: {
  item: Assessment;
  vacancyId: string;
  canEdit: boolean;
  notice: string | null;
  onChanged: (message: string) => Promise<void>;
}) {
  const { kind } = item;
  const [status, setStatus] = useState(item.status);
  const [date, setDate] = useState(item.event_date?.slice(0, 10) ?? "");
  const [fileId, setFileId] = useState(item.file_id ?? "");
  const [values, setValues] = useState<Row>(() =>
    Object.fromEntries(TEXT_FIELDS[kind].map((field) => [field.key, text(item.data[field.key])])),
  );
  const [questions, setQuestions] = useState<Row[]>(() => (item.data.questions as Row[]) ?? []);
  const [competencies, setCompetencies] = useState(() =>
    ((item.data.competencies as string[]) ?? []).join("\n"),
  );
  const [rubric, setRubric] = useState<Row[]>(() =>
    ((item.data.rubric as Record<string, string | null>[]) ?? []).map((row) => ({
      criterion: row.criterion ?? "",
      max_points: row.max_points ?? "",
      points: row.points ?? "",
    })),
  );
  const [passMark, setPassMark] = useState(text(item.data.pass_mark));
  const [answers, setAnswers] = useState<Record<string, Answer>>(
    () => (item.data.answers as Record<string, Answer>) ?? {},
  );
  const [reading, setReading] = useState<Digitization | null>(null);
  const [feedback, setFeedback] = useState<Feedback>(null);
  const [busy, setBusy] = useState(false);
  const filesClient = useQueryClient();
  const files = useQuery({
    queryKey: ["vacancy", vacancyId, "files"],
    queryFn: ({ signal }) => listFiles(vacancyId, signal),
    enabled: canEdit,
  });
  const documents = (files.data ?? []).filter((file) => file.document_type === KIND_DOCUMENT[kind]);

  function payload(): AssessmentData {
    if (kind === "ENTREVISTA") {
      return { ...values, questions, competencies: competencies.split("\n").filter((line) => line.trim()) };
    }
    if (kind === "PRUEBA_TECNICA") {
      return {
        ...values,
        pass_mark: passMark || null,
        rubric: rubric.map((row) => ({ ...row, points: row.points === "" ? null : row.points })),
      };
    }
    if (kind === "ESTUDIO_SOCIOECONOMICO") return { ...values, answers };
    return values;
  }
  async function run(action: () => Promise<unknown>, message: string) {
    setBusy(true);
    setFeedback(null);
    try {
      await action();
      await onChanged(message);
    } catch (caught) {
      setFeedback({ kind: "error", text: describeError(caught) });
    } finally {
      setBusy(false);
    }
  }
  const save = () =>
    run(
      () =>
        updateAssessment(item.id, {
          status,
          data: payload(),
          event_date: date ? `${date}T12:00:00Z` : null,
          file_id: fileId || null,
          version: item.version,
        }),
      "Evaluación guardada.",
    );
  async function digitize() {
    setBusy(true);
    setFeedback(null);
    try {
      const result = await digitizeStudy(item.id, fileId || documents[0].id);
      setReading(result);
      // Lo que lee la IA entra sin verificar: una persona lo revisa campo por campo.
      setAnswers({
        ...answers,
        ...Object.fromEntries(
          Object.entries(result.values).map(([id, value]) => [id, { value, verified: false, source: "IA" }]),
        ),
      });
      setFeedback({
        kind: "ok",
        text: "La IA llenó los campos que encontró. Revísalos, corrígelos y marca cuáles quedan verificados; todavía no se ha guardado.",
      });
    } catch (caught) {
      setFeedback({ kind: "error", text: describeError(caught) });
    } finally {
      setBusy(false);
    }
  }
  const setRow = (rows: Row[], set: (rows: Row[]) => void, index: number, patch: Row) =>
    set(rows.map((row, i) => (i === index ? { ...row, ...patch } : row)));

  return (
    <div className="mt-4 flex flex-col gap-4 border-t border-line pt-4">
      {kind === "PSICOMETRIA" && (
        <p className="text-sm text-ink-muted">
          Es un dato sensible. El sistema no diagnostica ni declara si alguien es apto: registra
          lo que el reporte documenta y la interpretación del profesional que lo validó.
        </p>
      )}
      {kind === "ESTUDIO_SOCIOECONOMICO" && (
        <p className="text-sm text-ink-muted">
          Es un dato sensible. El sistema no lo puntúa ni lo usa para ordenar candidatos: el
          dictamen y los niveles del formato los anota quien aplicó el estudio. Un dato solo
          cuenta como verificado cuando una persona lo marca así.
        </p>
      )}
      <div className="grid gap-3 md:grid-cols-3">
        <Labeled id={`status-${item.id}`} label="Estado">
          <select id={`status-${item.id}`} className={fieldClass} disabled={!canEdit} value={status} onChange={(event) => setStatus(event.target.value)}>
            {item.statuses.map((option) => (
              <option key={option} value={option}>
                {STATUS_LABELS[option] ?? option}
              </option>
            ))}
          </select>
        </Labeled>
        <Labeled id={`date-${item.id}`} label="Fecha">
          <input id={`date-${item.id}`} type="date" className={fieldClass} readOnly={!canEdit} value={date} onChange={(event) => setDate(event.target.value)} />
        </Labeled>
        {kind !== "ENTREVISTA" && (
          <Labeled id={`file-${item.id}`} label={kind === "ESTUDIO_SOCIOECONOMICO" ? "Formulario escaneado" : "Documento"}>
            <select id={`file-${item.id}`} className={fieldClass} disabled={!canEdit} value={fileId} onChange={(event) => setFileId(event.target.value)}>
              <option value="">Sin documento</option>
              {documents.map((file) => (
                <option key={file.id} value={file.id}>
                  {file.original_name}
                </option>
              ))}
            </select>
          </Labeled>
        )}
      </div>
      {fileId && (
        <a href={downloadUrl(fileId)} download className="self-start underline">
          Descargar el documento
        </a>
      )}
      <div className="grid gap-3 md:grid-cols-2">
        {TEXT_FIELDS[kind].map((field) => (
          <div key={field.key} className={field.area ? "md:col-span-2" : ""}>
            <Labeled id={`${field.key}-${item.id}`} label={field.label}>
              {field.area ? (
                <textarea id={`${field.key}-${item.id}`} rows={2} className={areaClass} readOnly={!canEdit} value={values[field.key]} onChange={(event) => setValues({ ...values, [field.key]: event.target.value })} />
              ) : (
                <input id={`${field.key}-${item.id}`} className={fieldClass} readOnly={!canEdit} value={values[field.key]} onChange={(event) => setValues({ ...values, [field.key]: event.target.value })} />
              )}
            </Labeled>
          </div>
        ))}
      </div>

      {kind === "ENTREVISTA" && (
        <>
          <ol aria-label="Preguntas de la entrevista" className="flex flex-col gap-3">
            {questions.map((row, index) => (
              <li key={index} className="flex flex-col gap-2">
                <input aria-label={`Pregunta ${index + 1} de la entrevista`} placeholder="Pregunta" className={fieldClass} readOnly={!canEdit} value={row.question ?? ""} onChange={(event) => setRow(questions, setQuestions, index, { question: event.target.value })} />
                <textarea aria-label={`Respuesta ${index + 1} de la entrevista`} placeholder="Respuesta anotada" rows={2} className={areaClass} readOnly={!canEdit} value={row.answer ?? ""} onChange={(event) => setRow(questions, setQuestions, index, { answer: event.target.value })} />
              </li>
            ))}
          </ol>
          {canEdit && (
            <button type="button" className={`${secondaryButtonClass} self-start`} onClick={() => setQuestions([...questions, { question: "", answer: "" }])}>
              Agregar pregunta
            </button>
          )}
          <Labeled id={`competencies-${item.id}`} label="Competencias observadas (una por línea)">
            <textarea id={`competencies-${item.id}`} rows={3} className={areaClass} readOnly={!canEdit} value={competencies} onChange={(event) => setCompetencies(event.target.value)} />
          </Labeled>
        </>
      )}

      {kind === "PRUEBA_TECNICA" && (
        <>
          <p className="font-medium">Rúbrica</p>
          <ul aria-label="Rúbrica" className="flex flex-col gap-2">
            {rubric.map((row, index) => (
              <li key={index} className="flex flex-wrap items-center gap-2">
                <input aria-label={`Criterio ${index + 1}`} placeholder="Criterio" className={`${fieldClass} flex-[3_1_200px]`} readOnly={!canEdit} value={row.criterion} onChange={(event) => setRow(rubric, setRubric, index, { criterion: event.target.value })} />
                <input aria-label={`Puntos obtenidos del criterio ${index + 1}`} placeholder="Obtenidos" inputMode="decimal" className={`${fieldClass} flex-[1_1_110px]`} readOnly={!canEdit} value={row.points} onChange={(event) => setRow(rubric, setRubric, index, { points: event.target.value })} />
                <input aria-label={`Puntos posibles del criterio ${index + 1}`} placeholder="Posibles" inputMode="decimal" className={`${fieldClass} flex-[1_1_110px]`} readOnly={!canEdit} value={row.max_points} onChange={(event) => setRow(rubric, setRubric, index, { max_points: event.target.value })} />
                {canEdit && (
                  <button type="button" className={dangerButtonClass} aria-label={`Quitar el criterio ${index + 1}`} onClick={() => setRubric(rubric.filter((_, i) => i !== index))}>
                    Quitar
                  </button>
                )}
              </li>
            ))}
          </ul>
          <div className="flex flex-wrap items-end gap-3">
            {canEdit && (
              <button type="button" className={secondaryButtonClass} onClick={() => setRubric([...rubric, { criterion: "", max_points: "", points: "" }])}>
                Agregar criterio
              </button>
            )}
            <Labeled id={`pass-${item.id}`} label="Mínimo aprobatorio (0 a 100, opcional)">
              <input id={`pass-${item.id}`} inputMode="decimal" className={`${fieldClass} max-w-48`} readOnly={!canEdit} value={passMark} onChange={(event) => setPassMark(event.target.value)} />
            </Labeled>
          </div>
          {item.score !== null && (
            <p>
              Calificación calculada por el sistema: <strong>{Number(item.score)} de 100</strong>
              {item.data.passed === true ? " · alcanza el mínimo" : item.data.passed === false ? " · no alcanza el mínimo" : ""}
            </p>
          )}
        </>
      )}

      {kind === "ESTUDIO_SOCIOECONOMICO" && item.form && (
        <>
          {canEdit && (
            <div className="flex flex-wrap items-center gap-3 rounded-2xl bg-white/60 px-4 py-3">
              <button type="button" className={secondaryButtonClass} disabled={busy || (!fileId && documents.length === 0)} onClick={digitize}>
                Leer el formulario escaneado con IA
              </button>
              <p className="flex-[1_1_260px] text-sm text-ink-muted">
                Elige arriba el formulario escaneado. La IA copia los datos que encuentre; no
                guarda nada y nada queda verificado hasta que tú lo marques.
              </p>
            </div>
          )}
          {reading && (reading.illegible.length > 0 || reading.missing.length > 0) && (
            <div className="rounded-2xl bg-accent-red-soft px-4 py-3 text-accent-red-ink">
              {reading.illegible.length > 0 && <p>No se pudo leer: {reading.illegible.join(", ")}.</p>}
              {reading.missing.length > 0 && <p>No aparece en el documento: {reading.missing.join(", ")}.</p>}
            </div>
          )}
          {item.form.map((section) => (
            <fieldset key={section.title} className="grid min-w-0 gap-3 md:grid-cols-2">
              <legend className="font-medium">{section.title}</legend>
              {section.fields.map((field) => (
                <StudyField
                  key={field.id}
                  field={field}
                  answer={answers[field.id]}
                  canEdit={canEdit}
                  documents={documents.map((file) => ({ id: file.id, name: file.original_name }))}
                  assessmentId={item.id}
                  vacancyId={vacancyId}
                  onUploaded={() =>
                    filesClient.invalidateQueries({ queryKey: ["vacancy", vacancyId, "files"] })
                  }
                  onChange={(answer) => {
                    const next = { ...answers };
                    if (answer) next[field.id] = answer;
                    else delete next[field.id];
                    setAnswers(next);
                  }}
                />
              ))}
            </fieldset>
          ))}
        </>
      )}

      <FeedbackLine feedback={feedback ?? (notice ? { kind: "ok", text: notice } : null)} />
      {canEdit && (
        <div className="flex flex-wrap gap-3">
          <button type="button" className={primaryButtonClass} disabled={busy} onClick={save}>
            {busy ? "Trabajando…" : "Guardar"}
          </button>
          {kind !== "ESTUDIO_SOCIOECONOMICO" && (
            <button type="button" className={secondaryButtonClass} disabled={busy} onClick={() => run(() => summarizeAssessment(item.id), "Resumen listo.")}>
              {kind === "ENTREVISTA" ? "Organizar con IA" : "Resumir con IA"}
            </button>
          )}
        </div>
      )}
      {canEdit && kind !== "ESTUDIO_SOCIOECONOMICO" && (
        <p className="text-sm text-ink-muted">
          Guarda antes de pedir el resumen: la IA trabaja con lo último guardado.
        </p>
      )}
      {item.ai_summary && (
        <section aria-label="Resumen de la IA" className="flex flex-col gap-2 rounded-3xl bg-white/60 p-5">
          <h3 className="text-lg font-medium">Resumen de la IA</h3>
          <p className="text-sm text-ink-muted">
            Resume lo documentado{item.ai_summary_at ? ` (${dateTimeFormat.format(new Date(item.ai_summary_at))})` : ""}. No
            es un diagnóstico ni una recomendación.
          </p>
          {text(item.ai_summary.resumen) && <p>{text(item.ai_summary.resumen)}</p>}
          {Object.entries(item.ai_summary).map(([key, list]) =>
            Array.isArray(list) && list.length > 0 ? (
              <div key={key}>
                <p className="font-medium">{SUMMARY_LABELS[key] ?? key}</p>
                <ul className="list-disc pl-5">
                  {list.map((entry) => (
                    <li key={entry}>{entry}</li>
                  ))}
                </ul>
              </div>
            ) : null,
          )}
        </section>
      )}
    </div>
  );
}

function Labeled({ id, label, children }: { id: string; label: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-2">
      <label htmlFor={id} className="text-sm text-ink-muted">
        {label}
      </label>
      {children}
    </div>
  );
}

function StudyField({
  field,
  answer,
  canEdit,
  documents,
  assessmentId,
  vacancyId,
  onUploaded,
  onChange,
}: {
  field: FormField;
  answer: Answer | undefined;
  canEdit: boolean;
  documents: { id: string; name: string }[];
  assessmentId: string;
  vacancyId: string;
  onUploaded: () => Promise<void>;
  onChange: (answer: Answer | null) => void;
}) {
  const id = `study-${field.id}`;
  const value = answer?.value ?? "";
  // Al escribir a mano, el dato deja de contar como leído por la IA.
  const set = (next: string | boolean | string[][]) =>
    onChange(
      next === "" || next === false || (Array.isArray(next) && next.length === 0)
        ? null
        : { value: next, verified: answer?.verified ?? false, source: "MANUAL" },
    );
  const label = `${field.label}${field.required ? " (obligatorio)" : ""}`;
  // Las tablas y los textos largos ocupan todo el ancho; lo demás va en dos columnas.
  const wide = ["TABLA", "PARRAFO", "OBSERVACION", "DOCUMENTO"].includes(field.type);
  let control;
  if (field.type === "TABLA") {
    const rows = Array.isArray(value) ? value : [];
    control = (
      <div className="flex min-w-0 max-w-full flex-col gap-2 overflow-x-auto">
        <table aria-label={field.label} className="w-full min-w-[560px] border-separate border-spacing-1 text-sm">
          <thead>
            <tr>
              {field.columns.map((column) => (
                <th key={column} scope="col" className="px-2 text-left font-normal text-ink-muted">
                  {column}
                </th>
              ))}
              {canEdit && <td />}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, rowIndex) => (
              // Las filas no tienen identificador propio: su posición es estable al editar.
              <tr key={rowIndex}>
                {field.columns.map((column, columnIndex) => (
                  <td key={column}>
                    <input
                      aria-label={`${field.label}, fila ${rowIndex + 1}: ${column}`}
                      className="min-h-11 w-full rounded-xl border border-ink/15 bg-surface px-3"
                      readOnly={!canEdit}
                      maxLength={300}
                      value={row[columnIndex] ?? ""}
                      onChange={(event) =>
                        set(
                          rows.map((cells, index) =>
                            index === rowIndex
                              ? field.columns.map((_, i) => (i === columnIndex ? event.target.value : (cells[i] ?? "")))
                              : cells,
                          ),
                        )
                      }
                    />
                  </td>
                ))}
                {canEdit && (
                  <td>
                    <button type="button" className={secondaryButtonClass} aria-label={`Quitar la fila ${rowIndex + 1} de ${field.label}`} onClick={() => set(rows.filter((_, index) => index !== rowIndex))}>
                      Quitar
                    </button>
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
        {rows.length === 0 && <p className="text-sm text-ink-muted">Sin filas.</p>}
        {canEdit && rows.length < 20 && (
          <button type="button" className={`${secondaryButtonClass} self-start`} aria-label={`Agregar fila a ${field.label}`} onClick={() => set([...rows, field.columns.map(() => "")])}>
            Agregar fila
          </button>
        )}
      </div>
    );
  } else if (field.type === "CASILLA") {
    control = (
      <label className="flex items-center gap-2">
        <input id={id} type="checkbox" className="size-5 accent-ink" disabled={!canEdit} checked={value === true} onChange={(event) => set(event.target.checked)} />
        {label}
      </label>
    );
  } else if (field.type === "DOCUMENTO") {
    control = (
      <StudyDocument
        id={id}
        field={field}
        answer={answer}
        canEdit={canEdit}
        documents={documents}
        assessmentId={assessmentId}
        vacancyId={vacancyId}
        onUploaded={onUploaded}
        onChange={onChange}
      />
    );
  } else if (field.type === "OPCIONES") {
    const options = field.options.map((option) => ({ id: option, name: option }));
    control = (
      <select id={id} className={fieldClass} disabled={!canEdit} value={String(value)} onChange={(event) => set(event.target.value)}>
        <option value="">Sin dato</option>
        {options.map((option) => (
          <option key={option.id} value={option.id}>
            {option.name}
          </option>
        ))}
      </select>
    );
  } else if (field.type === "PARRAFO" || field.type === "OBSERVACION") {
    control = <textarea id={id} rows={2} className={areaClass} readOnly={!canEdit} value={String(value)} onChange={(event) => set(event.target.value)} />;
  } else {
    control = (
      <input id={id} type={field.type === "FECHA" ? "date" : "text"} inputMode={field.type === "NUMERO" ? "decimal" : undefined} className={fieldClass} readOnly={!canEdit} value={String(value)} onChange={(event) => set(event.target.value)} />
    );
  }
  return (
    <div className={`flex min-w-0 flex-col gap-2 rounded-2xl bg-white/60 px-4 py-3 ${wide ? "md:col-span-2" : ""}`}>
      {field.type === "TABLA" ? (
        <p className="text-sm text-ink-muted">{label}</p>
      ) : (
        field.type !== "CASILLA" && (
          <label htmlFor={id} className="text-sm text-ink-muted">
            {label}
          </label>
        )
      )}
      {control}
      {field.manual_only && (
        <p className="text-sm text-ink-muted">Lo anota quien aplicó el estudio. La IA no lo llena.</p>
      )}
      {answer && (
        <div className="flex flex-wrap items-center gap-3 text-sm">
          <label className="flex items-center gap-2">
            <input
              type="checkbox"
              aria-label={`${field.label}: verificado`}
              className="size-4 accent-ink"
              disabled={!canEdit}
              checked={answer.verified}
              onChange={(event) => onChange({ ...answer, verified: event.target.checked })}
            />
            Verificado por una persona
          </label>
          {answer.source === "IA" && (
            <span className={`${pillClass} bg-neutral-soft text-neutral-ink`}>Leído por la IA</span>
          )}
        </div>
      )}
    </div>
  );
}

/**
 * Documento o fotografía de un campo del estudio: se elige uno ya cargado o se
 * adjunta ahí mismo. Si es una imagen, la IA puede proponer una descripción de
 * lo que se observa; la persona la revisa antes de guardar.
 */
function StudyDocument({
  id,
  field,
  answer,
  canEdit,
  documents,
  assessmentId,
  vacancyId,
  onUploaded,
  onChange,
}: {
  id: string;
  field: FormField;
  answer: Answer | undefined;
  canEdit: boolean;
  documents: { id: string; name: string }[];
  assessmentId: string;
  vacancyId: string;
  onUploaded: () => Promise<void>;
  onChange: (answer: Answer | null) => void;
}) {
  const picker = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState(false);
  const [feedback, setFeedback] = useState<Feedback>(null);
  const [unclear, setUnclear] = useState<string[]>([]);
  // Recién adjuntado: se muestra aunque la lista de documentos aún no se haya actualizado.
  const [uploaded, setUploaded] = useState<{ id: string; name: string } | null>(null);
  const fileId = typeof answer?.value === "string" ? answer.value : "";
  const options =
    uploaded && !documents.some((file) => file.id === uploaded.id)
      ? [...documents, uploaded]
      : documents;
  const selected = options.find((file) => file.id === fileId);
  const isPhoto = selected !== undefined && PHOTO_NAME.test(selected.name);

  const choose = (next: string) => {
    setUnclear([]);
    setFeedback(null);
    // Al cambiar de documento, la descripción anterior ya no corresponde.
    onChange(next ? { value: next, verified: false, source: "MANUAL" } : null);
  };

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

  async function attach(file: File) {
    const extension = file.name.slice(file.name.lastIndexOf(".")).toLowerCase();
    if (!STUDY_EXTENSIONS.includes(extension)) {
      return setFeedback({
        kind: "error",
        text: "Formato no permitido. Adjunta una foto JPG o PNG, o un PDF, DOCX o XLSX.",
      });
    }
    if (file.size > MAX_UPLOAD_BYTES) {
      return setFeedback({ kind: "error", text: "El archivo supera el límite de 20 MB." });
    }
    await run(async () => {
      const result = await uploadFile(vacancyId, file, "ESTUDIO_SOCIOECONOMICO");
      setUploaded({ id: result.file.id, name: result.file.original_name });
      await onUploaded();
      choose(result.file.id);
      setFeedback({ kind: "ok", text: "Archivo adjuntado. Guarda el estudio para conservarlo." });
    });
  }

  async function describe() {
    if (!answer) return;
    await run(async () => {
      const proposal = await describePhoto(assessmentId, fileId, field.id);
      setUnclear(proposal.unclear);
      onChange({ ...answer, description: proposal.description, description_source: "IA" });
      setFeedback({
        kind: "ok",
        text: "La IA propuso una descripción. Revísala y corrígela: todavía no se ha guardado.",
      });
    });
  }

  return (
    <div className="flex flex-col gap-2">
      <div className="flex flex-wrap items-center gap-2">
        <select
          id={id}
          className={`${fieldClass} flex-[2_1_220px]`}
          disabled={!canEdit}
          value={fileId}
          onChange={(event) => choose(event.target.value)}
        >
          <option value="">Sin dato</option>
          {options.map((option) => (
            <option key={option.id} value={option.id}>
              {option.name}
            </option>
          ))}
        </select>
        {canEdit && (
          <>
            <input
              ref={picker}
              type="file"
              aria-label={`Adjuntar archivo: ${field.label}`}
              accept={STUDY_EXTENSIONS.join(",")}
              className="sr-only"
              tabIndex={-1}
              onChange={async (event) => {
                const file = event.target.files?.[0];
                event.target.value = "";
                if (file) await attach(file);
              }}
            />
            <button
              type="button"
              className={secondaryButtonClass}
              disabled={busy}
              onClick={() => picker.current?.click()}
            >
              Adjuntar foto o archivo
            </button>
          </>
        )}
        {selected && (
          <a
            className="underline underline-offset-4"
            href={downloadUrl(selected.id)}
            target="_blank"
            rel="noreferrer"
          >
            Ver archivo
          </a>
        )}
      </div>
      {isPhoto && answer && (
        <div className="flex flex-col gap-2">
          <label htmlFor={`${id}-description`} className="text-sm text-ink-muted">
            Descripción de lo que se observa: {field.label}
          </label>
          <textarea
            id={`${id}-description`}
            rows={3}
            maxLength={2000}
            className={areaClass}
            readOnly={!canEdit}
            value={answer.description ?? ""}
            onChange={(event) =>
              // Al escribir a mano, deja de contar como propuesta por la IA.
              onChange({ ...answer, description: event.target.value, description_source: "MANUAL" })
            }
          />
          <div className="flex flex-wrap items-center gap-3">
            {canEdit && (
              <button
                type="button"
                className={secondaryButtonClass}
                disabled={busy}
                aria-label={`Describir con IA: ${field.label}`}
                onClick={describe}
              >
                {busy ? "Trabajando…" : "Describir con IA"}
              </button>
            )}
            {answer.description && answer.description_source === "IA" && (
              <span className={`${pillClass} bg-neutral-soft text-neutral-ink`}>
                Descripción propuesta por la IA
              </span>
            )}
          </div>
          {unclear.length > 0 && (
            <p className="text-sm text-ink-muted">La IA no distingue: {unclear.join("; ")}.</p>
          )}
          <p className="text-sm text-ink-muted">
            La IA describe solo lo que se ve; no saca conclusiones sobre la persona ni califica la
            vivienda. La foto se envía reducida y sin fecha ni ubicación.
          </p>
        </div>
      )}
      <FeedbackLine feedback={feedback} />
    </div>
  );
}
