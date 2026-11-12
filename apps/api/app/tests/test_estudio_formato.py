"""Estudio socioeconómico según el formato de la empresa «SGC.F3.RH» (datos inventados)."""

# ruff: noqa: F401, F811  (las fixtures se importan de otro módulo de pruebas)
from __future__ import annotations

import io

import pytest

from app.infrastructure.documents.text import extract_text
from app.modules.ai_settings.domain.models import ProviderCode
from app.modules.assessments.domain import assistant, rules
from app.modules.assessments.domain.company_study_format import (
    COMPANY_STUDY_TEMPLATE,
    FORMAT_NAME,
)
from app.modules.assessments.domain.models import FieldType
from app.tests.support.sample_files import xlsx
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
from app.tests.test_api_recruitment import assign, by_name, evaluated, new_bank, reply

SECTIONS = [
    "Aplicación del estudio",
    "Datos de identificación",
    "Estado civil",
    "Formación académica",
    "Verificación de documentos",
    "Redes sociales",
    "Condiciones del inmueble",
    "Economía familiar",
    "Cuestionario de salud",
    "Contactos de emergencia",
    "Situación social",
    "Relación con personal de gobierno",
    "Datos familiares",
    "Datos de geolocalización del domicilio",
    "Soporte fotográfico",
    "Dictamen",
    "Reporte cuantitativo del resultado de la investigación",
    "¿Se verificó la información anterior a través de?",
    "Ratificación y firmas",
]
MANUAL_ONLY = {
    "Dictamen (observaciones)",
    "Trayectoria escolar",
    "Situación económica",
    "Resultado de referencias personales",
    "Resultado de investigación laboral",
    "Veracidad de la información",
    "Score total",
    "¿Se considera candidato?",
    "Nombre del aplicador",
    "Nombre del Gerente de Recursos Humanos",
}


def test_la_plantilla_sigue_las_secciones_del_formato_de_la_empresa():
    sections = rules.template_sections(COMPANY_STUDY_TEMPLATE)
    assert [section.title for section in sections] == SECTIONS
    fields = {item.label: item for section in sections for item in section.fields}
    assert len(fields) == sum(len(section.fields) for section in sections) <= rules.MAX_FIELDS
    # Las tablas del formato, con sus columnas.
    tables = {label: item.columns for label, item in fields.items() if item.type is FieldType.TABLA}
    assert tables == {
        "Formación académica": (
            "Nivel",
            "Institución",
            "Periodo",
            "Lugar",
            "Documento obtenido",
            "Mostró documento",
            "Observaciones",
        ),
        "Familiares con enfermedades crónico-degenerativas": (
            "Nombre",
            "Edad",
            "Parentesco",
            "Enfermedad",
        ),
        "Contactos de emergencia": ("Nombre", "Teléfono", "Teléfono fijo", "Parentesco"),
        "Datos familiares": (
            "Nombre",
            "Edad",
            "Parentesco",
            "Escolaridad",
            "Ocupación",
            "Ingreso mensual",
        ),
    }
    assert fields["Estado civil"].options[:2] == ("Soltero (a)", "Casado (a)")
    assert fields["¿Se considera candidato?"].options == (
        "Es viable (9-10)",
        "Es viable con reservas (7-8)",
        "No es viable (0-6)",
    )
    assert fields["Score total"].maximum == 10 and fields["Alimentación"].minimum == 0
    # El dictamen, los niveles, la puntuación y las firmas solo los captura una persona.
    assert {label for label, item in fields.items() if item.manual_only} == MANUAL_ONLY
    assert [label for label, item in fields.items() if item.required] == [
        "Fecha de aplicación",
        "Nombre completo",
    ]


