"""Fotografías del estudio socioeconómico descritas por la IA (imágenes inventadas)."""

# ruff: noqa: F401, F811  (las fixtures se importan de otro módulo de pruebas)
from __future__ import annotations

import base64
import io
import json

import httpx
import pytest
from PIL import Image

from app.infrastructure.ai_providers.http_clients import (
    AnthropicClient,
    GeminiClient,
    OpenAIClient,
)
from app.infrastructure.documents.photos import PhotoError, prepare_photo
from app.modules.ai_settings.domain.models import ImageInput, ProviderCode
from app.modules.assessments.domain import assistant
from app.tests.support.sample_files import pdf_cv, photo
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

IMAGE = ImageInput("image/jpeg", b"\xff\xd8 imagen ficticia")
B64 = base64.b64encode(IMAGE.data).decode()


def _client(handler):
    return lambda: httpx.Client(transport=httpx.MockTransport(handler))


# --- Preparación de la fotografía ----------------------------------------------------------


def test_la_fotografia_se_envia_reducida_derecha_y_sin_metadatos():
    original = photo()
    with Image.open(io.BytesIO(original)) as image:
        assert image.size == (2400, 1800) and image.getexif().get_ifd(0x8825)  # trae GPS
    prepared = prepare_photo(original)
    with Image.open(io.BytesIO(prepared)) as image:
        # Girada como indicaba la cámara y reducida a 1600 px de lado mayor.
        assert image.format == "JPEG" and image.size == (1200, 1600)
        exif = image.getexif()
        assert len(exif) == 0 and not exif.get_ifd(0x8825)
    assert b"Telefono Ficticio" not in prepared and len(prepared) < len(original)
    # Un PNG con transparencia también sale como JPEG.
    buffer = io.BytesIO()
    Image.new("RGBA", (300, 200), (0, 0, 0, 0)).save(buffer, format="PNG")
    with Image.open(io.BytesIO(prepare_photo(buffer.getvalue()))) as image:
        assert image.format == "JPEG" and image.size == (300, 200)
        assert image.getpixel((10, 10)) == (255, 255, 255)
    for broken in (b"", b"no es una imagen", original[:200]):
        with pytest.raises(PhotoError):
            prepare_photo(broken)


# --- Clientes de los proveedores -----------------------------------------------------------


def test_los_tres_proveedores_reciben_la_imagen_en_su_formato():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        seen[request.url.host] = body
        if "googleapis" in request.url.host:
            return httpx.Response(
                200,
                json={
                    "candidates": [
                        {"content": {"parts": [{"text": "ok"}]}, "finishReason": "STOP"}
                    ],
                    "usageMetadata": {"promptTokenCount": 300, "candidatesTokenCount": 5},
                },
            )
        if "anthropic" in request.url.host:
            return httpx.Response(
                200,
                json={
                    "content": [{"type": "text", "text": "ok"}],
                    "usage": {"input_tokens": 300, "output_tokens": 5},
                },
            )
        return httpx.Response(
            200,
            json={
                "status": "completed",
                "output": [{"type": "message", "content": [{"type": "output_text", "text": "ok"}]}],
                "usage": {"input_tokens": 300, "output_tokens": 5},
            },
        )

    arguments = {"system": "sistema", "user": "usuario", "max_output_tokens": 500}
    for client in (
        GeminiClient(client_factory=_client(handler)),
        AnthropicClient("2026-10-21", client_factory=_client(handler)),
        OpenAIClient(client_factory=_client(handler)),
    ):
        assert client.generate("clave-ficticia", "modelo", images=[IMAGE], **arguments).text == "ok"

    assert seen["generativelanguage.googleapis.com"]["contents"] == [
        {
            "role": "user",
            "parts": [
                {"inline_data": {"mime_type": "image/jpeg", "data": B64}},
                {"text": "usuario"},
            ],
        }
    ]
    assert seen["api.anthropic.com"]["messages"] == [
        {
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {"type": "base64", "media_type": "image/jpeg", "data": B64},
                },
                {"type": "text", "text": "usuario"},
            ],
        }
    ]
    assert seen["api.openai.com"]["input"] == [
        {
            "role": "user",
            "content": [
                {"type": "input_text", "text": "usuario"},
                {"type": "input_image", "image_url": f"data:image/jpeg;base64,{B64}"},
            ],
        }
    ]
    assert seen["api.openai.com"]["store"] is False


# --- Desde la API ---------------------------------------------------------------------------


