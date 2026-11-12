import { z } from "zod";
import { apiFetch, setCsrfToken } from "./client";

export const roleSchema = z.enum(["ADMINISTRADOR", "RECLUTADOR", "ANALISTA_ESTUDIOS"]);
export type Role = z.infer<typeof roleSchema>;

export const ROLE_LABELS: Record<Role, string> = {
  ADMINISTRADOR: "Administrador",
  RECLUTADOR: "Reclutador",
  ANALISTA_ESTUDIOS: "Analista de estudios socioeconómicos",
};

export const userSchema = z.object({
  id: z.string(),
  email: z.string(),
  full_name: z.string(),
  role: roleSchema,
  is_active: z.boolean(),
  created_at: z.string(),
  last_activity_at: z.string().nullable(),
  deactivated_at: z.string().nullable(),
});
export type User = z.infer<typeof userSchema>;

const sessionSchema = z.object({ user: userSchema, csrf_token: z.string() });
export type Session = z.infer<typeof sessionSchema>;

export async function login(email: string, password: string): Promise<Session> {
  const session = await apiFetch("/auth/login", {
    method: "POST",
    body: { email, password },
    schema: sessionSchema,
  });
  setCsrfToken(session.csrf_token);
  return session;
}

export async function fetchSession(signal?: AbortSignal): Promise<Session> {
  const session = await apiFetch("/auth/me", { schema: sessionSchema, signal });
  setCsrfToken(session.csrf_token);
  return session;
}

export async function logout(): Promise<void> {
  await apiFetch("/auth/logout", { method: "POST" });
  setCsrfToken(null);
}
