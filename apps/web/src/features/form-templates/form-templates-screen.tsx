"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import {
  cardClass,
  dangerButtonClass,
  fieldClass,
  primaryButtonClass,
  secondaryButtonClass,
} from "@/components/ui/styles";
import { type Feedback, FeedbackLine, pillClass } from "@/features/recruitment/shared";
import {
  FIELD_TYPE_LABELS,
  type FieldInput,
  type FormTemplate,
  listTemplates,
  saveTemplate,
  templateAction,
} from "@/lib/api/assessments";
import { describeError } from "@/lib/api/client";

type SectionDraft = { title: string; fields: FieldInput[] };
const emptyField = (): FieldInput => ({
  id: null,
  label: "",
  type: "TEXTO",
  required: false,
  options: [],
  minimum: null,
  maximum: null,
});

/** Formularios del estudio socioeconómico (solo administradores). */
export function FormTemplatesScreen() {
  const queryClient = useQueryClient();
  const { data: templates, error } = useQuery({
    queryKey: ["form-templates"],
    queryFn: ({ signal }) => listTemplates(signal),
  });
  const [openId, setOpenId] = useState<string | null>(null);
  const [notice, setNotice] = useState<Feedback>(null);
  const selected = templates?.find((template) => template.id === openId);

  return (
    <>
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-4xl font-medium tracking-tight sm:text-5xl">Formularios</h1>
          <p className="mt-2 max-w-3xl text-ink-muted">
            Plantillas del estudio socioeconómico: secciones y campos para captura y verificación
            documental. No tienen puntuación. Al cambiar sus campos se crea una versión nueva; los
            estudios ya capturados conservan la suya.
          </p>
        </div>
        {openId === null ? (
          <button type="button" className={primaryButtonClass} onClick={() => setOpenId("new")}>
            Nuevo formulario
          </button>
        ) : (
          <button type="button" className={secondaryButtonClass} onClick={() => setOpenId(null)}>
            Volver a la lista
          </button>
        )}
      </div>
      <FeedbackLine feedback={notice} />
      {error && (
        <p role="alert" className="rounded-tile bg-accent-red-soft px-5 py-4 text-accent-red-ink">
          {describeError(error)}
        </p>
      )}
      {openId === null && templates && (
        <section className={`${cardClass} flex flex-col gap-2`}>
          <ul aria-label="Formularios" className="flex flex-col gap-2">
            {templates.map((template) => (
              <li key={template.id} className="flex flex-wrap items-center gap-x-4 gap-y-2 rounded-tile bg-surface px-5 py-3">
                <button
                  type="button"
                  className="min-w-0 flex-[1_1_220px] break-words text-left font-medium underline-offset-4 hover:underline"
                  onClick={() => {
                    setNotice(null);
                    setOpenId(template.id);
                  }}
                >
                  {template.name}
                </button>
                <span className="text-ink-muted">
                  versión {template.version_number} ·{" "}
                  {template.sections.reduce((total, section) => total + section.fields.length, 0)} campos
                </span>
                {template.status === "ARCHIVADA" && (
                  <span className={`${pillClass} bg-accent-red-soft text-accent-red-ink`}>Archivado</span>
                )}
              </li>
            ))}
          </ul>
        </section>
      )}
      {openId !== null && (openId === "new" || selected) && (
        <TemplateEditor
          key={openId === "new" ? "new" : `${selected?.id}-${selected?.version_number}-${selected?.status}`}
          template={selected}
          onSaved={async (saved, message) => {
            await queryClient.invalidateQueries({ queryKey: ["form-templates"] });
            setOpenId(saved.id);
            setNotice({ kind: "ok", text: message });
          }}
        />
      )}
    </>
  );
}

