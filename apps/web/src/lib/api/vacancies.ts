import { z } from "zod";
import { apiFetch } from "./client";

export const vacancyStatusSchema = z.enum([
  "BORRADOR",
  "ABIERTA",
  "PAUSADA",
  "CERRADA",
  "CANCELADA",
  "ARCHIVADA",
]);
export type VacancyStatus = z.infer<typeof vacancyStatusSchema>;

export const STATUS_LABELS: Record<VacancyStatus, string> = {
  BORRADOR: "Borrador",
  ABIERTA: "Abierta",
  PAUSADA: "Pausada",
  CERRADA: "Cerrada",
  CANCELADA: "Cancelada",
  ARCHIVADA: "Archivada",
};

/** Mismas transiciones que valida la API. */
export const STATUS_TRANSITIONS: Record<VacancyStatus, VacancyStatus[]> = {
  BORRADOR: ["ABIERTA", "CANCELADA"],
  ABIERTA: ["PAUSADA", "CERRADA", "CANCELADA"],
  PAUSADA: ["ABIERTA", "CERRADA", "CANCELADA"],
  CERRADA: ["ABIERTA", "ARCHIVADA"],
  CANCELADA: ["ARCHIVADA"],
  ARCHIVADA: [],
};

export const workModeSchema = z.enum(["PRESENCIAL", "HIBRIDA", "REMOTA"]);
export type WorkMode = z.infer<typeof workModeSchema>;
export const WORK_MODE_LABELS: Record<WorkMode, string> = {
  PRESENCIAL: "Presencial",
  HIBRIDA: "Híbrida",
  REMOTA: "Remota",
};

export const accessTypeSchema = z.enum(["LECTURA", "COLABORACION"]);
export type AccessType = z.infer<typeof accessTypeSchema>;
export const ACCESS_TYPE_LABELS: Record<AccessType, string> = {
  LECTURA: "Lectura",
  COLABORACION: "Colaboración",
};

export const myAccessSchema = z.enum(["LECTURA", "COLABORACION", "RESPONSABLE", "ADMINISTRADOR"]);
export type MyAccess = z.infer<typeof myAccessSchema>;
export const MY_ACCESS_LABELS: Record<MyAccess, string> = {
  LECTURA: "Lectura",
  COLABORACION: "Colaboración",
  RESPONSABLE: "Responsable",
  ADMINISTRADOR: "Administrador",
};

export const sensitiveClassSchema = z.enum(["PSICOMETRIA", "ESTUDIO_SOCIOECONOMICO"]);
export type SensitiveClass = z.infer<typeof sensitiveClassSchema>;
export const SENSITIVE_CLASS_LABELS: Record<SensitiveClass, string> = {
  PSICOMETRIA: "Resultados psicométricos",
  ESTUDIO_SOCIOECONOMICO: "Estudios socioeconómicos",
};

export const personSchema = z.object({
  id: z.string(),
  full_name: z.string(),
  email: z.string(),
  is_active: z.boolean(),
});
export type Person = z.infer<typeof personSchema>;

export const vacancySchema = z.object({
  id: z.string(),
  name: z.string(),
  department: z.string(),
  location: z.string(),
  work_mode: workModeSchema,
  contract_type: z.string(),
  description: z.string(),
  positions: z.number(),
  notes: z.string().nullable(),
  status: vacancyStatusSchema,
  owner: personSchema.nullable(),
  my_access: myAccessSchema,
  opened_at: z.string().nullable(),
  closed_at: z.string().nullable(),
  created_at: z.string(),
  updated_at: z.string(),
  version: z.number(),
});
export type Vacancy = z.infer<typeof vacancySchema>;

const vacancyPageSchema = z.object({
  items: z.array(vacancySchema),
  total: z.number(),
  page: z.number(),
  page_size: z.number(),
});
export type VacancyPage = z.infer<typeof vacancyPageSchema>;

export type VacancyInput = {
  name: string;
  department: string;
  location: string;
  work_mode: WorkMode;
  contract_type: string;
  description: string;
  positions: number;
  notes: string | null;
};

export type Scope = "mine" | "shared" | "all";

export function listVacancies(
  params: { scope: Scope; status?: VacancyStatus | ""; search?: string; page: number; pageSize: number },
  signal?: AbortSignal,
): Promise<VacancyPage> {
  return apiFetch("/vacancies", {
    schema: vacancyPageSchema,
    query: {
      scope: params.scope,
      status: params.status || undefined,
      search: params.search,
      page: params.page,
      page_size: params.pageSize,
    },
    signal,
  });
}

export function getVacancy(id: string, signal?: AbortSignal): Promise<Vacancy> {
  return apiFetch(`/vacancies/${id}`, { schema: vacancySchema, signal });
}

export function createVacancy(input: VacancyInput): Promise<Vacancy> {
  return apiFetch("/vacancies", { method: "POST", body: input, schema: vacancySchema });
}

export function updateVacancy(id: string, input: VacancyInput, version: number): Promise<Vacancy> {
  return apiFetch(`/vacancies/${id}`, {
    method: "PUT",
    body: { ...input, version },
    schema: vacancySchema,
  });
}

export function changeVacancyStatus(
  id: string,
  status: VacancyStatus,
  version: number,
): Promise<Vacancy> {
  return apiFetch(`/vacancies/${id}/status`, {
    method: "POST",
    body: { status, version },
    schema: vacancySchema,
  });
}

const memberSchema = z.object({
  user: personSchema.nullable(),
  access_type: accessTypeSchema,
  granted_at: z.string(),
  sensitive_classes: z.array(sensitiveClassSchema),
});
export type Member = z.infer<typeof memberSchema>;

export function listMembers(vacancyId: string, signal?: AbortSignal): Promise<Member[]> {
  return apiFetch(`/vacancies/${vacancyId}/members`, { schema: z.array(memberSchema), signal });
}

export function setMember(vacancyId: string, userId: string, accessType: AccessType): Promise<void> {
  return apiFetch(`/vacancies/${vacancyId}/members/${userId}`, {
    method: "PUT",
    body: { access_type: accessType },
  });
}

export function revokeMember(vacancyId: string, userId: string): Promise<void> {
  return apiFetch(`/vacancies/${vacancyId}/members/${userId}`, { method: "DELETE" });
}

export function setSensitiveGrants(
  vacancyId: string,
  userId: string,
  classes: SensitiveClass[],
): Promise<void> {
  return apiFetch(`/vacancies/${vacancyId}/members/${userId}/sensitive-grants`, {
    method: "PUT",
    body: { document_classes: classes },
  });
}

const ownershipChangeSchema = z.object({
  previous_owner: personSchema.nullable(),
  new_owner: personSchema.nullable(),
  changed_at: z.string(),
  reason: z.string(),
  authorized_by: personSchema.nullable(),
  part_of_mass_transfer: z.boolean(),
});
export type OwnershipChange = z.infer<typeof ownershipChangeSchema>;

export function ownershipHistory(vacancyId: string, signal?: AbortSignal): Promise<OwnershipChange[]> {
  return apiFetch(`/vacancies/${vacancyId}/ownership-history`, {
    schema: z.array(ownershipChangeSchema),
    signal,
  });
}

const directoryEntrySchema = z.object({ id: z.string(), full_name: z.string(), email: z.string() });
export type DirectoryEntry = z.infer<typeof directoryEntrySchema>;

export function searchDirectory(search: string, signal?: AbortSignal): Promise<DirectoryEntry[]> {
  return apiFetch("/users/directory", {
    schema: z.array(directoryEntrySchema),
    query: { search },
    signal,
  });
}
