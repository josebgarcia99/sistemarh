"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { type FormEvent, useState } from "react";
import { Modal } from "@/components/ui/modal";
import {
  cardClass,
  dangerButtonClass,
  fieldClass,
  primaryButtonClass,
  secondaryButtonClass,
} from "@/components/ui/styles";
import { AssessmentsSection } from "@/features/assessments/assessments-section";
import { DossierSection } from "@/features/assessments/dossier-section";
import { CallsSection } from "@/features/calls/calls-section";
import { describeError } from "@/lib/api/client";
import { downloadUrl } from "@/lib/api/files";
import {
  AI_LABELS,
  annotate,
  type ApplicationDetail,
  APPLICATION_STATUS_LABELS,
  formatMonths,
  getApplication,
  MOVEMENT_LABELS,
  moveApplications,
  OUTCOME_KINDS,
  OUTCOME_LABELS,
  type OutcomeInput,
  type OutcomeKind,
  recordOutcome,
  reopenApplication,
  updateCandidate,
} from "@/lib/api/recruitment";
import { type DialogProps, Field, MoveDialog } from "./dialogs";
import {
  AI_STYLES,
  areaClass,
  dateTimeFormat,
  type Feedback,
  FeedbackLine,
  formatDay,
  pillClass,
  STATUS_STYLES,
} from "./shared";

type Props = {
  applicationId: string;
  vacancyId: string;
  vacancyName: string;
  canEdit: boolean;
  onBack: () => void;
};
type Dialog = "move" | "note" | "outcome" | "reopen" | null;

