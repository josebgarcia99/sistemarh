"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { type FormEvent, useRef, useState } from "react";
import { Modal } from "@/components/ui/modal";
import {
  dangerButtonClass,
  fieldClass,
  primaryButtonClass,
  secondaryButtonClass,
} from "@/components/ui/styles";
import { describeError } from "@/lib/api/client";
import {
  ACCEPTED_EXTENSIONS,
  deleteFile,
  DOCUMENT_TYPE_LABELS,
  type DocumentType,
  documentTypeSchema,
  downloadUrl,
  formatBytes,
  listFiles,
  MAX_UPLOAD_BYTES,
  type StoredFile,
  UPLOADABLE_TYPES,
  uploadFile,
} from "@/lib/api/files";

type Props = { vacancyId: string; canUpload: boolean; canDelete: boolean };

const dateFormat = new Intl.DateTimeFormat("es-MX", {
  timeZone: "America/Mexico_City",
  dateStyle: "medium",
});

/** Documentos de una vacante: se guardan en el servidor y se descargan con permiso. */
export function VacancyDocuments({ vacancyId, canUpload, canDelete }: Props) {
  const queryClient = useQueryClient();
  const queryKey = ["vacancy", vacancyId, "files"];
  const { data: files, error } = useQuery({
    queryKey,
    queryFn: ({ signal }) => listFiles(vacancyId, signal),
  });
  const [notice, setNotice] = useState<string | null>(null);
  const [deleting, setDeleting] = useState<StoredFile | null>(null);

  async function reload(message: string) {
    setNotice(message);
    await queryClient.invalidateQueries({ queryKey });
  }

  return (
    <section aria-labelledby="documents-title" className="flex flex-col gap-3">
      <h3 id="documents-title" className="text-lg font-medium">
        Documentos
      </h3>

      {notice && (
        <p
          role="status"
          className="rounded-2xl bg-accent-blue-soft px-4 py-3 text-accent-blue-ink"
        >
          {notice}
        </p>
      )}

      {error ? (
        <p
          role="alert"
          className="rounded-2xl bg-accent-red-soft px-4 py-3 text-accent-red-ink"
        >
          {describeError(error)}
        </p>
      ) : !files ? (
        <p className="text-ink-muted">Cargando documentos…</p>
      ) : files.length === 0 ? (
        <p className="text-ink-muted">
          Todavía no hay documentos en esta vacante.
        </p>
      ) : (
        <ul
          aria-label="Documentos de la vacante"
          className="flex flex-col gap-1.5"
        >
          {files.map((file) => (
            <li
              key={file.id}
              className="flex flex-wrap items-center justify-between gap-3 rounded-2xl bg-surface px-4 py-3"
            >
              <div className="min-w-0">
                <a
                  href={downloadUrl(file.id)}
                  download={file.original_name}
                  aria-label={`Descargar ${file.original_name}`}
                  className="font-medium break-words underline underline-offset-4"
                >
                  {file.original_name}
                </a>
                <p className="text-sm text-ink-muted">
                  {DOCUMENT_TYPE_LABELS[file.document_type]} ·{" "}
                  {formatBytes(file.size_bytes)} ·{" "}
                  {file.uploaded_by_name ?? "Sin datos"} ·{" "}
                  {dateFormat.format(new Date(file.created_at))}
                  {file.sensitive && " · Sensible"}
                </p>
              </div>
              {canDelete && (
                <button
                  type="button"
                  className={dangerButtonClass}
                  aria-label={`Eliminar ${file.original_name}`}
                  onClick={() => setDeleting(file)}
                >
                  Eliminar
                </button>
              )}
            </li>
          ))}
        </ul>
      )}

      {canUpload && !error && (
        <UploadForm vacancyId={vacancyId} onUploaded={reload} />
      )}

      {deleting && (
        <Modal title="Eliminar documento" onClose={() => setDeleting(null)}>
          <DeleteForm
            file={deleting}
            onCancel={() => setDeleting(null)}
            onDone={() => {
              const name = deleting.original_name;
              setDeleting(null);
              void reload(
                `Se eliminó «${name}». La eliminación quedó registrada.`,
              );
            }}
          />
        </Modal>
      )}
    </section>
  );
}

