import { act, cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { AiWaitNotice, useAiWait } from "./ai-wait";

function Probe({ action }: { action: () => Promise<string> }) {
  const wait = useAiWait();
  return (
    <div>
      <button type="button" onClick={() => void wait.run(action).catch(() => undefined)}>
        Pedir
      </button>
      <AiWaitNotice wait={wait} />
    </div>
  );
}

afterEach(() => {
  cleanup();
  vi.useRealTimers();
});

describe("Aviso de espera de la IA", () => {
  it("muestra el tiempo transcurrido mientras la IA responde y desaparece al terminar", async () => {
    vi.useFakeTimers();
    let finish: (value: string) => void = () => undefined;
    const action = () => new Promise<string>((resolve) => (finish = resolve));
    render(<Probe action={action} />);
    expect(screen.queryByText(/La IA está trabajando/)).toBeNull();

    await act(async () => screen.getByRole("button", { name: "Pedir" }).click());
    expect(screen.getByText(/La IA está trabajando \(0:00\)/)).toBeTruthy();
    await act(async () => vi.advanceTimersByTime(75_000));
    expect(screen.getByText(/La IA está trabajando \(1:15\)/)).toBeTruthy();
    expect(screen.getByText(/no cierres ni recargues la pantalla/)).toBeTruthy();

    await act(async () => finish("listo"));
    expect(screen.queryByText(/La IA está trabajando/)).toBeNull();
  });

  it("también desaparece si la IA falla", async () => {
    vi.useFakeTimers();
    let fail: (reason: Error) => void = () => undefined;
    const action = () => new Promise<string>((_, reject) => (fail = reject));
    render(<Probe action={action} />);
    await act(async () => screen.getByRole("button", { name: "Pedir" }).click());
    expect(screen.getByText(/La IA está trabajando/)).toBeTruthy();
    await act(async () => fail(new Error("sin respuesta")));
    expect(screen.queryByText(/La IA está trabajando/)).toBeNull();
  });
});