/** Expediente de una postulación: datos, evaluación inicial, historial y llamadas. */
export function ApplicationDetailView({ applicationId, vacancyId, vacancyName, canEdit, onBack }: Props) {
  const queryClient = useQueryClient();
  const queryKey = ["application", applicationId];
  const { data: detail, error } = useQuery({
    queryKey,
    queryFn: ({ signal }) => getApplication(applicationId, signal),
  });
  const [dialog, setDialog] = useState<Dialog>(null);
  const [feedback, setFeedback] = useState<Feedback>(null);
  const [busy, setBusy] = useState(false);

  async function run(action: () => Promise<unknown>, message: string) {
    setBusy(true);
    setFeedback(null);
    try {
      await action();
      await queryClient.invalidateQueries({ queryKey });
      setDialog(null);
      setFeedback({ kind: "ok", text: message });
    } catch (caught) {
      setFeedback({ kind: "error", text: describeError(caught) });
    } finally {
      setBusy(false);
    }
  }

  const back = (
    <button type="button" className={secondaryButtonClass} onClick={onBack}>
      Volver a candidatos
    </button>
  );
  if (error) {
    return (
      <>
        {back}
        <p role="alert" className="rounded-tile bg-accent-red-soft px-5 py-4 text-accent-red-ink">
          {describeError(error)}
        </p>
      </>
    );
  }
  if (!detail) return <p className="text-ink-muted">Cargando expediente…</p>;

  const { application, pipeline, campaign } = detail;
  const stage = pipeline.stages.find((item) => item.id === application.stage_id);
  const active = application.status === "ACTIVA";
  const operable = canEdit && campaign.status === "ABIERTA";

  return (
    <>
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="text-sm text-ink-muted">
            {vacancyName} · {campaign.name}
          </p>
          <h1 className="text-4xl font-medium tracking-tight sm:text-5xl">{application.full_name}</h1>
          <div className="mt-3 flex flex-wrap items-center gap-2">
            <span className={`${pillClass} ${STATUS_STYLES[application.status]}`}>
              {APPLICATION_STATUS_LABELS[application.status]}
            </span>
            <span className={`${pillClass} bg-surface`}>Etapa: {stage?.name ?? "Sin etapa"}</span>
            {application.due_at && (
              <span className={`${pillClass} bg-surface`}>
                Fecha acordada: {dateTimeFormat.format(new Date(application.due_at))}
              </span>
            )}
          </div>
        </div>
        {back}
      </div>
      <FeedbackLine feedback={dialog ? null : feedback} />

      {canEdit && (
        <section className={`${cardClass} flex flex-wrap gap-3`} aria-label="Acciones">
          {operable && active && (
            <button type="button" className={primaryButtonClass} onClick={() => setDialog("move")}>
              Mover de etapa
            </button>
          )}
          <button type="button" className={secondaryButtonClass} onClick={() => setDialog("note")}>
            Incidencia o reprogramación
          </button>
          {active ? (
            <button type="button" className={dangerButtonClass} onClick={() => setDialog("outcome")}>
              Registrar resultado final
            </button>
          ) : (
            <button type="button" className={secondaryButtonClass} onClick={() => setDialog("reopen")}>
              Reabrir proceso
            </button>
          )}
        </section>
      )}

      <div className="flex flex-wrap items-start gap-6">
        <div className="flex min-w-0 flex-[3_1_520px] flex-col gap-6">
          <CandidateCard
            key={application.updated_at}
            detail={detail}
            canEdit={canEdit}
            busy={busy}
            onSave={(input) => run(() => updateCandidate(application.id, input), "Datos guardados.")}
          />
          <EvaluationCard detail={detail} />
          <CallsSection applicationId={application.id} canEdit={canEdit} active={active} />
          <AssessmentsSection applicationId={application.id} vacancyId={vacancyId} active={active} />
          <DossierSection detail={detail} canEdit={canEdit} />
        </div>
        <div className="flex min-w-0 flex-[1_1_300px] flex-col gap-6">
        <OutcomeCard detail={detail} />
        <section className={`${cardClass} flex flex-col gap-3`}>
          <h2 className="text-xl font-medium">Historial</h2>
          <ol aria-label="Historial de movimientos" className="flex flex-col gap-2">
            {[...detail.movements].reverse().map((movement) => (
              <li key={movement.id} className="rounded-2xl bg-surface px-4 py-3">
                <p className="font-medium">
                  {MOVEMENT_LABELS[movement.kind] ?? movement.kind}
                  {movement.to_stage ? `: ${movement.to_stage}` : movement.kind === "OMISION" ? `: ${movement.from_stage}` : ""}
                </p>
                <p className="text-sm text-ink-muted">
                  {dateTimeFormat.format(new Date(movement.occurred_at))} ·{" "}
                  {movement.actor_name ?? "Sistema"}
                  {movement.mass ? " · movimiento en grupo" : ""}
                </p>
                {movement.note && <p className="text-sm">{movement.note}</p>}
                {movement.due_at && (
                  <p className="text-sm">Nueva fecha: {dateTimeFormat.format(new Date(movement.due_at))}</p>
                )}
              </li>
            ))}
          </ol>
        </section>
        </div>
      </div>

      {dialog === "move" && (
        <MoveDialog
          title={`Mover a ${application.full_name}`}
          stages={pipeline.stages}
          currentStageId={application.stage_id}
          busy={busy}
          feedback={feedback}
          onClose={() => setDialog(null)}
          onSubmit={(stageId, note) =>
            run(() => moveApplications(vacancyId, [application.id], stageId, note), "Etapa actualizada.")
          }
        />
      )}
      {dialog === "note" && (
        <NoteDialog
          busy={busy}
          feedback={feedback}
          onClose={() => setDialog(null)}
          onSubmit={(note, dueAt) =>
            run(
              () => annotate(application.id, note, dueAt),
              dueAt ? "Etapa reprogramada." : "Incidencia registrada.",
            )
          }
        />
      )}
      {dialog === "outcome" && (
        <OutcomeDialog
          name={application.full_name}
          busy={busy}
          feedback={feedback}
          onClose={() => setDialog(null)}
          onSubmit={(input) =>
            run(() => recordOutcome(application.id, input), "Resultado final registrado.")
          }
        />
      )}
      {dialog === "reopen" && (
        <ReasonDialog
          title="Reabrir el proceso de esta persona"
          description="El resultado final anterior queda anulado, con tu nombre y el motivo. No se borra."
          busy={busy}
          feedback={feedback}
          onClose={() => setDialog(null)}
          onSubmit={(reason) =>
            run(() => reopenApplication(application.id, reason), "Proceso reabierto.")
          }
        />
      )}
    </>
  );
}

