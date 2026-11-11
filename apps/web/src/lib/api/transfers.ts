import { z } from "zod";
import { apiFetch } from "./client";
import { personSchema } from "./vacancies";

export function transferVacancy(input: {
  vacancy_id: string;
  to_user_id: string;
  reason: string;
  keep_previous_as_collaborator: boolean;
}): Promise<void> {
  return apiFetch("/vacancy-transfers/individual", { method: "POST", body: input });
}

const massPreviewSchema = z.object({
  from_user: personSchema,
  to_user: personSchema,
  vacancies: z.array(z.object({ id: z.string(), name: z.string(), status: z.string() })),
  memberships_to_revoke: z.number(),
  grants_to_revoke: z.number(),
  preview_token: z.string(),
});
export type MassPreview = z.infer<typeof massPreviewSchema>;

export function previewMassTransfer(fromUserId: string, toUserId: string): Promise<MassPreview> {
  return apiFetch("/vacancy-transfers/mass/preview", {
    method: "POST",
    body: { from_user_id: fromUserId, to_user_id: toUserId },
    schema: massPreviewSchema,
  });
}

const massResultSchema = z.object({
  operation_id: z.string(),
  completed_at: z.string(),
  vacancies_transferred: z.number(),
  memberships_revoked: z.number(),
  grants_revoked: z.number(),
  user_deactivated: z.boolean(),
});
export type MassResult = z.infer<typeof massResultSchema>;

export function executeMassTransfer(input: {
  operation_id: string;
  from_user_id: string;
  to_user_id: string;
  reason: string;
  preview_token: string;
}): Promise<MassResult> {
  return apiFetch("/vacancy-transfers/mass", {
    method: "POST",
    body: input,
    schema: massResultSchema,
  });
}
