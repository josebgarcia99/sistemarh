"""Validación de archivos: extensión permitida y tipo real por contenido.

No se confía en la extensión ni en el tipo que declara el navegador: se
inspecciona el contenido. Los documentos de Office con macros se rechazan.
"""

from __future__ import annotations

import re
import unicodedata
import zipfile
from enum import StrEnum
from pathlib import Path


class FileKind(StrEnum):
    PDF = "PDF"
    DOCX = "DOCX"
    DOC = "DOC"
    JPG = "JPG"
    PNG = "PNG"


EXTENSIONS: dict[str, FileKind] = {
    "pdf": FileKind.PDF,
    "docx": FileKind.DOCX,
    "doc": FileKind.DOC,
    "jpg": FileKind.JPG,
    "jpeg": FileKind.JPG,
    "png": FileKind.PNG,
}

CONTENT_TYPES: dict[FileKind, str] = {
    FileKind.PDF: "application/pdf",
    FileKind.DOCX: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    FileKind.DOC: "application/msword",
    FileKind.JPG: "image/jpeg",
    FileKind.PNG: "image/png",
}

MAX_NAME_LENGTH = 200
_ZIP_MAX_ENTRIES = 2000
_ZIP_MAX_UNCOMPRESSED = 300 * 1024 * 1024
_OLE_MAGIC = bytes.fromhex("D0CF11E0A1B11AE1")
_PNG_MAGIC = bytes.fromhex("89504E470D0A1A0A")


class FileRejectedError(Exception):
    """El archivo no se acepta. ``code`` es estable; ``message`` es para el usuario."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def sanitize_filename(name: str) -> str:
    """Nombre original seguro para guardar y devolver en la descarga.

    Quita cualquier ruta, caracteres de control y espacios sobrantes. El nombre
    nunca se usa para ubicar el archivo en el disco.
    """
    name = unicodedata.normalize("NFC", name).replace("\\", "/").rsplit("/", 1)[-1]
    name = "".join(ch for ch in name if unicodedata.category(ch)[0] != "C")
    name = re.sub(r'[<>:"|?*]', "_", name)
    name = re.sub(r"\s+", " ", name).strip(" .")
    if not name:
        return "documento"
    if len(name) > MAX_NAME_LENGTH:
        stem, dot, extension = name.rpartition(".")
        if dot and len(extension) <= 10:
            name = stem[: MAX_NAME_LENGTH - len(extension) - 1] + "." + extension
        else:
            name = name[:MAX_NAME_LENGTH]
    return name


def extension_of(name: str) -> str:
    _, dot, extension = name.rpartition(".")
    return extension.lower() if dot else ""


def require_allowed_extension(name: str) -> FileKind:
    kind = EXTENSIONS.get(extension_of(name))
    if kind is None:
        allowed = ", ".join(sorted({e.upper() for e in EXTENSIONS if e != "jpeg"}))
        raise FileRejectedError(
            "extension_no_permitida", f"Formato no permitido. Se aceptan: {allowed}."
        )
    return kind


def _utf16(text: str) -> bytes:
    return text.encode("utf-16-le")


def _inspect_docx(path: Path) -> None:
    mismatch = FileRejectedError(
        "tipo_no_coincide", "El contenido del archivo no corresponde a un documento Word (DOCX)."
    )
    if not zipfile.is_zipfile(path):
        raise mismatch
    try:
        with zipfile.ZipFile(path) as archive:
            entries = archive.infolist()
            names = {entry.filename for entry in entries}
            if "[Content_Types].xml" not in names or "word/document.xml" not in names:
                raise mismatch
            if len(entries) > _ZIP_MAX_ENTRIES or (
                sum(entry.file_size for entry in entries) > _ZIP_MAX_UNCOMPRESSED
            ):
                raise FileRejectedError(
                    "archivo_sospechoso", "El documento tiene una estructura anómala."
                )
            content_types = archive.read("[Content_Types].xml").lower()
            if b"macroenabled" in content_types or any(
                name.lower().endswith("vbaproject.bin") for name in names
            ):
                raise FileRejectedError(
                    "contiene_macros", "El documento contiene macros y no se acepta."
                )
            if archive.testzip() is not None:
                raise FileRejectedError("archivo_danado", "El documento está dañado.")
    except zipfile.BadZipFile as error:
        raise FileRejectedError("archivo_danado", "El documento está dañado.") from error


def _inspect_doc(data: bytes) -> None:
    if not data.startswith(_OLE_MAGIC) or _utf16("WordDocument") not in data:
        raise FileRejectedError(
            "tipo_no_coincide", "El contenido del archivo no corresponde a un documento Word (DOC)."
        )
    if _utf16("_VBA_PROJECT") in data or _utf16("Macros") in data:
        raise FileRejectedError("contiene_macros", "El documento contiene macros y no se acepta.")


def inspect_file(path: Path, name: str) -> FileKind:
    """Comprueba que el contenido corresponde a la extensión. Devuelve el tipo real."""
    kind = require_allowed_extension(name)
    size = path.stat().st_size
    if size == 0:
        raise FileRejectedError("archivo_vacio", "El archivo está vacío.")
    with open(path, "rb") as handle:
        head = handle.read(1024)
        handle.seek(max(0, size - 2048))
        tail = handle.read()

    if kind is FileKind.PDF:
        if not head.startswith(b"%PDF-"):
            raise FileRejectedError(
                "tipo_no_coincide", "El contenido del archivo no corresponde a un PDF."
            )
        if b"%%EOF" not in tail:
            raise FileRejectedError("archivo_danado", "El PDF está incompleto o dañado.")
    elif kind is FileKind.DOCX:
        _inspect_docx(path)
    elif kind is FileKind.DOC:
        _inspect_doc(path.read_bytes())
    elif kind is FileKind.JPG:
        if not head.startswith(b"\xff\xd8\xff"):
            raise FileRejectedError(
                "tipo_no_coincide", "El contenido del archivo no corresponde a una imagen JPG."
            )
    elif kind is FileKind.PNG:
        if not head.startswith(_PNG_MAGIC):
            raise FileRejectedError(
                "tipo_no_coincide", "El contenido del archivo no corresponde a una imagen PNG."
            )
        if b"IEND" not in tail:
            raise FileRejectedError("archivo_danado", "La imagen PNG está incompleta o dañada.")
    return kind
