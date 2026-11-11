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


_WORD_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


def docx_cv(*paragraphs: str) -> bytes:
    """DOCX válido con texto, para probar la lectura de CV."""
    body = "".join(f"<w:p><w:r><w:t>{text}</w:t></w:r></w:p>" for text in paragraphs)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            "[Content_Types].xml",
            '<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/'
            'content-types"><Default Extension="xml" ContentType="application/xml"/></Types>',
        )
        archive.writestr(
            "word/document.xml",
            f'<?xml version="1.0" encoding="UTF-8"?><w:document xmlns:w="{_WORD_NS}">'
            f"<w:body>{body}</w:body></w:document>",
        )
    return buffer.getvalue()


def pdf_cv(*lines: str) -> bytes:
    """PDF de una página con texto real (solo caracteres ASCII)."""
    text = "BT /F1 11 Tf 40 780 Td 14 TL " + " ".join(
        "(" + line.replace("\\", "").replace("(", "").replace(")", "") + ") Tj T*" for line in lines
    )
    stream = (text + " ET").encode("ascii")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents 4 0 R "
        b"/Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for number, content in enumerate(objects, start=1):
        offsets.append(len(out))
        out += str(number).encode() + b" 0 obj\n" + content + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 " + str(len(objects) + 1).encode() + b"\n0000000000 65535 f \n"
    for offset in offsets:
        out += f"{offset:010d} 00000 n \n".encode()
    out += (
        b"trailer\n<< /Size "
        + str(len(objects) + 1).encode()
        + b" /Root 1 0 R >>\nstartxref\n"
        + str(xref).encode()
        + b"\n%%EOF\n"
    )
    return bytes(out)
