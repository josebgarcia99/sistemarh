"""Validación de lo capturado en cada tipo de evaluación y cálculos en Python.

Aquí no hay ninguna puntuación de personas: el único cálculo es el resultado
de una prueba técnica con rúbrica, que es la suma de puntos obtenidos entre
los posibles. El estudio socioeconómico no se puntúa de ninguna forma.
"""

from __future__ import annotations

import re
import uuid
from datetime import date
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any

from app.modules.assessments.domain.models import (
    STATUSES,
    FieldType,
    FormField,
    FormSection,
    FormTemplateVersion,
    Kind,
)

MAX_TEXT = 6000
MAX_ROWS = 40
MAX_FIELDS = 120


class RuleError(ValueError):
    """Dato no válido. El mensaje es apto para mostrarse."""


def line(value: object, limit: int = 200) -> str:
    return " ".join(str(value or "").split())[:limit]


def block(value: object, limit: int = MAX_TEXT) -> str:
    lines = [" ".join(row.split()) for row in str(value or "").strip().splitlines()]
    return "\n".join(lines)[:limit].strip()


def _rows(value: object) -> list[dict[str, Any]]:
    rows = [row for row in (value if isinstance(value, list) else []) if isinstance(row, dict)]
    if len(rows) > MAX_ROWS:
        raise RuleError(f"Se admiten como máximo {MAX_ROWS} filas.")
    return rows


def _number(value: object, label: str) -> Decimal | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        raise RuleError(f"{label}: escribe un número.")
    try:
        number = Decimal(str(value).replace(",", "."))
    except InvalidOperation as error:
        raise RuleError(f"{label}: escribe un número.") from error
    if not number.is_finite():
        raise RuleError(f"{label}: escribe un número.")
    return number


def check_status(kind: Kind, status: str) -> str:
    if status not in STATUSES[kind]:
        raise RuleError("El estado no corresponde a este tipo de evaluación.")
    return status


# --- Psicometría -------------------------------------------------------------------------


def psychometric(data: dict[str, Any], status: str) -> dict[str, Any]:
    clean = {
        "instrument": line(data.get("instrument"), 150),
        "instrument_version": line(data.get("instrument_version"), 50),
        "provider": line(data.get("provider"), 150),
        "result": block(data.get("result")),
        "notes": block(data.get("notes")),
        # Quién interpretó la prueba: una persona con la formación para hacerlo.
        "professional_name": line(data.get("professional_name"), 200),
        "professional_license": line(data.get("professional_license"), 60),
        "validation_note": block(data.get("validation_note"), 2000),
    }
    if not clean["instrument"]:
        raise RuleError("Escribe el nombre del instrumento.")
    if status == "VALIDADA":
        if not clean["professional_name"]:
            raise RuleError("Para marcarla como validada, indica qué profesional la interpretó.")
        if not clean["result"]:
            raise RuleError("Para marcarla como validada, anota el resultado documentado.")
    return clean


# --- Entrevista con gerente --------------------------------------------------------------


def interview(data: dict[str, Any], status: str) -> dict[str, Any]:
    questions = [
        {"question": line(row.get("question"), 1000), "answer": block(row.get("answer"))}
        for row in _rows(data.get("questions"))
    ]
    competencies = [line(item, 150) for item in (data.get("competencies") or []) if line(item)]
    clean = {
        "interviewer": line(data.get("interviewer"), 200),
        "questions": [row for row in questions if row["question"] or row["answer"]],
        "competencies": list(dict.fromkeys(competencies))[:MAX_ROWS],
        "feedback": block(data.get("feedback")),
        "evidence": block(data.get("evidence")),
        "notes": block(data.get("notes")),
        # La conclusión es de quien entrevistó; la IA no la escribe ni la cambia.
        "conclusion": block(data.get("conclusion"), 2000),
    }
    if not clean["interviewer"]:
        raise RuleError("Escribe quién entrevistó.")
    if status == "REALIZADA" and not clean["conclusion"]:
        raise RuleError("Para marcarla como realizada, anota la conclusión de quien entrevistó.")
    return clean


# --- Prueba técnica ----------------------------------------------------------------------


