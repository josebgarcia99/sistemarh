"""El estudio socioeconómico capturado se descarga en el formato de la empresa.
El formato de estas pruebas es inventado y tiene la misma estructura que el real."""

# ruff: noqa: F401, F811  (las fixtures se importan de otro módulo de pruebas)
from __future__ import annotations

import io
import json
import zipfile
from urllib.parse import unquote

import pytest
from openpyxl import load_workbook

from app.infrastructure.documents.xlsx_template import SheetTemplate, TemplateError
from app.modules.assessments.infrastructure.study_workbook import check_format
from app.tests.support.sample_files import pdf_cv, photo
from app.tests.support.study_format import study_format_xlsx
from app.tests.test_analista_estudios import analyst
from app.tests.test_api_assessments import ana, create, update
from app.tests.test_api_cv_batches import (
    API,
    admin,
    app,
    audit,
    model,
    other,
    prompt,
    providers,
    recruiter,
    upload,
    vacancy_id,
)
from app.tests.test_api_recruitment import by_name, evaluated

XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _cells(content: bytes) -> dict[str, object]:
    sheet = load_workbook(io.BytesIO(content)).active
    return {
        cell.coordinate: cell.value
        for row in sheet.iter_rows()
        for cell in row
        if cell.value not in (None, "")
    }


def _at(cells: dict[str, object], text: str) -> list[str]:
    return [where for where, value in cells.items() if value == text]


# --- Llenar un Excel sin alterar su formato ------------------------------------------------


def test_solo_cambian_las_celdas_escritas_y_lo_demas_queda_identico():
    original = study_format_xlsx()
    sheet = SheetTemplate(original)
    where = next((r, c) for r, c, text in sheet.texts() if text == "Nombre completo:")
    sheet.set_text(*where, "Nombre completo: Persona <Ficticia> & Cía")
    check = next((r, c) for r, c, text in sheet.texts() if text == "INE:")
    assert sheet.is_check(check[0], check[1] + 1) and not sheet.is_check(*check)
    sheet.set_check(check[0], check[1] + 1, True)
    filled = sheet.save()

    before, after = zipfile.ZipFile(io.BytesIO(original)), zipfile.ZipFile(io.BytesIO(filled))
    assert before.namelist() == after.namelist()
    changed = [name for name in before.namelist() if before.read(name) != after.read(name)]
    assert changed == ["xl/worksheets/sheet1.xml"]
    cells = _cells(filled)
    # Los caracteres especiales no rompen el archivo y la fórmula sigue en su lugar.
    assert _at(cells, "Nombre completo: Persona <Ficticia> & Cía")
    assert _at(cells, "=C3") and _at(_cells(original), "=C3") == _at(cells, "=C3")
    assert sum(1 for value in cells.values() if value is True) == 1


def test_una_imagen_se_agrega_sin_tocar_las_que_ya_tenia():
    original = study_format_xlsx()
    sheet = SheetTemplate(original)
    caption = next((r, c) for r, c, text in sheet.texts() if text == "LOCALIZACIÓN")
    assert sheet.add_image(sheet.span(*caption), photo(), 800, 600, "Fotografía") is True
    archive = zipfile.ZipFile(io.BytesIO(sheet.save()))
    media = [name for name in archive.namelist() if name.startswith("xl/media/")]
    assert media == ["xl/media/image1.jpeg", "xl/media/estudio_imagen1.jpeg"]
    assert archive.read("xl/media/image1.jpeg") == zipfile.ZipFile(io.BytesIO(original)).read(
        "xl/media/image1.jpeg"
    )
    assert len(load_workbook(io.BytesIO(sheet.save())).active._images) == 2


def test_un_archivo_que_no_es_el_formato_se_rechaza():
    with pytest.raises(TemplateError, match="no es un Excel"):
        SheetTemplate(b"esto no es un excel")
    from app.tests.support.sample_files import profile_format_xlsx

    with pytest.raises(TemplateError, match="no parece el formato"):
        check_format(profile_format_xlsx())


# --- Desde la API --------------------------------------------------------------------------


