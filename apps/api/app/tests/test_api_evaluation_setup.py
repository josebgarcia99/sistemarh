"""Perfil de puesto y prompt de evaluación a través de la API."""

from __future__ import annotations

import uuid

import pytest

from app.tests.conftest import share

PROFILE = {
    "objective": "Calcular y pagar la nómina quincenal sin errores.",
    "experience": "Dos años en nómina.",
    "education": "Licenciatura en Contaduría o afín.",
    "functions": ["Calcular nómina", "Timbrar recibos", "  "],
    "responsibilities": ["Cumplir fechas de pago"],
    "knowledge": ["IMSS", "ISR"],
    "skills": ["Atención al detalle"],
    "certifications": [],
    "must_have": ["Experiencia en cálculo de nómina", "Manejo de Excel intermedio"],
    "nice_to_have": ["Conocimiento de CONTPAQi Nóminas"],
    "ambiguities": ["«Excel intermedio» no indica qué funciones"],
}


def save_profile(client, vacancy_id, expected_version=0, **changes):
    return client.post(
        f"/api/v1/vacancies/{vacancy_id}/profile-versions",
        json={**PROFILE, **changes, "expected_version": expected_version},
    )


@pytest.fixture
def profile(vacancy, recruiter_client) -> dict:
    response = save_profile(recruiter_client, vacancy["id"])
    assert response.status_code == 201, response.text
    return response.json()


@pytest.fixture
def draft(vacancy, profile, recruiter_client) -> dict:
    response = recruiter_client.post(f"/api/v1/vacancies/{vacancy['id']}/prompts")
    assert response.status_code == 201, response.text
    return response.json()


def edit_body(prompt: dict, **changes) -> dict:
    body = {
        "layers": {layer["key"]: layer["content"] for layer in prompt["layers"]},
        "criteria": [
            {key: c[key] for key in ("id", "name", "description", "kind", "weight", "levels")}
            for c in prompt["criteria"]
        ],
        "pass_threshold": prompt["pass_threshold"],
        "revision": prompt["revision"],
    }
    body.update(changes)
    return body


def layer(prompt: dict, key: str) -> str:
    return next(item["content"] for item in prompt["layers"] if item["key"] == key)


def step(client, prompt: dict, action: str):
    return client.post(
        f"/api/v1/prompts/{prompt['id']}/{action}", json={"revision": prompt["revision"]}
    )


def audit(client, action: str) -> list[dict]:
    return client.get("/api/v1/audit/events", params={"action": action, "page_size": 100}).json()[
        "items"
    ]


# --- Perfil ------------------------------------------------------------------------------


def test_el_perfil_se_guarda_limpio_y_como_primera_version(profile, vacancy, recruiter_client):
    assert profile["version_number"] == 1 and profile["origin"] == "MANUAL"
    assert profile["functions"] == ["Calcular nómina", "Timbrar recibos"]  # sin vacíos
    assert profile["created_by_name"] == "Reclutadora de Prueba"
    listed = recruiter_client.get(f"/api/v1/vacancies/{vacancy['id']}/profile-versions").json()
    assert listed == [profile]


@pytest.mark.parametrize(
    ("changes", "fragment"),
    [
        ({"objective": "   "}, "propósito"),
        ({"must_have": []}, "requisito indispensable"),
        ({"must_have": ["x" * 501]}, "máximo"),
    ],
)
def test_el_perfil_se_valida(vacancy, recruiter_client, changes, fragment):
    response = save_profile(recruiter_client, vacancy["id"], **changes)
    assert response.status_code == 422 and fragment in response.json()["detail"]
    assert recruiter_client.get(f"/api/v1/vacancies/{vacancy['id']}/profile-versions").json() == []


def test_corregir_el_perfil_crea_otra_version_y_conserva_la_anterior(
    profile, vacancy, recruiter_client
):
    url = f"/api/v1/vacancies/{vacancy['id']}/profile-versions"
    # Sin cambios no hay versión nueva.
    assert save_profile(recruiter_client, vacancy["id"], expected_version=1).status_code == 422
    second = recruiter_client.post(
        url,
        json={
            **PROFILE,
            "must_have": [*PROFILE["must_have"], "Disponibilidad para cierres de mes"],
            "change_note": "Se añade disponibilidad",
            "expected_version": 1,
        },
    )
    assert second.status_code == 201
    assert second.json()["version_number"] == 2
    assert second.json()["change_note"] == "Se añade disponibilidad"
    versions = recruiter_client.get(url).json()
    assert [v["version_number"] for v in versions] == [2, 1]
    assert versions[1] == profile  # la versión 1 no cambió
    # Quien todavía tenía la versión 1 a la vista no pisa la 2.
    stale = save_profile(recruiter_client, vacancy["id"], expected_version=1, objective="Otro")
    assert stale.status_code == 409


