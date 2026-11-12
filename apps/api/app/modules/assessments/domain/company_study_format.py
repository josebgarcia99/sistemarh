"""Plantilla del formato de la empresa «SGC.F3.RH. Estudio socioeconómico» (versión 09).

Las secciones y los campos siguen el orden del formato. Las tablas del formato
(formación académica, familiares, contactos) son campos de tipo tabla.

Dos decisiones de diseño:

- El dictamen, los niveles del reporte cuantitativo, la puntuación total y la
  viabilidad son de **captura manual**: los anota quien aplicó el estudio. El
  sistema no los calcula, la IA no los llena al leer un documento y no entran en
  la síntesis del expediente ni en los reportes.
- Los datos de salud, religión y antecedentes que pide el formato se guardan
  con el mismo permiso reforzado que el resto del estudio y tampoco salen de él.
"""

from __future__ import annotations

from typing import Any

FORMAT_NAME = "SGC.F3.RH. Estudio socioeconómico"
FORMAT_DESCRIPTION = (
    "Formato de la empresa (versión 09). Un administrador puede ajustarlo o crear otros."
)

_YES_NO = ["Sí", "No"]
_LEVELS = ["Suficiente (2)", "Medio (1)", "Inferior (0)"]


def _text(label: str, **extra: Any) -> dict[str, Any]:
    return {"label": label, "type": "TEXTO", **extra}


def _number(label: str, maximum: int | None = None, **extra: Any) -> dict[str, Any]:
    return {"label": label, "type": "NUMERO", "minimum": 0, "maximum": maximum, **extra}


def _options(label: str, options: list[str], **extra: Any) -> dict[str, Any]:
    return {"label": label, "type": "OPCIONES", "options": options, **extra}


def _box(label: str) -> dict[str, Any]:
    return {"label": label, "type": "CASILLA"}


def _table(label: str, columns: list[str]) -> dict[str, Any]:
    return {"label": label, "type": "TABLA", "columns": columns}


def _document(label: str) -> dict[str, Any]:
    return {"label": label, "type": "DOCUMENTO"}


_EXPENSES = (
    "Alimentación",
    "Despensa",
    "Gas",
    "Renta",
    "Agua",
    "Energía eléctrica",
    "Celular",
    "Internet",
    "Educación",
    "Transporte",
    "Gasolina",
    "Mantenimiento a vivienda",
    "Mantenimiento a vehículo",
    "Salud",
    "Entretenimiento",
    "Tarjeta de crédito",
    "Adeudos",
    "Otro gasto",
)

