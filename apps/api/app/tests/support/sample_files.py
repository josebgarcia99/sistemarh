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


# --- Formato «SGC.F15.RH. Perfil de puesto» (datos inventados) ------------------------------

PROFILE_FORMAT_DATA: dict[str, object] = {
    "version": "03",
    "updated": "2026-10-05",
    "name": "Analista de Nómina",
    "area": "Recursos Humanos",
    "location": "Oficina central",
    "reports_to": "Gerencia de RH",
    "supervises": "N/A",
    "contract": "Indefinido",
    "mode": "Híbrido",
    "schedule": "09:00 - 18:00 Lunes - Viernes",
    "offer": "",
    "age_min": 25,
    "age_max": None,
    "gender": "Indistinto",
    "purpose": "Calcular y pagar la nómina quincenal sin errores y a tiempo.",
    "internal": "Contabilidad y Tesorería",
    "external": "IMSS e INFONAVIT",
    "levels": ("Licenciatura", "TSU"),
    "specialty": "Contaduría, Administración",
    "experience": "2 años en cálculo de nómina",
    "must": (
        "Cálculo de nómina quincenal",
        "Cuotas IMSS e INFONAVIT",
        "Cálculo de ISR",
        "Timbrado de recibos",
        "Finiquitos y liquidaciones",
        "Manejo de incidencias\t\t",
    ),
    "knowledge": "Excel (tablas dinámicas, BUSCARV), CONTPAQi Nóminas, Ley Federal del Trabajo\t\t",
    "skills": ("Atención al detalle.", "Confidencialidad.", "Trabajo en equipo."),
    "functions": ("Calcular la nómina.", "Timbrar los recibos.", "Atender dudas del personal."),
    "activities": (
        ("Registrar incidencias.", "Diaria"),
        ("Calcular la nómina quincenal.", "Quincenal"),
        ("Presentar pagos provisionales.", "mensual"),
        ("Conciliar cuentas de nómina.", ""),
    ),
    "kpis": (
        ("Nóminas pagadas a tiempo", "100 % quincenal", "Nóminas a tiempo / nóminas del periodo"),
        ("Errores de cálculo", "Menos de 1 % mensual", ""),
    ),
}


