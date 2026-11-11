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
import { useSession } from "@/features/auth/use-session";
import {
  type AiModel,
  type AiProvider,
  assignModel,
  getAiOverview,
  listAiModels,
  listAssignments,
  OPERATION_LABELS,
  revokeProviderKey,
  setProviderKey,
  testProvider,
  updateProvider,
} from "@/lib/api/ai";
import { describeError } from "@/lib/api/client";

const dateFormat = new Intl.DateTimeFormat("es-MX", {
  timeZone: "America/Mexico_City",
  dateStyle: "medium",
  timeStyle: "short",
});

type Feedback = { kind: "ok" | "error"; text: string } | null;

export function AiSettingsScreen() {
  const { user } = useSession();
  const queryClient = useQueryClient();
  const isAdmin = user?.role === "ADMINISTRADOR";
  const overview = useQuery({
    queryKey: ["ai", "providers"],
    queryFn: ({ signal }) => getAiOverview(signal),
    enabled: isAdmin,
  });

  if (!isAdmin) {
    return (
      <div role="alert" className={cardClass}>
        <h1 className="text-2xl font-medium">Sin acceso</h1>
        <p className="mt-1 text-ink-muted">
          La configuración de inteligencia artificial es solo para administradores.
        </p>
      </div>
    );
  }

  const reload = () => queryClient.invalidateQueries({ queryKey: ["ai"] });

  return (
    <>
      <div>
        <h1 className="text-4xl font-medium tracking-tight sm:text-5xl">
          Configuración de inteligencia artificial
        </h1>
        <p className="mt-2 max-w-3xl text-ink-muted">
          Registra las API keys de cada proveedor y elige qué modelo usa cada operación. Las
          claves se guardan cifradas en el servidor y nunca se vuelven a mostrar completas.
        </p>
      </div>

      {overview.error ? (
        <p role="alert" className="rounded-tile bg-accent-red-soft px-5 py-4 text-accent-red-ink">
          {describeError(overview.error)}
        </p>
      ) : !overview.data ? (
        <p role="status" className="text-ink-muted">
          Cargando configuración…
        </p>
      ) : (
        <>
          {!overview.data.encryption_available && (
            <p role="alert" className="rounded-tile bg-accent-red-soft px-5 py-4 text-accent-red-ink">
              La clave maestra del servidor no está configurada, así que todavía no se pueden
              guardar API keys desde esta pantalla. Pídele a Sistemas que la configure.
            </p>
          )}
          <div className="grid gap-6 lg:grid-cols-2">
            {overview.data.providers.map((provider) => (
              <ProviderCard
                key={provider.code}
                provider={provider}
                canStoreKeys={overview.data.encryption_available}
                onChanged={reload}
              />
            ))}
          </div>
          <Assignments />
          <section className={cardClass}>
            <h2 className="text-xl font-medium">Consumo y costos</h2>
            <p className="mt-1 text-ink-muted">
              Todavía no hay consumo registrado. Aparecerá aquí, por modelo y operación, cuando se
              procesen documentos.
            </p>
          </section>
        </>
      )}
    </>
  );
}

