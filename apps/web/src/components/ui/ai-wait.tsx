"use client";

import { useCallback, useEffect, useState } from "react";

/**
 * Lleva la cuenta de cuánto lleva esperando una respuesta de la IA.
 *
 * Una respuesta larga (una rúbrica completa, una síntesis) puede tardar más de
 * un minuto. Mientras tanto la pantalla muestra el tiempo transcurrido, para
 * que se vea que sigue trabajando y no se cierre ni se recargue.
 */
export function useAiWait() {
  const [since, setSince] = useState<number | null>(null);
  const [seconds, setSeconds] = useState(0);

  useEffect(() => {
    if (since === null) return;
    const timer = window.setInterval(
      () => setSeconds(Math.floor((Date.now() - since) / 1000)),
      1000,
    );
    return () => window.clearInterval(timer);
  }, [since]);

  /** Ejecuta una llamada a la IA y cuenta el tiempo mientras dura. */
  const run = useCallback(async <T,>(action: () => Promise<T>): Promise<T> => {
    setSeconds(0);
    setSince(Date.now());
    try {
      return await action();
    } finally {
      setSince(null);
    }
  }, []);

  return { waiting: since !== null, seconds, run };
}

export type AiWait = Pick<ReturnType<typeof useAiWait>, "waiting" | "seconds">;

/** Aviso mientras la IA responde, con el tiempo que lleva. */
export function AiWaitNotice({ wait }: { wait: AiWait }) {
  if (!wait.waiting) return null;
  const minutes = Math.floor(wait.seconds / 60);
  const seconds = String(wait.seconds % 60).padStart(2, "0");
  return (
    // Sin role="status": el resultado de la operación ya se anuncia con ese papel.
    <p aria-live="polite" className="text-sm text-ink-muted">
      La IA está trabajando ({minutes}:{seconds}). Una respuesta larga puede tardar más de un
      minuto; no cierres ni recargues la pantalla.
    </p>
  );
}