def test_la_ia_describe_una_fotografia_del_estudio_y_la_persona_decide(
    ana, recruiter, admin, vacancy_id, providers
):
    [template] = recruiter.get(f"{API}/form-templates").json()
    ids = {f["label"]: f["id"] for section in template["sections"] for f in section["fields"]}
    facade = ids["Fotografía: fachada de la vivienda"]
    study = create(recruiter, ana, "ESTUDIO_SOCIOECONOMICO", template_id=template["id"]).json()
    picture = upload(
        recruiter, vacancy_id, "fachada.jpg", photo(), document_type="ESTUDIO_SOCIOECONOMICO"
    )
    assert picture["sensitive"] is True and picture["encrypted"] is True
    url = f"{API}/assessments/{study['id']}/photo-descriptions"
    body = {"file_id": picture["id"], "field_id": facade}

    # Sin un modelo asignado a la operación, se explica y no se envía nada.
    refused = recruiter.post(url, json=body)
    assert refused.status_code == 422 and "modelo" in refused.json()["detail"]
    assign(admin, "DESCRIPCION_FOTOGRAFIAS")
    fake = providers[ProviderCode.ANTHROPIC]
    fake.prompts, fake.images = [], []
    fake.script = [
        reply(
            {
                "descripcion": "Fachada de dos niveles con   acabado de pintura clara; "
                "portón metálico y una ventana al frente.",
                "no_se_distingue": ["El número exterior", "El número exterior", 7],
                # Nada de esto se acepta, aunque la IA lo devuelva.
                "nivel_socioeconomico": "medio",
                "recomendacion": "Persona confiable",
                "puntuacion": 9,
            }
        )
    ]
    response = recruiter.post(url, json=body)
    assert response.status_code == 200, response.text
    assert response.json() == {
        "description": "Fachada de dos niveles con acabado de pintura clara; portón metálico "
        "y una ventana al frente.",
        "unclear": ["El número exterior"],
    }
    _, system, user = fake.prompts[0]
    assert (
        system == assistant.PHOTO_SYSTEM and "No saques conclusiones sobre las personas" in system
    )
    assert "«Fotografía: fachada de la vivienda»" in user
    # Viaja una sola imagen: descifrada, reducida y sin los metadatos del teléfono.
    [sent] = fake.images
    assert sent.media_type == "image/jpeg" and b"Telefono Ficticio" not in sent.data
    with Image.open(io.BytesIO(sent.data)) as image:
        assert max(image.size) == 1600 and len(image.getexif()) == 0
    # Es una propuesta: el estudio no cambió.
    assert recruiter.get(f"{API}/assessments/{study['id']}").json()["data"]["answers"] == {}
    [event] = audit(admin, "estudio.fotografia_descrita")
    assert event["result"] == "PERMITIDO" and event["details"]["documento"] == picture["id"]
    usage = admin.get(f"{API}/ai/usage", params={"year": 2026, "month": 11}).json()["rows"]
    assert "DESCRIPCION_FOTOGRAFIAS" in {row["operation"] for row in usage}

    # La persona la acepta (o la corrige) y la guarda junto a la fotografía.
    answers = {
        facade: {
            "value": picture["id"],
            "description": response.json()["description"],
            "description_source": "IA",
        },
        ids["Fotografía: localización"]: {"value": picture["id"], "description": "   "},
        # Una descripción solo tiene sentido junto a un documento.
        ids["Ocupación"]: {"value": "Comerciante", "description": "no aplica"},
    }
    saved = update(recruiter, study, status="EN_PROCESO", data={"answers": answers})
    assert saved.status_code == 200, saved.text
    stored = saved.json()["data"]["answers"]
    assert stored[facade]["description"].startswith("Fachada de dos niveles")
    assert stored[facade]["description_source"] == "IA" and stored[facade]["verified"] is False
    assert "description" not in stored[ids["Fotografía: localización"]]
    assert "description" not in stored[ids["Ocupación"]]
    # Si la persona la reescribe, deja de contar como propuesta por la IA.
    corrected = {**stored, facade: {"value": picture["id"], "description": "Fachada de un nivel."}}
    again = update(recruiter, saved.json(), data={"answers": corrected})
    assert again.json()["data"]["answers"][facade]["description_source"] == "MANUAL"

    # La descripción guardada sí llega a la síntesis del expediente (quien la pide
    # tiene el permiso del estudio).
    assign(admin, "SINTESIS_EXPEDIENTES")
    fake.prompts = []
    fake.script = [reply({"observaciones_humanas": ["Fachada de un nivel (fotografía)"]})]
    synthesis = recruiter.post(f"{API}/applications/{ana}/syntheses")
    assert synthesis.status_code in (200, 201) and synthesis.json()["includes_study"] is True
    assert "(escrita a mano): Fachada de un nivel." in fake.prompts[0][2]


