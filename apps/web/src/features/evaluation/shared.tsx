/** Piezas que comparten el perfil de puesto y el prompt de evaluación. */

export type Feedback = { kind: "ok" | "error"; text: string } | null;

export const dateFormat = new Intl.DateTimeFormat("es-MX", {
  timeZone: "America/Mexico_City",
  dateStyle: "medium",
  timeStyle: "short",
});

export const areaClass =
  "w-full rounded-3xl border border-ink/15 bg-surface px-5 py-3 text-ink outline-none " +
  "focus-visible:border-ink focus-visible:ring-2 focus-visible:ring-accent-blue";

export function FeedbackLine({ feedback }: { feedback: Feedback }) {
  if (!feedback) return null;
  const ok = feedback.kind === "ok";
  return (
    <p
      role={ok ? "status" : "alert"}
      className={`rounded-2xl px-4 py-3 ${
        ok ? "bg-accent-blue-soft text-accent-blue-ink" : "bg-accent-red-soft text-accent-red-ink"
      }`}
    >
      {feedback.text}
    </p>
  );
}