def test_una_tabla_necesita_columnas_y_limpia_sus_filas():
    def table(columns):
        return [
            {"title": "T", "fields": [{"label": "Familia", "type": "TABLA", "columns": columns}]}
        ]

    with pytest.raises(rules.RuleError, match="de 2 a 8 columnas"):
        rules.template_sections(table(["Nombre"]))
    with pytest.raises(rules.RuleError, match="de 2 a 8 columnas"):
        rules.template_sections(table([f"C{n}" for n in range(9)]))
    [section] = rules.template_sections(table(["Nombre", " Edad ", "Nombre", ""]))
    [item] = section.fields
    assert item.columns == ("Nombre", "Edad")
    # Las filas se ajustan al número de columnas y las vacías se descartan.
    assert rules.table_rows(item, [["Ana", 40, "sobra"], ["", ""], ["  Luis  "]]) == [
        ["Ana", "40"],
        ["Luis", ""],
    ]
    assert rules.table_rows(item, [["", ""]]) is None
    with pytest.raises(rules.RuleError, match="formato esperado"):
        rules.table_rows(item, "Ana, 40")
    with pytest.raises(rules.RuleError, match="como máximo 20 filas"):
        rules.table_rows(item, [["Persona", "1"]] * 21)
    # Al leer una respuesta de la IA lo inesperado se ignora en lugar de fallar.
    assert rules.table_rows(item, "Ana, 40", strict=False) is None
    assert rules.table_rows(item, [["Ana", "40"], "no es fila"], strict=False) == [["Ana", "40"]]