def test_solo_se_describen_imagenes_del_estudio_y_con_permiso(
    ana, recruiter, admin, other, vacancy_id, providers
):
    [template] = recruiter.get(f"{API}/form-templates").json()
    study = create(recruiter, ana, "ESTUDIO_SOCIOECONOMICO", template_id=template["id"]).json()
    url = f"{API}/assessments/{study['id']}/photo-descriptions"
    assign(admin, "DESCRIPCION_FOTOGRAFIAS")
    fake = providers[ProviderCode.ANTHROPIC]
    fake.prompts, fake.images = [], []

    scanned = upload(
        recruiter,
        vacancy_id,
        "estudio.pdf",
        pdf_cv("Estudio ficticio " * 5),
        document_type="ESTUDIO_SOCIOECONOMICO",
    )
    not_image = recruiter.post(url, json={"file_id": scanned["id"]})
    assert not_image.status_code == 422 and "JPG o PNG" in not_image.json()["detail"]
    attachment = upload(recruiter, vacancy_id, "foto.jpg", photo(), document_type="ADJUNTO")
    wrong_type = recruiter.post(url, json={"file_id": attachment["id"]})
    assert wrong_type.status_code == 422 and "Estudio socioeconómico" in wrong_type.json()["detail"]
    # Otra persona, sin acceso a la vacante ni el permiso adicional, no puede pedirla.
    picture = upload(
        recruiter,
        vacancy_id,
        "fachada.png",
        photo(fmt="PNG"),
        document_type="ESTUDIO_SOCIOECONOMICO",
    )
    stranger, _ = other
    assert stranger.post(url, json={"file_id": picture["id"]}).status_code in (403, 404)
    # Solo aplica al estudio socioeconómico.
    test = create(recruiter, ana, "PRUEBA_TECNICA", data={"test_type": "Excel"}).json()
    other_kind = recruiter.post(
        f"{API}/assessments/{test['id']}/photo-descriptions", json={"file_id": picture["id"]}
    )
    assert other_kind.status_code == 422
    assert fake.images == [] and fake.prompts == []

    # Una respuesta sin descripción no sirve como propuesta; el intento queda auditado.
    fake.script = [reply({"descripcion": "", "nivel_socioeconomico": "alto"})]
    useless = recruiter.post(url, json={"file_id": picture["id"]})
    assert useless.status_code == 503
    assert [e["result"] for e in audit(admin, "estudio.fotografia_descrita")] == ["FALLIDO"]
    assert len(fake.images) == 1


# --- Las descripciones en la síntesis y en el reporte ---------------------------------------


def _study_with_photo(recruiter, vacancy_id, application_id):
    """Un estudio con una fotografía descrita y datos que no deben salir de él."""
    [template] = recruiter.get(f"{API}/form-templates").json()
    ids = {f["label"]: f["id"] for section in template["sections"] for f in section["fields"]}
    study = create(
        recruiter, application_id, "ESTUDIO_SOCIOECONOMICO", template_id=template["id"]
    ).json()
    picture = upload(
        recruiter, vacancy_id, "fachada.jpg", photo(), document_type="ESTUDIO_SOCIOECONOMICO"
    )
    answers = {
        ids["Fotografía: fachada de la vivienda"]: {
            "value": picture["id"],
            "description": "Fachada de dos niveles con portón metálico.",
            "description_source": "IA",
        },
        ids["Fotografía: localización"]: {
            "value": picture["id"],
            "description": "Calle pavimentada con alumbrado.",
        },
        ids["Religión"]: {"value": "RELIGION-SECRETA"},
        ids["Total ingreso mensual"]: {"value": "12345"},
        ids["Dictamen (observaciones)"]: {"value": "DICTAMEN-SECRETO"},
        ids["¿Se considera candidato?"]: {"value": "No es viable (0-6)"},
    }
    saved = update(recruiter, study, status="EN_PROCESO", data={"answers": answers})
    assert saved.status_code == 200, saved.text
    return saved.json()


