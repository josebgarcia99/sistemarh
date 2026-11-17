"""Llenado de un Excel existente sin alterar su formato.

Abrir y volver a guardar un Excel con una librería general pierde lo que esa
librería no conoce (casillas, formas, logotipos). Aquí se toca solo lo
necesario: el texto de las celdas indicadas, dentro del XML de la hoja, y las
imágenes que se agreguen. Todo lo demás del archivo se copia byte a byte.
"""

from __future__ import annotations

import html
import io
import re
import zipfile
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from xml.sax.saxutils import escape

MAX_TEMPLATE_BYTES = 5 * 1024 * 1024
MAX_UNCOMPRESSED_BYTES = 40 * 1024 * 1024
_EMU_PER_PIXEL = 9525
_EMU_PER_POINT = 12700
_IMAGE_REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/image"
_DRAWING_REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/drawing"
_RELS_NS = "http://schemas.openxmlformats.org/package/2006/relationships"

_ROW = re.compile(r'<row r="(\d+)"([^>]*?)(?:/>|>(.*?)</row>)', re.DOTALL)
_CELL = re.compile(r'<c r="([A-Z]+)(\d+)"([^>]*?)(?:/>|>(.*?)</c>)', re.DOTALL)
_TEXT = re.compile(r"<t(?:\s[^>]*)?>(.*?)</t>", re.DOTALL)
_MERGE = re.compile(r'<mergeCell ref="([A-Z]+)(\d+):([A-Z]+)(\d+)"')


class TemplateError(ValueError):
    """El archivo no es un Excel que se pueda llenar."""


def column_index(letters: str) -> int:
    number = 0
    for letter in letters:
        number = number * 26 + ord(letter) - 64
    return number


def column_letters(index: int) -> str:
    letters = ""
    while index:
        index, rest = divmod(index - 1, 26)
        letters = chr(65 + rest) + letters
    return letters


@dataclass
class _Row:
    number: int
    attributes: str
    cells: dict[int, str] = field(default_factory=dict)  # columna -> XML de la celda


