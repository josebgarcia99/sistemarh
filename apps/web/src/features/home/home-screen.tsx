"use client";

import { useSession } from "@/features/auth/use-session";
import { SystemStatus } from "@/features/system/system-status";

export function HomeScreen() {
  const { user } = useSession();
  const firstName = user?.full_name.split(" ")[0] ?? "";

  return (
    <>
      <div>
        <h1 className="text-4xl font-medium tracking-tight sm:text-5xl">Hola, {firstName}</h1>
        <p className="mt-2 max-w-2xl text-ink-muted">
          Ya funcionan el inicio de sesión y la administración de usuarios. Las vacantes llegan en
          la siguiente entrega.
        </p>
      </div>
      {user?.role === "ADMINISTRADOR" && <SystemStatus />}
    </>
  );
}