def test_las_descripciones_de_las_fotos_entran_en_la_sintesis_solo_con_permiso(
    ana, recruiter, admin, other, vacancy_id, providers
):
    _study_with_photo(recruiter, vacancy_id, ana)
    assign(admin, "SINTESIS_EXPEDIENTES")
    fake = providers[ProviderCode.ANTHROPIC]
    fake.prompts = []
    fake.script = [
        reply({"observaciones_humanas": ["Fachada de dos niveles (fotografía del estudio)"]})
    ]
    url = f"{API}/applications/{ana}/syntheses"
    created = recruiter.post(url)
    assert created.status_code in (200, 201), created.text
    synthesis = created.json()
    assert synthesis["includes_study"] is True
    assert "2 fotografías del estudio" in synthesis["sources"]
    _, system, sent = fake.prompts[0]
    assert (
        system == assistant.SYNTHESIS_SYSTEM and "No saques de ellas ninguna conclusión" in system
    )
    assert "FOTOGRAFÍAS DEL ESTUDIO SOCIOECONÓMICO" in sent
    assert (
        "- Fotografía: fachada de la vivienda (propuesta por la IA y revisada): "
        "Fachada de dos niveles con portón metálico." in sent
    )
    assert "- Fotografía: localización (escrita a mano): Calle pavimentada" in sent
    # Del estudio solo salen las descripciones: nada de economía, religión, dictamen ni viabilidad.
    for secret in ("RELIGION-SECRETA", "12345", "DICTAMEN-SECRETO", "No es viable"):
        assert secret not in sent

    # Con la vacante compartida pero sin el permiso del estudio, esa síntesis no se ve…
    stranger, stranger_id = other
    from app.tests.conftest import share

    share(recruiter, vacancy_id, stranger_id, "COLABORACION")
    hidden = stranger.get(url).json()
    assert hidden["latest"] is None and hidden["hidden"] is True
    # …y la que esa persona pida no lleva las fotografías.
    fake.prompts = []
    fake.script = [reply({"hechos_documentados": ["Tiene experiencia en nómina"]})]
    own = stranger.post(url)
    assert own.status_code in (200, 201), own.text
    assert own.json()["includes_study"] is False
    assert "FOTOGRAFÍAS" not in fake.prompts[0][2] and "Fachada" not in fake.prompts[0][2]
    # Un estudio anulado tampoco aporta fotografías.
    study = next(
        item
        for item in recruiter.get(f"{API}/applications/{ana}/assessments").json()["items"]
        if item["kind"] == "ESTUDIO_SOCIOECONOMICO"
    )
    assert update(recruiter, study, status="ANULADO").status_code == 200
    fake.prompts = []
    fake.script = [reply({"hechos_documentados": ["Tiene experiencia en nómina"]})]
    assert recruiter.post(url).json()["includes_study"] is False


def test_el_reporte_de_postulaciones_lleva_las_fotos_solo_para_quien_tiene_el_permiso(
    ana, recruiter, admin, other, vacancy_id, providers
):
    from openpyxl import load_workbook

    from app.tests.conftest import share

    _study_with_photo(recruiter, vacancy_id, ana)

    def export(client) -> tuple[list[str], dict[str, object], str]:
        made = client.post(f"{API}/reports/exports", json={"kind": "POSTULACIONES"})
        assert made.status_code == 201, made.text
        content = client.get(f"{API}/reports/exports/{made.json()['id']}/download").content
        book = load_workbook(io.BytesIO(content))
        sheet = book["Postulaciones"]
        header = [cell.value for cell in sheet[1]]
        rows = {row[0]: row for row in sheet.iter_rows(min_row=2, values_only=True)}
        about = " ".join(str(c.value) for row in book["Acerca del reporte"] for c in row if c.value)
        return header, rows, about

    column = "Fotografías del estudio socioeconómico (descripciones)"
    header, rows, about = export(recruiter)
    assert header[-1] == column and "Datos sensibles" in about
    text = rows["Ana Pérez Ficticia"][-1]
    assert text == (
        "Fotografía: localización: Calle pavimentada con alumbrado.\n"
        "Fotografía: fachada de la vivienda: Fachada de dos niveles con portón metálico."
    )
    # Las demás postulaciones no tienen fotografías; y del estudio no sale nada más.
    assert sum(1 for row in rows.values() if row[-1]) == 1
    flat = " ".join(str(value) for row in rows.values() for value in row)
    for secret in ("RELIGION-SECRETA", "12345", "DICTAMEN-SECRETO", "No es viable"):
        assert secret not in flat
    # El administrador también la ve.
    assert export(admin)[0][-1] == column

    # Con la vacante compartida pero sin el permiso del estudio, la columna no existe.
    stranger, stranger_id = other
    share(recruiter, vacancy_id, stranger_id, "LECTURA")
    header, rows, about = export(stranger)
    assert column not in header and "Datos sensibles" not in about
    assert "Fachada" not in " ".join(str(v) for row in rows.values() for v in row)
