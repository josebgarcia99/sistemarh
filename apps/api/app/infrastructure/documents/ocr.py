"""Lectura de documentos escaneados (OCR) dentro del servidor.

Usa Tesseract, un programa instalado en el propio servidor: ninguna imagen
sale hacia servicios externos. Las páginas de un PDF se convierten en imagen
con pypdfium2 y se leen una por una.
"""

from __future__ import annotations

import io
import logging
import shutil
import subprocess  # noqa: S404  (se invoca un programa local con argumentos fijos)
from typing import BinaryIO

logger = logging.getLogger(__name__)

MAX_PAGES = 15
RENDER_SCALE = 2.2  # unas 160 ppp: suficiente para texto impreso
MAX_PIXELS = 40_000_000
_TIMEOUT_SECONDS = 90


class OcrError(Exception):
    """El OCR no pudo leer el documento."""


class TesseractOcr:
    def __init__(self, languages: str = "spa+eng", command: str = "tesseract") -> None:
        self._languages = languages
        self._command = shutil.which(command)

    @property
    def available(self) -> bool:
        return self._command is not None

    def image_to_text(self, image: bytes) -> str:
        if self._command is None:
            raise OcrError("Tesseract no está instalado.")
        try:
            completed = subprocess.run(  # noqa: S603
                [self._command, "stdin", "stdout", "-l", self._languages, "--psm", "3"],
                input=image,
                capture_output=True,
                timeout=_TIMEOUT_SECONDS,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            raise OcrError("Tesseract no respondió.") from error
        if completed.returncode != 0:
            logger.warning("Tesseract terminó con error al leer una imagen")
            raise OcrError("Tesseract no pudo leer la imagen.")
        return completed.stdout.decode("utf-8", errors="replace")

    def pdf_to_text(self, handle: BinaryIO) -> str:
        import pypdfium2

        try:
            document = pypdfium2.PdfDocument(handle.read())
        except Exception as error:
            raise OcrError("El PDF no se pudo abrir.") from error
        texts = []
        try:
            for index in range(min(len(document), MAX_PAGES)):
                page = document[index]
                width, height = page.get_size()
                scale = RENDER_SCALE
                if width * height * scale * scale > MAX_PIXELS:
                    scale = (MAX_PIXELS / (width * height)) ** 0.5
                buffer = io.BytesIO()
                page.render(scale=scale, grayscale=True).to_pil().save(buffer, format="PNG")
                texts.append(self.image_to_text(buffer.getvalue()))
        except OcrError:
            raise
        except Exception as error:
            raise OcrError("No se pudieron leer las páginas del PDF.") from error
        finally:
            document.close()
        return "\n".join(texts)
