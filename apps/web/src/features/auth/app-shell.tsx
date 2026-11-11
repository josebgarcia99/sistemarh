"use client";

import { useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, type ReactNode } from "react";
import { secondaryButtonClass } from "@/components/ui/styles";
import { logout, ROLE_LABELS, type User } from "@/lib/api/auth";
import { describeError } from "@/lib/api/client";
import { useSession } from "./use-session";

const NAV_ITEMS: { href: string; label: string; adminOnly: boolean }[] = [
  { href: "/", label: "Inicio", adminOnly: false },
  { href: "/vacantes", label: "Vacantes", adminOnly: false },
  { href: "/usuarios", label: "Usuarios", adminOnly: true },
  { href: "/transferencias", label: "Bajas", adminOnly: true },
  { href: "/configuracion-ia", label: "IA", adminOnly: true },
  { href: "/auditoria", label: "Auditoría", adminOnly: true },
];

function initials(name: string): string {
  return name
    .split(" ")
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() ?? "")
    .join("");
}

/** Marco de la aplicación. Solo muestra su contenido con una sesión válida. */
export function AppShell({ children }: { children: ReactNode }) {
  const { user, isPending, unauthenticated, error } = useSession();

  useEffect(() => {
    // Navegación completa: descarta de la memoria cualquier dato de la sesión anterior.
    if (unauthenticated) window.location.replace("/login");
  }, [unauthenticated]);

  if (isPending || unauthenticated) {
    return (
      <p role="status" className="m-auto text-ink-muted">
        Comprobando tu sesión…
      </p>
    );
  }
  if (!user) {
    return (
      <div role="alert" className="m-auto max-w-md rounded-card bg-accent-red-soft p-7 text-accent-red-ink">
        <p className="font-medium">No se pudo comprobar tu sesión.</p>
        <p className="mt-1 text-sm">{describeError(error)}</p>
      </div>
    );
  }

  return (
    <div className="mx-auto flex w-full max-w-6xl flex-1 flex-col gap-6 px-6 py-7 sm:px-8">
      <Header user={user} />
      <main className="flex flex-1 flex-col gap-6">{children}</main>
    </div>
  );
}

function Header({ user }: { user: User }) {
  const pathname = usePathname();
  const queryClient = useQueryClient();

  async function handleLogout() {
    try {
      await logout();
    } finally {
      queryClient.clear();
      // Navegación completa, no del enrutador: el enrutador conserva en memoria
      // las pantallas visitadas y no deben sobrevivir al cierre de sesión.
      // eslint-disable-next-line @next/next/no-location-assign-relative-destination
      window.location.assign("/login");
    }
  }

  return (
    <header className="flex flex-wrap items-center justify-between gap-x-6 gap-y-4">
      <Link href="/" className="flex items-center gap-3 text-xl font-medium tracking-tight">
        <span
          aria-hidden="true"
          className="flex size-10 items-center justify-center rounded-2xl bg-ink text-sm font-semibold text-white"
        >
          R
        </span>
        Reclutamiento IA
      </Link>

      <nav aria-label="Principal" className="flex flex-wrap gap-1">
        {NAV_ITEMS.filter((item) => !item.adminOnly || user.role === "ADMINISTRADOR").map((item) => {
          const active = pathname === item.href;
          return (
            <Link
              key={item.href}
              href={item.href}
              aria-current={active ? "page" : undefined}
              className={`flex min-h-11 items-center rounded-full px-5 ${
                active ? "bg-ink text-white" : "text-ink hover:bg-white/60"
              }`}
            >
              {item.label}
            </Link>
          );
        })}
      </nav>

      <div className="flex flex-wrap items-center gap-3">
        <div className="flex items-center gap-3 rounded-full bg-surface py-1.5 pl-1.5 pr-5">
          <span
            aria-hidden="true"
            className="flex size-9 items-center justify-center rounded-full bg-ink text-xs font-semibold text-white"
          >
            {initials(user.full_name)}
          </span>
          <span className="flex flex-col leading-tight">
            <span className="text-sm font-medium">{user.full_name}</span>
            <span className="text-xs text-ink-muted">{ROLE_LABELS[user.role]}</span>
          </span>
        </div>
        <button type="button" onClick={handleLogout} className={secondaryButtonClass}>
          Cerrar sesión
        </button>
      </div>
    </header>
  );
}
