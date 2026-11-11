"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { fieldClass, primaryButtonClass } from "@/components/ui/styles";
import { login } from "@/lib/api/auth";
import { describeError } from "@/lib/api/client";
import { SESSION_QUERY_KEY } from "./use-session";

const schema = z.object({
  email: z.string().trim().min(1, "Escribe tu correo.").email("El correo no tiene un formato válido."),
  password: z.string().min(1, "Escribe tu contraseña."),
});
type Values = z.infer<typeof schema>;

export function LoginForm() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const [serverError, setServerError] = useState<string | null>(null);
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<Values>({ resolver: zodResolver(schema) });

  const onSubmit = handleSubmit(async (values) => {
    setServerError(null);
    try {
      const session = await login(values.email, values.password);
      queryClient.setQueryData(SESSION_QUERY_KEY, session);
      router.replace("/");
    } catch (error) {
      setServerError(describeError(error));
    }
  });

  return (
    <form onSubmit={onSubmit} noValidate className="flex flex-col gap-5">
      <div className="flex flex-col gap-2">
        <label htmlFor="email" className="text-sm text-ink-muted">
          Correo
        </label>
        <input
          id="email"
          type="email"
          autoComplete="username"
          aria-invalid={errors.email ? true : undefined}
          aria-describedby={errors.email ? "email-error" : undefined}
          className={fieldClass}
          {...register("email")}
        />
        {errors.email && (
          <p id="email-error" className="text-sm text-accent-red-ink">
            {errors.email.message}
          </p>
        )}
      </div>

      <div className="flex flex-col gap-2">
        <label htmlFor="password" className="text-sm text-ink-muted">
          Contraseña
        </label>
        <input
          id="password"
          type="password"
          autoComplete="current-password"
          aria-invalid={errors.password ? true : undefined}
          aria-describedby={errors.password ? "password-error" : undefined}
          className={fieldClass}
          {...register("password")}
        />
        {errors.password && (
          <p id="password-error" className="text-sm text-accent-red-ink">
            {errors.password.message}
          </p>
        )}
      </div>

      {serverError && (
        <p role="alert" className="rounded-tile bg-accent-red-soft px-5 py-4 text-accent-red-ink">
          {serverError}
        </p>
      )}

      <button type="submit" disabled={isSubmitting} className={primaryButtonClass}>
        {isSubmitting ? "Entrando…" : "Entrar"}
      </button>

      <p className="text-sm text-ink-muted">
        ¿Olvidaste tu contraseña? Pide al administrador que te asigne una nueva.
      </p>
    </form>
  );
}