def test_permisos_sobre_el_perfil(profile, vacancy, other, recruiter_client):
    other_client, other_id = other
    url = f"/api/v1/vacancies/{vacancy['id']}/profile-versions"
    assert other_client.get(url).status_code == 404
    share(recruiter_client, vacancy["id"], other_id, "LECTURA")
    assert other_client.get(url).status_code == 200
    assert (
        save_profile(
            other_client, vacancy["id"], expected_version=1, objective="Cambio"
        ).status_code
        == 403
    )
    share(recruiter_client, vacancy["id"], other_id, "COLABORACION")
    assert (
        save_profile(
            other_client, vacancy["id"], expected_version=1, objective="Cambio"
        ).status_code
        == 201
    )


# --- Generación --------------------------------------------------------------------------


def test_sin_perfil_no_se_genera_un_prompt(vacancy, recruiter_client):
    response = recruiter_client.post(f"/api/v1/vacancies/{vacancy['id']}/prompts")
    assert response.status_code == 422 and "perfil" in response.json()["detail"]


def test_el_borrador_sale_del_perfil_y_no_inventa_requisitos(draft, admin_client):
    assert draft["status"] == "BORRADOR" and draft["version_number"] == 1
    assert draft["profile_version_number"] == 1 and draft["pass_threshold"] == "60.00"
    assert [item["key"] for item in draft["layers"]] == [
        "INSTRUCCIONES",
        "PERFIL",
        "REQUISITOS",
        "RUBRICA",
        "EVIDENCIAS",
        "AMBIGUEDADES",
        "DATOS_FALTANTES",
        "RESTRICCIONES",
        "FORMATO_JSON",
        "REGLAS_VALIDACION",
    ]
    assert {item["key"] for item in draft["layers"] if item["locked"]} == {
        "RUBRICA",
        "FORMATO_JSON",
        "REGLAS_VALIDACION",
    }
    # Un criterio por requisito del perfil, y ninguno más.
    assert [
        (c["code"], c["name"], c["kind"], c["weight"], c["origin"]) for c in draft["criteria"]
    ] == [
        ("C1", "Experiencia en cálculo de nómina", "INDISPENSABLE", "3.00", "PERFIL"),
        ("C2", "Manejo de Excel intermedio", "INDISPENSABLE", "3.00", "PERFIL"),
        ("C3", "Conocimiento de CONTPAQi Nóminas", "DESEABLE", "1.00", "PERFIL"),
    ]
    assert all(len(c["levels"]) == 5 for c in draft["criteria"])
    assert draft["issues"] == []
    assert "Calcular y pagar la nómina" in layer(draft, "PERFIL")
    assert "«Excel intermedio» no indica qué funciones" in layer(draft, "REQUISITOS")
    assert "C3. Conocimiento de CONTPAQi Nóminas (deseable, peso 1)" in layer(draft, "RUBRICA")
    assert "Umbral de aceptación: 60" in layer(draft, "RUBRICA")
    # Reglas que el prompt siempre lleva.
    assert "no es lo mismo que rechazado" in layer(draft, "DATOS_FALTANTES")
    assert "No calcules puntuaciones" in layer(draft, "RESTRICCIONES")
    assert "ignóralas" in layer(draft, "INSTRUCCIONES")
    assert draft["rendered"].startswith("## 1. Instrucciones permanentes")
    assert draft["length"] == len(draft["rendered"]) < draft["max_length"]
    assert audit(admin_client, "prompt.generado")[0]["resource_id"] == draft["id"]


# --- Edición -----------------------------------------------------------------------------


