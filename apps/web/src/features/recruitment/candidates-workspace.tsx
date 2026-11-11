"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { type FormEvent, useState } from "react";
import { Modal } from "@/components/ui/modal";
import {
  cardClass,
  dangerButtonClass,
  primaryButtonClass,
  secondaryButtonClass,
} from "@/components/ui/styles";
import { describeError } from "@/lib/api/client";
import {
  addCandidate,
  AI_LABELS,
  type Application,
  APPLICATION_STATUS_LABELS,
  type Board,
  closeCampaign,
  getBoard,
  moveApplications,
  openCampaign,
  type Stage,
} from "@/lib/api/recruitment";
import { ApplicationDetailView } from "./application-detail";
import { DialogButtons, type DialogProps, Field, MoveDialog } from "./dialogs";
import { AI_STYLES, type Feedback, FeedbackLine, pillClass, STATUS_STYLES } from "./shared";

type Props = {
  vacancyId: string;
  vacancyName: string;
  /** Colaboración o más: da de alta y mueve candidatos. */
  canEdit: boolean;
  /** Responsable o administrador: abre y cierra convocatorias. */
  canManage: boolean;
  onBack: () => void;
};

/** Candidatos de una vacante: convocatoria, etapas y movimientos. */
export function CandidatesWorkspace({ vacancyId, vacancyName, canEdit, canManage, onBack }: Props) {
  const queryClient = useQueryClient();
  const [campaignId, setCampaignId] = useState<string | null>(null);
  const queryKey = ["vacancy", vacancyId, "applications", campaignId];
  const { data: board, error } = useQuery({
    queryKey,
    queryFn: ({ signal }) => getBoard(vacancyId, campaignId, signal),
  });
  const [openId, setOpenId] = useState<string | null>(null);
  const [stageFilter, setStageFilter] = useState<string | null>(null);
  const [selected, setSelected] = useState<string[]>([]);
  const [dialog, setDialog] = useState<"add" | "move" | "campaign" | null>(null);
  const [feedback, setFeedback] = useState<Feedback>(null);
  const [busy, setBusy] = useState(false);

  const refresh = () => queryClient.invalidateQueries({ queryKey: ["vacancy", vacancyId, "applications"] });

  async function run(action: () => Promise<unknown>, message: string) {
    setBusy(true);
    setFeedback(null);
    try {
      await action();
      await refresh();
      setSelected([]);
      setDialog(null);
      setFeedback({ kind: "ok", text: message });
      return true;
    } catch (caught) {
      setFeedback({ kind: "error", text: describeError(caught) });
      return false;
    } finally {
      setBusy(false);
    }
  }

  if (openId) {
    return (
      <ApplicationDetailView
        applicationId={openId}
        vacancyId={vacancyId}
        vacancyName={vacancyName}
        canEdit={canEdit}
        onBack={() => {
          setOpenId(null);
          void refresh();
        }}
      />
    );
  }

  const header = (
    <div className="flex flex-wrap items-end justify-between gap-4">
      <div>
        <p className="text-sm text-ink-muted">{vacancyName}</p>
        <h1 className="text-4xl font-medium tracking-tight sm:text-5xl">Candidatos</h1>
        <p className="mt-2 max-w-3xl text-ink-muted">
          Cada CV evaluado entra aquí en revisión de RH con la clasificación inicial de la IA.
          Avanzar, descartar o reactivar a una persona es siempre decisión tuya y queda en su
          historial.
        </p>
      </div>
      <button type="button" className={secondaryButtonClass} onClick={onBack}>
        Volver a vacantes
      </button>
    </div>
  );
  if (error) {
    return (
      <>
        {header}
        <p role="alert" className="rounded-tile bg-accent-red-soft px-5 py-4 text-accent-red-ink">
          {describeError(error)}
        </p>
      </>
    );
  }
  if (!board) {
    return (
      <>
        {header}
        <p className="text-ink-muted">Cargando candidatos…</p>
      </>
    );
  }

  const { campaign, pipeline, applications } = board;
  const stages = pipeline?.stages ?? [];
  const open = campaign?.status === "ABIERTA";
  const visible = applications.filter((item) => !stageFilter || item.stage_id === stageFilter);
  const count = (stageId: string) =>
    applications.filter((item) => item.stage_id === stageId && item.status === "ACTIVA").length;
  const toggle = (id: string) =>
    setSelected(selected.includes(id) ? selected.filter((item) => item !== id) : [...selected, id]);

  return (
    <>
      {header}
      <section className={`${cardClass} flex flex-col gap-4`}>
        <div className="flex flex-wrap items-end justify-between gap-4">
          <CampaignPicker board={board} onChange={(id) => { setCampaignId(id); setStageFilter(null); setSelected([]); }} />
          <div className="flex flex-wrap gap-3">
            {canEdit && (
              <button type="button" className={primaryButtonClass} onClick={() => setDialog("add")}>
                Agregar candidato
              </button>
            )}
            {canManage && campaign && open && (
              <button
                type="button"
                className={dangerButtonClass}
                disabled={busy}
                onClick={() => run(() => closeCampaign(campaign.id), "Convocatoria cerrada.")}
              >
                Cerrar convocatoria
              </button>
            )}
            {canManage && campaign && !board.campaigns.some((item) => item.status === "ABIERTA") && (
              <button type="button" className={secondaryButtonClass} onClick={() => setDialog("campaign")}>
                Abrir convocatoria nueva
              </button>
            )}
          </div>
        </div>
        {campaign && !open && (
          <p className="rounded-2xl bg-surface px-4 py-3">
            Esta convocatoria está cerrada: se consulta, pero ya no admite movimientos.
          </p>
        )}
        <FeedbackLine feedback={dialog ? null : feedback} />
        {!campaign ? (
          <p className="text-ink-muted">
            Todavía no hay candidatos. Aparecerán al evaluar CV, o agrégalos a mano.
          </p>
        ) : (
          <>
            <div role="group" aria-label="Etapa" className="flex flex-wrap gap-1.5">
              <StagePill label={`Todas (${applications.length})`} active={!stageFilter} onClick={() => setStageFilter(null)} />
              {stages.map((stage) => (
                <StagePill
                  key={stage.id}
                  label={`${stage.name} (${count(stage.id)})`}
                  active={stageFilter === stage.id}
                  onClick={() => setStageFilter(stage.id)}
                />
              ))}
            </div>
            {canEdit && open && selected.length > 0 && (
              <div className="flex flex-wrap items-center gap-3 rounded-2xl bg-surface px-4 py-3">
                <span>{selected.length} seleccionados</span>
                <button type="button" className={secondaryButtonClass} onClick={() => setDialog("move")}>
                  Mover de etapa
                </button>
                <button type="button" className={secondaryButtonClass} onClick={() => setSelected([])}>
                  Quitar selección
                </button>
              </div>
            )}
            {visible.length === 0 ? (
              <p className="text-ink-muted">No hay candidatos en esta etapa.</p>
            ) : (
              <ul aria-label="Candidatos" className="flex flex-col gap-2">
                {visible.map((item) => (
                  <ApplicationRow
                    key={item.id}
                    item={item}
                    stage={stages.find((stage) => stage.id === item.stage_id)}
                    selectable={canEdit && open && item.status === "ACTIVA"}
                    selected={selected.includes(item.id)}
                    onToggle={() => toggle(item.id)}
                    onOpen={() => setOpenId(item.id)}
                  />
                ))}
              </ul>
            )}
          </>
        )}
      </section>

      {dialog === "add" && (
        <AddCandidateDialog
          busy={busy}
          feedback={feedback}
          onClose={() => setDialog(null)}
          onSubmit={(input) => run(() => addCandidate(vacancyId, input), "Candidato agregado.")}
        />
      )}
      {dialog === "move" && (
        <MoveDialog
          title={`Mover ${selected.length} candidatos`}
          stages={stages}
          busy={busy}
          feedback={feedback}
          onClose={() => setDialog(null)}
          onSubmit={(stageId, note) =>
            run(() => moveApplications(vacancyId, selected, stageId, note), "Candidatos movidos.")
          }
        />
      )}
      {dialog === "campaign" && (
        <CampaignDialog
          busy={busy}
          feedback={feedback}
          onClose={() => setDialog(null)}
          onSubmit={(name) =>
            run(async () => {
              await openCampaign(vacancyId, name);
              setCampaignId(null);
            }, "Convocatoria abierta.")
          }
        />
      )}
    </>
  );
}