function UploadForm({
  vacancyId,
  onUploaded,
}: {
  vacancyId: string;
  onUploaded: (message: string) => Promise<void>;
}) {
  const input = useRef<HTMLInputElement>(null);
  const [documentType, setDocumentType] = useState<DocumentType>("CV");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    const file = input.current?.files?.[0];
    if (!file) return setError("Elige un archivo.");
    const extension = file.name.slice(file.name.lastIndexOf(".")).toLowerCase();
    if (!ACCEPTED_EXTENSIONS.includes(extension)) {
      return setError(
        "Formato no permitido. Se aceptan PDF, DOCX, DOC, JPG y PNG.",
      );
    }
    if (file.size > MAX_UPLOAD_BYTES)
      return setError("El archivo supera el límite de 20 MB.");
    setBusy(true);
    setError(null);
    try {
      const result = await uploadFile(vacancyId, file, documentType);
      if (input.current) input.current.value = "";
      const duplicate = result.duplicates[0];
      await onUploaded(
        duplicate
          ? `Se guardó «${result.file.original_name}». Ya estaba cargado en esta vacante como «${duplicate.original_name}».`
          : `Se guardó «${result.file.original_name}».`,
      );
    } catch (caught) {
      setError(describeError(caught));
    } finally {
      setBusy(false);
    }
  }

  return (
    <form
      className="flex flex-col gap-3 border-t border-line pt-4"
      onSubmit={submit}
      noValidate
    >
      <div className="flex flex-wrap gap-3">
        <div className="flex flex-[1_1_160px] flex-col gap-2">
          <label htmlFor="document-type" className="text-sm text-ink-muted">
            Tipo de documento
          </label>
          <select
            id="document-type"
            value={documentType}
            onChange={(event) =>
              setDocumentType(documentTypeSchema.parse(event.target.value))
            }
            className={fieldClass}
          >
            {UPLOADABLE_TYPES.map((type) => (
              <option key={type} value={type}>
                {DOCUMENT_TYPE_LABELS[type]}
              </option>
            ))}
          </select>
        </div>
        <div className="flex flex-[2_1_220px] flex-col gap-2">
          <label htmlFor="document-file" className="text-sm text-ink-muted">
            Archivo (PDF, DOCX, DOC, JPG o PNG; máximo 20 MB)
          </label>
          <input
            id="document-file"
            ref={input}
            type="file"
            accept={ACCEPTED_EXTENSIONS.join(",")}
            className="min-h-12 w-full rounded-full border border-ink/15 bg-surface px-5 py-2.5 file:mr-3 file:rounded-full file:border-0 file:bg-ink file:px-4 file:py-1 file:text-white"
          />
        </div>
      </div>
      {error && (
        <p role="alert" className="text-accent-red-ink">
          {error}
        </p>
      )}
      <button
        type="submit"
        className={`${secondaryButtonClass} self-start`}
        disabled={busy}
      >
        {busy ? "Guardando…" : "Cargar documento"}
      </button>
    </form>
  );
}

function DeleteForm({
  file,
  onCancel,
  onDone,
}: {
  file: StoredFile;
  onCancel: () => void;
  onDone: () => void;
}) {
  const [reason, setReason] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (reason.trim().length < 10)
      return setError("Escribe el motivo (mínimo 10 letras).");
    setBusy(true);
    setError(null);
    try {
      await deleteFile(file.id, reason);
      onDone();
    } catch (caught) {
      setError(describeError(caught));
      setBusy(false);
    }
  }

  return (
    <form className="flex flex-col gap-4" onSubmit={submit} noValidate>
      <p>
        Vas a eliminar <strong>{file.original_name}</strong>. El archivo se
        borra del servidor y no se puede recuperar desde la aplicación. Queda
        registrado quién lo eliminó y por qué.
      </p>
      <div className="flex flex-col gap-2">
        <label htmlFor="delete-reason" className="text-sm text-ink-muted">
          Motivo de la eliminación
        </label>
        <input
          id="delete-reason"
          value={reason}
          maxLength={500}
          onChange={(event) => setReason(event.target.value)}
          className={fieldClass}
        />
      </div>
      {error && (
        <p role="alert" className="text-accent-red-ink">
          {error}
        </p>
      )}
      <div className="flex flex-wrap justify-end gap-3">
        <button
          type="button"
          className={secondaryButtonClass}
          onClick={onCancel}
        >
          Cancelar
        </button>
        <button type="submit" className={primaryButtonClass} disabled={busy}>
          {busy ? "Eliminando…" : "Eliminar documento"}
        </button>
      </div>
    </form>
  );
}
