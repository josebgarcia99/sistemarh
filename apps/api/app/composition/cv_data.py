"""Los datos de un CV tal como deben verse en un expediente."""

from __future__ import annotations

from typing import Any

from app.modules.cv_processing.domain.extraction import is_complete, with_previous
from app.modules.cv_processing.domain.models import BatchItem, CvBatchRepository


def cv_data(batches: CvBatchRepository, item: BatchItem | None) -> dict[str, Any]:
    """Los datos del CV de una evaluación. Si en esa evaluación la IA no logró
    ordenarlos (falló, o no había modelo asignado), se toman los de la evaluación
    más reciente del mismo archivo que sí los tenga: experiencia, estudios y
    habilidades no dependen del prompt y no deben desaparecer del expediente
    porque el CV se volvió a evaluar."""
    if item is None:
        return {}
    if is_complete(item.extraction):
        return item.extraction or {}
    return with_previous(item.extraction, batches.complete_extraction(item.file_id))
