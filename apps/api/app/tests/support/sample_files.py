"""Archivos sintéticos para las pruebas. Ninguno contiene datos reales."""

from __future__ import annotations

import io
import zipfile

PDF = (
    b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\n"
    b"% Curriculum ficticio para pruebas\ntrailer\n<< /Root 1 0 R >>\n%%EOF\n"
)
PNG = bytes.fromhex("89504E470D0A1A0A") + b"\x00\x00\x00\rIHDR" + b"\x00" * 17 + b"IEND\xaeB`\x82"
JPG = b"\xff\xd8\xff\xe0\x00\x10JFIF" + b"\x00" * 32 + b"\xff\xd9"


def docx(*, macros: bool = False, body: str = "Documento ficticio") -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            "[Content_Types].xml",
            '<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/'
            'content-types"><Default Extension="xml" ContentType="application/xml"/></Types>',
        )
        archive.writestr("word/document.xml", f"<w:document><w:t>{body}</w:t></w:document>")
        if macros:
            archive.writestr("word/vbaProject.bin", b"macro ficticia")
    return buffer.getvalue()


def doc(*, macros: bool = False) -> bytes:
    data = bytes.fromhex("D0CF11E0A1B11AE1") + b"\x00" * 64 + "WordDocument".encode("utf-16-le")
    if macros:
        data += b"\x00" * 8 + "_VBA_PROJECT".encode("utf-16-le")
    return data + b"\x00" * 64


def zip_without_word() -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("notas.txt", "no es un documento Word")
    return buffer.getvalue()
