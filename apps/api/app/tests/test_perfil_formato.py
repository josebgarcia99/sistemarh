"""Perfil de puesto según el formato de la empresa «SGC.F15.RH. Perfil de puesto».

Los datos son inventados; la distribución de celdas es la del formato real.
"""

# ruff: noqa: F401, F811  (las fixtures se importan de otro módulo de pruebas)
from __future__ import annotations

import io

import pytest

from app.infrastructure.ai_providers.http_clients import Generation
from app.infrastructure.documents.spreadsheet import (
    SpreadsheetError,
    read_sheets,
    sheets_to_text,
)
from app.infrastructure.documents.text import extract_text
from app.modules.ai_settings.domain.models import ProviderCode
from app.modules.evaluation_setup.domain import assistant, generator
from app.modules.evaluation_setup.domain.company_format import parse_profile_format
from app.modules.evaluation_setup.domain.models import Activity, Kpi, ProfileContent
from app.tests.support import sample_files
from app.tests.support.sample_files import (
    profile_format_cells,
    profile_format_xlsx,
    repack,
    xlsx,
)
from app.tests.test_api_cv_batches import (
    API,
    admin,
    app,
    audit,
    other,
    providers,
    recruiter,
    upload,
    vacancy_id,
)
from app.tests.test_api_evaluation_ai import extract, models, reply, usage_rows
from app.tests.test_api_evaluation_setup import PROFILE

PROFILE_FIELDS = (
    "position_name area location reports_to supervises contract_type work_mode schedule offer "
    "document_version document_date objective internal_relations external_relations "
    "education_levels specialty education experience must_have nice_to_have knowledge skills "
    "certifications functions responsibilities activities kpis ambiguities"
).split()


def grid(content: bytes) -> dict:
    [sheet] = read_sheets(io.BytesIO(content))
    return sheet.cells


def read(**changes):
    reading = parse_profile_format(grid(profile_format_xlsx(**changes)))
    assert reading is not None
    return reading


# --- Lectura del formato -------------------------------------------------------------------


def test_el_formato_se_lee_campo_por_campo_sin_ia():
    reading = read()
    content = reading.content
    assert content.position_name == "Analista de Nómina" and content.area == "Recursos Humanos"
    assert content.location == "Oficina central" and content.reports_to == "Gerencia de RH"
    assert content.supervises == "N/A" and content.contract_type == "Indefinido"
    assert content.work_mode == "Híbrido" and content.schedule == "09:00 - 18:00 Lunes - Viernes"
    assert content.offer == ""  # vacía en el formato: la etiqueta siguiente no es su valor
    assert content.document_version == "03" and content.document_date == "2026-10-05"
    assert content.objective == "Calcular y pagar la nómina quincenal sin errores y a tiempo."
    assert content.internal_relations == "Contabilidad y Tesorería"
    assert content.external_relations == "IMSS e INFONAVIT"
    # Casillas marcadas, en el orden del formato.
    assert content.education_levels == ("Licenciatura", "TSU")
    assert content.specialty == "Contaduría, Administración"
    assert content.experience == "2 años en cálculo de nómina"
    # Lista numerada en dos columnas, en orden y sin los tabuladores del original.
    assert content.must_have == (
        "Cálculo de nómina quincenal",
        "Cuotas IMSS e INFONAVIT",
        "Cálculo de ISR",
        "Timbrado de recibos",
        "Finiquitos y liquidaciones",
        "Manejo de incidencias",
    )
    # Una sola celda con comas: se separa sin romper lo que va entre paréntesis.
    assert content.knowledge == (
        "Excel (tablas dinámicas, BUSCARV)",
        "CONTPAQi Nóminas",
        "Ley Federal del Trabajo",
    )
    assert content.skills == ("Atención al detalle.", "Confidencialidad.", "Trabajo en equipo.")
    assert content.functions == (
        "Calcular la nómina.",
        "Timbrar los recibos.",
        "Atender dudas del personal.",
    )
    assert content.activities == (
        Activity("Registrar incidencias.", "Diaria"),
        # «Quincenal» no es una periodicidad del formato: queda vacía y se avisa.
        Activity("Calcular la nómina quincenal.", ""),
        Activity("Presentar pagos provisionales.", "Mensual"),
        Activity("Conciliar cuentas de nómina.", ""),
    )
    assert content.kpis == (
        Kpi(
            "Nóminas pagadas a tiempo", "100 % quincenal", "Nóminas a tiempo / nóminas del periodo"
        ),
        Kpi("Errores de cálculo", "Menos de 1 % mensual", ""),
    )
    # Lo que el formato no trae queda vacío: no se inventa.
    assert content.nice_to_have == () and content.certifications == ()
    assert content.responsibilities == () and content.ambiguities == ()
    assert any("Quincenal" in notice and "Actividad 2" in notice for notice in reading.notices)
    # La propuesta leída pasa la validación con la que se guarda.
    assert generator.validate_profile(content.to_dict()) == content


