"""El estudio socioeconómico capturado, vaciado en el formato de la empresa.

Parte del Excel en blanco «SGC.F3.RH. Estudio socioeconómico» que cargó un
administrador y escribe cada dato donde va. No depende de posiciones fijas:
busca las etiquetas del formato («Nombre completo:», «Propia:»…) dentro de su
apartado, así que sigue funcionando si el formato gana o pierde renglones.
Lo que no encuentra dónde colocar lo devuelve en una lista, para avisarlo.
"""

from __future__ import annotations

import io
import unicodedata
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from PIL import Image

from app.infrastructure.documents.xlsx_template import SheetTemplate, TemplateError
from app.modules.assessments.domain.models import FieldType, FormTemplateVersion

Cell = tuple[int, int]
# Los apartados del formato, por el texto de su banda de título.
_SECTIONS = (
    "datosdeidentificacion",
    "estadocivil",
    "formacionacademica",
    "verificaciondedocumentos",
    "redessociales",
    "condicionesdelinmueble",
    "economiafamiliar",
    "cuestionariodesalud",
    "contactosdeemergencia",
    "situacionsocial",
    "relacionconpersonaldegobierno",
    "datosfamiliares",
    "datosdegeolocaliza",
    "soportefotografico",
    "dictamen",
    "reportegraficointegral",
)
MARK = "X"


def norm(text: object) -> str:
    """Texto reducido a letras y números, sin acentos: «Divorciado(a):» y
    «Divorciado (a)» quedan iguales."""
    plain = unicodedata.normalize("NFKD", str(text or "")).encode("ascii", "ignore").decode()
    return "".join(ch for ch in plain.lower() if ch.isalnum())


def _date(value: object) -> str:
    try:
        return date.fromisoformat(str(value)).strftime("%d/%m/%Y")
    except ValueError:
        return str(value)


@dataclass
class Filled:
    content: bytes
    # Datos capturados que no se pudieron colocar en el formato.
    unplaced: list[str] = field(default_factory=list)


