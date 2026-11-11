"""Excel del lote y ZIP con los originales."""

from __future__ import annotations

import csv
import io
import zipfile
from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass
from typing import BinaryIO

from openpyxl import Workbook
from openpyxl.styles import Font

from app.core.spreadsheets import safe_cell

CLASSIFICATION_LABELS = {
    "ACEPTADO_IA": "Aceptado por IA",
    "RECHAZADO_IA": "Rechazado por IA",
    "NO_EVALUABLE": "No evaluable",
}


@dataclass(frozen=True)
class ReportRow:
    file_name: str
    sha256: str
    classification: str | None
    score: str | None
    no_evidence: int
    quality_average: str | None
    digitization_suspect: bool
    reason: str
    notes: str
    criteria: list[
        tuple[str, str, str, str, str, str]
    ]  # código, nombre, peso, nivel, evidencia, just.


def build_excel(
    target: BinaryIO, *, summary: list[tuple[str, str]], rows: list[ReportRow], threshold: str
) -> None:
    book = Workbook()
    bold = Font(bold=True)

    sheet = book.active
    sheet.title = "Resumen"
    sheet.append(
        [
            "Archivo",
            "Clasificación inicial",
            "Puntuación (0 a 100)",
            "Umbral",
            "Criterios sin evidencia",
            "Calidad documental (0 a 4)",
            "Posible error de digitalización",
            "Motivo",
            "Observaciones",
            "SHA-256",
        ]
    )
    for row in rows:
        sheet.append(
            [
                safe_cell(row.file_name),
                CLASSIFICATION_LABELS.get(row.classification or "", "Sin evaluar"),
                float(row.score) if row.score is not None else None,
                float(threshold),
                row.no_evidence,
                float(row.quality_average) if row.quality_average is not None else None,
                "Sí" if row.digitization_suspect else "No",
                safe_cell(row.reason),
                safe_cell(row.notes),
                row.sha256,
            ]
        )

    detail = book.create_sheet("Criterios")
    detail.append(
        ["Archivo", "Criterio", "Requisito", "Peso", "Nivel (0 a 4)", "Evidencia", "Justificación"]
    )
    for row in rows:
        for code, name, weight, level, evidence, justification in row.criteria:
            detail.append(
                [
                    safe_cell(row.file_name),
                    code,
                    safe_cell(name),
                    float(weight),
                    safe_cell(level),
                    safe_cell(evidence),
                    safe_cell(justification),
                ]
            )

    info = book.create_sheet("Lote")
    for label, value in summary:
        info.append([label, safe_cell(value)])
    for current in (sheet, detail):
        for cell in current[1]:
            cell.font = bold
        current.freeze_panes = "A2"
    for cell in info["A"]:
        cell.font = bold
    book.save(target)


def _zip_name(position: int, name: str) -> str:
    # El número evita que dos originales con el mismo nombre se pisen.
    return f"{position:03d}_{name}"


def build_zip(
    target: BinaryIO,
    entries: Iterable[tuple[str, str, int, str, str, Callable[[], Iterator[bytes]]]],
) -> int:
    """ZIP con los originales y un manifiesto. Cada entrada: nombre, SHA-256,
    tamaño, clasificación, puntuación y una función que entrega el contenido."""
    manifest = io.StringIO()
    writer = csv.writer(manifest)
    writer.writerow(
        ["archivo_en_zip", "nombre_original", "sha256", "bytes", "clasificacion", "puntuacion"]
    )
    count = 0
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
        for count, (name, sha256, size, classification, score, read) in enumerate(entries, start=1):
            inside = _zip_name(count, name)
            with archive.open(inside, "w") as member:
                for chunk in read():
                    member.write(chunk)
            writer.writerow(
                [safe_cell(inside), safe_cell(name), sha256, size, classification, score]
            )
        archive.writestr("MANIFIESTO.csv", "﻿" + manifest.getvalue())
    return count
