import type { ApplicationStatus } from "@/lib/api/recruitment";

export type Feedback = { kind: "ok" | "error"; text: string } | null;

export const dateTimeFormat = new Intl.DateTimeFormat("es-MX", {
  timeZone: "America/Mexico_City",
  dateStyle: "medium",
  timeStyle: "short",
});
export const areaClass =
  "w-full rounded-3xl border border-ink/15 bg-surface px-5 py-3 text-ink outline-none " +
  "focus-visible:border-ink focus-visible:ring-2 focus-visible:ring-accent-blue";
export const pillClass = "inline-flex items-center rounded-full px-3 py-1 text-sm";
export const AI_STYLES: Record<string, string> = {
  ACEPTADO_IA: "bg-accent-blue-soft text-accent-blue-ink",
  RECHAZADO_IA: "bg-accent-red-soft text-accent-red-ink",
  NO_EVALUABLE: "bg-neutral-soft text-neutral-ink",
};
export const STATUS_STYLES: Record<ApplicationStatus, string> = {
  ACTIVA: "bg-ink text-white",
  DESISTIO: "bg-neutral-soft text-neutral-ink",
  DESCARTADA: "bg-accent-red-soft text-accent-red-ink",
  CANCELADA: "bg-neutral-soft text-neutral-ink",
  CONTRATADA: "bg-accent-blue-soft text-accent-blue-ink",
  NO_LOCALIZADA: "bg-neutral-soft text-neutral-ink",
  OTRO_CIERRE: "bg-neutral-soft text-neutral-ink",
};
export const dateFormat = new Intl.DateTimeFormat("es-MX", { timeZone: "UTC", dateStyle: "medium" });

/** Un día «AAAA-MM-DD» en texto, sin desplazarlo por la zona horaria. */
export function formatDay(day: string): string {
  return dateFormat.format(new Date(`${day}T00:00:00Z`));
}

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
