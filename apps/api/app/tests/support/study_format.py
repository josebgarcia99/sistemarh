"""Un Excel inventado con la misma estructura que el formato de la empresa
«SGC.F3.RH. Estudio socioeconómico»: bandas de apartado, etiquetas con su
dato en la misma celda, casillas, tablas y recuadros. No es el formato real
ni lleva datos de nadie; sirve para probar que cada dato cae en su lugar."""

from __future__ import annotations

import io

from openpyxl import Workbook
from openpyxl.drawing.image import Image as SheetImage
from PIL import Image


def study_format_xlsx(*, family_rows: int = 2) -> bytes:
    book = Workbook()
    sheet = book.active
    row = 0

    def band(title: str) -> int:
        nonlocal row
        row += 2
        sheet.cell(row, 2, title)
        sheet.merge_cells(start_row=row, start_column=2, end_row=row, end_column=13)
        return row

    def put(line: int, column: int, text: object, until: int | None = None) -> None:
        sheet.cell(line, column, text)
        if until:
            sheet.merge_cells(start_row=line, start_column=column, end_row=line, end_column=until)

    # Un logotipo, como en el formato real: así la hoja ya tiene imágenes.
    logo = io.BytesIO()
    Image.new("RGB", (40, 40), (200, 160, 40)).save(logo, format="JPEG")
    logo.seek(0)
    sheet.add_image(SheetImage(logo), "B1")

    put(3, 11, "Fecha de aplicación")
    put(4, 11, "Día:")
    put(4, 12, "Mes:")
    put(4, 13, "Año:")
    row = 4

    top = band("DATOS DE IDENTIFICACIÓN")
    put(top + 1, 2, "Nombre completo:", 4)
    put(top + 1, 5, "Fecha de nacimiento:", 7)
    put(top + 1, 8, "Edad:")
    put(top + 1, 11, "Domicilio: ", 13)
    put(top + 2, 9, "RFC o CURP:", 11)
    row = top + 2

    top = band("ESTADO CIVIL")
    for index, name in enumerate(("Soltero (a):", "Casado (a):", "Divorciado(a):")):
        put(top + 1, 2 + index * 2, name)
        put(top + 1, 3 + index * 2, False)
    row = top + 1

    top = band("FORMACIÓN ACADÉMICA")
    for column, name in ((2, "Nivel:"), (3, "Institución:"), (5, "Periodo:"), (7, "Lugar:")):
        put(top + 1, column, name)
    put(top + 1, 9, "Documento obtenido:")
    put(top + 1, 10, "Mostró documento:")
    put(top + 1, 11, "Observaciones:", 13)
    # Dos renglones en blanco para datos; como en el formato real, el apartado
    # siguiente empieza justo después.
    row = top + 2

    top = band("VERIFICACIÓN DE DOCUMENTOS")
    put(top + 1, 2, "INE:")
    put(top + 1, 3, False)
    put(top + 1, 4, "CURP:")
    put(top + 1, 5, False)
    # Como en el formato real, aquí queda una celda vacía antes de la casilla.
    put(top + 2, 5, "Comprobante de estudios:")
    put(top + 2, 7, False)
    row = top + 2

    top = band("REDES SOCIALES")
    put(top + 1, 2, "Correo electrónico:", 5)
    put(top + 2, 4, "Tiktok:", 7)
    put(top + 3, 2, "Observaciones:", 13)
    row = top + 3

    top = band("CONDICIONES DEL INMUEBLE ")
    put(top + 1, 2, "Tenencia de la vivienda:", 7)
    put(top + 1, 8, "Tipo de vivienda:", 13)
    put(top + 2, 2, "Propia:", 3)
    put(top + 2, 5, "Rentada:", 6)
    put(top + 2, 8, "Casa:", 9)
    put(top + 2, 11, "Multi familiar:", 12)
    put(top + 3, 2, "Automóvil:", 7)
    put(top + 3, 8, "Techo es:", 13)
    put(top + 4, 2, "Cuántos:", 3)
    put(top + 4, 5, "Financiado:", 6)
    put(top + 4, 8, "Lámina:", 9)
    put(top + 4, 11, "Concreto:", 12)
    put(top + 5, 2, "Distribución:", 7)
    put(top + 5, 8, "Suelo es:", 13)
    put(top + 6, 2, "Dormitorios: ", 3)
    put(top + 6, 5, "Baño:", 6)
    put(top + 6, 8, "Concreto:", 9)
    put(top + 6, 11, "Tierra: ", 12)
    row = top + 6

    top = band("ECONOMÍA FAMILIAR ")
    put(top + 1, 2, "Alimentación:", 3)
    put(top + 1, 4, "Renta:", 5)
    put(top + 1, 6, "Otro:", 7)
    put(top + 2, 2, "Total ingreso mensual:", 3)
    put(top + 2, 6, "¿Tiene déficit?    ", 9)
    put(top + 2, 10, "¿Cómo lo cubre?", 13)
    put(top + 3, 6, "¿Cuánto?", 9)
    row = top + 3

    top = band("CUESTIONARIO DE SALUD")
    put(top + 1, 2, "Tipo de sangre:", 5)
    put(top + 2, 2, "¿Padece alguna enfermedad crónica o degenerativa?", 5)
    put(top + 2, 10, "¿Alergias?", 13)
    put(top + 3, 2, "SÍ", 3)
    put(top + 3, 4, "NO", 5)
    put(top + 3, 6, "Médicos:")
    put(top + 3, 10, "Sí", 11)
    put(top + 3, 12, "No", 13)
    put(top + 4, 2, "¿Cuál?", 5)
    put(top + 4, 10, "¿Cuáles?", 13)
    put(top + 5, 2, "Nombre:", 5)
    put(top + 5, 6, "Edad:", 7)
    put(top + 5, 8, "Parentesco:", 9)
    put(top + 5, 10, "Enfermedad:", 13)
    # Un renglón para datos y, debajo, el pie de control del documento.
    put(top + 7, 2, "Elabora: Persona Inventada", 5)
    row = top + 7

    top = band("CONTACTOS DE EMERGENCIA")
    for line in (top + 1, top + 2):
        put(line, 2, "Nombre:", 5)
        put(line, 6, "Teléfono:", 8)
        put(line, 9, "Teléfono fijo:", 10)
        put(line, 11, "Parentesco:", 13)
    row = top + 2

    top = band("SITUACIÓN SOCIAL ")
    put(top + 1, 3, "Actividades en tiempo libre")
    put(top + 1, 7, "Religión")
    put(top + 1, 10, "¿Has estado detenido?")
    row = top + 1

    top = band("RELACIÓN CON PERSONAL DE GOBIERNO")
    put(top + 1, 2, "¿Tiene familiares laborando en el gobierno (seguridad)?", 5)
    put(top + 1, 6, "¿En que dependencia?", 9)
    put(top + 1, 10, "¿Qué cargo tiene?", 11)
    put(top + 1, 12, "Parentesco", 13)
    put(top + 2, 2, "Sí", 3)
    put(top + 2, 4, "No", 5)
    put(top + 2, 6, "GN")
    put(top + 2, 7, "SEDENA")
    put(top + 2, 9, "Otra:")
    row = top + 2

    top = band("DATOS FAMILIARES")
    put(top + 1, 2, "Nombre:", 5)
    put(top + 1, 6, "Edad:")
    put(top + 1, 7, "Parentesco:")
    put(top + 1, 8, "Escolaridad:", 9)
    put(top + 1, 10, "Ocupación:", 11)
    put(top + 1, 12, "Ingreso mensual:", 13)
    row = top + 1 + family_rows

    top = band("DATOS DE GEOLOCALIZACÓN DEL DOMICILIO ")
    sheet.merge_cells(start_row=top + 2, start_column=2, end_row=top + 2, end_column=13)
    sheet.row_dimensions[top + 2].height = 200
    row = top + 2

    top = band("SOPORTE FOTOGRÁFICO ")
    for column, name in (
        (2, "CONDICIONES DE HIGIENE"),
        (6, "LOCALIZACIÓN"),
        (10, "FACHADA DE LA VIVIENDA"),
    ):
        sheet.cell(top + 2, column, name)
        sheet.merge_cells(
            start_row=top + 2, start_column=column, end_row=top + 3, end_column=column + 3
        )
    sheet.row_dimensions[top + 2].height = 200
    row = top + 3

    top = band("DICTAMEN (OBSERVACIONES)")
    sheet.merge_cells(start_row=top + 2, start_column=2, end_row=top + 2, end_column=13)
    row = top + 2

    top = band("REPORTE GRÁFICO INTEGRAL CUANTITATIVO ")
    put(top + 1, 2, "INDICADORES", 4)
    put(top + 2, 5, "SUFICIENTE (2)", 7)
    put(top + 2, 8, "MEDIO (1)", 10)
    put(top + 2, 11, "INFERIOR (0)", 13)
    put(top + 3, 2, "TRAYECTORIA ESCOLAR", 4)
    put(top + 4, 2, "SITUACIÓN ECONÓMICA ", 4)
    put(top + 5, 11, "SCORE TOTAL")
    sheet.merge_cells(start_row=top + 5, start_column=12, end_row=top + 5, end_column=13)
    put(top + 7, 2, "¿Se considera condidato?")
    put(top + 8, 2, "Es viable (9-10)")
    put(top + 8, 3, False)
    put(top + 8, 4, "Es viable con reservas (7-8)", 5)
    put(top + 8, 6, False)
    put(top + 10, 2, "Visita domiciliaria:", 3)
    put(top + 10, 4, False)
    put(top + 10, 11, "Telefónica:")
    put(top + 10, 12, False)
    put(top + 14, 3, "Nombre y firma de aplicador")
    put(top + 14, 8, "Nombre y firma del Gerente de Recursos Humanos")
    # Una fórmula del pie del documento: no debe tocarse.
    put(top + 16, 3, "=C3")

    buffer = io.BytesIO()
    book.save(buffer)
    return buffer.getvalue()