function ProviderCard({
  provider,
  canStoreKeys,
  onChanged,
}: {
  provider: AiProvider;
  canStoreKeys: boolean;
  onChanged: () => Promise<void>;
}) {
  const [dialog, setDialog] = useState<"key" | "revoke" | null>(null);
  const [feedback, setFeedback] = useState<Feedback>(null);
  const [busy, setBusy] = useState(false);
  const [limit, setLimit] = useState(provider.monthly_limit_usd ?? "");
  const fromServer = provider.key_source === "ENTORNO";
  const titleId = `provider-${provider.code}`;

  /** La acción devuelve el aviso de éxito, o un aviso de error ya redactado. */
  async function run(action: () => Promise<string | NonNullable<Feedback>>) {
    setBusy(true);
    setFeedback(null);
    try {
      const outcome = await action();
      await onChanged();
      setFeedback(typeof outcome === "string" ? { kind: "ok", text: outcome } : outcome);
    } catch (caught) {
      setFeedback({ kind: "error", text: describeError(caught) });
    } finally {
      setBusy(false);
    }
  }

  const save = (enabled: boolean, text: string) =>
    run(async () => {
      await updateProvider(provider.code, {
        enabled,
        monthly_limit_usd: limit.trim() === "" ? null : limit.trim(),
      });
      return text;
    });

  return (
    <section aria-labelledby={titleId} className={`${cardClass} flex flex-col gap-4`}>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 id={titleId} className="text-2xl font-medium">
          {provider.name}
        </h2>
        <span
          className={`rounded-full px-3 py-1 text-sm ${
            provider.enabled ? "bg-accent-blue-soft text-accent-blue-ink" : "bg-neutral-soft text-neutral-ink"
          }`}
        >
          {provider.enabled ? "Habilitado" : "Deshabilitado"}
        </span>
      </div>

      <dl className="grid gap-3 sm:grid-cols-2">
        <div>
          <dt className="text-sm text-ink-muted">API key</dt>
          <dd className="font-medium">
            {provider.key_configured ? provider.key_mask : "Sin registrar"}
          </dd>
          <dd className="text-sm text-ink-muted">
            {fromServer
              ? "Definida por Sistemas en el servidor"
              : provider.key_updated_at
                ? `Registrada el ${dateFormat.format(new Date(provider.key_updated_at))}${
                    provider.key_updated_by_name ? ` por ${provider.key_updated_by_name}` : ""
                  }`
                : ""}
          </dd>
        </div>
        <div>
          <dt className="text-sm text-ink-muted">Última prueba de conexión</dt>
          <dd className="font-medium">
            {provider.last_test_ok === null
              ? "Sin probar"
              : provider.last_test_ok
                ? `Correcta · ${provider.models_available} modelos`
                : "Falló"}
          </dd>
          <dd className="text-sm text-ink-muted">
            {provider.last_test_ok === false && provider.last_test_error}
            {provider.last_test_ok && provider.last_test_at
              ? dateFormat.format(new Date(provider.last_test_at))
              : ""}
          </dd>
        </div>
      </dl>

      {feedback && (
        <p
          role={feedback.kind === "ok" ? "status" : "alert"}
          className={`rounded-2xl px-4 py-3 ${
            feedback.kind === "ok"
              ? "bg-accent-blue-soft text-accent-blue-ink"
              : "bg-accent-red-soft text-accent-red-ink"
          }`}
        >
          {feedback.text}
        </p>
      )}

      <div className="flex flex-wrap gap-2">
        {!fromServer && (
          <button
            type="button"
            className={secondaryButtonClass}
            disabled={busy || !canStoreKeys}
            onClick={() => setDialog("key")}
          >
            {provider.key_configured ? "Sustituir clave" : "Registrar clave"}
          </button>
        )}
        <button
          type="button"
          className={secondaryButtonClass}
          disabled={busy || !provider.key_configured}
          onClick={() =>
            run(async () => {
              const result = await testProvider(provider.code);
              if (!result.ok) {
                return { kind: "error", text: result.error ?? "La conexión falló." } as const;
              }
              return `Conexión correcta. El proveedor informa ${result.models_found} modelos.`;
            })
          }
        >
          Probar conexión
        </button>
        <button
          type="button"
          className={secondaryButtonClass}
          disabled={busy || (!provider.enabled && !provider.key_configured)}
          onClick={() =>
            save(
              !provider.enabled,
              provider.enabled
                ? `${provider.name} quedó deshabilitado.`
                : `${provider.name} quedó habilitado.`,
            )
          }
        >
          {provider.enabled ? "Deshabilitar" : "Habilitar"}
        </button>
        {!fromServer && provider.key_configured && (
          <button
            type="button"
            className={dangerButtonClass}
            disabled={busy}
            onClick={() => setDialog("revoke")}
          >
            Revocar clave
          </button>
        )}
      </div>

      <form
        className="flex flex-wrap items-end gap-3 border-t border-line pt-4"
        onSubmit={(event) => {
          event.preventDefault();
          void save(provider.enabled, "Límite mensual guardado.");
        }}
      >
        <div className="flex flex-[1_1_200px] flex-col gap-2">
          <label htmlFor={`limit-${provider.code}`} className="text-sm text-ink-muted">
            Límite de gasto mensual (USD)
          </label>
          <input
            id={`limit-${provider.code}`}
            inputMode="decimal"
            placeholder="Sin límite"
            value={limit}
            onChange={(event) => setLimit(event.target.value)}
            className={fieldClass}
          />
        </div>
        <button type="submit" className={secondaryButtonClass} disabled={busy}>
          Guardar límite
        </button>
      </form>

      {dialog === "key" && (
        <Modal
          title={`${provider.key_configured ? "Sustituir" : "Registrar"} clave de ${provider.name}`}
          onClose={() => setDialog(null)}
        >
          <KeyForm
            provider={provider}
            onCancel={() => setDialog(null)}
            onDone={async () => {
              setDialog(null);
              await onChanged();
              setFeedback({
                kind: "ok",
                text: "Clave guardada y cifrada. Prueba la conexión antes de habilitar el proveedor.",
              });
            }}
          />
        </Modal>
      )}
      {dialog === "revoke" && (
        <Modal title={`Revocar clave de ${provider.name}`} onClose={() => setDialog(null)}>
          <div className="flex flex-col gap-4">
            <p>
              La clave se borra del servidor y {provider.name} queda deshabilitado. Las
              operaciones que usen sus modelos dejarán de funcionar hasta registrar otra clave.
            </p>
            <div className="flex flex-wrap justify-end gap-3">
              <button type="button" className={secondaryButtonClass} onClick={() => setDialog(null)}>
                Cancelar
              </button>
              <button
                type="button"
                className={primaryButtonClass}
                onClick={() => {
                  setDialog(null);
                  void run(async () => {
                    await revokeProviderKey(provider.code);
                    return "Clave revocada y borrada del servidor.";
                  });
                }}
              >
                Revocar clave
              </button>
            </div>
          </div>
        </Modal>
      )}
    </section>
  );
}

