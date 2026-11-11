"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import {
  cardClass,
  dangerButtonClass,
  fieldClass,
  primaryButtonClass,
  secondaryButtonClass,
} from "@/components/ui/styles";
import { UserPicker } from "@/components/ui/user-picker";
import { useSession } from "@/features/auth/use-session";
import { describeError } from "@/lib/api/client";
import {
  executeMassTransfer,
  type MassPreview,
  type MassResult,
  previewMassTransfer,
} from "@/lib/api/transfers";
import { type DirectoryEntry, STATUS_LABELS, vacancyStatusSchema } from "@/lib/api/vacancies";

/**
 * Baja de un reclutador con transferencia de todo lo que tiene a su cargo.
 * Pasos: elegir personas, revisar la vista previa y confirmar.
 */
export function MassTransferScreen() {
  const { user } = useSession();
  const queryClient = useQueryClient();
  const [fromUser, setFromUser] = useState<DirectoryEntry | null>(null);
  const [toUser, setToUser] = useState<DirectoryEntry | null>(null);
  const [preview, setPreview] = useState<MassPreview | null>(null);
  // Un identificador por operación: repetir la confirmación no la duplica.
  const [operationId, setOperationId] = useState<string | null>(null);
  const [reason, setReason] = useState("");
  const [result, setResult] = useState<MassResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  if (user?.role !== "ADMINISTRADOR") {
    return (
      <div role="alert" className={cardClass}>
        <h1 className="text-2xl font-medium">Sin acceso</h1>
        <p className="mt-1 text-ink-muted">Las transferencias son solo para administradores.</p>
      </div>
    );
  }

  function reset() {
    setFromUser(null);
    setToUser(null);
    setPreview(null);
    setOperationId(null);
    setReason("");
    setResult(null);
    setError(null);
  }

  async function loadPreview() {
    if (!fromUser || !toUser) return;
    setBusy(true);
    setError(null);
    try {
      setPreview(await previewMassTransfer(fromUser.id, toUser.id));
      setOperationId(crypto.randomUUID());
    } catch (caught) {
      setPreview(null);
      setError(describeError(caught));
    } finally {
      setBusy(false);
    }
  }

  async function confirm() {
    if (!preview || !operationId) return;
    if (!reason.trim()) return setError("Escribe el motivo de la baja.");
    setBusy(true);
    setError(null);
    try {
      const done = await executeMassTransfer({
        operation_id: operationId,
        from_user_id: preview.from_user.id,
        to_user_id: preview.to_user.id,
        reason,
        preview_token: preview.preview_token,
      });
      setResult(done);
      void queryClient.invalidateQueries();
    } catch (caught) {
      setError(describeError(caught));
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <div>
        <h1 className="text-4xl font-medium tracking-tight sm:text-5xl">Baja con transferencia</h1>
        <p className="mt-2 max-w-3xl text-ink-muted">
          Da de baja a un reclutador y pasa todas sus vacantes a otra persona en una sola
          operación. Las vacantes, sus documentos y su historial se conservan; el usuario no se
          borra.
        </p>
      </div>

      {error && (
        <p role="alert" className="rounded-tile bg-accent-red-soft px-5 py-4 text-accent-red-ink">
          {error}
        </p>
      )}

      {result ? (
        <section role="status" className={`${cardClass} flex flex-col gap-4`}>
          <h2 className="text-2xl font-medium">Operación completada</h2>
          <ul className="flex flex-col gap-1">
            <li>
              Vacantes transferidas a {preview?.to_user.full_name}: {result.vacancies_transferred}
            </li>
            <li>Accesos a vacantes de otros revocados: {result.memberships_revoked}</li>
            <li>Permisos de documentos sensibles revocados: {result.grants_revoked}</li>
            <li>
              {result.user_deactivated
                ? `${preview?.from_user.full_name} quedó dado de baja y sus sesiones se cerraron.`
                : `${preview?.from_user.full_name} ya estaba dado de baja.`}
            </li>
          </ul>
          <button type="button" className={`${secondaryButtonClass} self-start`} onClick={reset}>
            Hacer otra baja
          </button>
        </section>
      ) : (
        <>
          <section className={`${cardClass} flex flex-col gap-5`}>
            <h2 className="text-xl font-medium">1. Quién sale y quién recibe</h2>
            <div className="grid gap-5 md:grid-cols-2">
              <UserPicker
                label="Usuario saliente"
                selected={fromUser}
                onSelect={(picked) => {
                  setFromUser(picked);
                  setPreview(null);
                }}
                excludeIds={[user.id, toUser?.id ?? ""]}
              />
              <UserPicker
                label="Usuario receptor"
                selected={toUser}
                onSelect={(picked) => {
                  setToUser(picked);
                  setPreview(null);
                }}
                excludeIds={[fromUser?.id ?? ""]}
              />
            </div>
            <button
              type="button"
              className={`${primaryButtonClass} self-start`}
              disabled={!fromUser || !toUser || busy}
              onClick={loadPreview}
            >
              {preview ? "Actualizar vista previa" : "Ver vista previa"}
            </button>
          </section>

          {preview && (
            <section className={`${cardClass} flex flex-col gap-5`}>
              <h2 className="text-xl font-medium">2. Revisa lo que va a ocurrir</h2>
              <div className="grid gap-3 sm:grid-cols-3">
                <div className="rounded-tile bg-surface px-5 py-4">
                  <p className="text-sm text-ink-muted">Vacantes que se transfieren</p>
                  <p className="text-3xl font-medium">{preview.vacancies.length}</p>
                </div>
                <div className="rounded-tile bg-surface px-5 py-4">
                  <p className="text-sm text-ink-muted">Accesos que se revocan</p>
                  <p className="text-3xl font-medium">{preview.memberships_to_revoke}</p>
                </div>
                <div className="rounded-tile bg-surface px-5 py-4">
                  <p className="text-sm text-ink-muted">Permisos sensibles que se revocan</p>
                  <p className="text-3xl font-medium">{preview.grants_to_revoke}</p>
                </div>
              </div>
              {preview.vacancies.length > 0 ? (
                <ul aria-label="Vacantes que se transfieren" className="flex flex-col gap-1.5">
                  {preview.vacancies.map((vacancy) => (
                    <li
                      key={vacancy.id}
                      className="flex flex-wrap justify-between gap-2 rounded-2xl bg-surface px-4 py-3"
                    >
                      <span className="font-medium">{vacancy.name}</span>
                      <span className="text-sm text-ink-muted">
                        {STATUS_LABELS[vacancyStatusSchema.parse(vacancy.status)]}
                      </span>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-ink-muted">
                  {preview.from_user.full_name} no es responsable de ninguna vacante.
                </p>
              )}

              <h2 className="text-xl font-medium">3. Confirma</h2>
              <div className="flex flex-col gap-2">
                <label htmlFor="mass-reason" className="text-sm text-ink-muted">
                  Motivo de la baja
                </label>
                <input
                  id="mass-reason"
                  value={reason}
                  maxLength={500}
                  onChange={(event) => setReason(event.target.value)}
                  className={fieldClass}
                />
              </div>
              <p className="text-sm text-ink-muted">
                Al confirmar, {preview.from_user.full_name} pierde el acceso de inmediato y{" "}
                {preview.to_user.full_name} queda como responsable. Todo se aplica junto: si algo
                falla, no cambia nada.
              </p>
              <button
                type="button"
                className={`${dangerButtonClass} self-start`}
                disabled={busy}
                onClick={confirm}
              >
                {busy ? "Aplicando…" : "Dar de baja y transferir"}
              </button>
            </section>
          )}
        </>
      )}
    </>
  );
}
