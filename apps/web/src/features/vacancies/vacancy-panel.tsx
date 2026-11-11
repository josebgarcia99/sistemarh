"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Modal } from "@/components/ui/modal";
import {
  dangerButtonClass,
  fieldClass,
  primaryButtonClass,
  secondaryButtonClass,
} from "@/components/ui/styles";
import { UserPicker } from "@/components/ui/user-picker";
import { VacancyDocuments } from "@/features/files/vacancy-documents";
import { describeError } from "@/lib/api/client";
import { transferVacancy } from "@/lib/api/transfers";
import {
  ACCESS_TYPE_LABELS,
  type AccessType,
  accessTypeSchema,
  changeVacancyStatus,
  type DirectoryEntry,
  getVacancy,
  listMembers,
  type Member,
  MY_ACCESS_LABELS,
  ownershipHistory,
  revokeMember,
  SENSITIVE_CLASS_LABELS,
  type SensitiveClass,
  sensitiveClassSchema,
  setMember,
  setSensitiveGrants,
  STATUS_LABELS,
  STATUS_TRANSITIONS,
  type Vacancy,
  type VacancyStatus,
  WORK_MODE_LABELS,
} from "@/lib/api/vacancies";
import { VacancyForm } from "./vacancy-form";

const dateFormat = new Intl.DateTimeFormat("es-MX", {
  timeZone: "America/Mexico_City",
  dateStyle: "medium",
  timeStyle: "short",
});

type Props = {
  vacancyId: string;
  onClose: () => void;
  /** Aviso que se muestra al abrir el panel (por ejemplo, tras crear la vacante). */
  initialNotice?: string;
  /** Abre el perfil de puesto y el prompt de evaluación de la vacante. */
  onOpenEvaluation?: (vacancy: Vacancy) => void;
  /** Abre los candidatos de la vacante: etapas, movimientos y llamadas. */
  onOpenCandidates?: (vacancy: Vacancy) => void;
};