def test_la_edad_y_el_genero_del_formato_no_se_copian_y_se_avisa():
    reading = read(age_min=25, age_max=40, gender="Masculino")
    [notice] = [n for n in reading.notices if "edad" in n]
    assert "mínima 25" in notice and "máxima 40" in notice and "género masculino" in notice
    assert "no se usan para evaluar" in notice
    stored = str(reading.content.to_dict()).lower()
    assert "masculino" not in stored and "edad" not in stored and "género" not in stored
    # Sin edad y con «Indistinto» no hay nada que avisar.
    assert not [n for n in read(age_min=None, gender="Indistinto").notices if "edad" in n]


def test_el_lector_tolera_filas_y_columnas_desplazadas_y_textos_en_la_celda_del_numero():
    cells = profile_format_cells()
    cells["C35"], cells["D35"] = "1.- Cálculo de nómina quincenal", None
    shifted = {}
    for position, value in cells.items():
        if value is None:
            continue
        column, row = position[0], int(position[1:])
        shifted[f"{chr(ord(column) + 2)}{row + 7}"] = value
    reading = parse_profile_format(grid(xlsx(shifted)))
    assert reading is not None and reading.content == read().content


def test_un_formato_incompleto_avisa_de_lo_que_falta():
    reading = read(purpose="", must=(), kpis=(), activities=(), levels=())
    assert reading.content.objective == "" and reading.content.must_have == ()
    assert reading.content.kpis == () and reading.content.education_levels == ()
    assert any("propósito" in n for n in reading.notices)
    assert any("requisitos indispensables" in n for n in reading.notices)


def test_una_hoja_que_no_es_el_formato_no_se_interpreta():
    assert parse_profile_format({}) is None
    assert parse_profile_format(grid(xlsx({"A1": "Ventas", "B1": 10, "A2": "Compras"}))) is None
    # Con las secciones pero sin el nombre del puesto tampoco se acepta.
    cells = {k: v for k, v in profile_format_cells().items() if k not in ("C9", "E9")}
    assert parse_profile_format(grid(xlsx(cells))) is None


# --- Lectura segura de la hoja de cálculo ---------------------------------------------------


def test_la_hoja_se_lee_con_limites_y_sin_las_hojas_ocultas():
    def add_hidden(book):
        hidden = book.create_sheet("Oculta")
        hidden["A1"] = "dato oculto"
        hidden.sheet_state = "hidden"

    content = xlsx({"A1": "Etiqueta:", "B1": True, "A2": 3.0, "B2": "  "}, extra=add_hidden)
    sheets = read_sheets(io.BytesIO(content))
    assert [sheet.name for sheet in sheets] == ["Perfil de puesto"]
    assert sheets[0].cells == {(1, 1): "Etiqueta:", (1, 2): True, (2, 1): 3.0}
    assert sheets_to_text(sheets) == "Etiqueta: | sí\n3"

    with pytest.raises(SpreadsheetError):
        read_sheets(io.BytesIO(b"esto no es un libro de Excel"))
    # Una definición DTD (vía de los ataques de expansión de entidades) se rechaza sin abrir.
    bomb = repack(
        content,
        replace=lambda name, data: (
            data.replace(b"<worksheet", b'<!DOCTYPE x [<!ENTITY a "aaaa">]><worksheet', 1)
            if name == "xl/worksheets/sheet1.xml"
            else data
        ),
    )
    with pytest.raises(SpreadsheetError):
        read_sheets(io.BytesIO(bomb))
    many = xlsx({f"A{row}": row for row in range(1, 2200)})
    assert max(row for row, _ in read_sheets(io.BytesIO(many))[0].cells) == 2000


def test_el_texto_de_un_excel_sirve_para_la_ia():
    found = extract_text(io.BytesIO(profile_format_xlsx()), "xlsx")
    assert "Nombre del puesto: | Analista de Nómina" in found.text
    assert "Licenciatura | sí" in found.text and "Maestría | no" in found.text
    assert found.truncated is False and found.ocr is False


# --- Desde la API ---------------------------------------------------------------------------