function TemplateEditor({
  template,
  onSaved,
}: {
  template: FormTemplate | undefined;
  onSaved: (template: FormTemplate, message: string) => Promise<void>;
}) {
  const [name, setName] = useState(template?.name ?? "");
  const [description, setDescription] = useState(template?.description ?? "");
  const [sections, setSections] = useState<SectionDraft[]>(() =>
    template
      ? template.sections.map((section) => ({
          title: section.title,
          fields: section.fields.map((field) => ({ ...field })),
        }))
      : [{ title: "", fields: [emptyField()] }],
  );
  const [feedback, setFeedback] = useState<Feedback>(null);
  const [busy, setBusy] = useState(false);

  const setSection = (index: number, patch: Partial<SectionDraft>) =>
    setSections(sections.map((section, i) => (i === index ? { ...section, ...patch } : section)));
  const setField = (sectionIndex: number, fieldIndex: number, patch: Partial<FieldInput>) =>
    setSection(sectionIndex, {
      fields: sections[sectionIndex].fields.map((field, i) => (i === fieldIndex ? { ...field, ...patch } : field)),
    });

  async function run(action: () => Promise<FormTemplate>, message: string) {
    setBusy(true);
    setFeedback(null);
    try {
      await onSaved(await action(), message);
    } catch (caught) {
      setFeedback({ kind: "error", text: describeError(caught) });
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className={`${cardClass} flex flex-col gap-5`}>
      <h2 className="text-xl font-medium">
        {template ? `${template.name} · versión ${template.version_number}` : "Nuevo formulario"}
      </h2>
      <div className="grid gap-4 md:grid-cols-2">
        <div className="flex flex-col gap-2">
          <label htmlFor="template-name" className="text-sm text-ink-muted">
            Nombre
          </label>
          <input id="template-name" className={fieldClass} value={name} onChange={(event) => setName(event.target.value)} />
        </div>
        <div className="flex flex-col gap-2">
          <label htmlFor="template-description" className="text-sm text-ink-muted">
            Descripción (opcional)
          </label>
          <input id="template-description" className={fieldClass} value={description} onChange={(event) => setDescription(event.target.value)} />
        </div>
      </div>
      {sections.map((section, sectionIndex) => (
        <fieldset key={sectionIndex} className="flex flex-col gap-3 rounded-3xl bg-surface p-4">
          <legend className="sr-only">Sección {sectionIndex + 1}</legend>
          <div className="flex flex-wrap items-end gap-3">
            <div className="flex flex-[1_1_260px] flex-col gap-2">
              <label htmlFor={`section-${sectionIndex}`} className="text-sm text-ink-muted">
                Sección {sectionIndex + 1}
              </label>
              <input id={`section-${sectionIndex}`} className={fieldClass} value={section.title} onChange={(event) => setSection(sectionIndex, { title: event.target.value })} />
            </div>
            <button type="button" className={dangerButtonClass} aria-label={`Quitar la sección ${sectionIndex + 1}`} onClick={() => setSections(sections.filter((_, i) => i !== sectionIndex))}>
              Quitar sección
            </button>
          </div>
          <ul aria-label={`Campos de la sección ${sectionIndex + 1}`} className="flex flex-col gap-2">
            {section.fields.map((field, fieldIndex) => {
              const label = `del campo ${fieldIndex + 1} de la sección ${sectionIndex + 1}`;
              return (
                <li key={field.id ?? `nuevo-${fieldIndex}`} className="flex flex-wrap items-center gap-2 rounded-2xl bg-white/70 p-3">
                  <input aria-label={`Nombre ${label}`} placeholder="Nombre del campo" className={`${fieldClass} flex-[3_1_220px]`} value={field.label} onChange={(event) => setField(sectionIndex, fieldIndex, { label: event.target.value })} />
                  <select aria-label={`Tipo ${label}`} className={`${fieldClass} flex-[1_1_160px]`} value={field.type} onChange={(event) => setField(sectionIndex, fieldIndex, { type: event.target.value })}>
                    {Object.entries(FIELD_TYPE_LABELS).map(([value, text]) => (
                      <option key={value} value={value}>
                        {text}
                      </option>
                    ))}
                  </select>
                  {field.type === "OPCIONES" && (
                    <input aria-label={`Opciones ${label}`} placeholder="Opciones separadas por coma" className={`${fieldClass} flex-[2_1_220px]`} value={field.options.join(",")} onChange={(event) => setField(sectionIndex, fieldIndex, { options: event.target.value.split(",") })} />
                  )}
                  {field.type === "NUMERO" && (
                    <>
                      <input aria-label={`Mínimo ${label}`} placeholder="Mínimo" inputMode="decimal" className={`${fieldClass} flex-[1_1_100px]`} value={field.minimum ?? ""} onChange={(event) => setField(sectionIndex, fieldIndex, { minimum: event.target.value || null })} />
                      <input aria-label={`Máximo ${label}`} placeholder="Máximo" inputMode="decimal" className={`${fieldClass} flex-[1_1_100px]`} value={field.maximum ?? ""} onChange={(event) => setField(sectionIndex, fieldIndex, { maximum: event.target.value || null })} />
                    </>
                  )}
                  <label className="flex items-center gap-2">
                    <input type="checkbox" className="size-5 accent-ink" checked={field.required} onChange={(event) => setField(sectionIndex, fieldIndex, { required: event.target.checked })} />
                    Obligatorio
                  </label>
                  <button type="button" className={dangerButtonClass} aria-label={`Quitar el campo ${fieldIndex + 1} de la sección ${sectionIndex + 1}`} onClick={() => setSection(sectionIndex, { fields: section.fields.filter((_, i) => i !== fieldIndex) })}>
                    Quitar
                  </button>
                </li>
              );
            })}
          </ul>
          <button type="button" className={`${secondaryButtonClass} self-start`} onClick={() => setSection(sectionIndex, { fields: [...section.fields, emptyField()] })}>
            Agregar campo
          </button>
        </fieldset>
      ))}
      <FeedbackLine feedback={feedback} />
      <div className="flex flex-wrap gap-3">
        <button type="button" className={secondaryButtonClass} onClick={() => setSections([...sections, { title: "", fields: [emptyField()] }])}>
          Agregar sección
        </button>
        <button
          type="button"
          className={primaryButtonClass}
          disabled={busy}
          onClick={() =>
            run(
              () =>
                saveTemplate(template?.id ?? null, {
                  name,
                  description: description.trim() || null,
                  sections: sections.map((section) => ({
                    ...section,
                    fields: section.fields.map((field) => ({
                      ...field,
                      // Las opciones se escriben separadas por coma; aquí se limpian.
                      options: field.options.map((option) => option.trim()).filter(Boolean),
                    })),
                  })),
                  expected_version: template?.version_number ?? 0,
                }),
              "Formulario guardado.",
            )
          }
        >
          {busy ? "Guardando…" : template ? "Guardar cambios" : "Crear formulario"}
        </button>
        {template && (
          <button
            type="button"
            className={template.status === "ACTIVA" ? dangerButtonClass : secondaryButtonClass}
            disabled={busy}
            onClick={() =>
              run(
                () => templateAction(template.id, template.status === "ACTIVA" ? "archive" : "restore"),
                template.status === "ACTIVA" ? "Formulario archivado." : "Formulario restaurado.",
              )
            }
          >
            {template.status === "ACTIVA" ? "Archivar" : "Restaurar"}
          </button>
        )}
      </div>
    </section>
  );
}