/** Panel de una vacante: datos, estado, con quién se comparte e historial. */
export function VacancyPanel({
  vacancyId,
  onClose,
  initialNotice,
  onOpenEvaluation,
  onOpenCandidates,
}: Props) {
  const queryClient = useQueryClient();
  const [notice, setNotice] = useState<string | null>(initialNotice ?? null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [dialog, setDialog] = useState<"edit" | "transfer" | null>(null);

  const vacancyQuery = useQuery({
    queryKey: ["vacancy", vacancyId],
    queryFn: ({ signal }) => getVacancy(vacancyId, signal),
  });
  const membersQuery = useQuery({
    queryKey: ["vacancy", vacancyId, "members"],
    queryFn: ({ signal }) => listMembers(vacancyId, signal),
  });
  const historyQuery = useQuery({
    queryKey: ["vacancy", vacancyId, "history"],
    queryFn: ({ signal }) => ownershipHistory(vacancyId, signal),
  });

  const vacancy = vacancyQuery.data;

  async function refresh(message?: string) {
    setActionError(null);
    if (message) setNotice(message);
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ["vacancy", vacancyId] }),
      queryClient.invalidateQueries({ queryKey: ["vacancies"] }),
    ]);
  }

  /** Ejecuta una acción y muestra su error en el panel si falla. */
  async function run(action: () => Promise<unknown>, message: string) {
    try {
      await action();
      await refresh(message);
    } catch (error) {
      setNotice(null);
      setActionError(describeError(error));
      // Si otra persona cambió la vacante, se recargan los datos vigentes.
      await queryClient.invalidateQueries({ queryKey: ["vacancy", vacancyId] });
    }
  }

  if (vacancyQuery.isPending) {
    return (
      <aside className="rounded-card bg-surface p-7" aria-label="Detalle de la vacante">
        <p role="status" className="text-ink-muted">
          Cargando la vacante…
        </p>
      </aside>
    );
  }
  if (!vacancy) {
    return (
      <aside className="rounded-card bg-surface p-7" aria-label="Detalle de la vacante">
        <p role="alert" className="text-accent-red-ink">
          {describeError(vacancyQuery.error)}
        </p>
        <button type="button" onClick={onClose} className={`${secondaryButtonClass} mt-4`}>
          Cerrar
        </button>
      </aside>
    );
  }

  const canManage = vacancy.my_access === "RESPONSABLE" || vacancy.my_access === "ADMINISTRADOR";
  const isAdmin = vacancy.my_access === "ADMINISTRADOR";
  const nextStatuses = STATUS_TRANSITIONS[vacancy.status];
  const members = membersQuery.data ?? [];

  return (
    <aside
      aria-label={`Detalle de ${vacancy.name}`}
      className="flex flex-col gap-6 rounded-card bg-surface p-7"
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-sm text-ink-muted">
            {vacancy.department} · {vacancy.location} · {WORK_MODE_LABELS[vacancy.work_mode]}
          </p>
          <h2 className="mt-1 text-2xl font-medium tracking-tight">{vacancy.name}</h2>
        </div>
        <button type="button" onClick={onClose} className={secondaryButtonClass}>
          Cerrar
        </button>
      </div>

      {notice && (
        <p role="status" className="rounded-tile bg-accent-blue-soft px-5 py-3 text-accent-blue-ink">
          {notice}
        </p>
      )}
      {actionError && (
        <p role="alert" className="rounded-tile bg-accent-red-soft px-5 py-3 text-accent-red-ink">
          {actionError}
        </p>
      )}

      <dl className="grid grid-cols-2 gap-x-4 gap-y-3 text-sm">
        <div>
          <dt className="text-ink-muted">Estado</dt>
          <dd className="font-medium">{STATUS_LABELS[vacancy.status]}</dd>
        </div>
        <div>
          <dt className="text-ink-muted">Mi acceso</dt>
          <dd className="font-medium">{MY_ACCESS_LABELS[vacancy.my_access]}</dd>
        </div>
        <div>
          <dt className="text-ink-muted">Posiciones</dt>
          <dd className="font-medium">{vacancy.positions}</dd>
        </div>
        <div>
          <dt className="text-ink-muted">Tipo de contratación</dt>
          <dd className="font-medium">{vacancy.contract_type}</dd>
        </div>
        {vacancy.description && (
          <div className="col-span-2">
            <dt className="text-ink-muted">Descripción</dt>
            <dd className="whitespace-pre-line">{vacancy.description}</dd>
          </div>
        )}
        {vacancy.notes && (
          <div className="col-span-2">
            <dt className="text-ink-muted">Observaciones</dt>
            <dd className="whitespace-pre-line">{vacancy.notes}</dd>
          </div>
        )}
      </dl>

      {canManage && (
        <div className="flex flex-wrap gap-2">
          {vacancy.status !== "ARCHIVADA" && (
            <button type="button" className={secondaryButtonClass} onClick={() => setDialog("edit")}>
              Editar datos
            </button>
          )}
          {nextStatuses.map((status: VacancyStatus) => (
            <button
              key={status}
              type="button"
              className={secondaryButtonClass}
              onClick={() =>
                run(
                  () => changeVacancyStatus(vacancy.id, status, vacancy.version),
                  `La vacante pasó a ${STATUS_LABELS[status].toLowerCase()}.`,
                )
              }
            >
              Pasar a {STATUS_LABELS[status].toLowerCase()}
            </button>
          ))}
        </div>
      )}

      <section aria-labelledby="share-title" className="flex flex-col gap-3">
        <h3 id="share-title" className="text-lg font-medium">
          Compartida con
        </h3>
        <div className="flex items-center gap-3 rounded-tile bg-surface-soft px-5 py-3">
          <span className="flex flex-col">
            <span className="font-medium">{vacancy.owner?.full_name ?? "Sin datos"}</span>
            <span className="text-sm text-ink-muted">Responsable principal</span>
          </span>
        </div>
        {membersQuery.isPending ? (
          <p role="status" className="text-ink-muted">
            Cargando accesos…
          </p>
        ) : members.length === 0 ? (
          <p className="text-sm text-ink-muted">Nadie más tiene acceso. La vacante es privada.</p>
        ) : (
          <ul className="flex flex-col gap-2">
            {members.map((member) => (
              <MemberRow
                key={member.user?.id ?? member.granted_at}
                member={member}
                canManage={canManage}
                onAccessChange={(accessType) =>
                  run(
                    () => setMember(vacancy.id, member.user!.id, accessType),
                    `${member.user!.full_name} ahora tiene acceso de ${ACCESS_TYPE_LABELS[accessType].toLowerCase()}.`,
                  )
                }
                onSensitiveChange={(classes) =>
                  run(
                    () => setSensitiveGrants(vacancy.id, member.user!.id, classes),
                    `Se actualizaron los permisos de documentos sensibles de ${member.user!.full_name}.`,
                  )
                }
                onRevoke={() =>
                  run(
                    () => revokeMember(vacancy.id, member.user!.id),
                    `${member.user!.full_name} ya no tiene acceso.`,
                  )
                }
              />
            ))}
          </ul>
        )}
        {canManage && (
          <ShareForm
            excludeIds={[vacancy.owner?.id ?? "", ...members.map((m) => m.user?.id ?? "")]}
            onShare={(user, accessType) =>
              run(
                () => setMember(vacancy.id, user.id, accessType),
                `Compartiste la vacante con ${user.full_name}. Sigues siendo responsable.`,
              )
            }
          />
        )}
        <p className="text-sm text-ink-muted">
          Compartir no transfiere la propiedad ni da acceso a psicometría o estudios
          socioeconómicos: esos permisos se otorgan aparte, por persona.
        </p>
      </section>

      {onOpenEvaluation && (
        <section aria-labelledby="evaluation-title" className="flex flex-col gap-3">
          <h3 id="evaluation-title" className="text-lg font-medium">
            Evaluación de CV
          </h3>
          <p className="text-sm text-ink-muted">
            Define el perfil de puesto y el prompt con el que la IA hará la revisión inicial.
          </p>
          <button
            type="button"
            className={`${secondaryButtonClass} self-start`}
            onClick={() => onOpenEvaluation(vacancy)}
          >
            Perfil, prompt y evaluación de CV
          </button>
        </section>
      )}

      {onOpenCandidates && (
        <section aria-labelledby="candidates-title" className="flex flex-col gap-3">
          <h3 id="candidates-title" className="text-lg font-medium">
            Candidatos
          </h3>
          <p className="text-sm text-ink-muted">
            Las personas de esta vacante, su etapa, su historial y sus llamadas.
          </p>
          <button
            type="button"
            className={`${secondaryButtonClass} self-start`}
            onClick={() => onOpenCandidates(vacancy)}
          >
            Candidatos y etapas
          </button>
        </section>
      )}

      <VacancyDocuments
        vacancyId={vacancy.id}
        canUpload={vacancy.my_access !== "LECTURA"}
        canDelete={isAdmin}
      />

      <section aria-labelledby="history-title" className="flex flex-col gap-3">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h3 id="history-title" className="text-lg font-medium">
            Historial de responsables
          </h3>
          {isAdmin && (
            <button
              type="button"
              className={secondaryButtonClass}
              onClick={() => setDialog("transfer")}
            >
              Transferir responsable
            </button>
          )}
        </div>
        <ol className="flex flex-col gap-2">
          {(historyQuery.data ?? []).map((change) => (
            <li
              key={`${change.changed_at}-${change.new_owner?.id}`}
              className="rounded-2xl bg-surface-soft px-4 py-3 text-sm"
            >
              <p className="font-medium">
                {change.previous_owner
                  ? `${change.previous_owner.full_name} → ${change.new_owner?.full_name ?? "Sin datos"}`
                  : `Responsable inicial: ${change.new_owner?.full_name ?? "Sin datos"}`}
              </p>
              <p className="text-ink-muted">
                {dateFormat.format(new Date(change.changed_at))} · {change.reason}
                {change.previous_owner && change.authorized_by
                  ? ` · autorizó ${change.authorized_by.full_name}`
                  : ""}
              </p>
            </li>
          ))}
        </ol>
      </section>

      {dialog === "edit" && (
        <Modal title="Editar vacante" onClose={() => setDialog(null)}>
          <VacancyForm
            vacancy={vacancy}
            onCancel={() => setDialog(null)}
            onDone={(_, message) => {
              setDialog(null);
              void refresh(message);
            }}
          />
        </Modal>
      )}
      {dialog === "transfer" && (
        <Modal
          title="Transferir responsable"
          description={`Responsable actual: ${vacancy.owner?.full_name ?? "sin datos"}. La vacante, sus documentos y su historial se conservan.`}
          onClose={() => setDialog(null)}
        >
          <TransferForm
            vacancy={vacancy}
            onCancel={() => setDialog(null)}
            onDone={(message) => {
              setDialog(null);
              void refresh(message);
            }}
          />
        </Modal>
      )}
    </aside>
  );
}