def technical(data: dict[str, Any], status: str) -> tuple[dict[str, Any], Decimal | None]:
    rubric = []
    for index, row in enumerate(_rows(data.get("rubric")), start=1):
        criterion = line(row.get("criterion"), 200)
        maximum = _number(row.get("max_points"), f"Criterio {index}, puntos posibles")
        points = _number(row.get("points"), f"Criterio {index}, puntos obtenidos")
        if not criterion and maximum is None and points is None:
            continue
        if not criterion:
            raise RuleError(f"El criterio {index} de la rúbrica no tiene nombre.")
        if maximum is None or maximum <= 0:
            raise RuleError(f"Criterio {index}: los puntos posibles deben ser mayores que cero.")
        if points is not None and not 0 <= points <= maximum:
            raise RuleError(f"Criterio {index}: los puntos obtenidos van de 0 a {maximum}.")
        rubric.append(
            {
                "criterion": criterion,
                "max_points": str(maximum),
                "points": str(points) if points is not None else None,
            }
        )
    pass_mark = _number(data.get("pass_mark"), "Mínimo aprobatorio")
    if pass_mark is not None and not 0 <= pass_mark <= 100:
        raise RuleError("El mínimo aprobatorio va de 0 a 100.")
    clean = {
        "test_type": line(data.get("test_type"), 150),
        "competency": line(data.get("competency"), 150),
        "responsible": line(data.get("responsible"), 200),
        "result": block(data.get("result")),
        "evidence": block(data.get("evidence")),
        "comments": block(data.get("comments")),
        "rubric": rubric,
        "pass_mark": str(pass_mark) if pass_mark is not None else None,
    }
    if not clean["test_type"]:
        raise RuleError("Escribe el tipo de prueba.")
    # Regla objetiva: puntos obtenidos entre puntos posibles, solo si la rúbrica está completa.
    score = None
    if rubric and all(row["points"] is not None for row in rubric):
        total = sum(Decimal(row["max_points"]) for row in rubric)
        earned = sum(Decimal(row["points"]) for row in rubric)
        score = (earned / total * 100).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    if status == "REALIZADA" and rubric and score is None:
        raise RuleError("Para marcarla como realizada, captura los puntos de toda la rúbrica.")
    clean["passed"] = score >= pass_mark if score is not None and pass_mark is not None else None
    return clean, score


# --- Formularios del estudio socioeconómico ----------------------------------------------

_FIELD_ID = re.compile(r"^[a-z0-9_]{1,40}$")


def template_sections(raw: list[dict[str, Any]]) -> tuple[FormSection, ...]:
    sections = []
    used: set[str] = set()
    for number, item in enumerate(raw, start=1):
        title = line(item.get("title"), 150)
        if not title:
            raise RuleError(f"La sección {number} no tiene título.")
        fields = []
        for row in _rows(item.get("fields")):
            label = line(row.get("label"), 200)
            if not label:
                raise RuleError(f"Hay un campo sin nombre en «{title}».")
            try:
                kind = FieldType(str(row.get("type")))
            except ValueError as error:
                raise RuleError(f"El tipo del campo «{label}» no es válido.") from error
            field_id = str(row.get("id") or "")
            # Un campo conserva su identificador entre versiones; uno nuevo recibe otro.
            if not _FIELD_ID.match(field_id) or field_id in used:
                field_id = "c_" + uuid.uuid4().hex[:12]
            used.add(field_id)
            options = tuple(
                dict.fromkeys(line(o, 100) for o in (row.get("options") or []) if line(o))
            )
            if kind is FieldType.OPCIONES and len(options) < 2:
                raise RuleError(f"El campo «{label}» necesita al menos dos opciones.")
            minimum = _number(row.get("minimum"), f"«{label}», mínimo")
            maximum = _number(row.get("maximum"), f"«{label}», máximo")
            if minimum is not None and maximum is not None and minimum > maximum:
                raise RuleError(f"En «{label}» el mínimo es mayor que el máximo.")
            numeric = kind is FieldType.NUMERO
            fields.append(
                FormField(
                    id=field_id,
                    label=label,
                    type=kind,
                    required=row.get("required") is True and kind is not FieldType.OBSERVACION,
                    options=options if kind is FieldType.OPCIONES else (),
                    minimum=minimum if numeric else None,
                    maximum=maximum if numeric else None,
                )
            )
        if not fields:
            raise RuleError(f"La sección «{title}» no tiene campos.")
        sections.append(FormSection(title, tuple(fields)))
    if not sections:
        raise RuleError("El formulario necesita al menos una sección.")
    if sum(len(section.fields) for section in sections) > MAX_FIELDS:
        raise RuleError(f"Un formulario admite como máximo {MAX_FIELDS} campos.")
    return tuple(sections)


