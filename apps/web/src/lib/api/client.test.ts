import { afterEach, describe, expect, it, vi } from "vitest";
import { z } from "zod";
import { ApiError, apiFetch } from "./client";

function mockFetch(status: number, body: unknown, headers: Record<string, string> = {}) {
  const fetchMock = vi.fn().mockResolvedValue(
    new Response(body === undefined ? "no es json" : JSON.stringify(body), { status, headers }),
  );
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("apiFetch", () => {
  const schema = z.object({ valor: z.number() });

  it("llama al mismo origen bajo /api/v1 y valida la respuesta", async () => {
    const fetchMock = mockFetch(200, { valor: 7 });
    await expect(apiFetch("/algo", { schema })).resolves.toEqual({ valor: 7 });
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/algo",
      expect.objectContaining({ method: "GET", credentials: "same-origin" }),
    );
  });

  it("rechaza una respuesta que no cumple el esquema", async () => {
    mockFetch(200, { valor: "siete" });
    await expect(apiFetch("/algo", { schema })).rejects.toThrow();
  });

  it("convierte un error uniforme de la API en ApiError", async () => {
    mockFetch(409, {
      title: "El recurso cambió o ya existe",
      status: 409,
      detail: "La vacante cambió desde tu última lectura.",
      code: "conflicto",
      correlation_id: "abc-12345678",
    });
    const error = await apiFetch("/algo", { schema }).catch((e: unknown) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({
      status: 409,
      code: "conflicto",
      correlationId: "abc-12345678",
      message: "La vacante cambió desde tu última lectura.",
    });
  });

  it("no falla ante un error sin formato reconocible y conserva la correlación", async () => {
    mockFetch(502, undefined, { "X-Correlation-ID": "proxy-12345678" });
    const error = await apiFetch("/algo", { schema }).catch((e: unknown) => e);
    expect(error).toMatchObject({
      status: 502,
      code: "respuesta_no_reconocida",
      correlationId: "proxy-12345678",
    });
  });

  it("acepta como dato un código declarado en acceptStatuses", async () => {
    mockFetch(503, { valor: 1 });
    await expect(apiFetch("/algo", { schema, acceptStatuses: [503] })).resolves.toEqual({
      valor: 1,
    });
  });
});
