"""Validación de la respuesta de la IA y cálculo de la puntuación. Todo en Python.

La IA solo asigna un nivel de 0 a 4 a cada criterio. La puntuación la calcula
este módulo: promedio ponderado de los niveles, de 0 a 100. Un criterio sin
evidencia aporta 0 puntos y se informa aparte, para que la persona que revisa
sepa que no hubo evidencia (que no es lo mismo que no cumplir).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from enum import StrEnum

from app.core.ai_json import parse_json_object

QUALITY_ASPECTS = (
    "redaccion",
    "ortografia",
    "organizacion",
    "claridad",
    "coherencia",
    "completitud",
)
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
_PHONE = re.compile(r"(?<![\w/.-])(?:\+?\d[\s().-]{0,2}){9,14}\d(?![\w/-])")


class Classification(StrEnum):
    ACEPTADO_IA = "ACEPTADO_IA"
    RECHAZADO_IA = "RECHAZADO_IA"
    NO_EVALUABLE = "NO_EVALUABLE"


class InvalidResponseError(ValueError):
    """La respuesta de la IA no cumple el formato acordado."""


@dataclass(frozen=True)
class CriterionSpec:
    code: str
    weight: Decimal


@dataclass(frozen=True)
class CriterionScore:
    code: str
    level: int | None
    no_evidence: bool
    evidence: str
    justification: str


@dataclass(frozen=True)
class Evaluation:
    classification: Classification
    score: Decimal | None
    scores: tuple[CriterionScore, ...]
    reason: str | None
    quality: dict[str, int] | None
    digitization_suspect: bool
    notes: str


def mask_contacts(text: str) -> str:
    """Quita correos y teléfonos antes de enviar el CV a un proveedor."""
    return _PHONE.sub("[teléfono]", _EMAIL.sub("[correo]", text))


def parse_json(text: str) -> dict[str, object]:
    try:
        return parse_json_object(text)
    except ValueError as error:
        raise InvalidResponseError("La respuesta no es un objeto JSON válido.") from error


def _text(value: object, limit: int) -> str:
    return " ".join(str(value or "").split())[:limit]


def _quality(raw: object) -> tuple[dict[str, int] | None, bool]:
    if not isinstance(raw, dict):
        return None, False
    values = {}
    for aspect in QUALITY_ASPECTS:
        level = raw.get(aspect)
        if isinstance(level, bool) or not isinstance(level, int) or not 0 <= level <= 4:
            return None, bool(raw.get("posible_error_de_digitalizacion") is True)
        values[aspect] = level
    return values, raw.get("posible_error_de_digitalizacion") is True


def evaluate(
    payload: dict[str, object], specs: list[CriterionSpec], threshold: Decimal
) -> Evaluation:
    """Valida la respuesta contra la rúbrica y calcula puntuación y clasificación."""
    evaluable = payload.get("evaluable")
    if not isinstance(evaluable, bool):
        raise InvalidResponseError("Falta indicar si el CV es evaluable.")
    quality, suspect = _quality(payload.get("calidad_documental"))
    notes = _text(payload.get("observaciones"), 1000)
    if not evaluable:
        reason = (
            _text(payload.get("motivo_no_evaluable"), 500) or "La IA lo marcó como no evaluable."
        )
        return Evaluation(Classification.NO_EVALUABLE, None, (), reason, quality, suspect, notes)

    raw = payload.get("criterios")
    if not isinstance(raw, list):
        raise InvalidResponseError("Falta la lista de criterios.")
    weights = {spec.code: spec.weight for spec in specs}
    found: dict[str, CriterionScore] = {}
    for item in raw:
        if not isinstance(item, dict):
            raise InvalidResponseError("Un criterio no tiene el formato esperado.")
        code = str(item.get("id"))
        if code not in weights or code in found:
            raise InvalidResponseError("La respuesta trae un criterio desconocido o repetido.")
        level = item.get("nivel")
        no_evidence = item.get("sin_evidencia") is True
        if level is None:
            if not no_evidence:
                raise InvalidResponseError(
                    f"El criterio {code} no tiene nivel ni marca de sin evidencia."
                )
        elif isinstance(level, bool) or not isinstance(level, int) or not 0 <= level <= 4:
            raise InvalidResponseError(f"El nivel del criterio {code} no es un entero de 0 a 4.")
        found[code] = CriterionScore(
            code=code,
            level=None if no_evidence else level,
            no_evidence=no_evidence,
            evidence=_text(item.get("evidencia"), 300),
            justification=_text(item.get("justificacion"), 600),
        )
    missing = [spec.code for spec in specs if spec.code not in found]
    if missing:
        raise InvalidResponseError("Faltan criterios en la respuesta: " + ", ".join(missing))

    scores = tuple(found[spec.code] for spec in specs)
    if all(item.no_evidence for item in scores):
        return Evaluation(
            Classification.NO_EVALUABLE,
            None,
            scores,
            "El CV no aporta evidencia sobre ningún criterio de la rúbrica.",
            quality,
            suspect,
            notes,
        )
    total_weight = sum(weights.values(), Decimal(0))
    earned = sum((weights[item.code] * (item.level or 0) for item in scores), Decimal(0))
    score = (earned / (total_weight * 4) * 100).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    classification = (
        Classification.ACEPTADO_IA if score >= threshold else Classification.RECHAZADO_IA
    )
    return Evaluation(classification, score, scores, None, quality, suspect, notes)