function MemberRow({
  member,
  canManage,
  onAccessChange,
  onSensitiveChange,
  onRevoke,
}: {
  member: Member;
  canManage: boolean;
  onAccessChange: (accessType: AccessType) => void;
  onSensitiveChange: (classes: SensitiveClass[]) => void;
  onRevoke: () => void;
}) {
  const name = member.user?.full_name ?? "Usuario sin datos";
  return (
    <li className="flex flex-col gap-3 rounded-tile bg-surface-soft px-5 py-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <span className="flex flex-col">
          <span className="font-medium">{name}</span>
          <span className="text-sm text-ink-muted">{member.user?.email}</span>
        </span>
        {canManage && member.user ? (
          <span className="flex flex-wrap items-center gap-2">
            <select
              aria-label={`Tipo de acceso de ${name}`}
              value={member.access_type}
              onChange={(event) => onAccessChange(accessTypeSchema.parse(event.target.value))}
              className="min-h-11 rounded-full border border-ink/15 bg-surface px-4"
            >
              {accessTypeSchema.options.map((type) => (
                <option key={type} value={type}>
                  {ACCESS_TYPE_LABELS[type]}
                </option>
              ))}
            </select>
            <button
              type="button"
              aria-label={`Revocar el acceso de ${name}`}
              onClick={onRevoke}
              className={dangerButtonClass}
            >
              Revocar
            </button>
          </span>
        ) : (
          <span className="rounded-full bg-neutral-soft px-3 py-1 text-sm text-neutral-ink">
            {ACCESS_TYPE_LABELS[member.access_type]}
          </span>
        )}
      </div>
      {canManage && member.user && (
        <fieldset className="flex flex-col gap-1">
          <legend className="text-sm text-ink-muted">Documentos sensibles</legend>
          {sensitiveClassSchema.options.map((documentClass) => {
            const checked = member.sensitive_classes.includes(documentClass);
            return (
              <label key={documentClass} className="flex min-h-11 items-center gap-3">
                <input
                  type="checkbox"
                  className="size-5 accent-ink"
                  checked={checked}
                  onChange={() =>
                    onSensitiveChange(
                      checked
                        ? member.sensitive_classes.filter((c) => c !== documentClass)
                        : [...member.sensitive_classes, documentClass],
                    )
                  }
                />
                {SENSITIVE_CLASS_LABELS[documentClass]}
              </label>
            );
          })}
        </fieldset>
      )}
    </li>
  );
}

