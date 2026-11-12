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

    # La descripción no llega a la síntesis del expediente.
    assign(admin, "SINTESIS_EXPEDIENTES")
    fake.prompts = []
    fake.script = [reply({"hechos_documentados": ["Tiene experiencia en nómina"]})]
    assert recruiter.post(f"{API}/applications/{ana}/syntheses").status_code in (200, 201)
    assert "Fachada" not in fake.prompts[0][2]


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