def profile_format_cells(**changes: object) -> dict[str, object]:
    """Celdas del formato de la empresa, con la misma distribución que el original:
    etiquetas con su valor a la derecha, listas numeradas en dos columnas y casillas."""
    data = {**PROFILE_FORMAT_DATA, **changes}
    cells: dict[str, object] = {
        "C4": "#VALUE!",
        "I5": "Versión del perfil:",
        "K5": data["version"],
        "I6": "Fecha de actualización:",
        "K6": data["updated"],
        "C8": "IDENTIFICACIÓN DEL PUESTO",
        "C9": "Nombre del puesto:",
        "E9": data["name"],
        "I9": "Área o departamento:",
        "K9": data["area"],
        "C10": "Ubicación (Oficina central, planta, remoto, home office):",
        "G10": data["location"],
        "C11": "Reporta a:",
        "D11": data["reports_to"],
        "I11": "Supervisa a:",
        "J11": data["supervises"],
        "C12": "Tipo de contratación (Temporal, indefinido, medio tiempo, etc.):",
        "G12": data["contract"],
        "C13": "Modalidad (Presencial, híbrido, remoto):",
        "F13": data["mode"],
        "J13": "Horario:",
        "K13": data["schedule"],
        "C14": "Oferta:",
        "D14": data["offer"],
        "G14": "Edad:",
        "I14": "Mínima:",
        "J14": data["age_min"],
        "K14": "Máxima:",
        "L14": data["age_max"],
        "D15": "Género:",
        "E15": "Masculino",
        "F15": data["gender"] == "Masculino",
        "G15": "Femenino",
        "I15": data["gender"] == "Femenino",
        "J15": "Indistinto",
        "K15": data["gender"] == "Indistinto",
        "C18": "PROPÓSITO DEL PUESTO",
        "C19": data["purpose"],
        "C23": "ALCANCE Y RELACIONES CLAVE",
        "C25": "Relaciones internas:",
        "E25": data["internal"],
        "C26": "Relaciones externas:",
        "E26": data["external"],
        "C29": "REQUISITOS DEL PUESTO",
        "C30": "Formación académica:",
        "C32": "Especialidad:",
        "D32": data["specialty"],
        "F32": "Experiencia previa (Años y tipo de experiencia):",
        "J32": data["experience"],
        "C34": "Requisitos indispensables del puesto (Conocimientos)",
        "C40": "Conocimientos específicos (Software, normativas, idiomas, etc.):",
        "G40": data["knowledge"],
        "C42": "Habilidades blandas (Características personales, ejemplo: Comunicación, "
        "liderazgo, trabajo en equipo, etc.):",
        "C50": "Elabora: Persona Ficticia",
        "C51": "Documento:",
        "D51": "Perfil de puesto",
        "C52": "Clave:",
        "D52": "SGC.F15.RH. Perfil de puesto",
        "C53": "Versión:",
        "D53": "05",
        "C57": "FUNCIONES Y ACTIVIDADES PRINCIPALES (Mín: 6, Máx: 8)",
        "C58": "Funciones del puesto",
        "C68": "Actividades del puesto",
        "I68": "Periodicidad (Ocasional, diaria, semanal, mensual y anual):",
        "C79": "KPI´s Y MEDICIÓN DE DESEMPEÑO",
        "C80": "KPI",
        "F80": "METAS (SEMANALES, QUINCENALES, MENSUALES, TRIMESTRALES Y/O ANUALES)",
        "J80": "FÓRMULA",
        "D90": "Nombre y firma de autorización del Gerente.",
        "C94": "Elabora: Persona Ficticia",
        "C100": "HISTORIAL DE CAMBIOS DE PUESTO",
        "C101": "Descripción del cambio",
        "C112": "HISTORIAL DE CAMBIOS DEL DOCUMENTO",
        "C114": "Creación del documento (Word)",
    }
    levels = {"F30": "Maestría", "I30": "Ingeniería", "K30": "Bachillerato"}
    levels |= {"F31": "Licenciatura", "I31": "TSU", "K31": "Secundaria"}
    for position, label in levels.items():
        column, row = position[0], position[1:]
        cells[position] = label
        cells[f"{chr(ord(column) + 1)}{row}"] = label in data["levels"]  # type: ignore[operator]

    def two_columns(first_row: int, items: tuple[str, ...]) -> None:
        """Diez renglones numerados: 1 a 5 a la izquierda y 6 a 10 a la derecha."""
        for number in range(1, 11):
            left = number <= 5
            row = first_row + (number - 1) % 5
            cells[f"{'C' if left else 'I'}{row}"] = f"{number}.-"
            if number <= len(items):
                cells[f"{'D' if left else 'J'}{row}"] = items[number - 1]

    two_columns(35, data["must"])  # type: ignore[arg-type]
    two_columns(43, data["skills"])  # type: ignore[arg-type]
    for number in range(1, 9):
        cells[f"C{58 + number}"] = f"{number}.-"
        cells[f"C{68 + number}"] = f"{number}.-"
        cells[f"I{68 + number}"] = f"{number}.-"
    for number, text in enumerate(data["functions"], start=1):  # type: ignore[arg-type]
        cells[f"D{58 + number}"] = text
    for number, (text, frequency) in enumerate(data["activities"], start=1):  # type: ignore[arg-type]
        cells[f"D{68 + number}"] = text
        cells[f"J{68 + number}"] = frequency
    for number, (name, goal, formula) in enumerate(data["kpis"], start=1):  # type: ignore[arg-type]
        cells[f"C{80 + number}"] = name
        cells[f"F{80 + number}"] = goal
        cells[f"J{80 + number}"] = formula
    return {position: value for position, value in cells.items() if value not in (None, "")}


def xlsx(cells: dict[str, object], *, title: str = "Perfil de puesto", extra=None) -> bytes:
    """Libro de Excel con las celdas indicadas. ``extra`` recibe el libro para
    añadir hojas u otros cambios antes de guardarlo."""
    from datetime import date

    from openpyxl import Workbook

    book = Workbook()
    sheet = book.active
    sheet.title = title
    for position, value in cells.items():
        if position == "K6" and isinstance(value, str):
            value = date.fromisoformat(value)
        sheet[position] = value
    if extra is not None:
        extra(book)
    buffer = io.BytesIO()
    book.save(buffer)
    return buffer.getvalue()


def profile_format_xlsx(**changes: object) -> bytes:
    return xlsx(profile_format_cells(**changes))


def repack(content: bytes, *, add: dict[str, bytes] | None = None, replace=None) -> bytes:
    """Reescribe un documento de Office cambiando o añadiendo partes del ZIP."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(content)) as source, zipfile.ZipFile(buffer, "w") as target:
        for entry in source.infolist():
            data = source.read(entry)
            if replace is not None:
                data = replace(entry.filename, data)
            target.writestr(entry, data)
        for name, data in (add or {}).items():
            target.writestr(name, data)
    return buffer.getvalue()
