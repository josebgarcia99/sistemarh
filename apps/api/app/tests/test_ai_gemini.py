"""Gemini como tercer proveedor de IA.

El cliente se prueba con un transporte HTTP simulado, con la forma de las
respuestas que documenta Google. No se ha ejecutado contra el servicio real.
"""

# ruff: noqa: F401, F811  (las fixtures se importan de otro módulo de pruebas)
from __future__ import annotations

import json
import logging

import httpx
import pytest

from app.composition.ai import build_provider_clients, env_api_keys
from app.core.config.settings import Environment, Settings
from app.core.logging.setup import redact
from app.infrastructure.ai_providers.http_clients import GeminiClient, ProviderHttpError
from app.modules.ai_settings.domain.models import (
    PROVIDER_NAMES,
    Generation,
    ProviderCode,
    ProviderError,
)
from app.tests.test_api_ai_settings import (
    admin,
    audit,
    master_key,
    provider,
    providers,
    stored_credentials,
)

API = "/api/v1"
# Empieza como una clave de Google pero es inventada y más corta que una real.
GEMINI_KEY = "AIzaFICTICIA-clave-de-prueba-ABCD"


def _client(handler):
    return lambda: httpx.Client(transport=httpx.MockTransport(handler))


# --- Cliente HTTP --------------------------------------------------------------------------


def test_el_cliente_de_gemini_lista_solo_los_modelos_que_generan_texto_y_pagina():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        assert request.url.path == "/v1beta/models"
        # La clave va en la cabecera, nunca en la dirección.
        assert request.headers["x-goog-api-key"] == GEMINI_KEY
        assert GEMINI_KEY not in str(request.url)
        if "pageToken" not in request.url.params:
            return httpx.Response(
                200,
                json={
                    "models": [
                        {
                            "name": "models/gemini-ficticio-pro",
                            "displayName": "Gemini Ficticio Pro",
                            "inputTokenLimit": 1000000,
                            "outputTokenLimit": 65536,
                            "supportedGenerationMethods": ["generateContent", "countTokens"],
                        },
                        {
                            "name": "models/vectores-ficticio",
                            "displayName": "Vectores",
                            "supportedGenerationMethods": ["embedContent"],
                        },
                    ],
                    "nextPageToken": "pagina-2",
                },
            )
        assert request.url.params["pageToken"] == "pagina-2"
        return httpx.Response(
            200,
            json={
                "models": [
                    {
                        "name": "models/gemini-ficticio-flash",
                        "supportedGenerationMethods": ["generateContent"],
                    }
                ]
            },
        )

    models = GeminiClient(client_factory=_client(handler)).list_models(GEMINI_KEY)
    assert [(m.model_id, m.display_name) for m in models] == [
        ("gemini-ficticio-pro", "Gemini Ficticio Pro"),
        ("gemini-ficticio-flash", "gemini-ficticio-flash"),
    ]
    assert models[0].capabilities == {"inputTokenLimit": 1000000, "outputTokenLimit": 65536}
    assert models[1].capabilities is None and len(calls) == 2


def test_el_cliente_de_gemini_genera_texto_y_cuenta_el_razonamiento_como_salida():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1beta/models/gemini-ficticio-pro:generateContent"
        assert request.headers["x-goog-api-key"] == GEMINI_KEY
        assert json.loads(request.content) == {
            "systemInstruction": {"parts": [{"text": "sistema"}]},
            "contents": [{"role": "user", "parts": [{"text": "usuario"}]}],
            "generationConfig": {"maxOutputTokens": 300},
        }
        return httpx.Response(
            200,
            json={
                "candidates": [
                    {
                        "content": {
                            "role": "model",
                            "parts": [
                                {"text": "pensando…", "thought": True},
                                {"text": '{"ok": '},
                                {"text": "true}"},
                            ],
                        },
                        "finishReason": "STOP",
                    }
                ],
                "usageMetadata": {
                    "promptTokenCount": 40,
                    "candidatesTokenCount": 6,
                    "thoughtsTokenCount": 14,
                    "totalTokenCount": 60,
                },
            },
        )

    generation = GeminiClient(client_factory=_client(handler)).generate(
        GEMINI_KEY, "gemini-ficticio-pro", system="sistema", user="usuario", max_output_tokens=300
    )
    assert generation.text == '{"ok": true}' and generation.complete is True
    assert (generation.input_tokens, generation.output_tokens) == (40, 20)


@pytest.mark.parametrize(
    ("response", "kind", "complete"),
    [
        # Cortada por el límite de salida: se entrega marcada como incompleta.
        (
            {
                "candidates": [
                    {"content": {"parts": [{"text": "a medias"}]}, "finishReason": "MAX_TOKENS"}
                ],
                "usageMetadata": {"promptTokenCount": 5, "candidatesTokenCount": 2},
            },
            None,
            False,
        ),
        # Sin candidatos (solicitud bloqueada) o con un formato inesperado.
        ({"promptFeedback": {"blockReason": "SAFETY"}}, "proveedor", None),
        ({"candidates": [{"content": {"parts": [{"text": "x"}]}}]}, "proveedor", None),
        ({"inesperado": True}, "proveedor", None),
    ],
)
def test_el_cliente_de_gemini_distingue_respuestas_cortadas_bloqueadas_y_malformadas(
    response, kind, complete
):
    client = GeminiClient(
        client_factory=_client(lambda request: httpx.Response(200, json=response))
    )
    if kind is None:
        generation = client.generate(GEMINI_KEY, "m", system="s", user="u", max_output_tokens=10)
        assert generation.complete is complete and generation.text == "a medias"
        return
    with pytest.raises(ProviderHttpError) as error:
        client.generate(GEMINI_KEY, "m", system="s", user="u", max_output_tokens=10)
    assert error.value.kind == kind


