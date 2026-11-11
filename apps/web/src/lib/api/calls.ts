import { z } from "zod";
import { apiFetch } from "./client";

const questionSchema = z.object({
  id: z.string(),
  text: z.string(),
  competency: z.string(),
  guidance: z.string(),
  origin: z.string(),
});
export type Question = z.infer<typeof questionSchema>;
export type QuestionInput = {
  id: string | null;
  text: string;
  competency: string;
  guidance: string;
  origin: string;
};

const bankSchema = z.object({
  id: z.string(),
  name: z.string(),
  description: z.string().nullable(),
  owner_name: z.string().nullable(),
  mine: z.boolean(),
  can_edit: z.boolean(),
  shared: z.boolean(),
  status: z.enum(["ACTIVO", "ARCHIVADO"]),
  version_number: z.number(),
  questions: z.array(questionSchema),
  updated_at: z.string(),
});
export type Bank = z.infer<typeof bankSchema>;

const bankDetailSchema = z.object({
  bank: bankSchema,
  versions: z.array(
    z.object({
      version_number: z.number(),
      questions: z.number(),
      change_note: z.string().nullable(),
      created_at: z.string(),
      created_by_name: z.string().nullable(),
    }),
  ),
});
export type BankDetail = z.infer<typeof bankDetailSchema>;

export type BankInput = {
  name: string;
  description: string | null;
  shared: boolean;
  questions: QuestionInput[];
};

const proposedSchema = z.array(
  z.object({ text: z.string(), competency: z.string(), guidance: z.string() }),
);
export type ProposedQuestion = z.infer<typeof proposedSchema>[number];

export function listBanks(signal?: AbortSignal) {
  return apiFetch("/question-banks", { schema: z.array(bankSchema), signal });
}

export function getBank(bankId: string, signal?: AbortSignal) {
  return apiFetch(`/question-banks/${bankId}`, { schema: bankDetailSchema, signal });
}

export function createBank(input: BankInput) {
  return apiFetch("/question-banks", { method: "POST", body: input, schema: bankSchema });
}

export function updateBank(
  bankId: string,
  input: BankInput & { change_note: string | null; expected_version: number },
) {
  return apiFetch(`/question-banks/${bankId}`, { method: "PUT", body: input, schema: bankSchema });
}

export function bankAction(bankId: string, action: "archive" | "restore" | "duplicate") {
  return apiFetch(`/question-banks/${bankId}/${action}`, { method: "POST", schema: bankSchema });
}

export function proposeQuestions(vacancyId: string, count: number) {
  return apiFetch("/question-banks/question-proposals", {
    method: "POST",
    body: { vacancy_id: vacancyId, count },
    schema: proposedSchema,
  });
}

export const ANALYSIS_SECTIONS: [string, string][] = [
  ["evidencias", "Evidencias"],
  ["competencias_exploradas", "Competencias exploradas"],
  ["informacion_faltante", "Información que faltó"],
  ["coincidencias_con_cv", "Coincide con el CV"],
  ["discrepancias_verificables", "Diferencias por aclarar con el CV"],
  ["preguntas_de_seguimiento", "Preguntas de seguimiento"],
];

const callSchema = z.object({
  id: z.string(),
  application_id: z.string(),
  status: z.enum(["BORRADOR", "CERRADA"]),
  bank_name: z.string(),
  bank_version: z.number(),
  called_at: z.string(),
  created_by_name: z.string().nullable(),
  notes: z.string(),
  questions: z.array(
    questionSchema.extend({ answer: z.string(), notes: z.string(), not_asked: z.boolean() }),
  ),
  analysis: z
    .object({ resumen: z.string() })
    .catchall(z.union([z.string(), z.array(z.string())]))
    .nullable(),
  analysis_at: z.string().nullable(),
  closed_at: z.string().nullable(),
});
export type Call = z.infer<typeof callSchema>;
export type AnswerInput = {
  question_id: string;
  answer: string;
  notes: string;
  not_asked: boolean;
};

export function listCalls(applicationId: string, signal?: AbortSignal) {
  return apiFetch(`/applications/${applicationId}/calls`, { schema: z.array(callSchema), signal });
}

export function openCall(applicationId: string, bankId: string) {
  return apiFetch(`/applications/${applicationId}/calls`, {
    method: "POST",
    body: { bank_id: bankId },
    schema: callSchema,
  });
}

export function saveCall(
  callId: string,
  input: { answers: AnswerInput[]; notes: string; close: boolean },
) {
  return apiFetch(`/calls/${callId}`, { method: "PUT", body: input, schema: callSchema });
}

export function analyzeCall(callId: string) {
  return apiFetch(`/calls/${callId}/analysis`, { method: "POST", schema: callSchema });
}
