import { z } from "zod";
import { type Role, type User, userSchema } from "./auth";
import { apiFetch } from "./client";

const userPageSchema = z.object({
  items: z.array(userSchema),
  total: z.number(),
  page: z.number(),
  page_size: z.number(),
});
export type UserPage = z.infer<typeof userPageSchema>;

export function listUsers(
  params: { search?: string; page: number; pageSize: number },
  signal?: AbortSignal,
): Promise<UserPage> {
  return apiFetch("/users", {
    schema: userPageSchema,
    query: { search: params.search, page: params.page, page_size: params.pageSize },
    signal,
  });
}

export function createUser(input: {
  email: string;
  full_name: string;
  password: string;
  role: Role;
}): Promise<User> {
  return apiFetch("/users", { method: "POST", body: input, schema: userSchema });
}

export function updateUser(id: string, input: { full_name?: string; role?: Role }): Promise<User> {
  return apiFetch(`/users/${id}`, { method: "PATCH", body: input, schema: userSchema });
}

const resetSchema = z.object({ sessions_closed: z.number() });

export function resetPassword(id: string, newPassword: string): Promise<{ sessions_closed: number }> {
  return apiFetch(`/users/${id}/reset-password`, {
    method: "POST",
    body: { new_password: newPassword },
    schema: resetSchema,
  });
}

export function setUserActive(id: string, active: boolean): Promise<User> {
  return apiFetch(`/users/${id}/${active ? "activate" : "deactivate"}`, {
    method: "POST",
    schema: userSchema,
  });
}
