"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import {
  dangerButtonClass,
  fieldClass,
  primaryButtonClass,
  secondaryButtonClass,
} from "@/components/ui/styles";
import { ROLE_LABELS, roleSchema, type User } from "@/lib/api/auth";
import { describeError } from "@/lib/api/client";
import { createUser, resetPassword, setUserActive, updateUser } from "@/lib/api/users";

// Misma regla que la API: mínimo 12 caracteres.
const passwordSchema = z
  .string()
  .min(12, "La contraseña debe tener al menos 12 caracteres.")
  .max(128, "La contraseña no puede superar 128 caracteres.");
const nameSchema = z.string().trim().min(1, "Escribe el nombre completo.").max(200);

type FormProps = { onDone: (message: string) => void; onCancel: () => void };

function Field({
  id,
  label,
  error,
  children,
}: {
  id: string;
  label: string;
  error?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex flex-col gap-2">
      <label htmlFor={id} className="text-sm text-ink-muted">
        {label}
      </label>
      {children}
      {error && (
        <p id={`${id}-error`} className="text-sm text-accent-red-ink">
          {error}
        </p>
      )}
    </div>
  );
}

function FormFooter({
  submitLabel,
  busy,
  serverError,
  onCancel,
  danger = false,
}: {
  submitLabel: string;
  busy: boolean;
  serverError: string | null;
  onCancel: () => void;
  danger?: boolean;
}) {
  return (
    <>
      {serverError && (
        <p role="alert" className="rounded-tile bg-accent-red-soft px-5 py-4 text-accent-red-ink">
          {serverError}
        </p>
      )}
      <div className="flex flex-wrap justify-end gap-3">
        <button type="button" onClick={onCancel} className={secondaryButtonClass}>
          Cancelar
        </button>
        <button
          type="submit"
          disabled={busy}
          className={danger ? dangerButtonClass : primaryButtonClass}
        >
          {busy ? "Guardando…" : submitLabel}
        </button>
      </div>
    </>
  );
}

function PasswordInput({
  id,
  invalid,
  registration,
}: {
  id: string;
  invalid: boolean;
  registration: object;
}) {
  const [visible, setVisible] = useState(false);
  return (
    <div className="flex gap-2">
      <input
        id={id}
        type={visible ? "text" : "password"}
        autoComplete="new-password"
        aria-invalid={invalid ? true : undefined}
        aria-describedby={invalid ? `${id}-error` : undefined}
        className={fieldClass}
        {...registration}
      />
      <button
        type="button"
        onClick={() => setVisible((v) => !v)}
        aria-pressed={visible}
        className={secondaryButtonClass}
      >
        {visible ? "Ocultar" : "Mostrar"}
      </button>
    </div>
  );
}

const createSchema = z.object({
  email: z.string().trim().min(1, "Escribe el correo.").email("El correo no tiene un formato válido."),
  full_name: nameSchema,
  password: passwordSchema,
  role: roleSchema,
});

export function CreateUserForm({ onDone, onCancel }: FormProps) {
  const [serverError, setServerError] = useState<string | null>(null);
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<z.infer<typeof createSchema>>({
    resolver: zodResolver(createSchema),
    defaultValues: { role: "RECLUTADOR" },
  });

  const onSubmit = handleSubmit(async (values) => {
    setServerError(null);
    try {
      const user = await createUser(values);
      onDone(`Se creó la cuenta de ${user.full_name}. Entrégale su contraseña por un medio seguro.`);
    } catch (error) {
      setServerError(describeError(error));
    }
  });

  return (
    <form onSubmit={onSubmit} noValidate className="flex flex-col gap-4">
      <Field id="new-name" label="Nombre completo" error={errors.full_name?.message}>
        <input
          id="new-name"
          autoComplete="off"
          aria-invalid={errors.full_name ? true : undefined}
          className={fieldClass}
          {...register("full_name")}
        />
      </Field>
      <Field id="new-email" label="Correo" error={errors.email?.message}>
        <input
          id="new-email"
          type="email"
          autoComplete="off"
          aria-invalid={errors.email ? true : undefined}
          className={fieldClass}
          {...register("email")}
        />
      </Field>
      <Field id="new-password" label="Contraseña" error={errors.password?.message}>
        <PasswordInput
          id="new-password"
          invalid={Boolean(errors.password)}
          registration={register("password")}
        />
      </Field>
      <Field id="new-role" label="Rol" error={errors.role?.message}>
        <select id="new-role" className={fieldClass} {...register("role")}>
          {roleSchema.options.map((role) => (
            <option key={role} value={role}>
              {ROLE_LABELS[role]}
            </option>
          ))}
        </select>
      </Field>
      <p className="text-sm text-ink-muted">
        La contraseña no se envía por correo y nadie podrá consultarla después; solo se puede
        restablecer.
      </p>
      <FormFooter
        submitLabel="Crear usuario"
        busy={isSubmitting}
        serverError={serverError}
        onCancel={onCancel}
      />
    </form>
  );
}

