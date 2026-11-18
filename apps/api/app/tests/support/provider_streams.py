"""Respuestas por partes de los proveedores de IA, simuladas para las pruebas.

Imitan el formato que documenta cada proveedor (eventos enviados por el
servidor). Todo el contenido es inventado."""

from __future__ import annotations

import json
from collections.abc import Iterator

import httpx

Event = dict | tuple[str, dict]


def _lines(events: list[Event]) -> bytes:
    out: list[str] = []
    for event in events:
        name, data = event if isinstance(event, tuple) else (None, event)
        if name:
            out.append(f"event: {name}")
        out += ["data: " + json.dumps(data, ensure_ascii=False), ""]
    return ("\n".join(out) + "\n").encode()


def sse(events: list[Event], *, done: bool = False) -> httpx.Response:
    """Una respuesta por partes completa."""
    body = _lines(events) + (b"data: [DONE]\n\n" if done else b"")
    return httpx.Response(200, headers={"content-type": "text/event-stream"}, content=body)


class _Broken(httpx.SyncByteStream):
    def __init__(self, body: bytes, error: Exception) -> None:
        self._body, self._error = body, error

    def __iter__(self) -> Iterator[bytes]:
        if self._body:
            yield self._body
        raise self._error


def cut(events: list[Event], error: Exception) -> httpx.Response:
    """Una respuesta que entrega esos eventos y después falla (silencio o corte)."""
    return httpx.Response(
        200, headers={"content-type": "text/event-stream"}, stream=_Broken(_lines(events), error)
    )


def anthropic_events(
    parts: list[str],
    *,
    input_tokens: int = 12,
    output_tokens: int = 7,
    stop_reason: str = "end_turn",
    end: bool = True,
) -> list[Event]:
    events: list[Event] = [
        (
            "message_start",
            {
                "type": "message_start",
                "message": {
                    "content": [],
                    "usage": {"input_tokens": input_tokens, "output_tokens": 1},
                },
            },
        ),
        ("ping", {"type": "ping"}),
    ]
    if parts:
        events.append(
            (
                "content_block_start",
                {
                    "type": "content_block_start",
                    "index": 0,
                    "content_block": {"type": "text", "text": ""},
                },
            )
        )
        events += [
            (
                "content_block_delta",
                {
                    "type": "content_block_delta",
                    "index": 0,
                    "delta": {"type": "text_delta", "text": part},
                },
            )
            for part in parts
        ]
        events.append(("content_block_stop", {"type": "content_block_stop", "index": 0}))
    if end:
        events += [
            (
                "message_delta",
                {
                    "type": "message_delta",
                    "delta": {"stop_reason": stop_reason, "stop_sequence": None},
                    "usage": {"output_tokens": output_tokens},
                },
            ),
            ("message_stop", {"type": "message_stop"}),
        ]
    return events


def openai_events(
    parts: list[str],
    *,
    input_tokens: int = 20,
    output_tokens: int = 3,
    status: str = "completed",
    end: bool = True,
) -> list[Event]:
    events: list[Event] = [
        ("response.created", {"type": "response.created", "response": {"status": "in_progress"}}),
        (
            "response.in_progress",
            {"type": "response.in_progress", "response": {"status": "in_progress"}},
        ),
    ]
    events += [
        (
            "response.output_text.delta",
            {"type": "response.output_text.delta", "output_index": 0, "delta": part},
        )
        for part in parts
    ]
    if end:
        response: dict = {
            "status": status,
            "usage": {"input_tokens": input_tokens, "output_tokens": output_tokens},
        }
        if status == "incomplete":
            response["incomplete_details"] = {"reason": "max_output_tokens"}
        events.append((f"response.{status}", {"type": f"response.{status}", "response": response}))
    return events


def gemini_events(
    parts: list[str],
    *,
    input_tokens: int = 40,
    output_tokens: int = 6,
    thoughts: int = 0,
    finish: str | None = "STOP",
) -> list[Event]:
    """Cada dato es una respuesta parcial; la última trae el motivo de fin."""
    usage = {"promptTokenCount": input_tokens, "candidatesTokenCount": output_tokens}
    if thoughts:
        usage["thoughtsTokenCount"] = thoughts
    events: list[Event] = [
        {"candidates": [{"content": {"role": "model", "parts": [{"text": part}]}}]}
        for part in parts[:-1]
    ]
    last: dict = {"content": {"role": "model", "parts": [{"text": part} for part in parts[-1:]]}}
    if finish:
        last["finishReason"] = finish
    events.append({"candidates": [last], "usageMetadata": usage})
    return events