def _field_value(item: FormField, value: object) -> object:
    """Valor limpio del campo, o ``None`` si está vacío. Lanza si no es válido."""
    if item.type is FieldType.CASILLA:
        # Una casilla sin marcar no se guarda: equivale a no tener el dato.
        return True if value is True else None
    if value is None or value == "":
        return None
    if item.type is FieldType.NUMERO:
        number = _number(value, item.label)
        if number is not None and (
            (item.minimum is not None and number < item.minimum)
            or (item.maximum is not None and number > item.maximum)
        ):
            raise RuleError(f"«{item.label}» está fuera del rango permitido.")
        return str(number) if number is not None else None
    if item.type is FieldType.FECHA:
        try:
            return date.fromisoformat(str(value)).isoformat()
        except ValueError as error:
            raise RuleError(f"«{item.label}»: la fecha no es válida.") from error
    if item.type is FieldType.OPCIONES:
        if value not in item.options:
            raise RuleError(f"«{item.label}»: elige una de las opciones.")
        return value
    if item.type is FieldType.DOCUMENTO:
        try:
            return str(uuid.UUID(str(value)))
        except ValueError as error:
            raise RuleError(f"«{item.label}»: el documento no es válido.") from error
    limit = 300 if item.type is FieldType.TEXTO else MAX_TEXT
    return (line(value, limit) if item.type is FieldType.TEXTO else block(value, limit)) or None


def study(data: dict[str, Any], status: str, version: FormTemplateVersion) -> dict[str, Any]:
    raw = data.get("answers") if isinstance(data.get("answers"), dict) else {}
    answers: dict[str, dict[str, Any]] = {}
    missing = []
    for item in version.fields:
        entry = raw.get(item.id) if isinstance(raw.get(item.id), dict) else {}
        value = _field_value(item, entry.get("value"))
        if item.required and value is None:
            missing.append(item.label)
        if value is None:
            continue
        answers[item.id] = {
            "value": value,
            # Un dato solo está verificado si una persona lo marcó así.
            "verified": entry.get("verified") is True,
            # De dónde salió el valor: capturado a mano o leído por la IA de un documento.
            "source": "IA" if entry.get("source") == "IA" else "MANUAL",
        }
    if status == "COMPLETADO" and missing:
        raise RuleError("Para completarlo faltan: " + ", ".join(missing[:8]) + ".")
    return {
        "performed_by": line(data.get("performed_by"), 200),
        "notes": block(data.get("notes")),
        "answers": answers,
    }


def document_field_ids(version: FormTemplateVersion, answers: dict[str, Any]) -> list[str]:
    return [
        str(answers[item.id]["value"])
        for item in version.fields
        if item.type is FieldType.DOCUMENTO and item.id in answers
    ]


DEFAULT_TEMPLATE: list[dict[str, Any]] = [
    {
        "title": "Datos de la visita",
        "fields": [
            {"label": "Fecha de la visita", "type": "FECHA", "required": True},
            {"label": "Persona que atendió", "type": "TEXTO"},
            {"label": "Domicilio declarado", "type": "PARRAFO", "required": True},
        ],
    },
    {
        "title": "Verificación documental",
        "fields": [
            {"label": "Identificación oficial cotejada", "type": "CASILLA"},
            {"label": "Comprobante de domicilio cotejado", "type": "CASILLA"},
            {"label": "Comprobante de estudios cotejado", "type": "CASILLA"},
            {
                "label": "Referencias laborales contactadas",
                "type": "NUMERO",
                "minimum": 0,
                "maximum": 20,
            },
            {
                "label": "Resultado de las referencias laborales",
                "type": "OPCIONES",
                "options": ["Confirmadas", "Confirmadas en parte", "No se pudieron contactar"],
            },
            {"label": "Formulario escaneado", "type": "DOCUMENTO"},
        ],
    },
    {
        "title": "Observaciones",
        "fields": [{"label": "Observaciones de quien realizó el estudio", "type": "OBSERVACION"}],
    },
]
