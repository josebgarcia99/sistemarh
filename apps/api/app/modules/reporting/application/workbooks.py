"""Excel de indicadores y de postulaciones.

Todo texto que alguien capturó pasa por ``safe_cell`` para que no pueda
ejecutarse como fórmula. Las fechas se escriben en la hora local configurada.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date, datetime, tzinfo
from decimal import Decimal
from typing import BinaryIO

from openpyxl import Workbook
from openpyxl.styles import Font
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.worksheet import Worksheet

from app.core.spreadsheets import safe_cell
from app.modules.reporting.domain.metrics import HistoryRow, Overview

OUTCOME_LABELS = {
    "EN_PROCESO": "En proceso",
    "CONTRATADO": "Contratado",
    "NO_CONTRATADO": "No contratado",
    "DESISTIO": "Desistió",
    "NO_LOCALIZADO": "No localizado",
    "VACANTE_CANCELADA": "Vacante cancelada",
    "OTRO_CIERRE": "Otro cierre",
}
CLASSIFICATION_LABELS = {
    "ACEPTADO_IA": "Aceptado por IA",
    "RECHAZADO_IA": "Rechazado por IA",
    "NO_EVALUABLE": "No evaluable",
}
VACANCY_STATUS_LABELS = {
    "BORRADOR": "Borrador",
    "ABIERTA": "Abierta",
    "PAUSADA": "Pausada",
    "CERRADA": "Cerrada",
    "CANCELADA": "Cancelada",
    "ARCHIVADA": "Archivada",
}
OPERATION_LABELS = {
    "ANALISIS_PERFILES": "Análisis de perfiles",
    "GENERACION_PROMPTS": "Generación de prompts",
    "EXTRACCION_CV": "Extracción de CV",
    "EVALUACION_DOCUMENTAL": "Evaluación de CV",
    "ANALISIS_LLAMADAS": "Análisis de llamadas",
    "LECTURA_DOCUMENTOS": "Lectura de documentos",
    "RESUMEN_PRUEBAS": "Resumen de pruebas",
    "SINTESIS_EXPEDIENTES": "Síntesis de expedientes",
    "DESCRIPCION_FOTOGRAFIAS": "Descripción de fotografías",
}
_BOLD = Font(bold=True)
_DATE_FORMAT = "yyyy-mm-dd hh:mm"
_MAX_WIDTH = 60


def _cell(value: object, zone: tzinfo) -> object:
    if isinstance(value, datetime):
        # Excel no admite zonas horarias: se escribe la hora local.
        return value.astimezone(zone).replace(tzinfo=None)
    if isinstance(value, Decimal):
        return float(value)
    return safe_cell(value)


def _table(
    sheet: Worksheet, headers: list[str], rows: Iterable[list[object]], zone: tzinfo
) -> None:
    sheet.append(headers)
    for cell in sheet[sheet.max_row]:
        cell.font = _BOLD
    header_row = sheet.max_row
    widths = [len(header) for header in headers]
    # La fila se lleva a mano: preguntarle a la hoja cuál es la última obliga a
    # recorrerla entera, y con miles de filas eso se vuelve muy lento.
    current = header_row
    for row in rows:
        values = [_cell(value, zone) for value in row]
        sheet.append(values)
        current += 1
        for index, value in enumerate(values):
            if isinstance(value, datetime):
                sheet.cell(row=current, column=index + 1).number_format = _DATE_FORMAT
                widths[index] = max(widths[index], 16)
            elif value is not None:
                widths[index] = max(widths[index], len(str(value)))
    for index, width in enumerate(widths, start=1):
        sheet.column_dimensions[get_column_letter(index)].width = min(width + 2, _MAX_WIDTH)
    if header_row == 1:
        sheet.freeze_panes = "A2"


def _pairs(sheet: Worksheet, title: str, pairs: list[tuple[str, object]], zone: tzinfo) -> None:
    sheet.append([title])
    sheet.cell(row=sheet.max_row, column=1).font = _BOLD
    for label, value in pairs:
        sheet.append([label, _cell(value, zone)])
    sheet.append([])


def _context(
    sheet: Worksheet,
    *,
    generated_at: datetime,
    generated_by: str,
    filters: dict[str, str],
    zone: tzinfo,
) -> None:
    _pairs(
        sheet,
        "Reporte",
        [
            ("Generado", generated_at.astimezone(zone).strftime("%Y-%m-%d %H:%M")),
            ("Generado por", generated_by),
            ("Zona horaria", str(zone)),
            *(filters.items() if filters else [("Filtros", "Sin filtros")]),
        ],
        zone,
    )


def build_overview(
    target: BinaryIO,
    data: Overview,
    *,
    generated_at: datetime,
    generated_by: str,
    filters: dict[str, str],
    zone: tzinfo,
) -> int:
    """Escribe el Excel de indicadores y devuelve cuántas vacantes incluye."""
    book = Workbook()
    sheet = book.active
    sheet.title = "Resumen"
    _context(
        sheet, generated_at=generated_at, generated_by=generated_by, filters=filters, zone=zone
    )
    snapshot, totals = data.snapshot, data.totals
    _pairs(
        sheet,
        "Hoy",
        [
            ("Vacantes", snapshot.vacancies),
            ("Vacantes abiertas", snapshot.vacancies_open),
            ("Procesos pendientes (postulaciones activas)", snapshot.active_applications),
            ("Candidatos en llamada", snapshot.in_calls),
            ("Pruebas pendientes", snapshot.tests_pending),
            ("Entrevistas pendientes", snapshot.interviews_pending),
        ],
        zone,
    )
    _pairs(
        sheet,
        "En el periodo",
        [
            ("CV analizados", totals.cv_analyzed),
            ("Aceptados por IA", totals.ai_accepted),
            ("Rechazados por IA", totals.ai_rejected),
            ("No evaluables", totals.ai_unevaluable),
            ("Postulaciones nuevas", totals.applications),
            ("Procesos cerrados", totals.closed),
            ("Contrataciones", totals.hires),
            ("Desistimientos", totals.withdrawals),
            ("No contratados", totals.not_hired),
            ("No localizados", totals.not_located),
            ("Vacante cancelada", totals.cancelled),
            ("Otros cierres", totals.other_closures),
            ("Tiempo de cobertura promedio (días)", totals.coverage_days),
        ],
        zone,
    )
    if data.cv_failures is not None and data.ai is not None:
        _pairs(
            sheet,
            "Errores técnicos en el periodo",
            [
                ("CV que no se pudieron evaluar", data.cv_failures),
                ("Fallos de IA", data.ai.failures),
            ],
            zone,
        )
    sheet.column_dimensions["A"].width = 46
    sheet.column_dimensions["B"].width = 28

    _table(
        book.create_sheet("Etapas"),
        [
            "Etapa",
            "Activas hoy",
            "Llegaron (altas del periodo)",
            "Pasan a la siguiente (%)",
            "Días promedio en la etapa",
            "Estancias medidas",
        ],
        ([s.name, s.active, s.reached, s.conversion, s.average_days, s.stays] for s in data.stages),
        zone,
    )
    _table(
        book.create_sheet("Vacantes"),
        [
            "Vacante",
            "Departamento",
            "Estado",
            "Responsable",
            "Plazas",
            "Contrataciones vigentes",
            "Postulaciones activas hoy",
            "CV analizados (periodo)",
            "Postulaciones nuevas (periodo)",
            "Procesos cerrados (periodo)",
            "Contrataciones (periodo)",
            "Cobertura promedio (días)",
        ],
        (
            [
                v.name,
                v.department,
                VACANCY_STATUS_LABELS.get(v.status, v.status),
                v.owner_name,
                v.positions,
                v.hires_total,
                v.active,
                v.cv_analyzed,
                v.applications,
                v.closed,
                v.hires,
                v.coverage_days,
            ]
            for v in data.vacancies
        ),
        zone,
    )
    if data.recruiters is not None:
        _table(
            book.create_sheet("Reclutadores"),
            [
                "Responsable",
                "Vacantes",
                "Vacantes abiertas",
                "Colabora en (vacantes de otros)",
                "Postulaciones activas hoy",
                "Procesos cerrados (periodo)",
                "Contrataciones (periodo)",
            ],
            (
                [
                    r.name,
                    r.vacancies,
                    r.vacancies_open,
                    r.collaborating,
                    r.active,
                    r.closed,
                    r.hires,
                ]
                for r in data.recruiters
            ),
            zone,
        )
    _table(
        book.create_sheet("Mensual"),
        [
            "Mes",
            "CV analizados",
            "Postulaciones nuevas",
            "Procesos cerrados",
            "Contrataciones",
            "Desistimientos",
        ],
        (
            [m.month, m.cv_analyzed, m.applications, m.closed, m.hires, m.withdrawals]
            for m in data.months
        ),
        zone,
    )
    if data.ai is not None:
        _table(
            book.create_sheet("IA"),
            ["Operación", "Llamadas", "Fallos", "Costo estimado (USD)"],
            (
                [OPERATION_LABELS.get(o.operation, o.operation), o.calls, o.failures, o.cost_usd]
                for o in data.ai.operations
            ),
            zone,
        )
    book.save(target)
    return len(data.vacancies)


def _day(value: date | None) -> str | None:
    return value.isoformat() if value else None


def build_history(
    target: BinaryIO,
    rows: list[HistoryRow],
    *,
    generated_at: datetime,
    generated_by: str,
    filters: dict[str, str],
    zone: tzinfo,
) -> int:
    """Escribe el Excel de postulaciones y devuelve cuántas filas incluye."""
    book = Workbook()
    sheet = book.active
    sheet.title = "Postulaciones"
    _table(
        sheet,
        [
            "Candidato",
            "Vacante",
            "Departamento",
            "Responsable",
            "Etapa",
            "Resultado final",
            "Motivo del resultado",
            "Clasificación inicial de la IA",
            "Calificación (0 a 100)",
            "Modelo",
            "Versión del prompt",
            "Alta de la postulación",
            "Carga del CV",
            "Evaluación del CV",
            "Último movimiento",
            "Cierre",
            "Registró el cierre",
            "Fecha de incorporación",
        ],
        (
            [
                r.candidate,
                r.vacancy,
                r.department,
                r.owner_name,
                r.stage,
                OUTCOME_LABELS.get(r.outcome, r.outcome),
                r.outcome_reason,
                CLASSIFICATION_LABELS.get(r.ai_classification or "", None),
                r.ai_score,
                r.model,
                r.prompt_version,
                r.created_at,
                r.cv_uploaded_at,
                r.evaluated_at,
                r.last_movement_at,
                r.closed_at,
                r.closed_by_name,
                _day(r.start_date),
            ]
            for r in rows
        ),
        zone,
    )
    about = book.create_sheet("Acerca del reporte")
    _context(
        about, generated_at=generated_at, generated_by=generated_by, filters=filters, zone=zone
    )
    about.append(["Postulaciones", len(rows)])
    about.column_dimensions["A"].width = 30
    about.column_dimensions["B"].width = 40
    book.save(target)
    return len(rows)
