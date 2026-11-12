"""Lectura de hojas de cálculo (XLSX) dentro del servidor.

Solo se leen los valores de las celdas: no se evalúan fórmulas, no se siguen
vínculos externos y no se ejecuta nada del archivo. Antes de abrirlo se revisa
el contenedor (tamaño de cada parte y ausencia de definiciones DTD, que son la
vía de los ataques de expansión de entidades), y la lectura tiene límites de
hojas, filas, columnas y celdas.
"""

from __future__ import annotations

import zipfile
from dataclasses import dataclass
from datetime import date, datetime, time
from typing import BinaryIO

from openpyxl import load_workbook

MAX_SHEETS = 10
MAX_ROWS = 2_000
MAX_COLUMNS = 100
MAX_CELLS = 40_000
MAX_CELL_CHARS = 8_000
MAX_PART_BYTES = 30 * 1024 * 1024
_FORBIDDEN_XML = (b"<!DOCTYPE", b"<!ENTITY")

CellValue = str | bool | int | float | date


class SpreadsheetError(Exception):
    """La hoja de cálculo no se pudo leer."""


@dataclass(frozen=True)
class Sheet:
    name: str
    # (fila, columna) -> valor. Filas y columnas empiezan en 1.
    cells: dict[tuple[int, int], CellValue]


def _check_container(handle: BinaryIO) -> None:
    try:
        with zipfile.ZipFile(handle) as archive:
            for entry in archive.infolist():
                if not entry.filename.lower().endswith((".xml", ".rels", ".vml")):
                    continue
                if entry.file_size > MAX_PART_BYTES:
                    raise SpreadsheetError("parte demasiado grande")
                with archive.open(entry) as part:
                    # Las definiciones van al principio del documento.
                    head = part.read(4096)
                if any(marker in head for marker in _FORBIDDEN_XML):
                    raise SpreadsheetError("definiciones no admitidas")
    except (zipfile.BadZipFile, KeyError, OSError, RuntimeError) as error:
        raise SpreadsheetError("contenedor ilegible") from error
    handle.seek(0)


def _value(raw: object) -> CellValue | None:
    if raw is None or isinstance(raw, bool | int | float):
        return raw
    if isinstance(raw, datetime):
        return raw.date() if raw.time() == time.min else raw
    if isinstance(raw, date):
        return raw
    text = str(raw)[:MAX_CELL_CHARS]
    return text if text.strip() else None


def read_sheets(handle: BinaryIO) -> list[Sheet]:
    """Valores de las hojas visibles de un XLSX. Lanza ``SpreadsheetError``."""
    _check_container(handle)
    sheets: list[Sheet] = []
    total = 0
    try:
        book = load_workbook(handle, read_only=True, data_only=True)
        try:
            for worksheet in book.worksheets[:MAX_SHEETS]:
                if worksheet.sheet_state != "visible":
                    continue
                # El tamaño que declara el archivo puede ser falso: se recalcula al leer.
                worksheet.reset_dimensions()
                cells: dict[tuple[int, int], CellValue] = {}
                for row in worksheet.iter_rows(max_row=MAX_ROWS, max_col=MAX_COLUMNS):
                    for cell in row:
                        value = _value(cell.value)
                        if value is None:
                            continue
                        cells[(cell.row, cell.column)] = value
                        total += 1
                        if total > MAX_CELLS:
                            raise SpreadsheetError("demasiadas celdas")
                if cells:
                    sheets.append(Sheet(str(worksheet.title), cells))
        finally:
            book.close()
    except SpreadsheetError:
        raise
    except Exception as error:  # openpyxl lanza errores muy variados ante archivos dañados
        raise SpreadsheetError("hoja ilegible") from error
    return sheets


def _cell_text(value: CellValue) -> str:
    if isinstance(value, bool):
        return "sí" if value else "no"
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    if isinstance(value, date):
        return value.isoformat()
    return " ".join(str(value).split())


def sheets_to_text(sheets: list[Sheet]) -> str:
    """Texto plano de las hojas: una línea por fila, celdas separadas por « | ».
    Las casillas de verificación quedan como «sí» o «no» junto a su etiqueta."""
    blocks = []
    for sheet in sheets:
        rows: dict[int, list[str]] = {}
        for (row, _column), value in sorted(sheet.cells.items()):
            text = _cell_text(value)
            if text and not text.startswith("#"):
                rows.setdefault(row, []).append(text)
        lines = [" | ".join(parts) for _, parts in sorted(rows.items())]
        blocks.append("\n".join(([f"Hoja: {sheet.name}"] if len(sheets) > 1 else []) + lines))
    return "\n\n".join(blocks)
