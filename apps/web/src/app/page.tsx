import { SystemStatus } from "@/features/system/system-status";

export default function HomePage() {
  return (
    <div className="mx-auto flex w-full max-w-5xl flex-1 flex-col gap-6 px-6 py-8 sm:px-8">
      <header className="flex items-center gap-3">
        <span
          aria-hidden="true"
          className="flex size-10 items-center justify-center rounded-2xl bg-ink text-sm font-semibold text-white"
        >
          R
        </span>
        <span className="text-xl font-medium tracking-tight">Reclutamiento IA</span>
      </header>

      <main className="flex flex-col gap-6">
        <div>
          <h1 className="text-4xl font-medium tracking-tight sm:text-5xl">Fundamentos listos</h1>
          <p className="mt-2 max-w-2xl text-ink-muted">
            Fase 1 del proyecto. Esta pantalla confirma que la interfaz, la API y sus servicios se
            comunican. El inicio de sesión y las vacantes llegan en la Fase 2.
          </p>
        </div>
        <SystemStatus />
      </main>
    </div>
  );
}