function CandidateCard({
  detail,
  canEdit,
  busy,
  onSave,
}: {
  detail: ApplicationDetail;
  canEdit: boolean;
  busy: boolean;
  onSave: (input: { full_name: string; email: string | null; phone: string | null }) => void;
}) {
  const { application } = detail;
  const [name, setName] = useState(application.full_name);
  const [email, setEmail] = useState(application.email ?? "");
  const [phone, setPhone] = useState(application.phone ?? "");
  function submit(event: FormEvent) {
    event.preventDefault();
    onSave({ full_name: name, email: email.trim() || null, phone: phone.trim() || null });
  }
  return (
    <form onSubmit={submit} noValidate className={`${cardClass} flex flex-col gap-4`}>
      <h2 className="text-xl font-medium">Datos de la persona</h2>
      <div className="grid gap-4 md:grid-cols-3">
        <Field id="person-name" label="Nombre completo" value={name} onChange={setName} readOnly={!canEdit} />
        <Field id="person-email" label="Correo" value={email} onChange={setEmail} readOnly={!canEdit} />
        <Field id="person-phone" label="Teléfono" value={phone} onChange={setPhone} readOnly={!canEdit} />
      </div>
      <div className="flex flex-wrap items-center gap-3">
        {canEdit && (
          <button type="submit" className={secondaryButtonClass} disabled={busy}>
            Guardar datos
          </button>
        )}
        {application.cv_file_id && (
          <a href={downloadUrl(application.cv_file_id)} download className={`${secondaryButtonClass} inline-flex items-center`}>
            Descargar CV
          </a>
        )}
      </div>
    </form>
  );
}

function EvaluationCard({ detail }: { detail: ApplicationDetail }) {
  const { evaluation, tenure, application } = detail;
  if (!evaluation) {
    return (
      <section className={`${cardClass} flex flex-col gap-2`}>
        <h2 className="text-xl font-medium">Evaluación inicial de la IA</h2>
        <p className="text-ink-muted">Esta persona se dio de alta a mano; no tiene evaluación de CV.</p>
      </section>
    );
  }
  const criteria = evaluation.result.criterios ?? [];
  const extraction = evaluation.extraction;
  return (
    <section className={`${cardClass} flex flex-col gap-4`}>
      <div className="flex flex-wrap items-center gap-3">
        <h2 className="text-xl font-medium">Evaluación inicial de la IA</h2>
        <span className={`${pillClass} ${AI_STYLES[evaluation.classification] ?? ""}`}>
          {AI_LABELS[evaluation.classification] ?? evaluation.classification}
          {application.ai_score !== null ? ` · ${Number(application.ai_score)} de 100` : ""}
        </span>
      </div>
      <p className="text-sm text-ink-muted">
        Es una sugerencia inicial sobre «{evaluation.file_name}». No cambia cuando mueves a la
        persona y no decide nada.
      </p>
      {evaluation.result.motivo && <p>{evaluation.result.motivo}</p>}
      {criteria.length > 0 && (
        <details>
          <summary className="cursor-pointer text-ink-muted underline">Ver niveles por criterio</summary>
          <ul className="mt-3 flex flex-col gap-2">
            {criteria.map((criterion) => (
              <li key={criterion.id} className="rounded-2xl bg-surface px-4 py-3">
                <p className="font-medium">
                  {criterion.id}: {criterion.sin_evidencia ? "sin evidencia" : `nivel ${criterion.nivel} de 4`}
                </p>
                {criterion.evidencia && <p className="text-sm">«{criterion.evidencia}»</p>}
                <p className="text-sm text-ink-muted">{criterion.justificacion}</p>
              </li>
            ))}
          </ul>
        </details>
      )}
      {tenure && (
        <div className="flex flex-col gap-2">
          <h3 className="text-lg font-medium">Experiencia según el CV</h3>
          <ul aria-label="Experiencia" className="flex flex-col gap-1.5">
            {tenure.jobs.map((job, index) => (
              <li key={index} className="rounded-2xl bg-surface px-4 py-2">
                <span className="font-medium">{job.title || "Puesto sin nombre"}</span>
                {job.company ? ` · ${job.company}` : ""}
                <span className="text-ink-muted">
                  {" "}
                  · {job.start || "?"} a {job.current ? "hoy" : job.end || "?"} · {formatMonths(job.months)}
                  {job.approximate ? " (aproximado)" : ""}
                </span>
              </li>
            ))}
          </ul>
          <p className="text-sm text-ink-muted">
            Tiempo total documentado: {formatMonths(tenure.total_months)} · promedio por empleo:{" "}
            {formatMonths(tenure.average_months)} · mediana: {formatMonths(tenure.median_months)}
            {tenure.overlaps > 0 ? ` · ${tenure.overlaps} periodos simultáneos` : ""}
            {tenure.incomplete > 0 ? ` · ${tenure.incomplete} sin fechas completas` : ""}. Es
            información de apoyo: una permanencia breve no es motivo de rechazo.
          </p>
        </div>
      )}
      {(extraction.habilidades?.length ?? 0) > 0 && (
        <p>
          <span className="text-ink-muted">Habilidades: </span>
          {extraction.habilidades?.join(", ")}
        </p>
      )}
      {(extraction.estudios?.length ?? 0) > 0 && (
        <p>
          <span className="text-ink-muted">Estudios: </span>
          {extraction.estudios
            ?.map((study) => [study.titulo, study.institucion, study.periodo].filter(Boolean).join(", "))
            .join(" · ")}
        </p>
      )}
      {(extraction.certificaciones?.length ?? 0) > 0 && (
        <p>
          <span className="text-ink-muted">Certificaciones: </span>
          {extraction.certificaciones?.join(", ")}
        </p>
      )}
    </section>
  );
}

