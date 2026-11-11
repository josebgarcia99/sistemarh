import type { Metadata } from "next";
import { LoginForm } from "@/features/auth/login-form";

export const metadata: Metadata = { title: "Iniciar sesión · Reclutamiento IA" };

export default function LoginPage() {
  return (
    <main className="flex flex-1 items-center justify-center px-6 py-10">
      <div className="flex w-full max-w-md flex-col gap-8 rounded-card bg-surface p-8 sm:p-10">
        <div className="flex items-center gap-3">
          <span
            aria-hidden="true"
            className="flex size-10 items-center justify-center rounded-2xl bg-ink text-sm font-semibold text-white"
          >
            R
          </span>
          <span className="text-xl font-medium tracking-tight">Reclutamiento IA</span>
        </div>
        <div>
          <h1 className="text-4xl font-medium tracking-tight">Iniciar sesión</h1>
          <p className="mt-2 text-ink-muted">Usa el correo y la contraseña que te dio el administrador.</p>
        </div>
        <LoginForm />
      </div>
    </main>
  );
}