def _study(recruiter, vacancy_id, application_id) -> tuple[dict, dict]:
    [template] = recruiter.get(f"{API}/form-templates").json()
    ids = {f["label"]: f["id"] for section in template["sections"] for f in section["fields"]}
    picture = upload(
        recruiter, vacancy_id, "fachada.jpg", photo(), document_type="ESTUDIO_SOCIOECONOMICO"
    )
    scanned = upload(
        recruiter,
        vacancy_id,
        "croquis.pdf",
        pdf_cv("Croquis"),
        document_type="ESTUDIO_SOCIOECONOMICO",
    )
    values = {
        "Fecha de aplicación": "2026-11-15",
        "Nombre completo": "Ana Pérez Ficticia",
        "Fecha de nacimiento": "1994-03-08",
        "Edad": "32",
        "Domicilio": "Calle Inventada 123",
        "RFC o CURP": "XAXX010101000",
        "Estado civil": "Divorciado (a)",
        "Formación académica": [
            ["Licenciatura", "Universidad Ficticia", "2012-2016", "Monterrey", "Título", "Sí", ""],
            ["Preparatoria", "Prepa de Ejemplo", "2009-2012", "Monterrey", "", "", ""],
            ["Secundaria", "Escuela Inventada", "2006-2009", "Monterrey", "", "", ""],
        ],
        "INE": True,
        "Comprobante de estudios": True,
        "Correo electrónico": "ana@ejemplo.test",
        "TikTok": "@anaficticia",
        "Observaciones de redes sociales": "Sin hallazgos.",
        "Tenencia de la vivienda": "Rentada",
        "Tipo de vivienda": "Multifamiliar",
        "Techo": "Concreto",
        "Suelo": "Tierra",
        "Automóviles: cuántos": "1",
        "Automóvil financiado": True,
        "Distribución: dormitorios": "2",
        "Distribución: baños": "1",
        "Alimentación": "4000",
        "Renta": "6000",
        "Otro gasto": "150",
        "Total ingreso mensual": "22000",
        "¿Tiene déficit?": "No",
        "¿Cuánto es el déficit?": "0",
        "¿Cómo lo cubre?": "No aplica",
        "Tipo de sangre": "O+",
        "¿Padece alguna enfermedad crónica o degenerativa?": "No",
        "¿Alergias?": "Sí",
        "¿Cuáles alergias?": "Polen",
        "Gastos que genera: médicos": "0",
        "Familiares con enfermedades crónico-degenerativas": [
            ["Madre Ficticia", "60", "Madre", "Diabetes"]
        ],
        "Contactos de emergencia": [["Hermano Ficticio", "55 0000 0011", "", "Hermano"]],
        "Actividades en tiempo libre": "Lectura",
        "Religión": "Ninguna",
        "¿Has estado detenido?": "No",
        "¿Tiene familiares laborando en el gobierno (seguridad)?": "Sí",
        "¿En qué dependencia?": "Otra",
        "Otra dependencia": "Policía municipal",
        "¿Qué cargo tiene?": "Oficial",
        "Parentesco del familiar en gobierno": "Primo",
        "Datos familiares": [
            ["Hermano Ficticio", "30", "Hermano", "Preparatoria", "Chofer", "9000"]
        ],
        "Ubicación del domicilio (enlace o coordenadas)": "25.6866, -100.3161",
        "Fotografía: localización": picture["id"],
        "Fotografía: fachada de la vivienda": scanned["id"],
        "Dictamen (observaciones)": "Dictamen inventado.",
        "Trayectoria escolar": "Suficiente (2)",
        "Situación económica": "Medio (1)",
        "Score total": "9",
        "¿Se considera candidato?": "Es viable con reservas (7-8)",
        "Visita domiciliaria": True,
        "Telefónica": True,
        "Nombre del aplicador": "Analista Ficticia",
        "Nombre del Gerente de Recursos Humanos": "Gerente Ficticio",
    }
    answers = {ids[label]: {"value": value} for label, value in values.items()}
    answers[ids["Fotografía: fachada de la vivienda"]]["description"] = "Croquis en PDF."
    study = create(
        recruiter, application_id, "ESTUDIO_SOCIOECONOMICO", template_id=template["id"]
    ).json()
    saved = update(recruiter, study, status="EN_PROCESO", data={"answers": answers})
    assert saved.status_code == 200, saved.text
    return template, saved.json()