function KeyForm({
  provider,
  onCancel,
  onDone,
}: {
  provider: AiProvider;
  onCancel: () => void;
  onDone: () => Promise<void>;
}) {
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    // La clave no se guarda en el estado de la pantalla: se lee del campo y se envía.
    const field = event.currentTarget.elements.namedItem("api_key") as HTMLInputElement;
    const value = field.value.trim();
    if (value.length < 20) return setError("Pega la API key completa.");
    setBusy(true);
    setError(null);
    try {
      await setProviderKey(provider.code, value);
      field.value = "";
      await onDone();
    } catch (caught) {
      setError(describeError(caught));
      setBusy(false);
    }
  }

  return (
    <form className="flex flex-col gap-4" onSubmit={submit} noValidate autoComplete="off">
      <p className="text-ink-muted">
        Pega la clave que generaste en tu cuenta de {provider.name}. Se cifra al guardarla y
        después solo verás sus últimos cuatro caracteres.
        {provider.key_configured && " La clave anterior se borra."}
      </p>
      <div className="flex flex-col gap-2">
        <label htmlFor="api-key" className="text-sm text-ink-muted">
          API key
        </label>
        <input
          id="api-key"
          name="api_key"
          type="password"
          autoComplete="off"
          spellCheck={false}
          className={fieldClass}
        />
      </div>
      {error && (
        <p role="alert" className="text-accent-red-ink">
          {error}
        </p>
      )}
      <div className="flex flex-wrap justify-end gap-3">
        <button type="button" className={secondaryButtonClass} onClick={onCancel}>
          Cancelar
        </button>
        <button type="submit" className={primaryButtonClass} disabled={busy}>
          {busy ? "Guardando…" : "Guardar clave"}
        </button>
      </div>
    </form>
  );
}

function Assignments() {
  const queryClient = useQueryClient();
  const assignments = useQuery({
    queryKey: ["ai", "assignments"],
    queryFn: ({ signal }) => listAssignments(signal),
  });
  const models = useQuery({
    queryKey: ["ai", "models"],
    queryFn: ({ signal }) => listAiModels(signal),
  });
  const providers = useQuery({
    queryKey: ["ai", "providers"],
    queryFn: ({ signal }) => getAiOverview(signal),
  });
  const [feedback, setFeedback] = useState<Feedback>(null);

  const enabled = new Set(
    providers.data?.providers.filter((p) => p.enabled).map((p) => p.code) ?? [],
  );
  const usable = (models.data ?? []).filter((m) => m.is_available && enabled.has(m.provider_code));
  const groups = new Map<string, AiModel[]>();
  for (const model of usable) {
    groups.set(model.provider_name, [...(groups.get(model.provider_name) ?? []), model]);
  }

  async function change(operation: string, modelId: string) {
    setFeedback(null);
    try {
      await assignModel(operation, modelId || null);
      await queryClient.invalidateQueries({ queryKey: ["ai", "assignments"] });
      setFeedback({ kind: "ok", text: `Modelo actualizado para «${OPERATION_LABELS[operation]}».` });
    } catch (caught) {
      setFeedback({ kind: "error", text: describeError(caught) });
    }
  }

  return (
    <section aria-labelledby="assignments-title" className={`${cardClass} flex flex-col gap-4`}>
      <div>
        <h2 id="assignments-title" className="text-xl font-medium">
          Modelo de cada operación
        </h2>
        <p className="mt-1 text-ink-muted">
          {usable.length === 0
            ? "Para elegir modelos, registra una clave, prueba la conexión y habilita el proveedor."
            : "Solo aparecen los modelos que el proveedor informa y cuyos proveedores están habilitados."}
        </p>
      </div>
      {feedback && (
        <p
          role={feedback.kind === "ok" ? "status" : "alert"}
          className={`rounded-2xl px-4 py-3 ${
            feedback.kind === "ok"
              ? "bg-accent-blue-soft text-accent-blue-ink"
              : "bg-accent-red-soft text-accent-red-ink"
          }`}
        >
          {feedback.text}
        </p>
      )}
      <ul className="flex flex-col gap-2">
        {(assignments.data ?? []).map((assignment) => {
          const current = assignment.model;
          const stale = current !== null && !usable.some((m) => m.id === current.id);
          return (
            <li
              key={assignment.operation}
              className="flex flex-wrap items-center justify-between gap-3 rounded-2xl bg-surface px-4 py-3"
            >
              <label htmlFor={`op-${assignment.operation}`} className="font-medium">
                {OPERATION_LABELS[assignment.operation] ?? assignment.operation}
              </label>
              <select
                id={`op-${assignment.operation}`}
                value={current?.id ?? ""}
                onChange={(event) => void change(assignment.operation, event.target.value)}
                className={`${fieldClass} max-w-sm`}
              >
                <option value="">Sin modelo asignado</option>
                {stale && current && (
                  <option value={current.id}>{current.display_name} (ya no disponible)</option>
                )}
                {[...groups.entries()].map(([providerName, items]) => (
                  <optgroup key={providerName} label={providerName}>
                    {items.map((model) => (
                      <option key={model.id} value={model.id}>
                        {model.display_name}
                      </option>
                    ))}
                  </optgroup>
                ))}
              </select>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