function OutcomeCard({ detail }: { detail: ApplicationDetail }) {
  const current = detail.outcomes.find((item) => item.voided_at === null);
  const voided = detail.outcomes.filter((item) => item.voided_at !== null);
  return (
    <section className={`${cardClass} flex flex-col gap-3`} aria-label="Resultado final">
      <h2 className="text-xl font-medium">Resultado final</h2>
      {current ? (
        <div className="flex flex-col gap-1 rounded-2xl bg-surface px-4 py-3">
          <p className="text-lg font-medium">{OUTCOME_LABELS[current.outcome] ?? current.outcome}</p>
          <p className="text-sm text-ink-muted">
            {dateTimeFormat.format(new Date(current.recorded_at))} · {current.recorded_by_name ?? "—"}
          </p>
          {current.start_date && <p>Fecha de incorporación: {formatDay(current.start_date)}</p>}
          {current.reason && <p>Motivo: {current.reason}</p>}
          {current.notes && <p className="whitespace-pre-line text-sm">{current.notes}</p>}
        </div>
      ) : (
        <p className="text-ink-muted">
          {detail.application.status === "ACTIVA"
            ? "En proceso. El resultado lo registra una persona; la IA no decide contrataciones."
            : "Cerrada antes de que se registraran los resultados finales."}
        </p>
      )}
      {voided.length > 0 && (
        <ul aria-label="Resultados anulados" className="flex flex-col gap-2">
          {voided.map((item) => (
            <li key={item.id} className="rounded-2xl bg-surface px-4 py-3 text-sm">
              <p>
                <span className="line-through">{OUTCOME_LABELS[item.outcome] ?? item.outcome}</span>{" "}
                · anulado
              </p>
              <p className="text-ink-muted">
                {dateTimeFormat.format(new Date(item.voided_at ?? item.recorded_at))} ·{" "}
                {item.voided_by_name ?? "—"}
              </p>
              {item.void_reason && <p>{item.void_reason}</p>}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

function OutcomeDialog({
  name,
  busy,
  feedback,
  onClose,
  onSubmit,
}: DialogProps & { name: string; onSubmit: (input: OutcomeInput) => void }) {
  const [outcome, setOutcome] = useState<OutcomeKind>("CONTRATADO");
  const [reason, setReason] = useState("");
  const [notes, setNotes] = useState("");
  const [startDate, setStartDate] = useState("");
  const hired = outcome === "CONTRATADO";
  function submit(event: FormEvent) {
    event.preventDefault();
    onSubmit({
      outcome,
      reason: reason.trim() || null,
      notes: notes.trim() || null,
      start_date: hired && startDate ? startDate : null,
    });
  }
  return (
    <Modal
      title={`Resultado final de ${name}`}
      description="Cierra el proceso de esta persona en la vacante. Queda registrado con tu nombre y la fecha, y cuenta en los indicadores."
      onClose={onClose}
    >
      <form onSubmit={submit} noValidate className="flex flex-col gap-4">
        <div className="flex flex-col gap-2">
          <label htmlFor="outcome-kind" className="text-sm text-ink-muted">
            Resultado
          </label>
          <select
            id="outcome-kind"
            className={fieldClass}
            value={outcome}
            onChange={(event) => setOutcome(event.target.value as OutcomeKind)}
          >
            {OUTCOME_KINDS.map((kind) => (
              <option key={kind} value={kind}>
                {OUTCOME_LABELS[kind]}
              </option>
            ))}
          </select>
        </div>
        {hired && (
          <div className="flex flex-col gap-2">
            <label htmlFor="outcome-start" className="text-sm text-ink-muted">
              Fecha de incorporación (opcional)
            </label>
            <input
              id="outcome-start"
              type="date"
              className={fieldClass}
              value={startDate}
              onChange={(event) => setStartDate(event.target.value)}
            />
          </div>
        )}
        <Field
          id="outcome-reason"
          label={hired ? "Motivo (opcional)" : "Motivo"}
          value={reason}
          onChange={setReason}
        />
        <div className="flex flex-col gap-2">
          <label htmlFor="outcome-notes" className="text-sm text-ink-muted">
            Observaciones (opcional)
          </label>
          <textarea
            id="outcome-notes"
            rows={3}
            className={areaClass}
            value={notes}
            onChange={(event) => setNotes(event.target.value)}
          />
        </div>
        <FeedbackLine feedback={feedback} />
        <div className="flex flex-wrap justify-end gap-3">
          <button type="button" className={secondaryButtonClass} onClick={onClose}>
            Cancelar
          </button>
          <button type="submit" className={primaryButtonClass} disabled={busy}>
            {busy ? "Guardando…" : "Registrar resultado"}
          </button>
        </div>
      </form>
    </Modal>
  );
}

function ReasonDialog({
  title,
  description,
  busy,
  feedback,
  onClose,
  onSubmit,
}: DialogProps & { title: string; description: string; onSubmit: (note: string) => void }) {
  const [note, setNote] = useState("");
  return (
    <Modal title={title} description={description} onClose={onClose}>
      <form
        onSubmit={(event) => {
          event.preventDefault();
          onSubmit(note);
        }}
        noValidate
        className="flex flex-col gap-4"
      >
        <Field id="reason" label="Motivo" value={note} onChange={setNote} />
        <FeedbackLine feedback={feedback} />
        <div className="flex flex-wrap justify-end gap-3">
          <button type="button" className={secondaryButtonClass} onClick={onClose}>
            Cancelar
          </button>
          <button type="submit" className={primaryButtonClass} disabled={busy}>
            Confirmar
          </button>
        </div>
      </form>
    </Modal>
  );
}

function NoteDialog({
  busy,
  feedback,
  onClose,
  onSubmit,
}: DialogProps & { onSubmit: (note: string, dueAt: string | null) => void }) {
  const [note, setNote] = useState("");
  const [due, setDue] = useState("");
  return (
    <Modal
      title="Incidencia o reprogramación"
      description="Anota lo ocurrido. Si indicas una fecha nueva, la etapa actual queda reprogramada."
      onClose={onClose}
    >
      <form
        onSubmit={(event) => {
          event.preventDefault();
          onSubmit(note, due ? new Date(due).toISOString() : null);
        }}
        noValidate
        className="flex flex-col gap-4"
      >
        <Field id="incident-note" label="Qué ocurrió" value={note} onChange={setNote} />
        <div className="flex flex-col gap-2">
          <label htmlFor="incident-due" className="text-sm text-ink-muted">
            Nueva fecha (opcional)
          </label>
          <input
            id="incident-due"
            type="datetime-local"
            className={fieldClass}
            value={due}
            onChange={(event) => setDue(event.target.value)}
          />
        </div>
        <FeedbackLine feedback={feedback} />
        <div className="flex flex-wrap justify-end gap-3">
          <button type="button" className={secondaryButtonClass} onClick={onClose}>
            Cancelar
          </button>
          <button type="submit" className={primaryButtonClass} disabled={busy}>
            Registrar
          </button>
        </div>
      </form>
    </Modal>
  );
}
