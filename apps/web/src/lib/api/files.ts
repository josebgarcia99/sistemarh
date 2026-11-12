import { z } from "zod";
import { apiFetch } from "./client";

export const documentTypeSchema = z.enum([
  "CV",
  "PERFIL_PUESTO",
  "PSICOMETRIA",
  "PRUEBA_TECNICA",
  "ESTUDIO_SOCIOECONOMICO",
  "ADJUNTO",
]);
export type DocumentType = z.infer<typeof documentTypeSchema>;

export const DOCUMENT_TYPE_LABELS: Record<DocumentType, string> = {
  CV: "Currículum",
  PERFIL_PUESTO: "Perfil de puesto",
  PSICOMETRIA: "Psicometría",
  PRUEBA_TECNICA: "Prueba técnica",
  ESTUDIO_SOCIOECONOMICO: "Estudio socioeconómico",
  ADJUNTO: "Adjunto",
};

/** Tipos que exigen un permiso adicional y se guardan cifrados. */
export const SENSITIVE_TYPES: DocumentType[] = ["PSICOMETRIA", "ESTUDIO_SOCIOECONOMICO"];

export const ACCEPTED_EXTENSIONS = [
  ".pdf",
  ".docx",
  ".doc",
  ".jpg",
  ".jpeg",
  ".png",
];
/** Tipos que además admiten Excel: los que tienen un formato de la empresa. */
export const SPREADSHEET_TYPES: DocumentType[] = ["PERFIL_PUESTO", "ESTUDIO_SOCIOECONOMICO"];

export function acceptedExtensions(documentType: DocumentType): string[] {
  return SPREADSHEET_TYPES.includes(documentType)
    ? [...ACCEPTED_EXTENSIONS, ".xlsx"]
    : ACCEPTED_EXTENSIONS;
}
export const MAX_UPLOAD_BYTES = 20 * 1024 * 1024;

const storedFileSchema = z.object({
  id: z.string(),
  vacancy_id: z.string(),
  document_type: documentTypeSchema,
  sensitive: z.boolean(),
  original_name: z.string(),
  content_type: z.string().nullable(),
  size_bytes: z.number().nullable(),
  sha256: z.string().nullable(),
  malware_scan: z.string().nullable(),
  encrypted: z.boolean(),
  uploaded_by: z.string(),
  uploaded_by_name: z.string().nullable(),
  created_at: z.string(),
});
export type StoredFile = z.infer<typeof storedFileSchema>;

const uploadResultSchema = z.object({
  file: storedFileSchema,
  duplicates: z.array(storedFileSchema),
});
export type UploadResult = z.infer<typeof uploadResultSchema>;

export function listFiles(
  vacancyId: string,
  signal?: AbortSignal,
): Promise<StoredFile[]> {
  return apiFetch(`/vacancies/${vacancyId}/files`, {
    schema: z.array(storedFileSchema),
    signal,
  });
}

export function uploadFile(
  vacancyId: string,
  file: File,
  documentType: DocumentType,
): Promise<UploadResult> {
  return apiFetch(`/vacancies/${vacancyId}/files`, {
    method: "POST",
    file,
    query: { document_type: documentType, filename: file.name },
    schema: uploadResultSchema,
  });
}

export function deleteFile(fileId: string, reason: string): Promise<void> {
  return apiFetch(`/files/${fileId}/deletion`, {
    method: "POST",
    body: { reason },
  });
}

/** La descarga pasa siempre por la API, que comprueba el permiso en ese momento. */
export function downloadUrl(fileId: string): string {
  return `/api/v1/files/${fileId}/download`;
}

export function formatBytes(bytes: number | null): string {
  if (bytes === null) return "";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}
