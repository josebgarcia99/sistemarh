"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { fieldClass, primaryButtonClass, secondaryButtonClass } from "@/components/ui/styles";
import { describeError } from "@/lib/api/client";
import {
  createVacancy,
  updateVacancy,
  type Vacancy,
  WORK_MODE_LABELS,
  workModeSchema,
} from "@/lib/api/vacancies";

const schema = z.object({
  name: z.string().trim().min(1, "Escribe el nombre de la vacante.").max(200),
  department: z.string().trim().min(1, "Escribe el departamento.").max(120),
  location: z.string().trim().min(1, "Escribe la ubicación.").max(120),
  work_mode: workModeSchema,
  contract_type: z.string().trim().min(1, "Escribe el tipo de contratación.").max(80),
  positions: z
    .number({ error: "Indica cuántas posiciones." })
    .int("Debe ser un número entero.")
    .min(1, "Debe haber al menos 1 posición.")
    .max(9999),
  description: z.string().max(20000),
  notes: z.string().max(20000),
});
type Values = z.infer<typeof schema>;

type Props = {
  /** Vacante a editar; sin ella el formulario crea una nueva. */
  vacancy?: Vacancy;
  onDone: (vacancy: Vacancy, message: string) => void;
  onCancel: () => void;
};

export function VacancyForm({ vacancy, onDone, onCancel }: Props) {
  const [serverError, setServerError] = useState<string | null>(null);
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<Values>({
    resolver: zodResolver(schema),
    defaultValues: vacancy
      ? {
          name: vacancy.name,
          department: vacancy.department,
          location: vacancy.location,
          work_mode: vacancy.work_mode,
          contract_type: vacancy.contract_type,
          positions: vacancy.positions,
          description: vacancy.description,
          notes: vacancy.notes ?? "",
        }
      : { work_mode: "PRESENCIAL", positions: 1, description: "", notes: "" },
  });

  const onSubmit = handleSubmit(async (values) => {
    setServerError(null);
    const input = { ...values, notes: values.notes.trim() || null };
    try {
      if (vacancy) {
        const saved = await updateVacancy(vacancy.id, input, vacancy.version);
        onDone(saved, "Se guardaron los cambios de la vacante.");
      } else {
        const created = await createVacancy(input);
        onDone(created, `Se creó la vacante «${created.name}» en borrador. Solo tú la ves.`);
      }
    } catch (error) {
      setServerError(describeError(error));
    }
  });

  const text = (id: keyof Values, label: string) => (
    <div className="flex flex-col gap-2">
      <label htmlFor={`vacancy-${id}`} className="text-sm text-ink-muted">
        {label}
      </label>
      <input
        id={`vacancy-${id}`}
        autoComplete="off"
        aria-invalid={errors[id] ? true : undefined}
        className={fieldClass}
        {...register(id)}
      />
      {errors[id] && <p className="text-sm text-accent-red-ink">{errors[id]?.message}</p>}
    </div>
  );

  return (
    <form onSubmit={onSubmit} noValidate className="flex flex-col gap-4">
      {text("name", "Nombre de la vacante")}
      <div className="grid gap-4 sm:grid-cols-2">
        {text("department", "Departamento")}
        {text("location", "Ubicación")}
        <div className="flex flex-col gap-2">
          <label htmlFor="vacancy-work_mode" className="text-sm text-ink-muted">
            Modalidad
          </label>
          <select id="vacancy-work_mode" className={fieldClass} {...register("work_mode")}>
            {workModeSchema.options.map((mode) => (
              <option key={mode} value={mode}>
                {WORK_MODE_LABELS[mode]}
              </option>
            ))}
          </select>
        </div>
        {text("contract_type", "Tipo de contratación")}
        <div className="flex flex-col gap-2">
          <label htmlFor="vacancy-positions" className="text-sm text-ink-muted">
            Número de posiciones
          </label>
          <input
            id="vacancy-positions"
            type="number"
            min={1}
            aria-invalid={errors.positions ? true : undefined}
            className={fieldClass}
            {...register("positions", { valueAsNumber: true })}
          />
          {errors.positions && (
            <p className="text-sm text-accent-red-ink">{errors.positions.message}</p>
          )}
        </div>
      </div>
      <div className="flex flex-col gap-2">
        <label htmlFor="vacancy-description" className="text-sm text-ink-muted">
          Descripción
        </label>
        <textarea
          id="vacancy-description"
          rows={3}
          className="w-full rounded-3xl border border-ink/15 bg-surface px-5 py-3 outline-none focus-visible:border-ink focus-visible:ring-2 focus-visible:ring-accent-blue"
          {...register("description")}
        />
      </div>
      <div className="flex flex-col gap-2">
        <label htmlFor="vacancy-notes" className="text-sm text-ink-muted">
          Observaciones (opcional)
        </label>
        <textarea
          id="vacancy-notes"
          rows={2}
          className="w-full rounded-3xl border border-ink/15 bg-surface px-5 py-3 outline-none focus-visible:border-ink focus-visible:ring-2 focus-visible:ring-accent-blue"
          {...register("notes")}
        />
      </div>

      {serverError && (
        <p role="alert" className="rounded-tile bg-accent-red-soft px-5 py-4 text-accent-red-ink">
          {serverError}
        </p>
      )}
      <div className="flex flex-wrap justify-end gap-3">
        <button type="button" onClick={onCancel} className={secondaryButtonClass}>
          Cancelar
        </button>
        <button type="submit" disabled={isSubmitting} className={primaryButtonClass}>
          {isSubmitting ? "Guardando…" : vacancy ? "Guardar cambios" : "Crear vacante"}
        </button>
      </div>
    </form>
  );
}