def test_subir_el_formato_llena_el_perfil_sin_usar_la_ia(recruiter, admin, vacancy_id, providers):
    document = upload(
        recruiter,
        vacancy_id,
        "SGC.F15.RH. Perfil de puesto.xlsx",
        profile_format_xlsx(age_min=30),
        document_type="PERFIL_PUESTO",
    )
    assert document["content_type"].endswith("spreadsheetml.sheet")
    # No hay modelo asignado ni clave: la lectura del formato no los necesita.
    response = extract(recruiter, vacancy_id, file_id=document["id"])
    assert response.status_code == 200, response.text
    proposal = response.json()
    assert proposal["origin"] == "FORMATO" and proposal["source_file_id"] == document["id"]
    assert proposal["position_name"] == "Analista de Nómina"
    assert proposal["education_levels"] == ["Licenciatura", "TSU"]
    assert proposal["activities"][0] == {
        "description": "Registrar incidencias.",
        "frequency": "Diaria",
    }
    assert proposal["kpis"][1] == {
        "name": "Errores de cálculo",
        "goal": "Menos de 1 % mensual",
        "formula": "",
    }
    assert any("edad mínima 30" in notice for notice in proposal["notices"])
    assert all(not fake.prompts for fake in providers.values())
    assert usage_rows(admin) == []
    # Es una propuesta: no hay ninguna versión guardada.
    assert recruiter.get(f"{API}/vacancies/{vacancy_id}/profile-versions").json() == []
    [event] = audit(admin, "perfil.leido_del_formato")
    assert event["details"]["documento"] == document["id"]
    assert audit(admin, "perfil.extraido_con_ia") == []

    # La persona la revisa y la guarda: queda marcada como leída del formato.
    fields = {name: proposal[name] for name in PROFILE_FIELDS}
    saved = recruiter.post(
        f"{API}/vacancies/{vacancy_id}/profile-versions",
        json={
            **fields,
            "expected_version": 0,
            "origin": "FORMATO",
            "source_file_id": document["id"],
        },
    )
    assert saved.status_code == 201, saved.text
    version = saved.json()
    assert version["origin"] == "FORMATO" and version["version_number"] == 1
    [stored] = recruiter.get(f"{API}/vacancies/{vacancy_id}/profile-versions").json()
    assert {name: stored[name] for name in PROFILE_FIELDS} == fields

    # El prompt que sale de ese perfil usa el puesto, la formación y las actividades.
    prompt = recruiter.post(f"{API}/vacancies/{vacancy_id}/prompts", json={})
    assert prompt.status_code == 201, prompt.text
    layer = next(item for item in prompt.json()["layers"] if item["key"] == "PERFIL")["content"]
    assert "Puesto: Analista de Nómina" in layer and "Registrar incidencias." in layer
    assert "Formación: Licenciatura o TSU; especialidad en Contaduría, Administración" in layer
    # Ni la oferta, ni el horario, ni a quién reporta forman parte de la evaluación de un CV.
    assert "Gerencia de RH" not in layer and "09:00" not in layer
    assert [c["name"] for c in prompt.json()["criteria"]][:2] == [
        "Cálculo de nómina quincenal",
        "Cuotas IMSS e INFONAVIT",
    ]


def test_un_excel_que_no_es_el_formato_se_lee_con_la_ia(recruiter, vacancy_id, models, providers):
    content = xlsx(
        {
            "A1": "Perfil del puesto",
            "A2": "Puesto",
            "B2": "Analista de Nómina",
            "A3": "Objetivo",
            "B3": "Calcular y pagar la nómina quincenal sin errores.",
            "A4": "Indispensable",
            "B4": "Dos años de experiencia en cálculo de nómina",
        }
    )
    document = upload(recruiter, vacancy_id, "perfil.xlsx", content, document_type="PERFIL_PUESTO")
    fake = providers[ProviderCode.ANTHROPIC]
    fake.script, fake.prompts = [], []
    fake.script.append(
        reply(
            {
                "puesto": "Analista de Nómina",
                "proposito": "Calcular y pagar la nómina quincenal sin errores.",
                "niveles_de_formacion": ["licenciatura", "Doctorado"],
                "fecha_de_actualizacion": "no es fecha",
                "requisitos_indispensables": ["Dos años de experiencia en cálculo de nómina"],
                "actividades": [
                    {"actividad": "Registrar incidencias", "periodicidad": "DIARIA"},
                    {"actividad": "", "periodicidad": "Semanal"},
                    "no es una fila",
                ],
                "kpis": [{"kpi": "Nóminas a tiempo", "meta": "100 %", "formula": 5}],
                "edad_maxima": 35,
            }
        )
    )
    response = extract(recruiter, vacancy_id, file_id=document["id"])
    assert response.status_code == 200, response.text
    proposal = response.json()
    assert proposal["origin"] == "IA" and proposal["notices"] == []
    assert proposal["position_name"] == "Analista de Nómina"
    assert proposal["education_levels"] == ["Licenciatura"] and proposal["document_date"] == ""
    assert proposal["activities"] == [
        {"description": "Registrar incidencias", "frequency": "Diaria"}
    ]
    assert proposal["kpis"] == [{"name": "Nóminas a tiempo", "goal": "100 %", "formula": "5"}]
    _, system, user = fake.prompts[0]
    assert system == assistant.PROFILE_SYSTEM
    assert "Puesto | Analista de Nómina" in user