@pytest.mark.parametrize(
    ("status", "kind"), [(401, "clave"), (403, "clave"), (429, "limite"), (500, "proveedor")]
)
def test_los_errores_de_gemini_no_repiten_la_clave_ni_la_respuesta(status, kind):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, json={"error": {"message": f"clave {GEMINI_KEY} rechazada"}})

    client = GeminiClient(client_factory=_client(handler))
    for call in (
        lambda: client.list_models(GEMINI_KEY),
        lambda: client.generate(GEMINI_KEY, "m", system="s", user="u", max_output_tokens=10),
    ):
        with pytest.raises(ProviderHttpError) as error:
            call()
        assert error.value.kind == kind and GEMINI_KEY not in error.value.message


def test_gemini_se_configura_como_los_demas_proveedores():
    settings = Settings(environment=Environment.TEST, gemini_api_key=GEMINI_KEY)
    assert set(build_provider_clients(settings)) == set(ProviderCode)
    assert env_api_keys(settings) == {ProviderCode.GEMINI: GEMINI_KEY}
    assert env_api_keys(Settings(environment=Environment.TEST)) == {}
    assert PROVIDER_NAMES[ProviderCode.GEMINI] == "Google Gemini"
    # Una clave de Google que llegara a un registro sale oculta.
    assert GEMINI_KEY not in redact(f"fallo con x-goog-api-key: {GEMINI_KEY} en la llamada")
    assert GEMINI_KEY not in redact(f"la clave es {GEMINI_KEY}")


# --- Configuración desde la API ------------------------------------------------------------


def test_gemini_se_registra_prueba_habilita_y_usa_desde_la_pantalla(
    admin, providers, backend, caplog
):
    caplog.set_level(logging.DEBUG)
    before = provider(admin, "GEMINI")
    assert before["name"] == "Google Gemini" and before["key_configured"] is False

    saved = admin.put(f"{API}/ai/providers/GEMINI/key", json={"api_key": GEMINI_KEY})
    assert saved.status_code == 200 and GEMINI_KEY not in saved.text
    assert saved.json()["key_mask"] == "••••ABCD" and saved.json()["key_source"] == "PANTALLA"
    [credential] = stored_credentials(backend)
    assert credential.provider_code == "GEMINI"
    assert GEMINI_KEY not in credential.ciphertext

    tested = admin.post(f"{API}/ai/providers/GEMINI/test").json()
    assert tested["ok"] is True and tested["models_found"] == 2
    assert providers[ProviderCode.GEMINI].received_keys == [GEMINI_KEY]
    assert providers[ProviderCode.ANTHROPIC].received_keys == []

    enabled = admin.put(f"{API}/ai/providers/GEMINI", json={"enabled": True})
    assert enabled.status_code == 200 and enabled.json()["enabled"] is True
    [model] = [
        m
        for m in admin.get(f"{API}/ai/models", params={"provider": "GEMINI"}).json()
        if m["model_id"] == "modelo-grande-1"
    ]
    assigned = admin.put(
        f"{API}/ai/assignments/EVALUACION_DOCUMENTAL", json={"model_id": model["id"]}
    )
    assert assigned.status_code == 200, assigned.text
    assert assigned.json()["model"]["provider_code"] == "GEMINI"

    # La prueba de un modelo llega a Gemini y no a los otros proveedores.
    providers[ProviderCode.GEMINI].script = [Generation("listo", 12, 3, True)]
    probe = admin.post(f"{API}/ai/models/{model['id']}/test")
    assert probe.status_code == 200 and probe.json()["ok"] is True, probe.text
    assert providers[ProviderCode.GEMINI].prompts and not providers[ProviderCode.OPENAI].prompts
    usage = admin.get(f"{API}/ai/usage", params={"year": 2026, "month": 11}).json()
    assert {row["provider_code"] for row in usage["rows"]} == {"GEMINI"}

    # La clave no aparece en respuestas, auditoría ni registros.
    for path in ("/ai/providers", "/ai/models", "/ai/assignments", "/ai/usage"):
        assert GEMINI_KEY not in admin.get(f"{API}{path}").text
    assert GEMINI_KEY not in json.dumps(audit(admin, "ia.clave_registrada"))
    assert GEMINI_KEY not in caplog.text

    revoked = admin.delete(f"{API}/ai/providers/GEMINI/key")
    assert revoked.status_code == 200 and revoked.json()["key_configured"] is False
    assert revoked.json()["enabled"] is False
    assert all(row.ciphertext is None for row in stored_credentials(backend))
