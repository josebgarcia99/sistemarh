"""Lectura de respuestas JSON de un modelo de IA."""

from __future__ import annotations

import json
import re

_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE)


def parse_json_object(text: str) -> dict[str, object]:
    """Devuelve el objeto JSON de la respuesta, aunque venga en un bloque de código.
    Lanza ``ValueError`` si no es un objeto JSON válido."""
    cleaned = _FENCE.sub("", text.strip()).strip()
    payload = json.loads(cleaned)
    if not isinstance(payload, dict):
        raise ValueError("La respuesta no es un objeto JSON.")
    return payload
