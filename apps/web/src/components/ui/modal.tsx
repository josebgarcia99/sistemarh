"use client";

import { useEffect, useId, useRef, type ReactNode } from "react";

type ModalProps = {
  title: string;
  description?: string;
  onClose: () => void;
  children: ReactNode;
};

/** Diálogo modal accesible: foco inicial, Escape para cerrar y fondo que cierra. */
export function Modal({ title, description, onClose, children }: ModalProps) {
  const titleId = useId();
  const descriptionId = useId();
  const panelRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const previouslyFocused = document.activeElement as HTMLElement | null;
    const firstField = panelRef.current?.querySelector<HTMLElement>(
      "input, select, textarea, button",
    );
    (firstField ?? panelRef.current)?.focus();

    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") onClose();
    }
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("keydown", onKeyDown);
      previouslyFocused?.focus();
    };
  }, [onClose]);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-ink/40 p-4"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        aria-describedby={description ? descriptionId : undefined}
        tabIndex={-1}
        className="flex max-h-full w-full max-w-lg flex-col gap-5 overflow-y-auto rounded-card bg-surface p-7 outline-none sm:p-8"
      >
        <div>
          <h2 id={titleId} className="text-2xl font-medium tracking-tight">
            {title}
          </h2>
          {description && (
            <p id={descriptionId} className="mt-1 text-ink-muted">
              {description}
            </p>
          )}
        </div>
        {children}
      </div>
    </div>
  );
}