class SheetTemplate:
    """La primera hoja de un libro de Excel, lista para escribir en sus celdas."""

    def __init__(self, data: bytes) -> None:
        if len(data) > MAX_TEMPLATE_BYTES:
            raise TemplateError("El formato supera el tamaño permitido (5 MB).")
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                infos = archive.infolist()
                if sum(item.file_size for item in infos) > MAX_UNCOMPRESSED_BYTES:
                    raise TemplateError("El formato es demasiado grande al descomprimirse.")
                self._order = [item.filename for item in infos]
                self._files = {item.filename: archive.read(item.filename) for item in infos}
        except zipfile.BadZipFile as error:
            raise TemplateError("El archivo no es un Excel (.xlsx) válido.") from error
        self._sheet_path = self._first_sheet()
        xml = self._files[self._sheet_path].decode("utf-8")
        start, end = xml.find("<sheetData>"), xml.find("</sheetData>")
        if start < 0 or end < 0:
            raise TemplateError("La primera hoja del Excel está vacía.")
        self._head, self._tail = xml[: start + len("<sheetData>")], xml[end:]
        strings = self._shared_strings()
        self._rows: dict[int, _Row] = {}
        self._texts: dict[tuple[int, int], str] = {}
        self._checks: set[tuple[int, int]] = set()
        for number, attributes, body in _ROW.findall(xml[start:end]):
            row = _Row(int(number), attributes)
            for match in _CELL.finditer(body or ""):
                column = column_index(match.group(1))
                row.cells[column] = match.group(0)
                self._read(row.number, column, match.group(3), match.group(4) or "", strings)
            self._rows[row.number] = row
        self.merged = [
            (int(r1), column_index(c1), int(r2), column_index(c2))
            for c1, r1, c2, r2 in _MERGE.findall(self._tail)
        ]
        self._images = 0

    # --- Lectura -------------------------------------------------------------------------

    def _first_sheet(self) -> str:
        workbook = self._files.get("xl/workbook.xml", b"").decode("utf-8", "replace")
        rels = self._files.get("xl/_rels/workbook.xml.rels", b"").decode("utf-8", "replace")
        sheet = re.search(r'<sheet\b[^>]*\br:id="([^"]+)"', workbook)
        if sheet:
            target = re.search(
                rf'<Relationship\b(?=[^>]*\bId="{re.escape(sheet.group(1))}")[^>]*\bTarget="([^"]+)"',
                rels,
            )
            if target:
                path = target.group(1).lstrip("/")
                path = path if path.startswith("xl/") else f"xl/{path}"
                if path in self._files:
                    return path
        if "xl/worksheets/sheet1.xml" in self._files:
            return "xl/worksheets/sheet1.xml"
        raise TemplateError("El Excel no tiene ninguna hoja.")

    def _shared_strings(self) -> list[str]:
        xml = self._files.get("xl/sharedStrings.xml", b"").decode("utf-8", "replace")
        return [
            html.unescape("".join(_TEXT.findall(item)))
            for item in re.findall(r"<si>(.*?)</si>", xml, re.DOTALL)
        ]

    def _read(self, row: int, column: int, attributes: str, body: str, strings: list[str]) -> None:
        kind = re.search(r'\bt="(\w+)"', attributes)
        value = re.search(r"<v>(.*?)</v>", body, re.DOTALL)
        if "<f" in body:
            return  # una fórmula no es una etiqueta ni se sobrescribe
        if kind and kind.group(1) == "s" and value:
            index = int(value.group(1))
            if 0 <= index < len(strings):
                self._texts[(row, column)] = strings[index]
        elif kind and kind.group(1) == "b":
            self._checks.add((row, column))
        elif kind and kind.group(1) in ("str", "inlineStr"):
            text = "".join(_TEXT.findall(body)) or (value.group(1) if value else "")
            self._texts[(row, column)] = html.unescape(text)

    def text(self, row: int, column: int) -> str:
        return self._texts.get((row, column), "")

    def texts(self) -> Iterator[tuple[int, int, str]]:
        """Las celdas con texto, por fila y columna."""
        for (row, column), text in sorted(self._texts.items()):
            yield row, column, text

    def is_check(self, row: int, column: int) -> bool:
        """La celda es una casilla (un verdadero/falso)."""
        return (row, column) in self._checks

    def span(self, row: int, column: int) -> tuple[int, int, int, int]:
        """El bloque combinado que contiene la celda, o la celda sola."""
        for r1, c1, r2, c2 in self.merged:
            if r1 <= row <= r2 and c1 <= column <= c2:
                return r1, c1, r2, c2
        return row, column, row, column

    @property
    def last_row(self) -> int:
        return max(self._rows, default=0)

    # --- Escritura -----------------------------------------------------------------------

    def _style(self, row: int, column: int) -> str:
        cell = self._rows.get(row, _Row(row, "")).cells.get(column, "")
        style = re.search(r'\bs="(\d+)"', cell[: cell.find(">") + 1] if cell else "")
        return f' s="{style.group(1)}"' if style else ""

    def _put(self, row: int, column: int, xml: str) -> None:
        self._rows.setdefault(row, _Row(row, "")).cells[column] = xml

    def set_text(self, row: int, column: int, text: str) -> None:
        """Escribe texto en la celda conservando su estilo."""
        reference = f"{column_letters(column)}{row}"
        clean = "".join(ch for ch in text if ch in "\n\t" or ord(ch) >= 32)[:30000]
        self._put(
            row,
            column,
            f'<c r="{reference}"{self._style(row, column)} t="inlineStr">'
            f'<is><t xml:space="preserve">{escape(clean)}</t></is></c>',
        )
        self._texts[(row, column)] = clean

    def set_check(self, row: int, column: int, checked: bool) -> None:
        """Marca o desmarca una casilla (celda de verdadero/falso)."""
        reference = f"{column_letters(column)}{row}"
        self._put(
            row,
            column,
            f'<c r="{reference}"{self._style(row, column)} t="b"><v>{int(checked)}</v></c>',
        )

    # --- Imágenes ------------------------------------------------------------------------

    def _column_width(self, column: int) -> int:
        """Ancho de la columna en EMU (unidades de dibujo de Office)."""
        width = 8.43
        for low, high, value in re.findall(
            r'<col min="(\d+)" max="(\d+)" width="([\d.]+)"', self._head
        ):
            if int(low) <= column <= int(high):
                width = float(value)
        return int(width * 7 + 5) * _EMU_PER_PIXEL

    def _row_height(self, row: int) -> int:
        found = self._rows.get(row)
        height = re.search(r'\bht="([\d.]+)"', found.attributes) if found else None
        default = re.search(r'defaultRowHeight="([\d.]+)"', self._head)
        points = float(height.group(1)) if height else float(default.group(1)) if default else 15
        return int(points * _EMU_PER_POINT)

    @staticmethod
    def _walk(offset: int, start: int, size: Callable[[int], int]) -> tuple[int, int]:
        """Convierte un desplazamiento desde ``start`` en (índice, resto)."""
        index = start
        while offset > size(index) > 0:
            offset -= size(index)
            index += 1
        return index, offset

    def add_image(
        self, area: tuple[int, int, int, int], jpeg: bytes, width: int, height: int, name: str
    ) -> bool:
        """Coloca una imagen JPEG centrada dentro del bloque de celdas, sin
        deformarla. Devuelve ``False`` si la hoja no admite imágenes."""
        rels_path = self._sheet_path.replace("worksheets/", "worksheets/_rels/", 1) + ".rels"
        rels = self._files.get(rels_path, b"").decode("utf-8", "replace")
        target = re.search(
            rf'<Relationship\b(?=[^>]*\bType="{re.escape(_DRAWING_REL)}")[^>]*\bTarget="([^"]+)"',
            rels,
        )
        if not target or width <= 0 or height <= 0:
            return False
        reference = target.group(1)
        if reference.startswith("/"):
            drawing_path = reference.lstrip("/")
        elif reference.startswith("../"):
            drawing_path = "xl/" + reference[3:]
        else:
            drawing_path = "xl/worksheets/" + reference
        drawing = self._files.get(drawing_path, b"").decode("utf-8", "replace")
        # La etiqueta que cierra el dibujo, con o sin prefijo según quién creó el Excel.
        closing = re.search(r"</(?:\w+:)?wsDr>\s*$", drawing)
        if closing is None:
            return False
        r1, c1, r2, c2 = area
        box_width = sum(self._column_width(column) for column in range(c1, c2 + 1))
        box_height = sum(self._row_height(row) for row in range(r1, r2 + 1))
        scale = min(box_width / width, box_height / height) * 0.9
        image_width, image_height = int(width * scale), int(height * scale)
        column, column_offset = self._walk((box_width - image_width) // 2, c1, self._column_width)
        row, row_offset = self._walk((box_height - image_height) // 2, r1, self._row_height)

        self._images += 1
        media = f"xl/media/estudio_imagen{self._images}.jpeg"
        relation = f"rIdEstudio{self._images}"
        identifier = max((int(n) for n in re.findall(r'cNvPr id="(\d+)"', drawing)), default=1)
        # Los prefijos se declaran aquí mismo: así no importa cuáles use el archivo.
        anchor = (
            '<xdr:oneCellAnchor xmlns:xdr="http://schemas.openxmlformats.org/drawingml/2006/'
            'spreadsheetDrawing" xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">'
            f"<xdr:from><xdr:col>{column - 1}</xdr:col><xdr:colOff>{column_offset}</xdr:colOff>"
            f"<xdr:row>{row - 1}</xdr:row><xdr:rowOff>{row_offset}</xdr:rowOff></xdr:from>"
            f'<xdr:ext cx="{image_width}" cy="{image_height}"/>'
            f'<xdr:pic><xdr:nvPicPr><xdr:cNvPr id="{identifier + 1}" name="{escape(name)}"/>'
            '<xdr:cNvPicPr><a:picLocks noChangeAspect="1"/></xdr:cNvPicPr></xdr:nvPicPr>'
            "<xdr:blipFill>"
            '<a:blip xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" '
            f'r:embed="{relation}"/><a:stretch><a:fillRect/></a:stretch></xdr:blipFill>'
            f'<xdr:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="{image_width}" cy="{image_height}"/>'
            '</a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom></xdr:spPr></xdr:pic>'
            "<xdr:clientData/></xdr:oneCellAnchor>"
        )
        self._files[drawing_path] = (
            drawing[: closing.start()] + anchor + drawing[closing.start() :]
        ).encode("utf-8")

        drawing_rels = drawing_path.replace("drawings/", "drawings/_rels/", 1) + ".rels"
        current = self._files.get(drawing_rels, b"").decode("utf-8", "replace")
        if "</Relationships>" not in current:
            current = (
                '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                f'<Relationships xmlns="{_RELS_NS}"></Relationships>'
            )
            self._order.append(drawing_rels)
        entry = (
            f'<Relationship Id="{relation}" Type="{_IMAGE_REL}" '
            f'Target="../media/{media.rsplit("/", 1)[1]}"/>'
        )
        self._files[drawing_rels] = current.replace(
            "</Relationships>", entry + "</Relationships>", 1
        ).encode("utf-8")
        self._files[media] = jpeg
        self._order.append(media)
        types = self._files["[Content_Types].xml"].decode("utf-8")
        if 'Extension="jpeg"' not in types:
            types = types.replace(
                "</Types>", '<Default Extension="jpeg" ContentType="image/jpeg"/></Types>', 1
            )
            self._files["[Content_Types].xml"] = types.encode("utf-8")
        return True

    # --- Resultado -----------------------------------------------------------------------

    def save(self) -> bytes:
        rows = []
        for number in sorted(self._rows):
            row = self._rows[number]
            cells = "".join(row.cells[column] for column in sorted(row.cells))
            rows.append(f'<row r="{number}"{row.attributes}>{cells}</row>')
        self._files[self._sheet_path] = (self._head + "".join(rows) + self._tail).encode("utf-8")
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
            for name in self._order:
                archive.writestr(name, self._files[name])
        return buffer.getvalue()