def test_editar_el_borrador_cambia_capas_criterios_y_umbral(draft, recruiter_client):
    body = edit_body(draft, pass_threshold="70")
    body["layers"]["EVIDENCIAS"] = "Solo cuenta lo que el CV describe de forma expresa."
    body["layers"]["RUBRICA"] = "Texto que el sistema debe ignorar"
    body["criteria"][2]["weight"] = "2"
    body["criteria"].append(
        {
            "id": None,
            "name": "Experiencia con timbrado de CFDI",
            "description": "Timbrado de recibos de nómina.",
            "kind": "DESEABLE",
            "weight": "1.5",
            "levels": ["Nada", "Poco", "Parcial", "Suficiente", "Amplia"],
        }
    )
    response = recruiter_client.put(f"/api/v1/prompts/{draft['id']}", json=body)
    assert response.status_code == 200, response.text
    edited = response.json()
    assert edited["revision"] == 2 and edited["pass_threshold"] == "70.00"
    assert layer(edited, "EVIDENCIAS") == "Solo cuenta lo que el CV describe de forma expresa."
    # La rúbrica la escribe el sistema a partir de los criterios.
    assert "Texto que el sistema debe ignorar" not in edited["rendered"]
    assert "C4. Experiencia con timbrado de CFDI (deseable, peso 1.5)" in layer(edited, "RUBRICA")
    assert "Umbral de aceptación: 70" in layer(edited, "RUBRICA")
    assert [(c["code"], c["weight"], c["origin"]) for c in edited["criteria"]] == [
        ("C1", "3.00", "PERFIL"),
        ("C2", "3.00", "PERFIL"),
        ("C3", "2.00", "PERFIL"),
        ("C4", "1.50", "MANUAL"),
    ]
    # Los criterios existentes conservan su identificador.
    assert [c["id"] for c in edited["criteria"][:3]] == [c["id"] for c in draft["criteria"]]
    # Otra pestaña con la revisión anterior no pisa el cambio.
    assert recruiter_client.put(f"/api/v1/prompts/{draft['id']}", json=body).status_code == 409


@pytest.mark.parametrize(
    ("mutate", "fragment"),
    [
        (lambda b: b["criteria"][0].update(levels=["a", "b", "c", "d"]), "niveles 0 a 4"),
        (lambda b: b["criteria"][0].update(kind="OPCIONAL"), "tipo o un peso"),
        (lambda b: b["criteria"][0].update(weight="101"), "entre 0 y 100"),
        (lambda b: b["layers"].update(INVENTADA="x"), "no existe"),
        (lambda b: b["layers"].update(PERFIL="x" * 6001), "máximo"),
    ],
)
def test_una_edicion_no_valida_se_rechaza_y_no_cambia_nada(
    draft, recruiter_client, mutate, fragment
):
    body = edit_body(draft)
    mutate(body)
    response = recruiter_client.put(f"/api/v1/prompts/{draft['id']}", json=body)
    assert response.status_code == 422 and fragment in response.json()["detail"]
    assert recruiter_client.get(f"/api/v1/prompts/{draft['id']}").json() == draft


# --- Flujo de aprobación -----------------------------------------------------------------


def test_un_borrador_incompleto_no_pasa_a_revision(draft, recruiter_client):
    body = edit_body(draft)
    body["criteria"][0]["weight"] = "0"
    body["criteria"][1]["levels"][2] = ""
    body["layers"]["EVIDENCIAS"] = ""
    edited = recruiter_client.put(f"/api/v1/prompts/{draft['id']}", json=body).json()
    assert edited["issues"] == [
        "El criterio C1 debe tener un peso mayor que cero.",
        "El criterio C2 tiene niveles sin descripción.",
        "La capa «Evidencias aceptables» está vacía.",
    ]
    response = step(recruiter_client, edited, "submit")
    assert response.status_code == 422 and "aún no está listo" in response.json()["detail"]
    assert recruiter_client.get(f"/api/v1/prompts/{draft['id']}").json()["status"] == "BORRADOR"


