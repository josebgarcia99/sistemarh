"use client";

import { type FormEvent, useState } from "react";
import { Modal } from "@/components/ui/modal";
import { fieldClass, primaryButtonClass, secondaryButtonClass } from "@/components/ui/styles";
import type { Stage } from "@/lib/api/recruitment";
import { type Feedback, FeedbackLine } from "./shared";

export type DialogProps = { busy: boolean; feedback: Feedback; onClose: () => void };


export function DialogButtons({ busy, label, onClose }: { busy: boolean; label: string; onClose: () => void }) {
  return (
    <div className="flex flex-wrap justify-end gap-3">
      <button type="button" className={secondaryButtonClass} onClick={onClose}>
        Cancelar
      </button>
      <button type="submit" className={primaryButtonClass} disabled={busy}>
        {busy ? "Guardando…" : label}
      </button>
    </div>
  );
}

export function MoveDialog({
  title,
  stages,
  currentStageId,
  busy,
  feedback,
  onClose,
  onSubmit,
}: DialogProps & {
  title: string;
  stages: Stage[];
  currentStageId?: string;
  onSubmit: (stageId: string, note: string | null) => void;
}) {
  const options = stages.filter((stage) => stage.id !== currentStageId);
  const [stageId, setStageId] = useState(options[0]?.id ?? "");
  const [note, setNote] = useState("");
  function submit(event: FormEvent) {
    event.preventDefault();
    onSubmit(stageId, note.trim() || null);
  }
  return (
    <Modal
      title={title}
      description="El motivo es obligatorio para regresar de etapa, para omitir etapas y para avanzar a quien la IA no clasificó como aceptado."
      onClose={onClose}
    >
      <form onSubmit={submit} noValidate className="flex flex-col gap-4">
        <div className="flex flex-col gap-2">
          <label htmlFor="move-stage" className="text-sm text-ink-muted">
            Etapa de destino
          </label>
          <select id="move-stage" className={fieldClass} value={stageId} onChange={(event) => setStageId(event.target.value)}>
            {options.map((stage) => (
              <option key={stage.id} value={stage.id}>
                {stage.position}. {stage.name}
                {stage.is_optional ? " (opcional)" : ""}
              </option>
            ))}
          </select>
        </div>
        <Field id="move-note" label="Motivo" value={note} onChange={setNote} />
        <FeedbackLine feedback={feedback} />
        <DialogButtons busy={busy} label="Mover" onClose={onClose} />
      </form>
    </Modal>
  );
}

export function Field({
  id,
  label,
  value,
  onChange,
  readOnly,
}: {
  id: string;
  label: string;
  value: string;
  onChange: (value: string) => void;
  readOnly?: boolean;
}) {
  return (
    <div className="flex flex-col gap-2">
      <label htmlFor={id} className="text-sm text-ink-muted">
        {label}
      </label>
      <input
        id={id}
        className={fieldClass}
        value={value}
        readOnly={readOnly}
        onChange={(event) => onChange(event.target.value)}
      />
    </div>
  );
}