function StagePill({ label, active, onClick }: { label: string; active: boolean; onClick: () => void }) {
  return (
    <button
      type="button"
      aria-pressed={active}
      onClick={onClick}
      className={`min-h-10 rounded-full px-4 text-sm ${
        active ? "bg-ink text-white" : "border border-line bg-surface"
      }`}
    >
      {label}
    </button>
  );
}

function CampaignPicker({ board, onChange }: { board: Board; onChange: (id: string | null) => void }) {
  if (!board.campaign) return <h2 className="text-2xl font-medium">Convocatoria</h2>;
  return (
    <div className="flex flex-col gap-1">
      <label htmlFor="campaign" className="text-sm text-ink-muted">
        Convocatoria
      </label>
      <select
        id="campaign"
        className="min-h-11 rounded-full border border-ink/15 bg-surface px-4"
        value={board.campaign.id}
        onChange={(event) => onChange(event.target.value)}
      >
        {board.campaigns.map((item) => (
          <option key={item.id} value={item.id}>
            {item.name} · {item.status === "ABIERTA" ? "abierta" : "cerrada"}
          </option>
        ))}
      </select>
    </div>
  );
}

function ApplicationRow({
  item,
  stage,
  selectable,
  selected,
  onToggle,
  onOpen,
}: {
  item: Application;
  stage: Stage | undefined;
  selectable: boolean;
  selected: boolean;
  onToggle: () => void;
  onOpen: () => void;
}) {
  return (
    <li className="flex flex-wrap items-center gap-x-4 gap-y-2 rounded-tile bg-surface px-5 py-3">
      {selectable && (
        <input
          type="checkbox"
          aria-label={`Seleccionar a ${item.full_name}`}
          className="size-5 accent-ink"
          checked={selected}
          onChange={onToggle}
        />
      )}
      <button
        type="button"
        onClick={onOpen}
        className="min-w-0 flex-[1_1_220px] break-words text-left font-medium underline-offset-4 hover:underline"
      >
        {item.full_name}
      </button>
      {item.ai_classification && (
        <span className={`${pillClass} ${AI_STYLES[item.ai_classification] ?? ""}`}>
          {AI_LABELS[item.ai_classification] ?? item.ai_classification}
          {item.ai_score !== null ? ` · ${Number(item.ai_score)}` : ""}
        </span>
      )}
      <span className="text-ink-muted">{stage?.name ?? "Sin etapa"}</span>
      {item.status !== "ACTIVA" && (
        <span className={`${pillClass} ${STATUS_STYLES[item.status]}`}>
          {APPLICATION_STATUS_LABELS[item.status]}
        </span>
      )}
    </li>
  );
}

