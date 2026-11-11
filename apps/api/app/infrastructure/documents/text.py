"""Extracción de texto de documentos, dentro del servidor.

Hoy lee PDF con texto y DOCX. Los PDF escaneados y las imágenes necesitan OCR,
y los DOC antiguos una conversión: ambos están pendientes, así que se informan
como "sin texto" en lugar de inventar contenido.
"""

from __future__ import annotations

import logging
import re
import zipfile
from typing import BinaryIO
from xml.etree import ElementTree

from pypdf import PdfReader
from pypdf.errors import PyPdfError

# pypdf avisa de cada PDF defectuoso; aquí ya se informa como "ilegible".
logging.getLogger("pypdf").setLevel(logging.ERROR)

MAX_CHARS = 60_000
MIN_CHARS = 50
MAX_PDF_PAGES = 60
MAX_DOCX_XML_BYTES = 20 * 1024 * 1024
_WORD_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


class TextExtractionError(Exception):
    """No se obtuvo texto. ``code``: sin_texto, formato_sin_texto, protegido o ilegible."""

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


def extract_text(handle: BinaryIO, extension: str) -> tuple[str, bool]:
    """Devuelve el texto y si hubo que recortarlo por su longitud."""
    if extension == "pdf":
        text = _pdf(handle)
    elif extension == "docx":
        text = _docx(handle)
    else:
        raise TextExtractionError("formato_sin_texto")
    lines = [re.sub(r"[ \t ]+", " ", line).strip() for line in text.splitlines()]
    text = re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()
    if len(text) < MIN_CHARS:
        raise TextExtractionError("sin_texto")
    return text[:MAX_CHARS], len(text) > MAX_CHARS