function ShareForm({
  excludeIds,
  onShare,
}: {
  excludeIds: string[];
  onShare: (user: DirectoryEntry, accessType: AccessType) => Promise<void>;
}) {
  const [user, setUser] = useState<DirectoryEntry | null>(null);
  const [accessType, setAccessType] = useState<AccessType>("LECTURA");
  const [busy, setBusy] = useState(false);
  // Cambia tras cada envío para que el buscador empiece vacío.
  const [round, setRound] = useState(0);

  return (
    <form
      className="flex flex-col gap-3 border-t border-line pt-4"
      onSubmit={async (event) => {
        event.preventDefault();
        if (!user) return;
        setBusy(true);
        await onShare(user, accessType);
        setBusy(false);
        setUser(null);
        setRound((n) => n + 1);
      }}
    >
      <UserPicker
        key={round}
        label="Compartir con"
        selected={user}
        onSelect={setUser}
        excludeIds={excludeIds}
      />
      <div className="flex flex-wrap gap-3">
        <select
          aria-label="Tipo de acceso al compartir"
          value={accessType}
          onChange={(event) => setAccessType(accessTypeSchema.parse(event.target.value))}
          className={`${fieldClass} flex-1`}
        >
          {accessTypeSchema.options.map((type) => (
            <option key={type} value={type}>
              {ACCESS_TYPE_LABELS[type]}
            </option>
          ))}
        </select>
        <button type="submit" disabled={!user || busy} className={primaryButtonClass}>
          Compartir
        </button>
      </div>
    </form>
  );
}

