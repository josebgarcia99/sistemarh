"""Permanencia laboral, calculada en Python a partir de los periodos del CV.

Es información para quien revisa. No es un criterio de evaluación y una
permanencia breve nunca es motivo automático de rechazo.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from statistics import median

_PERIOD = re.compile(r"^(\d{4})(?:-(\d{2}))?$")


@dataclass(frozen=True)
class JobTenure:
    title: str
    company: str
    start: str
    end: str
    current: bool
    # Meses de duración; vacío si faltan fechas.
    months: int | None
    # Alguna fecha solo traía el año: la duración es aproximada.
    approximate: bool


@dataclass(frozen=True)
class TenureSummary:
    jobs: tuple[JobTenure, ...]
    average_months: float | None
    median_months: float | None
    # Meses con algún empleo, sin contar dos veces los periodos simultáneos.
    total_months: int
    overlaps: int
    incomplete: int


def _month_index(text: str, *, end: bool) -> tuple[int, bool] | None:
    """Meses desde el año 0. Si solo hay año, toma enero (inicio) o diciembre (fin)."""
    match = _PERIOD.match(text or "")
    if not match:
        return None
    year, month = int(match.group(1)), match.group(2)
    if not 1950 <= year <= 2100:
        return None
    if month is None:
        return year * 12 + (11 if end else 0), True
    return year * 12 + int(month) - 1, False


def summarize(jobs: list[dict[str, object]], today: date) -> TenureSummary:
    now = today.year * 12 + today.month - 1
    rows: list[JobTenure] = []
    spans: list[tuple[int, int]] = []
    for job in jobs:
        start_text, end_text = str(job.get("inicio") or ""), str(job.get("fin") or "")
        current = job.get("actual") is True
        start = _month_index(start_text, end=False)
        end = (now, False) if current and not end_text else _month_index(end_text, end=True)
        months = None
        approximate = False
        if start is not None and end is not None and start[0] <= min(end[0], now):
            last = min(end[0], now)
            months = last - start[0] + 1
            approximate = start[1] or end[1]
            spans.append((start[0], last))
        rows.append(
            JobTenure(
                title=str(job.get("puesto") or ""),
                company=str(job.get("empresa") or ""),
                start=start_text,
                end=end_text,
                current=current,
                months=months,
                approximate=approximate,
            )
        )
    durations = [row.months for row in rows if row.months is not None]
    covered: set[int] = set()
    for first, last in spans:
        covered.update(range(first, last + 1))
    overlaps = sum(
        1
        for index, (first, last) in enumerate(spans)
        for other_first, other_last in spans[index + 1 :]
        if first <= other_last and other_first <= last
    )
    return TenureSummary(
        jobs=tuple(rows),
        average_months=round(sum(durations) / len(durations), 1) if durations else None,
        median_months=float(median(durations)) if durations else None,
        total_months=len(covered),
        overlaps=overlaps,
        incomplete=len(rows) - len(durations),
    )