const editSchema = z.object({ full_name: nameSchema, role: roleSchema });

export function EditUserForm({ user, onDone, onCancel }: FormProps & { user: User }) {
  const [serverError, setServerError] = useState<string | null>(null);
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<z.infer<typeof editSchema>>({
    resolver: zodResolver(editSchema),
    defaultValues: { full_name: user.full_name, role: user.role },
  });

  const onSubmit = handleSubmit(async (values) => {
    setServerError(null);
    try {
      await updateUser(user.id, values);
      onDone("Se guardaron los cambios.");
    } catch (error) {
      setServerError(describeError(error));
    }
  });

  return (
    <form onSubmit={onSubmit} noValidate className="flex flex-col gap-4">
      <Field id="edit-name" label="Nombre completo" error={errors.full_name?.message}>
        <input
          id="edit-name"
          aria-invalid={errors.full_name ? true : undefined}
          className={fieldClass}
          {...register("full_name")}
        />
      </Field>
      <Field id="edit-role" label="Rol" error={errors.role?.message}>
        <select id="edit-role" className={fieldClass} {...register("role")}>
          {roleSchema.options.map((role) => (
            <option key={role} value={role}>
              {ROLE_LABELS[role]}
            </option>
          ))}
        </select>
      </Field>
      <FormFooter
        submitLabel="Guardar cambios"
        busy={isSubmitting}
        serverError={serverError}
        onCancel={onCancel}
      />
    </form>
  );
}

const resetSchema = z.object({ password: passwordSchema });

export function ResetPasswordForm({ user, onDone, onCancel }: FormProps & { user: User }) {
  const [serverError, setServerError] = useState<string | null>(null);
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<z.infer<typeof resetSchema>>({ resolver: zodResolver(resetSchema) });

  const onSubmit = handleSubmit(async (values) => {
    setServerError(null);
    try {
      const result = await resetPassword(user.id, values.password);
      const closed =
        result.sessions_closed === 1
          ? "Se cerró 1 sesión abierta."
          : `Se cerraron ${result.sessions_closed} sesiones abiertas.`;
      onDone(`Contraseña de ${user.full_name} restablecida. ${closed}`);
    } catch (error) {
      setServerError(describeError(error));
    }
  });

  return (
    <form onSubmit={onSubmit} noValidate className="flex flex-col gap-4">
      <Field id="reset-password" label="Contraseña nueva" error={errors.password?.message}>
        <PasswordInput
          id="reset-password"
          invalid={Boolean(errors.password)}
          registration={register("password")}
        />
      </Field>
      <FormFooter
        submitLabel="Restablecer contraseña"
        busy={isSubmitting}
        serverError={serverError}
        onCancel={onCancel}
      />
    </form>
  );
}

export function ToggleActiveForm({ user, onDone, onCancel }: FormProps & { user: User }) {
  const [serverError, setServerError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const deactivating = user.is_active;

  async function onSubmit(event: React.FormEvent) {
    event.preventDefault();
    setServerError(null);
    setBusy(true);
    try {
      await setUserActive(user.id, !deactivating);
      onDone(
        deactivating
          ? `${user.full_name} quedó sin acceso. Su historial se conserva.`
          : `${user.full_name} puede volver a entrar.`,
      );
    } catch (error) {
      setServerError(describeError(error));
      setBusy(false);
    }
  }

  return (
    <form onSubmit={onSubmit} className="flex flex-col gap-4">
      <FormFooter
        submitLabel={deactivating ? "Dar de baja" : "Reactivar"}
        busy={busy}
        serverError={serverError}
        onCancel={onCancel}
        danger={deactivating}
      />
    </form>
  );
}
