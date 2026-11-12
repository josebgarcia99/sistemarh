"""Lectura directa del formato «SGC.F15.RH. Perfil de puesto» (Excel). Sin IA.

El formato de la empresa es una hoja con secciones tituladas, etiquetas con su
valor a la derecha, listas numeradas («1.-», «2.-»…) y casillas de verificación.
Este lector ubica cada dato por su etiqueta, no por la posición exacta de la
celda, para tolerar filas o columnas añadidas.

Qué no se copia al perfil: la edad y el género que pide el formato. Son datos
con los que no se debe evaluar a una persona candidata, así que se avisa a quien
revisa y se dejan fuera. El resultado es una propuesta: nada se guarda sin que
una persona la revise.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime

from app.modules.evaluation_setup.domain.generator import (
    MAX_ITEM,
    MAX_ITEMS,
    MAX_LINE,
    MAX_ROWS,
    MAX_TEXT,
    fold,
    option,
)
from app.modules.evaluation_setup.domain.models import (
    EDUCATION_LEVELS,
    FREQUENCIES,
    Activity,
    Kpi,
    ProfileContent,
)

# Valores de una hoja: (fila, columna) -> contenido de la celda. Empiezan en 1.
Grid = Mapping[tuple[int, int], object]

FORMAT_NAME = "SGC.F15.RH. Perfil de puesto"

_MARKER = re.compile(r"^(\d{1,2})\s*[.\-)]+\s*-?\s*(.*)$", re.DOTALL)
_TRUE = {"true", "verdadero", "x", "si", "1"}
# Títulos de sección, como empiezan una vez sin acentos y en minúsculas.
_SECTIONS = {
    "identification": "identificacion del puesto",
    "purpose": "proposito del puesto",
    "scope": "alcance y relaciones",
    "requirements": "requisitos del puesto",
    "functions": "funciones y actividades",
    "kpis": "kpi",
    "history": "historial de cambios",
}
# Con qué empieza el pie de cada página y el bloque de firmas.
_FOOTER = ("elabora", "nombre y firma", "documento")
# Secciones que deben aparecer para aceptar la hoja como el formato de la empresa.
_REQUIRED = ("identification", "purpose", "requirements", "functions")


@dataclass(frozen=True)
class FormatReading:
    content: ProfileContent
    # Avisos para quien revisa: qué se dejó fuera o qué no se pudo leer.
    notices: tuple[str, ...]


@dataclass(frozen=True)
class _Cell:
    row: int
    column: int
    value: object
    text: str  # en limpio, tal como se copia al perfil
    key: str  # sin acentos ni mayúsculas, para comparar

    @property
    def is_label(self) -> bool:
        return self.text.endswith(":")

    @property
    def marker(self) -> re.Match[str] | None:
        return _MARKER.match(self.text) if isinstance(self.value, str) else None

    @property
    def checked(self) -> bool | None:
        """Estado de una casilla, o ``None`` si la celda no es una casilla."""
        if isinstance(self.value, bool):
            return self.value
        if self.key in _TRUE:
            return True
        if self.key in {"false", "falso", "no", "0"}:
            return False
        return None


def _text(value: object) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    # Las celdas del formato traen tabuladores y saltos de línea sobrantes.
    return " ".join(str(value).split())


class _Sheet:
    def __init__(self, grid: Grid) -> None:
        self.rows: dict[int, list[_Cell]] = {}
        for (row, column), value in sorted(grid.items()):
            if value is None:
                continue
            text = _text(value)
            if text and not text.startswith("#"):  # «#VALUE!» y otros errores de Excel
                self.rows.setdefault(row, []).append(_Cell(row, column, value, text, fold(text)))
        self.last_row = max(self.rows, default=0)
        self.sections: dict[str, int] = {}
        for row, cells in self.rows.items():
            for name, start in _SECTIONS.items():
                if name not in self.sections and cells[0].key.startswith(start):
                    self.sections[name] = row

    def section(self, name: str) -> range:
        """Filas de una sección: desde su título hasta el siguiente título."""
        start = self.sections.get(name)
        if start is None:
            return range(0)
        later = [row for row in self.sections.values() if row > start]
        return range(start + 1, min(later, default=self.last_row + 1))

    def cells(self, rows: range) -> list[_Cell]:
        return [cell for row in rows for cell in self.rows.get(row, [])]

    def find(self, prefix: str, rows: range) -> _Cell | None:
        return next((cell for cell in self.cells(rows) if cell.key.startswith(prefix)), None)

    def right_of(self, cell: _Cell) -> list[_Cell]:
        return [other for other in self.rows.get(cell.row, []) if other.column > cell.column]

    def value_of(self, prefix: str, rows: range, limit: int = MAX_LINE) -> str:
        """Valor escrito a la derecha de una etiqueta, antes de la etiqueta siguiente."""
        label = self.find(prefix, rows)
        if label is None:
            return ""
        following = self.right_of(label)
        if not following or following[0].is_label or following[0].checked is not None:
            return ""
        return following[0].text[:limit]

    def numbered(self, rows: range, columns: range | None = None) -> dict[int, str]:
        """Lista numerada: «1.-» y, a su derecha, el texto. Devuelve número -> texto."""
        items: dict[int, str] = {}
        for cell in self.cells(rows):
            match = cell.marker
            if match is None or (columns is not None and cell.column not in columns):
                continue
            text = match.group(2).strip()
            if not text:
                following = self.right_of(cell)
                if following and following[0].marker is None and not following[0].is_label:
                    text = following[0].text
            if text:
                items.setdefault(int(match.group(1)), text[:MAX_ITEM])
        return dict(sorted(items.items()))

    def block(self, start: _Cell | None, rows: range, stops: tuple[str, ...]) -> range:
        """Filas que siguen a un subtítulo, hasta el siguiente subtítulo o el fin de la sección."""
        if start is None:
            return range(0)
        end = rows.stop
        for row in range(start.row + 1, rows.stop):
            cells = self.rows.get(row, [])
            if cells and cells[0].key.startswith(stops):
                end = row
                break
        return range(start.row + 1, end)


def _split(text: str) -> tuple[str, ...]:
    """Parte «Diseño mecánico, Sensores, Inglés (leído, escrito)» en sus elementos,
    sin romper lo que va entre paréntesis."""
    items, depth, current = [], 0, ""
    for char in text:
        if char == "(":
            depth += 1
        elif char == ")":
            depth = max(0, depth - 1)
        if char in ",;\n" and depth == 0:
            items.append(current)
            current = ""
        else:
            current += char
    items.append(current)
    cleaned = (" ".join(item.split()).strip(" .") for item in items)
    return tuple(dict.fromkeys(item for item in cleaned if item))[:MAX_ITEMS]


def _checked(sheet: _Sheet, rows: range) -> list[str]:
    """Etiquetas cuya casilla (la celda de su derecha) está marcada."""
    marked = []
    for cell in sheet.cells(rows):
        following = sheet.right_of(cell)
        if cell.checked is None and following and following[0].checked:
            marked.append(cell.text.rstrip(":"))
    return marked


def _excluded(sheet: _Sheet, rows: range) -> list[str]:
    """Edad y género que pide el formato: se informan, no se copian."""
    found = []
    age = sheet.find("edad", rows)
    if age is not None:
        limits = []
        for label, name in (("minima", "mínima"), ("maxima", "máxima")):
            value = sheet.value_of(label, range(age.row, age.row + 1))
            if value:
                limits.append(f"{name} {value}")
        if limits:
            found.append("edad " + " y ".join(limits))
    gender = sheet.find("genero", rows)
    if gender is not None:
        marked = [m for m in _checked(sheet, range(gender.row, gender.row + 1)) if m != "Género"]
        if any(fold(m) != "indistinto" for m in marked):
            found.append("género " + " o ".join(m.lower() for m in marked))
    return found


def parse_profile_format(grid: Grid) -> FormatReading | None:
    """Lee una hoja con el formato de la empresa. Devuelve ``None`` si la hoja
    no es ese formato (entonces el documento se trata como cualquier otro)."""
    sheet = _Sheet(grid)
    if any(name not in sheet.sections for name in _REQUIRED):
        return None
    identification = sheet.section("identification")
    if sheet.find("nombre del puesto", identification) is None:
        return None
    notices: list[str] = []

    # Encabezado e identificación del puesto.
    header = range(1, sheet.sections["identification"])
    values: dict[str, object] = {
        "document_version": sheet.value_of("version del perfil", header),
        "position_name": sheet.value_of("nombre del puesto", identification),
        "area": sheet.value_of("area o departamento", identification),
        "location": sheet.value_of("ubicacion", identification),
        "reports_to": sheet.value_of("reporta a", identification),
        "supervises": sheet.value_of("supervisa a", identification),
        "contract_type": sheet.value_of("tipo de contratacion", identification),
        "work_mode": sheet.value_of("modalidad", identification),
        "schedule": sheet.value_of("horario", identification),
        "offer": sheet.value_of("oferta", identification),
    }
    updated = sheet.value_of("fecha de actualizacion", header)
    try:
        values["document_date"] = date.fromisoformat(updated).isoformat() if updated else ""
    except ValueError:
        values["document_date"] = ""
        notices.append(f"No se pudo leer la fecha de actualización («{updated}»).")
    excluded = _excluded(sheet, identification)
    if excluded:
        notices.append(
            "El formato pide " + " y ".join(excluded) + ". No se copió al perfil: la edad y "
            "el género no se usan para evaluar a las personas candidatas."
        )

    # Propósito: el texto que sigue al título de la sección.
    purpose = [c.text for c in sheet.cells(sheet.section("purpose")) if not c.is_label]
    values["objective"] = "\n".join(purpose)[:MAX_TEXT]

    scope = sheet.section("scope")
    values["internal_relations"] = sheet.value_of("relaciones internas", scope, MAX_TEXT)
    values["external_relations"] = sheet.value_of("relaciones externas", scope, MAX_TEXT)

    # Requisitos del puesto.
    requirements = sheet.section("requirements")
    stops = ("requisitos indispensables", "conocimientos especificos", "habilidades blandas")
    academic = sheet.find("formacion academica", requirements)
    specialty = sheet.find("especialidad", requirements)
    if academic is not None:
        end = specialty.row if specialty and specialty.row > academic.row else academic.row + 3
        marked = {
            option(label, EDUCATION_LEVELS) for label in _checked(sheet, range(academic.row, end))
        }
        values["education_levels"] = tuple(level for level in EDUCATION_LEVELS if level in marked)
    values["specialty"] = sheet.value_of("especialidad", requirements)
    values["experience"] = sheet.value_of("experiencia previa", requirements, MAX_TEXT)
    must = sheet.block(sheet.find("requisitos indispensables", requirements), requirements, stops)
    values["must_have"] = tuple(dict.fromkeys(sheet.numbered(must).values()))
    values["knowledge"] = _split(
        sheet.value_of("conocimientos especificos", requirements, MAX_TEXT)
    )
    soft = sheet.block(sheet.find("habilidades blandas", requirements), requirements, stops)
    values["skills"] = tuple(dict.fromkeys(sheet.numbered(soft).values()))

    # Funciones y actividades (con su periodicidad).
    functions = sheet.section("functions")
    stops = ("funciones del puesto", "actividades del puesto")
    listed = sheet.block(sheet.find("funciones del puesto", functions), functions, stops)
    values["functions"] = tuple(dict.fromkeys(sheet.numbered(listed).values()))
    heading = sheet.find("actividades del puesto", functions)
    block = sheet.block(heading, functions, stops)
    frequency = sheet.find("periodicidad", range(heading.row, heading.row + 1)) if heading else None
    split = frequency.column if frequency else 10**6
    descriptions = sheet.numbered(block, range(1, split))
    frequencies = sheet.numbered(block, range(split, 10**6)) if frequency else {}
    activities = []
    for number, description in descriptions.items():
        written = frequencies.get(number, "")
        known = option(written, FREQUENCIES) or ""
        if written and not known:
            notices.append(
                f"Actividad {number}: la periodicidad «{written}» no es una de las del "
                "formato (" + ", ".join(FREQUENCIES) + ") y se dejó vacía."
            )
        activities.append(Activity(description, known))
    values["activities"] = tuple(activities[:MAX_ROWS])

    # Indicadores: tabla con las columnas KPI, METAS y FÓRMULA.
    kpis: list[Kpi] = []
    table = sheet.section("kpis")
    head = next(
        (
            row
            for row in table
            if any(cell.key == "kpi" for cell in sheet.rows.get(row, []))
            and any(cell.key.startswith("meta") for cell in sheet.rows.get(row, []))
        ),
        None,
    )
    if head is not None:
        columns = {
            name: next((c.column for c in sheet.rows[head] if c.key.startswith(name)), 10**6)
            for name in ("meta", "formula")
        }
        for row in range(head + 1, table.stop):
            cells = sheet.rows.get(row, [])
            if cells and cells[0].key.startswith(_FOOTER):
                break
            name = " ".join(c.text for c in cells if c.column < columns["meta"])
            goal = " ".join(
                c.text for c in cells if columns["meta"] <= c.column < columns["formula"]
            )
            formula = " ".join(c.text for c in cells if c.column >= columns["formula"])
            if name:
                kpis.append(Kpi(name[:MAX_ITEM], goal[:MAX_ITEM], formula[:MAX_ITEM]))
    values["kpis"] = tuple(kpis[:MAX_ROWS])

    content = ProfileContent(**values)  # type: ignore[arg-type]
    if not content.objective:
        notices.append("El formato no trae el propósito del puesto: escríbelo antes de guardar.")
    if not content.must_have:
        notices.append(
            "El formato no trae requisitos indispensables: agrega al menos uno antes de guardar."
        )
    return FormatReading(content, tuple(notices))