def test_el_estudio_se_descarga_en_el_formato_con_cada_dato_en_su_lugar(
    ana, recruiter, admin, other, analyst, vacancy_id
):
    template, study = _study(recruiter, vacancy_id, ana)
    download = f"{API}/assessments/{study['id']}/study-format"
    upload_url = f"{API}/form-templates/{template['id']}/study-format"
    headers = {"Content-Type": XLSX}

    # Mientras nadie cargue el formato en blanco, se explica qué falta.
    assert template["has_study_format"] is False
    early = recruiter.get(download)
    assert early.status_code == 422 and "administrador" in early.json()["detail"]

    # Solo un administrador lo carga, y solo si es el formato del estudio.
    blank = study_format_xlsx()
    assert recruiter.put(upload_url, content=blank, headers=headers).status_code == 403
    assert "no es un Excel" in admin.put(upload_url, content=b"x", headers=headers).json()["detail"]
    from app.tests.support.sample_files import profile_format_xlsx

    wrong = admin.put(upload_url, content=profile_format_xlsx(), headers=headers)
    assert wrong.status_code == 422 and "no parece el formato" in wrong.json()["detail"]
    loaded = admin.put(upload_url, content=blank, headers=headers)
    assert loaded.status_code == 200, loaded.text
    assert loaded.json() == {"missing_sections": []}
    assert recruiter.get(f"{API}/form-templates").json()[0]["has_study_format"] is True
    # Se puede volver a cargar: el vigente es el último.
    assert admin.put(upload_url, content=blank, headers=headers).status_code == 200

    response = recruiter.get(download)
    assert response.status_code == 200, response.text
    assert response.headers["content-type"] == XLSX
    assert "Estudio%20socioeconomico%20-%20Ana" in response.headers["content-disposition"]
    unplaced = json.loads(unquote(response.headers["x-unplaced"]))
    # El formato de prueba tiene dos renglones de formación: el tercero no cabe y se avisa.
    assert unplaced == ["Formación académica: solo caben 2 filas; faltan 1"]

    cells = _cells(response.content)
    blank_cells = _cells(blank)

    def beside(label: str, nth: int = 0, gap: int = 1) -> object:
        """El valor de la celda que sigue, a la derecha, a esa etiqueta."""
        where = _at(blank_cells, label)[nth]
        sheet = load_workbook(io.BytesIO(response.content)).active
        cell = sheet[where]
        span = next((r for r in sheet.merged_cells.ranges if where in r), None)
        column = (span.max_col if span else cell.column) + gap
        return sheet.cell(cell.row, column).value

    # El dato va en la misma celda que su etiqueta.
    for text in (
        "Día: 15",
        "Mes: 11",
        "Año: 2026",
        "Nombre completo: Ana Pérez Ficticia",
        "Fecha de nacimiento: 08/03/1994",
        "Edad: 32",
        "Domicilio: Calle Inventada 123",
        "RFC o CURP: XAXX010101000",
        "Correo electrónico: ana@ejemplo.test",
        "Tiktok: @anaficticia",
        "Observaciones: Sin hallazgos.",
        "Alimentación: 4000",
        "Renta: 6000",
        "Otro: 150",
        "Total ingreso mensual: 22000",
        "¿Tiene déficit? No",
        "¿Cuánto? 0",
        "¿Cómo lo cubre? No aplica",
        "Tipo de sangre: O+",
        "Médicos: 0",
        "¿Cuáles? Polen",
        "Actividades en tiempo libre: Lectura",
        "Religión: Ninguna",
        "¿Has estado detenido? No",
        "Otra: Policía municipal",
        "Nombre: Hermano Ficticio",
        "Teléfono: 55 0000 0011",
        "Parentesco: Hermano",
    ):
        assert _at(cells, text), text
    # Sí y No aparecen dos veces en salud: la enfermedad (No) y las alergias (Sí).
    assert _at(cells, "NO: X") and _at(cells, "Sí: X") and not _at(cells, "SÍ: X")
    assert len(_at(cells, "Sí: X")) == 2  # alergias y familiares en gobierno
    # Casillas: solo las elegidas quedan marcadas, también con una celda vacía en medio.
    assert beside("Divorciado(a):") is True and beside("Soltero (a):") is False
    assert beside("INE:") is True and beside("CURP:") is False
    assert beside("Comprobante de estudios:", gap=2) is True
    assert beside("Es viable con reservas (7-8)") is True and beside("Es viable (9-10)") is False
    assert beside("Visita domiciliaria:") is True and beside("Telefónica:") is True
    # Opciones del inmueble: «Concreto» existe en techo y en suelo; solo se marca el techo.
    assert beside("Rentada:") == "X" and beside("Propia:") is None
    assert beside("Multi familiar:") == "X"
    assert beside("Concreto:", nth=0) == "X" and beside("Concreto:", nth=1) is None
    assert beside("Tierra: ") == "X"
    assert beside("Cuántos:") == "1" and beside("Financiado:") == "X"
    assert beside("Dormitorios: ") == "2" and beside("Baño:") == "1"
    assert beside("SCORE TOTAL") == "9"
    # Tablas, recuadros, niveles y firmas.
    for text in (
        "Licenciatura",
        "Universidad Ficticia",
        "Prepa de Ejemplo",
        "Madre Ficticia",
        "Diabetes",
        "Chofer",
        "9000",
        "25.6866, -100.3161",
        "Dictamen inventado.",
        "Oficial",
        "Primo",
        "Analista Ficticia",
        "Gerente Ficticio",
    ):
        assert _at(cells, text), text
    assert not _at(cells, "Escuela Inventada")
    sheet = load_workbook(io.BytesIO(response.content)).active
    level = {
        cell.value: cell.column
        for row in sheet.iter_rows()
        for cell in row
        if cell.value in ("SUFICIENTE (2)", "MEDIO (1)")
    }
    marks = {
        cell.row: cell.column
        for row in sheet.iter_rows()
        for cell in row
        if cell.value == "X" and cell.column in level.values()
    }
    rows = {
        cell.value.strip(): cell.row
        for row in sheet.iter_rows()
        for cell in row
        if isinstance(cell.value, str)
        and cell.value.strip() in ("TRAYECTORIA ESCOLAR", "SITUACIÓN ECONÓMICA")
    }
    assert marks[rows["TRAYECTORIA ESCOLAR"]] == level["SUFICIENTE (2)"]
    assert marks[rows["SITUACIÓN ECONÓMICA"]] == level["MEDIO (1)"]
    # La fotografía queda dentro del Excel; el PDF no es imagen y deja su descripción.
    assert len(sheet._images) == 2  # el logotipo y la fotografía de localización
    assert _at(cells, "FACHADA DE LA VIVIENDA\nCroquis en PDF.")

    # Quién puede descargarlo: con el permiso del estudio, y la analista de estudios.
    stranger, stranger_id = other
    from app.tests.conftest import share

    share(recruiter, vacancy_id, stranger_id, "COLABORACION")
    assert stranger.get(download).status_code == 403
    assert analyst.get(download).status_code == 200
    assert analyst.put(upload_url, content=blank, headers=headers).status_code == 403
    # Solo los estudios se descargan así.
    interview = create(recruiter, ana, "ENTREVISTA", data={"interviewer": "Gerente Ficticio"})
    refused = recruiter.get(f"{API}/assessments/{interview.json()['id']}/study-format")
    assert refused.status_code == 422

    # El formato en blanco vive en el almacenamiento del servidor, una sola copia,
    # y la conciliación lo reconoce: no lo aparta como archivo sin dueño.
    storage = recruiter.app.state.context.storage
    [stored] = [key for key in storage.iter_keys() if key.startswith("private/formato_estudio/")]
    reconciled = admin.post(f"{API}/storage/reconciliation", json={}).json()
    assert reconciled["orphans_quarantined"] == 0 and storage.exists(stored)
    assert recruiter.get(download).status_code == 200

    assert len(audit(admin, "estudio.formato_cargado")) == 2
    events = audit(admin, "estudio.descargado")
    assert len(events) == 3 and events[0]["details"]["sin_colocar"] == 1