def test_el_excel_solo_se_acepta_donde_hay_un_formato_de_la_empresa(recruiter, vacancy_id):
    def post(name, content, document_type):
        return recruiter.post(
            f"{API}/vacancies/{vacancy_id}/files",
            params={"document_type": document_type, "filename": name},
            content=content,
        )

    book = profile_format_xlsx()
    # Un CV no puede ser una hoja de cálculo.
    refused = post("cv.xlsx", book, "CV")
    assert refused.status_code == 422 and "XLSX" not in refused.json()["detail"]
    # Como perfil sí, pero el contenido debe ser de verdad un libro de Excel y sin macros.
    fake = post("perfil.xlsx", b"PK\x03\x04 no es un libro", "PERFIL_PUESTO")
    assert fake.status_code == 422 and "Excel" in fake.json()["detail"]
    document = post("perfil.xlsx", sample_files.docx(), "PERFIL_PUESTO")
    assert document.status_code == 422 and "Excel" in document.json()["detail"]
    macros = post("perfil.xlsx", repack(book, add={"xl/vbaProject.bin": b"macro"}), "PERFIL_PUESTO")
    assert macros.status_code == 422 and "macros" in macros.json()["detail"]
    accepted = post("perfil.xlsx", book, "PERFIL_PUESTO")
    assert accepted.status_code == 201, accepted.text
    listed = recruiter.get(f"{API}/vacancies/{vacancy_id}/files").json()
    assert [item["original_name"] for item in listed] == ["perfil.xlsx"]


def test_los_campos_nuevos_del_perfil_se_validan(recruiter, vacancy_id):
    def save(**changes):
        return recruiter.post(
            f"{API}/vacancies/{vacancy_id}/profile-versions",
            json={**PROFILE, **changes, "expected_version": 0},
        )

    for changes, fragment in (
        ({"education_levels": ["Doctorado"]}, "formación académica"),
        ({"document_date": "05/10/2026"}, "fecha"),
        ({"activities": [{"description": "Calcular", "frequency": "Quincenal"}]}, "periodicidad"),
        ({"activities": [{"description": "", "frequency": "Diaria"}]}, "sin su actividad"),
        ({"kpis": [{"name": "", "goal": "100 %"}]}, "sin el nombre"),
        ({"position_name": "x" * 301}, "máximo"),
        ({"activities": [{"description": f"Actividad {n}"} for n in range(31)]}, "máximo"),
        ({"origin": "FORMATO"}, "documento"),
    ):
        response = save(**changes)
        assert response.status_code == 422, changes
        assert fragment in response.json()["detail"], response.json()

    saved = save(
        position_name="  Analista   de Nómina ",
        education_levels=["tsu", "LICENCIATURA", "TSU"],
        document_date="2026-10-05",
        activities=[
            {"description": " Calcular la nómina ", "frequency": "semanal"},
            {"description": "", "frequency": ""},
        ],
        kpis=[{"name": "Nóminas a tiempo", "goal": "100 %", "formula": ""}],
    )
    assert saved.status_code == 201, saved.text
    body = saved.json()
    assert body["position_name"] == "Analista de Nómina" and body["origin"] == "MANUAL"
    assert body["education_levels"] == ["Licenciatura", "TSU"]
    assert body["activities"] == [{"description": "Calcular la nómina", "frequency": "Semanal"}]
    assert body["kpis"] == [{"name": "Nóminas a tiempo", "goal": "100 %", "formula": ""}]


def test_un_perfil_guardado_antes_del_formato_se_sigue_leyendo():
    old = {
        "objective": "Calcular la nómina.",
        "experience": "",
        "education": "Licenciatura",
        "functions": ["Calcular nómina"],
        "must_have": ["Experiencia en nómina"],
    }
    content = ProfileContent.from_stored(old)
    assert content.objective == "Calcular la nómina." and content.functions == ("Calcular nómina",)
    assert content.position_name == "" and content.activities == () and content.kpis == ()
    assert content.education_levels == ()