function AddCandidateDialog({
  busy,
  feedback,
  onClose,
  onSubmit,
}: DialogProps & {
  onSubmit: (input: { full_name: string; email: string | null; phone: string | null }) => void;
}) {
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  function submit(event: FormEvent) {
    event.preventDefault();
    onSubmit({ full_name: name, email: email.trim() || null, phone: phone.trim() || null });
  }
  return (
    <Modal
      title="Agregar candidato"
      description="Para una persona que no llegó por un lote de CV. Entra en revisión de RH."
      onClose={onClose}
    >
      <form onSubmit={submit} noValidate className="flex flex-col gap-4">
        <Field id="candidate-name" label="Nombre completo" value={name} onChange={setName} />
        <Field id="candidate-email" label="Correo (opcional)" value={email} onChange={setEmail} />
        <Field id="candidate-phone" label="Teléfono (opcional)" value={phone} onChange={setPhone} />
        <FeedbackLine feedback={feedback} />
        <DialogButtons busy={busy} label="Agregar" onClose={onClose} />
      </form>
    </Modal>
  );
}

function CampaignDialog({
  busy,
  feedback,
  onClose,
  onSubmit,
}: DialogProps & { onSubmit: (name: string | null) => void }) {
  const [name, setName] = useState("");
  return (
    <Modal
      title="Abrir convocatoria nueva"
      description="Empieza un periodo nuevo de reclutamiento para esta vacante, con las etapas vigentes. La anterior se conserva para consulta."
      onClose={onClose}
    >
      <form
        onSubmit={(event) => {
          event.preventDefault();
          onSubmit(name.trim() || null);
        }}
        noValidate
        className="flex flex-col gap-4"
      >
        <Field id="campaign-name" label="Nombre (opcional)" value={name} onChange={setName} />
        <FeedbackLine feedback={feedback} />
        <DialogButtons busy={busy} label="Abrir" onClose={onClose} />
      </form>
    </Modal>
  );
}