class StudyWorkbook:
    def __init__(
        self,
        template: bytes,
        version: FormTemplateVersion,
        data: dict[str, Any],
        photo: Callable[[str], bytes | None] | None = None,
    ) -> None:
        self._sheet = SheetTemplate(template)
        self._photo = photo or (lambda file_id: None)
        self._unplaced: list[str] = []
        self._version = version
        self._fields = {item.label: item for item in version.fields}
        answers = data.get("answers") or {}
        self._values = {
            item.label: answers[item.id]["value"]
            for item in version.fields
            if isinstance(answers.get(item.id), dict) and answers[item.id].get("value") is not None
        }
        self._descriptions = {
            item.label: str(answers[item.id].get("description") or "")
            for item in version.fields
            if isinstance(answers.get(item.id), dict)
        }
        self._labels = [(row, column, norm(text)) for row, column, text in self._sheet.texts()]
        # Renglón donde empieza cada apartado y dónde termina (el siguiente apartado).
        # Una banda de título ocupa varias columnas; así no se confunde con un campo.
        starts = sorted(
            (row, key)
            for row, column, text in self._labels
            for key in _SECTIONS
            if text.startswith(key) and self._sheet.span(row, column)[3] - column >= 3
        )
        self._ranges: dict[str, tuple[int, int]] = {}
        for index, (row, key) in enumerate(starts):
            end = starts[index + 1][0] - 1 if index + 1 < len(starts) else self._sheet.last_row
            self._ranges.setdefault(key, (row, end))
        self._first = starts[0][0] if starts else 1

    # --- Búsqueda ------------------------------------------------------------------------

    def _find(
        self,
        label: str,
        rows: tuple[int, int],
        *,
        columns: tuple[int, int] | None = None,
        nth: int = 0,
    ) -> Cell | None:
        wanted = norm(label)
        found = [
            (row, column)
            for row, column, text in self._labels
            if text == wanted
            and rows[0] <= row <= rows[1]
            and (columns is None or columns[0] <= column <= columns[1])
        ]
        return found[nth] if nth < len(found) else None

    def _after(self, cell: Cell) -> Cell:
        """La celda que sigue, a la derecha, al bloque de la etiqueta."""
        row, _, _, last = self._sheet.span(*cell)
        return row, last + 1

    def _section(self, key: str) -> tuple[int, int] | None:
        return self._ranges.get(key)

    # --- Escritura -----------------------------------------------------------------------

    def _inline(self, cell: Cell, value: object) -> None:
        """«Etiqueta: valor» en la misma celda de la etiqueta."""
        label = self._sheet.text(*cell).strip()
        joiner = " " if label.endswith((":", "?")) else ": "
        self._sheet.set_text(*cell, f"{label}{joiner}{value}")

    def _write(self, cell: Cell, value: object) -> None:
        self._sheet.set_text(*cell, str(value))

    def _check(self, cell: Cell) -> None:
        """Marca la casilla que sigue a la etiqueta. A veces queda una celda vacía
        en medio; si no hay casilla, escribe una X junto a la etiqueta."""
        row, column = cell
        for candidate in range(column, column + 3):
            if self._sheet.is_check(row, candidate):
                return self._sheet.set_check(row, candidate, True)
            if self._sheet.text(row, candidate):
                break
        self._sheet.set_text(row, column, MARK)

    def _text_value(self, label: str) -> str | None:
        value = self._values.get(label)
        if value is None or value == "" or value is False:
            return None
        item = self._fields[label]
        return _date(value) if item.type is FieldType.FECHA else str(value)

    def _missing(self, label: str) -> None:
        if label not in self._unplaced:
            self._unplaced.append(label)

    def _place_inline(
        self, label: str, key: str, sheet_label: str | None = None, nth: int = 0
    ) -> None:
        value = self._text_value(label)
        if value is None:
            return
        rows = self._section(key)
        cell = self._find(sheet_label or label, rows, nth=nth) if rows else None
        if cell is None:
            self._missing(label)
        else:
            self._inline(cell, value)

    def _place_option(
        self,
        label: str,
        key: str,
        *,
        header: str | None = None,
        target: str = "check",
        nth: int = 0,
    ) -> None:
        """Marca la opción elegida. ``header`` limita la búsqueda al bloque que
        encabeza esa etiqueta (por ejemplo «Techo es:»)."""
        value = self._values.get(label)
        if not value:
            return
        rows = self._section(key)
        columns = None
        if rows and header:
            top = self._find(header, rows)
            if top is None:
                return self._missing(label)
            _, c1, r2, c2 = self._sheet.span(*top)
            rows, columns = (r2 + 1, min(r2 + 2, rows[1])), (c1, c2)
        cell = self._find(str(value), rows, columns=columns, nth=nth) if rows else None
        if cell is None:
            return self._missing(label)
        if target == "inline":
            self._inline(cell, MARK)
        else:
            self._check(self._after(cell))

    def _place_next(self, label: str, key: str, header: str, sheet_label: str) -> None:
        """Un valor o una marca en la celda que sigue a su etiqueta, dentro del
        bloque que encabeza ``header``."""
        value = self._values.get(label)
        if value in (None, "", False):
            return
        rows = self._section(key)
        top = self._find(header, rows) if rows else None
        if rows is None or top is None:
            return self._missing(label)
        _, c1, r2, c2 = self._sheet.span(*top)
        cell = self._find(sheet_label, (r2 + 1, min(r2 + 3, rows[1])), columns=(c1, c2))
        if cell is None:
            return self._missing(label)
        target = self._after(cell)
        if value is True:
            self._check(target)
        else:
            self._write(target, value)

    def _place_box(self, label: str, key: str, sheet_label: str | None = None) -> None:
        """Una casilla: la celda que sigue a su etiqueta."""
        if self._values.get(label) is not True:
            return
        rows = self._section(key) or (self._first, self._sheet.last_row)
        cell = self._find(sheet_label or label, rows)
        if cell is None:
            return self._missing(label)
        self._check(self._after(cell))

    def _table(self, label: str, key: str, headers: dict[str, str]) -> None:
        """Una tabla: cada columna va bajo su encabezado, un renglón por fila."""
        rows_data = self._values.get(label)
        if not isinstance(rows_data, list) or not rows_data:
            return
        rows = self._section(key)
        item = self._fields[label]
        columns: dict[int, int] = {}
        header_row = None
        for position, name in enumerate(item.columns):
            cell = self._find(headers.get(name, name), rows) if rows else None
            if cell is None:
                continue
            header_row = cell[0] if header_row is None else header_row
            if cell[0] == header_row:
                columns[position] = cell[1]
        if rows is None or header_row is None:
            return self._missing(label)
        row = header_row + 1
        placed = 0
        for values in rows_data:
            if row > rows[1] or any(self._sheet.text(row, c) for c in columns.values()):
                break
            for position, column in columns.items():
                if position < len(values) and values[position] not in (None, ""):
                    self._write((row, column), values[position])
            placed += 1
            row += 1
        if placed < len(rows_data):
            self._unplaced.append(
                f"{label}: solo caben {placed} filas; faltan {len(rows_data) - placed}"
            )

    def _labelled_rows(self, label: str, key: str) -> None:
        """Renglones que ya traen sus etiquetas («Nombre:», «Teléfono:»…)."""
        rows_data = self._values.get(label)
        if not isinstance(rows_data, list) or not rows_data:
            return
        rows = self._section(key)
        item = self._fields[label]
        placed = 0
        for index, values in enumerate(rows_data):
            cells = [self._find(name, rows, nth=index) if rows else None for name in item.columns]
            if not any(cells):
                break
            for cell, value in zip(cells, values, strict=False):
                if cell is not None and value not in (None, ""):
                    self._inline(cell, value)
            placed += 1
        if placed < len(rows_data):
            self._unplaced.append(
                f"{label}: solo caben {placed} filas; faltan {len(rows_data) - placed}"
            )

    def _block_below(self, key: str) -> Cell | None:
        """El recuadro grande que sigue a la banda de un apartado."""
        rows = self._section(key)
        if rows is None:
            return None
        for row in range(rows[0] + 1, min(rows[0] + 4, rows[1] + 1)):
            r1, c1, _, c2 = self._sheet.span(row, 2)
            if c2 > c1 and not self._sheet.text(r1, c1):
                return r1, c1
        return rows[0] + 1, 2

    def _image(self, label: str, area: tuple[int, int, int, int]) -> bool:
        file_id = self._values.get(label)
        content = self._photo(str(file_id)) if file_id else None
        if not content:
            return False
        try:
            with Image.open(io.BytesIO(content)) as picture:
                width, height = picture.size
        except OSError:
            return False
        return self._sheet.add_image(area, content, width, height, label)

    # --- El formato, apartado por apartado ------------------------------------------------

    def fill(self) -> Filled:
        whole = (1, self._sheet.last_row)
        applied = self._values.get("Fecha de aplicación")
        if applied:
            try:
                day = date.fromisoformat(str(applied))
                parts = (("Día", f"{day.day:02d}"), ("Mes", f"{day.month:02d}"), ("Año", day.year))
                cells = [self._find(name, (1, self._first)) for name, _ in parts]
                if all(cells):
                    for cell, (_, value) in zip(cells, parts, strict=True):
                        self._inline(cell, value)  # type: ignore[arg-type]
                else:
                    self._missing("Fecha de aplicación")
            except ValueError:
                self._missing("Fecha de aplicación")

        for label in (
            "Nombre completo",
            "Fecha de nacimiento",
            "Edad",
            "Ocupación",
            "Domicilio",
            "Tiempo de habitar",
            "Lugar de nacimiento",
            "Nacionalidad",
            "Escolaridad",
            "RFC o CURP",
            "Número de teléfono",
        ):
            self._place_inline(label, "datosdeidentificacion")
        self._place_option("Estado civil", "estadocivil")
        self._table("Formación académica", "formacionacademica", {})
        for label in (
            "INE",
            "CURP",
            "Acta de nacimiento",
            "Constancia de situación fiscal actualizada (RFC)",
            "Comprobante de domicilio (no mayor a tres meses)",
            "Comprobante de estudios",
            "Datos bancarios",
        ):
            self._place_box(label, "verificaciondedocumentos")
        for label in ("Correo electrónico", "Facebook", "Instagram", "TikTok", "X"):
            self._place_inline(label, "redessociales")
        self._place_inline("Observaciones de redes sociales", "redessociales", "Observaciones")

        home = "condicionesdelinmueble"
        for label, header in (
            ("Tenencia de la vivienda", "Tenencia de la vivienda"),
            ("Tipo de vivienda", "Tipo de vivienda"),
            ("Orden y limpieza", "Orden y limpieza"),
            ("Techo", "Techo es"),
            ("Suelo", "Suelo es"),
        ):
            self._place_option(label, home, header=header)
        for label, header, sheet_label in (
            ("Automóviles: cuántos", "Automóvil", "Cuántos"),
            ("Automóvil propio", "Automóvil", "Propio"),
            ("Automóvil financiado", "Automóvil", "Financiado"),
            ("Automóvil rentado", "Automóvil", "Rentado"),
            ("Distribución: dormitorios", "Distribución", "Dormitorios"),
            ("Distribución: salas", "Distribución", "Sala"),
            ("Distribución: cocinas", "Distribución", "Cocina"),
            ("Distribución: comedores", "Distribución", "Comedor"),
            ("Distribución: áreas de lavado", "Distribución", "Area de lavado"),
            ("Distribución: baños", "Distribución", "Baño"),
            ("Mobiliario: pantallas", "Mobiliario", "Pantallas"),
            ("Mobiliario: equipos de audio", "Mobiliario", "Equipos de audio"),
            ("Mobiliario: consolas de videojuegos", "Mobiliario", "Consolas de vídeo juegos"),
            ("Mobiliario: electrodomésticos", "Mobiliario", "Electrodomésticos"),
            ("Mobiliario: equipos de cómputo", "Mobiliario", "Equipos de cómputo"),
            ("Mobiliario: otro", "Mobiliario", "Otro"),
        ):
            self._place_next(label, home, header, sheet_label)

        money = "economiafamiliar"
        for section in self._version.sections:
            if norm(section.title) != money:
                continue
            # Gastos, totales y déficit: cada dato va junto a su etiqueta.
            for item in section.fields:
                self._place_inline(item.label, money, _MONEY_ALIASES.get(item.label))

        health = "cuestionariodesalud"
        for label, sheet_label in (
            ("Tipo de sangre", None),
            ("Intervenciones quirúrgicas", None),
            ("¿Se encuentra en tratamiento médico, psicológico o psiquiátrico?", None),
            ("¿Cuál enfermedad?", "¿Cuál?"),
            ("Gastos que genera: médicos", "Médicos"),
            ("Gastos que genera: hospitalización", "Hospitalización"),
            ("Gastos que genera: medicamentos", "Medicamentos"),
            ("¿Cuáles alergias?", "¿Cuáles?"),
        ):
            self._place_inline(label, health, sheet_label)
        # «Sí» y «No» aparecen dos veces: primero la enfermedad, después las alergias.
        self._place_option(
            "¿Padece alguna enfermedad crónica o degenerativa?", health, target="inline", nth=0
        )
        self._place_option("¿Alergias?", health, target="inline", nth=1)
        self._table(
            "Familiares con enfermedades crónico-degenerativas",
            health,
            {},
        )
        self._labelled_rows("Contactos de emergencia", "contactosdeemergencia")
        for label in ("Actividades en tiempo libre", "Religión", "¿Has estado detenido?"):
            self._place_inline(label, "situacionsocial")

        government = "relacionconpersonaldegobierno"
        self._place_option(
            "¿Tiene familiares laborando en el gobierno (seguridad)?", government, target="inline"
        )
        other = self._text_value("Otra dependencia")
        if not (other and self._values.get("¿En qué dependencia?") == "Otra"):
            self._place_option("¿En qué dependencia?", government, target="inline")
        self._place_inline("Otra dependencia", government, "Otra")
        for label, sheet_label in (
            ("¿Qué cargo tiene?", "¿Qué cargo tiene?"),
            ("Parentesco del familiar en gobierno", "Parentesco"),
        ):
            value = self._text_value(label)
            rows = self._section(government)
            cell = self._find(sheet_label, rows) if rows and value else None
            if value and cell is None:
                self._missing(label)
            elif value and cell:
                self._write((self._sheet.span(*cell)[2] + 1, cell[1]), value)
        self._table("Datos familiares", "datosfamiliares", {})

        location = self._text_value("Ubicación del domicilio (enlace o coordenadas)")
        box = self._block_below("datosdegeolocaliza")
        if box and location:
            self._write(box, location)
        elif location:
            self._missing("Ubicación del domicilio (enlace o coordenadas)")
        if box and self._values.get("Mapa de localización"):
            self._image("Mapa de localización", self._sheet.span(*box))

        photos = self._section("soportefotografico")
        for label, caption in (
            ("Fotografía: condiciones de higiene", "Condiciones de higiene"),
            ("Fotografía: localización", "Localización"),
            ("Fotografía: fachada de la vivienda", "Fachada de la vivienda"),
        ):
            if not self._values.get(label):
                continue
            cell = self._find(caption, photos) if photos else None
            if cell is None:
                self._missing(label)
            elif not self._image(label, self._sheet.span(*cell)):
                # Un PDF u otro archivo que no es imagen: queda su descripción.
                note = self._descriptions.get(label) or "Archivo adjunto en el sistema."
                self._sheet.set_text(*cell, f"{self._sheet.text(*cell).strip()}\n{note}")

        verdict = self._text_value("Dictamen (observaciones)")
        box = self._block_below("dictamen")
        if verdict and box:
            self._write(box, verdict)
        elif verdict:
            self._missing("Dictamen (observaciones)")

        report = self._section("reportegraficointegral") or whole
        for label in (
            "Trayectoria escolar",
            "Situación económica",
            "Resultado de referencias personales",
            "Resultado de investigación laboral",
            "Veracidad de la información",
        ):
            level = self._values.get(label)
            if not level:
                continue
            indicator = self._find(label, report)
            column = self._find(str(level), report)
            if indicator is None or column is None:
                self._missing(label)
            else:
                self._write((indicator[0], column[1]), MARK)
        score = self._text_value("Score total")
        cell = self._find("Score total", report)
        if score and cell:
            self._write(self._after(cell), score)
        elif score:
            self._missing("Score total")
        tail = (report[0], self._sheet.last_row)
        self._place_option_in("¿Se considera candidato?", tail)
        for label in ("Visita domiciliaria", "Visita colateral", "Videollamada", "Telefónica"):
            if self._values.get(label) is True:
                cell = self._find(label, tail)
                if cell is None:
                    self._missing(label)
                else:
                    self._check(self._after(cell))
        for label, caption in (
            ("Nombre del aplicador", "Nombre y firma de aplicador"),
            (
                "Nombre del Gerente de Recursos Humanos",
                "Nombre y firma del Gerente de Recursos Humanos",
            ),
        ):
            value = self._text_value(label)
            cell = self._find(caption, tail) if value else None
            if value and cell is None:
                self._missing(label)
            elif value and cell:
                self._write((cell[0] - 1, cell[1]), value)
        return Filled(self._sheet.save(), self._unplaced)

    def _place_option_in(self, label: str, rows: tuple[int, int]) -> None:
        value = self._values.get(label)
        if not value:
            return
        cell = self._find(str(value), rows)
        if cell is None:
            self._missing(label)
        else:
            self._check(self._after(cell))


# Datos de economía cuyo nombre en el formato difiere del nombre del campo.
_MONEY_ALIASES = {"Otro gasto": "Otro", "¿Cuánto es el déficit?": "¿Cuánto?"}


def fill_study(
    template: bytes,
    version: FormTemplateVersion,
    data: dict[str, Any],
    photo: Callable[[str], bytes | None] | None = None,
) -> Filled:
    return StudyWorkbook(template, version, data, photo).fill()


def check_format(template: bytes) -> list[str]:
    """Comprueba que el Excel sea el formato del estudio. Devuelve los apartados
    que no encontró; con demasiados faltantes, no es el formato."""
    sheet = SheetTemplate(template)
    found = {norm(text) for _, _, text in sheet.texts()}
    missing = [key for key in _SECTIONS if not any(text.startswith(key) for text in found)]
    if len(missing) > len(_SECTIONS) // 2:
        raise TemplateError(
            "El archivo no parece el formato «SGC.F3.RH. Estudio socioeconómico»: no se "
            "encontraron sus apartados."
        )
    return missing