function TransferForm({
  vacancy,
  onDone,
  onCancel,
}: {
  vacancy: Vacancy;
  onDone: (message: string) => void;
  onCancel: () => void;
}) {
  const [target, setTarget] = useState<DirectoryEntry | null>(null);
  const [reason, setReason] = useState("");
  const [keepPrevious, setKeepPrevious] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  return (
    <form
      className="flex flex-col gap-4"
      onSubmit={async (event) => {
        event.preventDefault();
        if (!target) return setError("Elige a la persona que será responsable.");
        if (!reason.trim()) return setError("Escribe el motivo de la transferencia.");
        setBusy(true);
        setError(null);
        try {
          await transferVacancy({
            vacancy_id: vacancy.id,
            to_user_id: target.id,
            reason,
            keep_previous_as_collaborator: keepPrevious,
          });
          onDone(`${target.full_name} es ahora responsable de la vacante.`);
        } catch (caught) {
          setError(describeError(caught));
          setBusy(false);
        }
      }}
    >
      <UserPicker
        label="Nuevo responsable"
        selected={target}
        onSelect={setTarget}
        excludeIds={[vacancy.owner?.id ?? ""]}
      />
      <div className="flex flex-col gap-2">
        <label htmlFor="transfer-reason" className="text-sm text-ink-muted">
          Motivo
        </label>
        <input
          id="transfer-reason"
          value={reason}
          maxLength={500}
          onChange={(event) => setReason(event.target.value)}
          className={fieldClass}
        />
      </div>
      <label className="flex min-h-11 items-center gap-3">
        <input
          type="checkbox"
          className="size-5 accent-ink"
          checked={keepPrevious}
          onChange={(event) => setKeepPrevious(event.target.checked)}
        />
        Dejar al responsable anterior como colaborador
      </label>
      {error && (
        <p role="alert" className="rounded-tile bg-accent-red-soft px-5 py-4 text-accent-red-ink">
          {error}
        </p>
      )}
      <div className="flex flex-wrap justify-end gap-3">
        <button type="button" onClick={onCancel} className={secondaryButtonClass}>
          Cancelar
        </button>
        <button type="submit" disabled={busy} className={primaryButtonClass}>
          {busy ? "Transfiriendo…" : "Transferir"}
        </button>
      </div>
    </form>
  );
}