COMPANY_STUDY_TEMPLATE: list[dict[str, Any]] = [
    {
        "title": "Aplicación del estudio",
        "fields": [{"label": "Fecha de aplicación", "type": "FECHA", "required": True}],
    },
    {
        "title": "Datos de identificación",
        "fields": [
            _text("Nombre completo", required=True),
            {"label": "Fecha de nacimiento", "type": "FECHA"},
            _number("Edad", 120),
            _text("Ocupación"),
            {"label": "Domicilio", "type": "PARRAFO"},
            _text("Tiempo de habitar"),
            _text("Lugar de nacimiento"),
            _text("Nacionalidad"),
            _text("Escolaridad"),
            _text("RFC o CURP"),
            _text("Número de teléfono"),
        ],
    },
    {
        "title": "Estado civil",
        "fields": [
            _options(
                "Estado civil",
                [
                    "Soltero (a)",
                    "Casado (a)",
                    "Concubinato",
                    "Separado (a)",
                    "Viudo (a)",
                    "Divorciado (a)",
                ],
            )
        ],
    },
    {
        "title": "Formación académica",
        "fields": [
            _table(
                "Formación académica",
                [
                    "Nivel",
                    "Institución",
                    "Periodo",
                    "Lugar",
                    "Documento obtenido",
                    "Mostró documento",
                    "Observaciones",
                ],
            )
        ],
    },
    {
        "title": "Verificación de documentos",
        "fields": [
            _box("INE"),
            _box("CURP"),
            _box("Acta de nacimiento"),
            _box("Constancia de situación fiscal actualizada (RFC)"),
            _box("Comprobante de domicilio (no mayor a tres meses)"),
            _box("Comprobante de estudios"),
            _box("Datos bancarios"),
        ],
    },
    {
        "title": "Redes sociales",
        "fields": [
            _text("Correo electrónico"),
            _text("Facebook"),
            _text("Instagram"),
            _text("TikTok"),
            _text("X"),
            {"label": "Observaciones de redes sociales", "type": "OBSERVACION"},
        ],
    },
    {
        "title": "Condiciones del inmueble",
        "fields": [
            _options("Tenencia de la vivienda", ["Propia", "Rentada", "Prestada", "Hipotecada"]),
            _options("Tipo de vivienda", ["Cuarto", "Departamento", "Casa", "Multifamiliar"]),
            _options("Orden y limpieza", ["Excelente", "Buena", "Regular", "Mala"]),
            _options("Techo", ["Ladrillo", "Lámina", "Concreto", "Teja"]),
            _options("Suelo", ["Loseta", "Madera", "Concreto", "Tierra"]),
            _number("Automóviles: cuántos", 20),
            _box("Automóvil propio"),
            _box("Automóvil financiado"),
            _box("Automóvil rentado"),
            _number("Distribución: dormitorios", 30),
            _number("Distribución: salas", 30),
            _number("Distribución: cocinas", 30),
            _number("Distribución: comedores", 30),
            _number("Distribución: áreas de lavado", 30),
            _number("Distribución: baños", 30),
            _number("Mobiliario: pantallas", 50),
            _number("Mobiliario: equipos de audio", 50),
            _number("Mobiliario: consolas de videojuegos", 50),
            _number("Mobiliario: electrodomésticos", 50),
            _number("Mobiliario: equipos de cómputo", 50),
            _text("Mobiliario: otro"),
        ],
    },
    {
        "title": "Economía familiar",
        "fields": [
            *[_number(expense) for expense in _EXPENSES],
            _number("Total ingreso mensual"),
            _number("Total egreso mensual"),
            _options("¿Tiene déficit?", _YES_NO),
            _number("¿Cuánto es el déficit?"),
            _text("¿Cómo lo cubre?"),
        ],
    },
    {
        "title": "Cuestionario de salud",
        "fields": [
            _text("Tipo de sangre"),
            _text("Intervenciones quirúrgicas"),
            _text("¿Se encuentra en tratamiento médico, psicológico o psiquiátrico?"),
            _options("¿Padece alguna enfermedad crónica o degenerativa?", _YES_NO),
            _text("¿Cuál enfermedad?"),
            _number("Gastos que genera: médicos"),
            _number("Gastos que genera: hospitalización"),
            _number("Gastos que genera: medicamentos"),
            _options("¿Alergias?", _YES_NO),
            _text("¿Cuáles alergias?"),
            _table(
                "Familiares con enfermedades crónico-degenerativas",
                ["Nombre", "Edad", "Parentesco", "Enfermedad"],
            ),
        ],
    },
    {
        "title": "Contactos de emergencia",
        "fields": [
            _table("Contactos de emergencia", ["Nombre", "Teléfono", "Teléfono fijo", "Parentesco"])
        ],
    },
    {
        "title": "Situación social",
        "fields": [
            {"label": "Actividades en tiempo libre", "type": "PARRAFO"},
            _text("Religión"),
            _text("¿Has estado detenido?"),
        ],
    },
    {
        "title": "Relación con personal de gobierno",
        "fields": [
            _options("¿Tiene familiares laborando en el gobierno (seguridad)?", _YES_NO),
            _options("¿En qué dependencia?", ["GN", "SEDENA", "FGR", "Otra"]),
            _text("Otra dependencia"),
            _text("¿Qué cargo tiene?"),
            _text("Parentesco del familiar en gobierno"),
        ],
    },
    {
        "title": "Datos familiares",
        "fields": [
            _table(
                "Datos familiares",
                ["Nombre", "Edad", "Parentesco", "Escolaridad", "Ocupación", "Ingreso mensual"],
            )
        ],
    },
    {
        "title": "Datos de geolocalización del domicilio",
        "fields": [
            _text("Ubicación del domicilio (enlace o coordenadas)"),
            _document("Mapa de localización"),
        ],
    },
    {
        "title": "Soporte fotográfico",
        "fields": [
            _document("Fotografía: condiciones de higiene"),
            _document("Fotografía: localización"),
            _document("Fotografía: fachada de la vivienda"),
        ],
    },
    {
        "title": "Dictamen",
        "fields": [
            {"label": "Dictamen (observaciones)", "type": "OBSERVACION", "manual_only": True}
        ],
    },
    {
        # Lo anota quien aplicó el estudio. El sistema no lo calcula ni lo usa.
        "title": "Reporte cuantitativo del resultado de la investigación",
        "fields": [
            _options("Trayectoria escolar", _LEVELS, manual_only=True),
            _options("Situación económica", _LEVELS, manual_only=True),
            _options("Resultado de referencias personales", _LEVELS, manual_only=True),
            _options("Resultado de investigación laboral", _LEVELS, manual_only=True),
            _options("Veracidad de la información", _LEVELS, manual_only=True),
            _number("Score total", 10, manual_only=True),
            _options(
                "¿Se considera candidato?",
                ["Es viable (9-10)", "Es viable con reservas (7-8)", "No es viable (0-6)"],
                manual_only=True,
            ),
        ],
    },
    {
        "title": "¿Se verificó la información anterior a través de?",
        "fields": [
            _box("Visita domiciliaria"),
            _box("Visita colateral"),
            _box("Videollamada"),
            _box("Telefónica"),
        ],
    },
    {
        "title": "Ratificación y firmas",
        "fields": [
            _text("Nombre del aplicador", manual_only=True),
            _text("Nombre del Gerente de Recursos Humanos", manual_only=True),
            _document("Formato firmado (escaneado)"),
        ],
    },
]