def test_el_estudio_se_captura_con_el_formato_y_el_dictamen_es_solo_humano(
    ana, recruiter, admin, vacancy_id, providers
):
    [template] = recruiter.get(f"{API}/form-templates").json()
    assert template["name"] == FORMAT_NAME and len(template["sections"]) == 19
    fields = {f["label"]: f for section in template["sections"] for f in section["fields"]}
    ids = {label: item["id"] for label, item in fields.items()}
    assert fields["Datos familiares"]["columns"][0] == "Nombre"
    assert fields["Situación económica"]["manual_only"] is True
    study = create(recruiter, ana, "ESTUDIO_SOCIOECONOMICO", template_id=template["id"]).json()

    # El formato lleno en Excel se sube como documento del estudio y la IA lo transcribe.
    scanned = upload(
        recruiter,
        vacancy_id,
        "SGC.F3.RH. Estudio.xlsx",
        xlsx(
            {
                "E3": "SGC.F3.RH. Estudio socioeconómico.",
                "B10": "Nombre completo:",
                "C10": "Persona Ficticia",
                "B15": "Soltero (a):",
                "C15": True,
                "D15": "Casado (a):",
                "E15": False,
                "B98": "Nombre:",
                "F98": "Edad:",
                "B99": "Familiar Ficticio",
                "F99": 52,
                "B121": "DICTAMEN (OBSERVACIONES)",
                "B122": "Dictamen inventado del aplicador.",
            },
            title="Hoja1",
        ),
        document_type="ESTUDIO_SOCIOECONOMICO",
    )
    assign(admin, "LECTURA_DOCUMENTOS")
    fake = providers[ProviderCode.ANTHROPIC]
    fake.prompts = []
    fake.script = [
        reply(
            {
                "valores": {
                    ids["Nombre completo"]: "Persona Ficticia",
                    ids["Estado civil"]: "Soltero (a)",
                    ids["Datos familiares"]: [
                        ["Familiar Ficticio", 52, "Madre", "", "Comerciante", "8000"],
                        "no es una fila",
                    ],
                    ids["Contactos de emergencia"]: "no es una tabla",
                    # La IA no puede llenar el dictamen ni los niveles, aunque lo intente.
                    ids["Dictamen (observaciones)"]: "Persona confiable",
                    ids["Situación económica"]: "Suficiente (2)",
                    ids["Score total"]: 10,
                    ids["¿Se considera candidato?"]: "Es viable (9-10)",
                },
                "ilegibles": [],
                "faltantes": [],
            }
        )
    ]
    proposal = recruiter.post(
        f"{API}/assessments/{study['id']}/digitization", json={"file_id": scanned["id"]}
    )
    assert proposal.status_code == 200, proposal.text
    assert proposal.json()["values"] == {
        ids["Nombre completo"]: "Persona Ficticia",
        ids["Estado civil"]: "Soltero (a)",
        ids["Datos familiares"]: [["Familiar Ficticio", "52", "Madre", "", "Comerciante", "8000"]],
    }
    _, system, user = fake.prompts[0]
    assert system == assistant.DIGITIZATION_SYSTEM
    # La IA recibe las casillas del Excel como sí/no y las columnas de cada tabla…
    assert "Soltero (a): | sí" in user and "Casado (a): | no" in user
    assert f"- {ids['Datos familiares']}: Datos familiares [TABLA] (columnas: Nombre | Edad" in user
    # …pero no los campos de captura manual.
    for label in MANUAL_ONLY:
        assert ids[label] not in user

    # La persona acepta la lectura y anota a mano el dictamen y los niveles.
    answers = {
        key: {"value": value, "source": "IA"} for key, value in proposal.json()["values"].items()
    }
    answers |= {
        ids["Fecha de aplicación"]: {"value": "2026-11-10"},
        ids["Contactos de emergencia"]: {"value": [["Contacto Ficticio", "5512345678", "", "Tía"]]},
        ids["Alimentación"]: {"value": "3500"},
        ids["Dictamen (observaciones)"]: {"value": "Dictamen del aplicador.", "source": "IA"},
        ids["Situación económica"]: {"value": "Medio (1)", "source": "IA"},
        ids["Score total"]: {"value": "8"},
        ids["¿Se considera candidato?"]: {"value": "Es viable con reservas (7-8)"},
        ids["Visita domiciliaria"]: {"value": True},
    }
    saved = update(recruiter, study, status="COMPLETADO", data={"answers": answers})
    assert saved.status_code == 200, saved.text
    stored = saved.json()["data"]["answers"]
    assert stored[ids["Datos familiares"]]["source"] == "IA"
    assert stored[ids["Contactos de emergencia"]]["value"] == [
        ["Contacto Ficticio", "5512345678", "", "Tía"]
    ]
    # Un campo de captura manual nunca queda como «leído por la IA».
    assert stored[ids["Dictamen (observaciones)"]]["source"] == "MANUAL"
    assert stored[ids["Situación económica"]]["source"] == "MANUAL"
    # El sistema guarda lo que anotó la persona, pero no calcula ninguna puntuación.
    assert saved.json()["score"] is None and stored[ids["Score total"]]["value"] == "8"

    # Reglas de los campos del formato.
    for field, value, fragment in (
        ("Score total", "11", "fuera del rango"),
        ("Alimentación", "-5", "fuera del rango"),
        ("Estado civil", "Comprometido", "elige una de las opciones"),
        ("Datos familiares", "texto suelto", "formato esperado"),
    ):
        bad = update(
            recruiter,
            saved.json(),
            data={"answers": {**answers, ids[field]: {"value": value}}},
        )
        assert bad.status_code == 422 and fragment in bad.json()["detail"], field

    # Nada del estudio llega a la síntesis del expediente.
    assign(admin, "SINTESIS_EXPEDIENTES")
    fake.prompts = []
    fake.script = [reply({"hechos_documentados": ["Tiene experiencia en nómina"]})]
    synthesis = recruiter.post(f"{API}/applications/{ana}/syntheses")
    assert synthesis.status_code in (200, 201), synthesis.text
    sent = fake.prompts[0][2]
    for secret in ("Dictamen del aplicador", "Es viable", "Medio (1)", "Contacto Ficticio", "3500"):
        assert secret not in sent


def test_el_estudio_en_excel_no_se_acepta_como_cv(recruiter, vacancy_id):
    book = xlsx({"A1": "Estudio"})
    refused = recruiter.post(
        f"{API}/vacancies/{vacancy_id}/files",
        params={"document_type": "PSICOMETRIA", "filename": "prueba.xlsx"},
        content=book,
    )
    assert refused.status_code == 422 and "Formato no permitido" in refused.json()["detail"]
    found = extract_text(
        io.BytesIO(xlsx({"A1": "Nombre completo:", "B1": "Persona " * 10})), "xlsx"
    )
    assert found.text.startswith("Nombre completo: | Persona")
