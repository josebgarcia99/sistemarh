"use client";

import { useQuery } from "@tanstack/react-query";
import { fetchSession } from "@/lib/api/auth";
import { ApiError } from "@/lib/api/client";

export const SESSION_QUERY_KEY = ["session"] as const;

/** Sesión actual. `unauthenticated` es true cuando la API responde 401. */
export function useSession() {
  const query = useQuery({
    queryKey: SESSION_QUERY_KEY,
    queryFn: ({ signal }) => fetchSession(signal),
    retry: false,
    staleTime: 60_000,
  });
  const unauthenticated = query.error instanceof ApiError && query.error.status === 401;
  return { ...query, user: query.data?.user ?? null, unauthenticated };
}
