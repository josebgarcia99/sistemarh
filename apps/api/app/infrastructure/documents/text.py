"""Extracción de texto de documentos, dentro del servidor.

Lee PDF con texto, DOCX y hojas de cálculo XLSX (los valores de sus celdas).
Los PDF escaneados y las imágenes se leen con OCR (Tesseract) si está instalado.
Los DOC antiguos requieren una conversión que no está construida: se informan
como formato no legible, sin inventar contenido.
"""

from __future__ import annotations

import logging
import re
import zipfile
from dataclasses import dataclass
from typing import BinaryIO, Protocol
from xml.etree import ElementTree

from pypdf import PdfReader
from pypdf.errors import PyPdfError

from app.infrastructure.documents.ocr import OcrError
from app.infrastructure.documents.spreadsheet import SpreadsheetError, read_sheets, sheets_to_text

# pypdf avisa de cada PDF defectuoso; aquí ya se informa como "ilegible".
logging.getLogger("pypdf").setLevel(logging.ERROR)

MAX_CHARS = 60_000
MIN_CHARS = 50
MAX_PDF_PAGES = 60
MAX_DOCX_XML_BYTES = 20 * 1024 * 1024
_WORD_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


class TextExtractionError(Exception):
    """No se obtuvo texto. ``code``: sin_texto, formato_sin_texto, protegido,
    ilegible u ocr_fallido."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def _pdf(handle: BinaryIO) -> str:
    try:
        reader = PdfReader(handle)
        if reader.is_encrypted:
            raise TextExtractionError("protegido")
        pages = reader.pages[:MAX_PDF_PAGES]
        return "\n".join(page.extract_text() or "" for page in pages)
    except TextExtractionError:
        raise
    except (PyPdfError, ValueError, KeyError, OSError, RecursionError) as error:
        raise TextExtractionError("ilegible") from error


def _docx(handle: BinaryIO) -> str:
    try:
        with zipfile.ZipFile(handle) as archive:
            if archive.getinfo("word/document.xml").file_size > MAX_DOCX_XML_BYTES:
                raise TextExtractionError("ilegible")
            # El analizador de la biblioteca estándar no resuelve entidades externas.
            root = ElementTree.fromstring(archive.read("word/document.xml"))  # noqa: S314
    except TextExtractionError:
        raise
    except (zipfile.BadZipFile, KeyError, ElementTree.ParseError, OSError) as error:
        raise TextExtractionError("ilegible") from error
    paragraphs = []
    for paragraph in root.iter(f"{_WORD_NS}p"):
        parts = []
        for node in paragraph.iter():
            if node.tag == f"{_WORD_NS}t":
                parts.append(node.text or "")
            elif node.tag in (f"{_WORD_NS}tab", f"{_WORD_NS}br"):
                parts.append(" ")
        paragraphs.append("".join(parts))
    return "\n".join(paragraphs)


@dataclass(frozen=True)
class ExtractedText:
    text: str
    # Hubo que recortarlo por su longitud.
    truncated: bool
    # Salió de reconocer imágenes: puede traer errores que no son de quien lo escribió.
    ocr: bool


class Ocr(Protocol):
    @property
    def available(self) -> bool: ...

    def image_to_text(self, image: bytes) -> str: ...

    def pdf_to_text(self, handle: BinaryIO) -> str: ...


IMAGE_EXTENSIONS = frozenset({"jpg", "jpeg", "png"})


def _normalize(text: str) -> str:
    lines = [re.sub(r"[ \t\u00a0]+", " ", line).strip() for line in text.splitlines()]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


def extract_text(handle: BinaryIO, extension: str, ocr: Ocr | None = None) -> ExtractedText:
    """Texto de un PDF, un DOCX, un XLSX o una imagen.

    Un PDF sin capa de texto (escaneado) y las imágenes se leen con OCR si está
    disponible. Los DOC antiguos requieren conversión, que no está construida."""
    used_ocr = False
    can_ocr = ocr is not None and ocr.available
    try:
        if extension == "pdf":
            text = _normalize(_pdf(handle))
            if len(text) < MIN_CHARS and can_ocr:
                handle.seek(0)
                text, used_ocr = _normalize(ocr.pdf_to_text(handle)), True
        elif extension == "docx":
            text = _normalize(_docx(handle))
        elif extension == "xlsx":
            text = _normalize(sheets_to_text(read_sheets(handle)))
        elif extension in IMAGE_EXTENSIONS and can_ocr:
            text, used_ocr = _normalize(ocr.image_to_text(handle.read())), True
        else:
            raise TextExtractionError("formato_sin_texto")
    except OcrError as error:
        raise TextExtractionError("ocr_fallido") from error
    except SpreadsheetError as error:
        raise TextExtractionError("ilegible") from error
    if len(text) < MIN_CHARS:
        raise TextExtractionError("sin_texto")
    return ExtractedText(text[:MAX_CHARS], len(text) > MAX_CHARS, used_ocr)
