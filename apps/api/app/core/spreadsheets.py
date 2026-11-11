"""Utilidades comunes para los Excel que genera el sistema."""

from __future__ import annotations

_FORMULA_START = ("=", "+", "-", "@", "\t", "\r")


def safe_cell(value: object) -> object:
    """Evita que un texto capturado por alguien se interprete como fórmula al
    abrir el Excel (inyección de fórmulas)."""
    if isinstance(value, str) and value.startswith(_FORMULA_START):
        return "'" + value
    return value