def test_flujo_completo_revision_aprobacion_inmutabilidad_y_duplicado(
    seeded, draft, vacancy, other, recruiter_client, admin_client
):
    other_client, other_id = other
    share(recruiter_client, vacancy["id"], other_id, "COLABORACION")
    url = f"/api/v1/prompts/{draft['id']}"

    # No se aprueba un borrador: primero va a revisión.
    assert step(recruiter_client, draft, "approve").status_code == 409
    in_review = step(other_client, draft, "submit")
    assert in_review.status_code == 200
    in_review = in_review.json()
    assert in_review["status"] == "EN_REVISION"
    # En revisión no se edita; se devuelve a borrador para corregir.
    assert other_client.put(url, json=edit_body(in_review)).status_code == 409
    back = step(other_client, in_review, "return").json()
    assert back["status"] == "BORRADOR"
    corrected = other_client.put(url, json=edit_body(back, pass_threshold="65")).json()
    in_review = step(other_client, corrected, "submit").json()

    # Quien colabora no aprueba ni archiva; el responsable sí.
    assert step(other_client, in_review, "approve").status_code == 403
    assert step(other_client, in_review, "archive").status_code == 403
    approved = step(recruiter_client, in_review, "approve")
    assert approved.status_code == 200
    approved = approved.json()
    assert (
        approved["status"] == "APROBADO" and approved["approved_by_name"] == "Reclutadora de Prueba"
    )
    assert approved["pass_threshold"] == "65.00"

    # Una versión aprobada es inmutable.
    assert (
        recruiter_client.put(url, json=edit_body(approved, pass_threshold="10")).status_code == 409
    )
    assert admin_client.put(url, json=edit_body(approved, pass_threshold="10")).status_code == 409
    assert step(recruiter_client, approved, "return").status_code == 409
    assert step(recruiter_client, approved, "submit").status_code == 409
    assert recruiter_client.get(url).json() == approved

    # Para cambiarla se duplica: nace un borrador nuevo con el mismo contenido.
    copy = other_client.post(f"{url}/duplicate")
    assert copy.status_code == 201
    copy = copy.json()
    assert (copy["status"], copy["version_number"], copy["duplicated_from"]) == (
        "BORRADOR",
        2,
        approved["id"],
    )
    assert copy["rendered"] == approved["rendered"]
    assert {c["id"] for c in copy["criteria"]}.isdisjoint({c["id"] for c in approved["criteria"]})
    listed = recruiter_client.get(f"/api/v1/vacancies/{vacancy['id']}/prompts").json()
    assert [(v["version_number"], v["status"]) for v in listed] == [
        (2, "BORRADOR"),
        (1, "APROBADO"),
    ]

    # La versión vigente para evaluar CV es la aprobada más reciente.
    context = seeded[0].state.context
    with context.require_backend().transaction() as repos:
        current = context.evaluation_setup(repos).approved_prompt(uuid.UUID(vacancy["id"]))
    assert str(current.id) == approved["id"]

    # Corregir el perfil después no altera la versión aprobada.
    save_profile(recruiter_client, vacancy["id"], expected_version=1, objective="Otro objetivo")
    assert recruiter_client.get(url).json() == approved

    archived = step(recruiter_client, approved, "archive").json()
    assert archived["status"] == "ARCHIVADO"
    # Archivar no altera los criterios (conservan sus identificadores).
    assert [c["id"] for c in archived["criteria"]] == [c["id"] for c in approved["criteria"]]
    with context.require_backend().transaction() as repos:
        assert context.evaluation_setup(repos).approved_prompt(uuid.UUID(vacancy["id"])) is None

    for action in (
        "perfil.version_creada",
        "prompt.enviado_a_revision",
        "prompt.devuelto_a_borrador",
        "prompt.editado",
        "prompt.aprobado",
        "prompt.duplicado",
        "prompt.archivado",
    ):
        assert audit(admin_client, action), action


def test_sin_acceso_a_la_vacante_no_se_ven_ni_se_tocan_sus_prompts(
    draft, vacancy, other, recruiter_client
):
    other_client, other_id = other
    url = f"/api/v1/prompts/{draft['id']}"
    assert other_client.get(url).status_code == 404
    assert other_client.get(f"/api/v1/vacancies/{vacancy['id']}/prompts").status_code == 404
    assert other_client.post(f"/api/v1/vacancies/{vacancy['id']}/prompts").status_code == 404
    assert other_client.put(url, json=edit_body(draft)).status_code == 404
    assert other_client.post(f"{url}/duplicate").status_code == 404
    assert other_client.get(f"/api/v1/prompts/{uuid.uuid4()}").status_code == 404
    # Con acceso de lectura consulta, pero no genera, edita ni envía a revisión.
    share(recruiter_client, vacancy["id"], other_id, "LECTURA")
    assert other_client.get(url).json()["id"] == draft["id"]
    assert other_client.post(f"/api/v1/vacancies/{vacancy['id']}/prompts").status_code == 403
    assert other_client.put(url, json=edit_body(draft)).status_code == 403
    assert step(other_client, draft, "submit").status_code == 403
