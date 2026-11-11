"""Configuración de IA a través de la API.

Los proveedores están simulados: ninguna prueba se conecta a Anthropic ni a
OpenAI, y las claves son ficticias. Incluye la comprobación de seguridad 9 de
la sección 32.3: las API keys no aparecen en respuestas, logs ni auditoría.
"""

from __future__ import annotations

import json
import logging

import httpx
import pytest
import sqlalchemy as sa

from app.core.config.settings import Environment, Settings
from app.core.security.master_key import MasterKey, generate_key_text
from app.infrastructure.ai_providers.http_clients import (
    AnthropicClient,
    OpenAIClient,
    ProviderHttpError,
)
from app.main import create_app
from app.modules.ai_settings.domain.models import (
    DiscoveredModel,
    Generation,
    Operation,
    ProviderCode,
    ProviderError,
)
from app.modules.ai_settings.infrastructure.orm import AiProviderCredentialRow
from app.tests.conftest import ADMIN_EMAIL, ADMIN_PASSWORD, login

FAKE_KEY = "clave-ficticia-anthropic-0000-ABCD"
OTHER_KEY = "clave-ficticia-anthropic-1111-WXYZ"


class FakeProvider:
    def __init__(self) -> None:
        self.models = [
            DiscoveredModel("modelo-grande-1", "Modelo Grande 1", {"vision": True}),
            DiscoveredModel("modelo-rapido-1", "Modelo Rápido 1", None),
        ]
        self.error: ProviderError | None = None
        self.received_keys: list[str] = []

    def list_models(self, api_key: str) -> list[DiscoveredModel]:
        self.received_keys.append(api_key)
        if self.error is not None:
            raise self.error
        return list(self.models)

    # Respuestas programadas para generate: textos o errores, en orden.
    script: list[Generation | ProviderError] | None = None
    prompts: list[tuple[str, str, str]] | None = None

    def generate(self, api_key, model, *, system, user, max_output_tokens) -> Generation:
        self.prompts = [*(self.prompts or []), (model, system, user)]
        step = self.script.pop(0) if self.script else Generation("OK", 1000, 500, True)
        if isinstance(step, ProviderError):
            raise step
        return step


@pytest.fixture
def providers() -> dict[ProviderCode, FakeProvider]:
    return {code: FakeProvider() for code in ProviderCode}


@pytest.fixture
def master_key() -> MasterKey:
    return MasterKey.from_text(generate_key_text())


def _app(seeded, backend, hasher, clock, providers, master_key, **settings):
    return create_app(
        settings=Settings(environment=Environment.TEST, **settings),
        health_checks={"c": lambda: True},
        backend=backend,
        hasher=hasher,
        clock=clock,
        master_key=master_key,
        ai_clients=providers,
        ai_sleep=lambda seconds: None,
    )


@pytest.fixture
def admin(seeded, backend, hasher, clock, providers, master_key):
    return login(
        _app(seeded, backend, hasher, clock, providers, master_key), ADMIN_EMAIL, ADMIN_PASSWORD
    )


def provider(client, code="ANTHROPIC") -> dict:
    overview = client.get("/api/v1/ai/providers").json()
    return next(item for item in overview["providers"] if item["code"] == code)


def stored_credentials(backend) -> list[AiProviderCredentialRow]:
    with backend._session_factory() as session:
        return list(session.execute(sa.select(AiProviderCredentialRow)).scalars())


def audit(client, action: str) -> list[dict]:
    return client.get("/api/v1/audit/events", params={"action": action, "page_size": 100}).json()[
        "items"
    ]


# --- Acceso ------------------------------------------------------------------------------


def test_la_configuracion_de_ia_es_solo_para_administradores(seeded, recruiter_client):
    for method, path, body in (
        ("get", "/api/v1/ai/providers", None),
        ("get", "/api/v1/ai/models", None),
        ("get", "/api/v1/ai/assignments", None),
        ("put", "/api/v1/ai/providers/ANTHROPIC/key", {"api_key": FAKE_KEY}),
        ("delete", "/api/v1/ai/providers/ANTHROPIC/key", None),
        ("post", "/api/v1/ai/providers/ANTHROPIC/test", None),
        ("put", "/api/v1/ai/providers/ANTHROPIC", {"enabled": True}),
        ("put", "/api/v1/ai/assignments/EXTRACCION_CV", {"model_id": None}),
    ):
        response = getattr(recruiter_client, method)(path, **({"json": body} if body else {}))
        assert response.status_code == 403, f"{method} {path}"


def test_al_inicio_no_hay_claves_ni_modelos(admin):
    overview = admin.get("/api/v1/ai/providers").json()
    assert overview["encryption_available"] is True
    assert [item["name"] for item in overview["providers"]] == ["Anthropic", "OpenAI"]
    for item in overview["providers"]:
        assert item["key_configured"] is False and item["enabled"] is False
        assert item["key_mask"] is None and item["models_available"] == 0
    assert admin.get("/api/v1/ai/models").json() == []
    assignments = admin.get("/api/v1/ai/assignments").json()
    assert [a["operation"] for a in assignments] == [operation.value for operation in Operation]
    assert all(a["model"] is None for a in assignments)


# --- Claves ------------------------------------------------------------------------------


def test_seguridad_9_la_api_key_se_guarda_cifrada_y_nunca_se_devuelve(
    admin, backend, master_key, caplog
):
    caplog.set_level(logging.DEBUG)
    response = admin.put("/api/v1/ai/providers/ANTHROPIC/key", json={"api_key": f"  {FAKE_KEY} "})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["key_configured"] is True and body["key_source"] == "PANTALLA"
    assert body["key_mask"] == "••••ABCD"
    assert body["key_updated_by_name"] == "Administradora de Prueba"
    assert body["enabled"] is False  # registrar la clave no habilita el proveedor

    # En la base: cifrada con la clave maestra y ligada al proveedor.
    (row,) = stored_credentials(backend)
    assert FAKE_KEY not in row.ciphertext and row.last4 == "ABCD"
    assert row.master_key_id == master_key.key_id
    assert master_key.decrypt_text(row.ciphertext, context="ai-provider:ANTHROPIC") == FAKE_KEY

    # La clave no aparece en ninguna respuesta, en la auditoría ni en los logs.
    responses = [
        response.text,
        admin.get("/api/v1/ai/providers").text,
        admin.get("/api/v1/audit/events", params={"page_size": 100}).text,
        admin.post("/api/v1/ai/providers/ANTHROPIC/test").text,
    ]
    # Los logs sí se capturaron: la comprobación no es vacía.
    assert "/api/v1/ai/providers/ANTHROPIC/key" in caplog.text
    for text in (*responses, caplog.text):
        assert FAKE_KEY not in text and "clave-ficticia" not in text
    (event,) = audit(admin, "ia.clave_registrada")
    assert event["details"] == {"terminacion": "ABCD", "sustituye_a_otra": False}


@pytest.mark.parametrize("bad", ["", "corta", "con espacio en medio de la clave", "x" * 501])
def test_una_clave_mal_formada_se_rechaza_sin_repetirla(admin, backend, bad):
    response = admin.put("/api/v1/ai/providers/OPENAI/key", json={"api_key": bad})
    assert response.status_code == 422
    assert bad == "" or bad not in response.text
    assert stored_credentials(backend) == []


def test_sustituir_borra_la_clave_anterior_y_revocar_borra_la_vigente(admin, backend, master_key):
    admin.put("/api/v1/ai/providers/ANTHROPIC/key", json={"api_key": FAKE_KEY})
    admin.put("/api/v1/ai/providers/ANTHROPIC", json={"enabled": True})
    replaced = admin.put("/api/v1/ai/providers/ANTHROPIC/key", json={"api_key": OTHER_KEY})
    assert replaced.json()["key_mask"] == "••••WXYZ"
    rows = sorted(stored_credentials(backend), key=lambda r: r.created_at)
    assert [row.last4 for row in rows] == ["ABCD", "WXYZ"]
    assert rows[0].ciphertext is None and rows[0].revoked_at is not None
    assert master_key.decrypt_text(rows[1].ciphertext, context="ai-provider:ANTHROPIC") == OTHER_KEY
    assert audit(admin, "ia.clave_registrada")[0]["details"]["sustituye_a_otra"] in (True, False)
    assert {e["details"]["sustituye_a_otra"] for e in audit(admin, "ia.clave_registrada")} == {
        True,
        False,
    }

    revoked = admin.delete("/api/v1/ai/providers/ANTHROPIC/key")
    assert revoked.status_code == 200
    assert revoked.json()["key_configured"] is False and revoked.json()["enabled"] is False
    assert all(row.ciphertext is None for row in stored_credentials(backend))
    assert audit(admin, "ia.clave_revocada")[0]["details"] == {"terminacion": "WXYZ"}
    assert admin.delete("/api/v1/ai/providers/ANTHROPIC/key").status_code == 404


def test_sin_clave_maestra_no_se_puede_guardar_una_api_key(
    seeded, backend, hasher, clock, providers
):
    client = login(
        _app(seeded, backend, hasher, clock, providers, None), ADMIN_EMAIL, ADMIN_PASSWORD
    )
    assert client.get("/api/v1/ai/providers").json()["encryption_available"] is False
    response = client.put("/api/v1/ai/providers/ANTHROPIC/key", json={"api_key": FAKE_KEY})
    assert response.status_code == 503 and "clave maestra" in response.json()["detail"]
    assert stored_credentials(backend) == []


def test_una_clave_cifrada_con_otra_clave_maestra_no_se_usa(
    seeded, admin, backend, hasher, clock, providers
):
    admin.put("/api/v1/ai/providers/ANTHROPIC/key", json={"api_key": FAKE_KEY})
    other_master = MasterKey.from_text(generate_key_text())
    client = login(
        _app(seeded, backend, hasher, clock, providers, other_master), ADMIN_EMAIL, ADMIN_PASSWORD
    )
    response = client.post("/api/v1/ai/providers/ANTHROPIC/test")
    assert response.status_code == 503 and "clave maestra" in response.json()["detail"]
    assert providers[ProviderCode.ANTHROPIC].received_keys == []


def test_una_clave_definida_por_el_servidor_no_se_cambia_desde_la_pantalla(
    seeded, backend, hasher, clock, providers, master_key
):
    app = _app(
        seeded,
        backend,
        hasher,
        clock,
        providers,
        master_key,
        openai_api_key="clave-entorno-0000-ZZZZ",
    )
    client = login(app, ADMIN_EMAIL, ADMIN_PASSWORD)
    item = provider(client, "OPENAI")
    assert item["key_source"] == "ENTORNO" and item["key_mask"] == "••••ZZZZ"
    assert "clave-entorno" not in client.get("/api/v1/ai/providers").text
    assert (
        client.put("/api/v1/ai/providers/OPENAI/key", json={"api_key": FAKE_KEY}).status_code == 409
    )
    assert client.delete("/api/v1/ai/providers/OPENAI/key").status_code == 409
    assert client.post("/api/v1/ai/providers/OPENAI/test").json()["ok"] is True
    assert providers[ProviderCode.OPENAI].received_keys == ["clave-entorno-0000-ZZZZ"]


# --- Conexión y modelos ------------------------------------------------------------------


def test_probar_la_conexion_usa_la_clave_y_registra_los_modelos(admin, providers):
    assert admin.post("/api/v1/ai/providers/ANTHROPIC/test").status_code == 422  # sin clave
    admin.put("/api/v1/ai/providers/ANTHROPIC/key", json={"api_key": FAKE_KEY})

    result = admin.post("/api/v1/ai/providers/ANTHROPIC/test").json()
    assert result["ok"] is True and result["models_found"] == 2 and result["error"] is None
    assert (
        result["provider"]["last_test_ok"] is True and result["provider"]["models_available"] == 2
    )
    assert providers[ProviderCode.ANTHROPIC].received_keys == [FAKE_KEY]
    models = admin.get("/api/v1/ai/models", params={"provider": "ANTHROPIC"}).json()
    assert [(m["model_id"], m["reports_capabilities"]) for m in models] == [
        ("modelo-grande-1", True),
        ("modelo-rapido-1", False),
    ]
    assert admin.get("/api/v1/ai/models", params={"provider": "OPENAI"}).json() == []

    # El proveedor retira un modelo y publica otro: el retirado deja de estar disponible.
    providers[ProviderCode.ANTHROPIC].models = [
        DiscoveredModel("modelo-grande-1", "Modelo Grande 1 (actualizado)", None),
        DiscoveredModel("modelo-grande-2", "Modelo Grande 2", None),
    ]
    assert admin.post("/api/v1/ai/providers/ANTHROPIC/test").json()["models_found"] == 2
    by_id = {m["model_id"]: m for m in admin.get("/api/v1/ai/models").json()}
    assert by_id["modelo-rapido-1"]["is_available"] is False
    assert by_id["modelo-grande-2"]["is_available"] is True
    assert by_id["modelo-grande-1"]["display_name"] == "Modelo Grande 1 (actualizado)"
    assert len(by_id) == 3


def test_una_conexion_fallida_se_informa_sin_perder_los_modelos(admin, providers):
    admin.put("/api/v1/ai/providers/ANTHROPIC/key", json={"api_key": FAKE_KEY})
    admin.post("/api/v1/ai/providers/ANTHROPIC/test")
    providers[ProviderCode.ANTHROPIC].error = ProviderError(
        "clave", "El proveedor rechazó la clave: no es válida o no tiene permisos."
    )
    result = admin.post("/api/v1/ai/providers/ANTHROPIC/test")
    assert result.status_code == 200
    body = result.json()
    assert body["ok"] is False and "rechazó la clave" in body["error"]
    assert body["provider"]["last_test_ok"] is False
    assert body["provider"]["models_available"] == 2
    events = audit(admin, "ia.conexion_probada")
    assert {event["result"] for event in events} == {"PERMITIDO", "FALLIDO"}


# --- Habilitar, límites y asignaciones ---------------------------------------------------


def test_habilitar_exige_clave_y_el_limite_se_valida(admin):
    assert admin.put("/api/v1/ai/providers/OPENAI", json={"enabled": True}).status_code == 422
    assert (
        admin.put(
            "/api/v1/ai/providers/OPENAI", json={"enabled": False, "monthly_limit_usd": "50"}
        ).json()["monthly_limit_usd"]
        == "50.00"
    )
    admin.put("/api/v1/ai/providers/OPENAI/key", json={"api_key": FAKE_KEY})
    enabled = admin.put(
        "/api/v1/ai/providers/OPENAI", json={"enabled": True, "monthly_limit_usd": "120.50"}
    ).json()
    assert enabled["enabled"] is True and enabled["monthly_limit_usd"] == "120.50"
    assert (
        admin.put(
            "/api/v1/ai/providers/OPENAI", json={"enabled": True, "monthly_limit_usd": "-1"}
        ).status_code
        == 422
    )
    assert provider(admin, "OPENAI")["monthly_limit_usd"] == "120.50"


def test_solo_se_asignan_modelos_disponibles_de_proveedores_habilitados(admin, providers, seeded):
    admin.put("/api/v1/ai/providers/ANTHROPIC/key", json={"api_key": FAKE_KEY})
    admin.post("/api/v1/ai/providers/ANTHROPIC/test")
    models = {m["model_id"]: m["id"] for m in admin.get("/api/v1/ai/models").json()}
    url = "/api/v1/ai/assignments/EXTRACCION_CV"

    # El proveedor aún no está habilitado.
    assert admin.put(url, json={"model_id": models["modelo-grande-1"]}).status_code == 422
    admin.put("/api/v1/ai/providers/ANTHROPIC", json={"enabled": True})
    assigned = admin.put(url, json={"model_id": models["modelo-grande-1"]})
    assert assigned.status_code == 200
    assert assigned.json()["model"]["model_id"] == "modelo-grande-1"
    by_operation = {a["operation"]: a for a in admin.get("/api/v1/ai/assignments").json()}
    assert by_operation["EXTRACCION_CV"]["model"]["provider_name"] == "Anthropic"
    assert by_operation["EVALUACION_DOCUMENTAL"]["model"] is None
    assert audit(admin, "ia.modelo_asignado")[0]["details"] == {
        "proveedor": "ANTHROPIC",
        "modelo": "modelo-grande-1",
    }

    # Para ejecutar la operación se resuelven el modelo y la clave en ese momento.
    context = seeded[0].state.context
    with context.require_backend().transaction() as repos:
        resolved = admin.app.state.context.ai_settings(repos).resolve(Operation.EXTRACCION_CV)
    assert (resolved.provider_code, resolved.model_id, resolved.api_key) == (
        ProviderCode.ANTHROPIC,
        "modelo-grande-1",
        FAKE_KEY,
    )

    # Un modelo que el proveedor retiró o un identificador inexistente no se asignan.
    providers[ProviderCode.ANTHROPIC].models = providers[ProviderCode.ANTHROPIC].models[:1]
    admin.post("/api/v1/ai/providers/ANTHROPIC/test")
    assert admin.put(url, json={"model_id": models["modelo-rapido-1"]}).status_code == 422
    assert (
        admin.put(url, json={"model_id": "00000000-0000-0000-0000-000000000000"}).status_code == 404
    )
    assert admin.put("/api/v1/ai/assignments/NO_EXISTE", json={"model_id": None}).status_code == 422
    assert admin.put(url, json={"model_id": None}).json()["model"] is None


# --- Clientes HTTP de los proveedores (transporte simulado) ------------------------------


def _client(handler):
    return lambda: httpx.Client(transport=httpx.MockTransport(handler))


def test_el_cliente_de_anthropic_pagina_y_envia_la_version_configurada():
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if "after_id" not in request.url.params:
            page = {
                "data": [
                    {"id": "m-1", "display_name": "Modelo 1", "capabilities": {"batch": True}}
                ],
                "has_more": True,
                "last_id": "m-1",
            }
        else:
            page = {"data": [{"id": "m-2", "display_name": "Modelo 2"}], "has_more": False}
        return httpx.Response(200, json=page)

    client = AnthropicClient("2026-10-21", client_factory=_client(handler))
    models = client.list_models(FAKE_KEY)
    assert [(m.model_id, m.display_name, m.capabilities) for m in models] == [
        ("m-1", "Modelo 1", {"batch": True}),
        ("m-2", "Modelo 2", None),
    ]
    assert [request.url.path for request in seen] == ["/v1/models", "/v1/models"]
    assert seen[0].url.host == "api.anthropic.com"
    assert seen[0].headers["authorization"] == f"Bearer {FAKE_KEY}"
    assert seen[0].headers["anthropic-version"] == "2026-10-21"
    assert seen[1].url.params["after_id"] == "m-1"


def test_el_cliente_de_openai_lista_modelos():
    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == "https://api.openai.com/v1/models"
        assert request.headers["authorization"] == f"Bearer {FAKE_KEY}"
        return httpx.Response(200, json={"object": "list", "data": [{"id": "modelo-a"}]})

    models = OpenAIClient(client_factory=_client(handler)).list_models(FAKE_KEY)
    assert [(m.model_id, m.display_name) for m in models] == [("modelo-a", "modelo-a")]


@pytest.mark.parametrize(
    ("status", "kind"), [(401, "clave"), (403, "clave"), (429, "limite"), (500, "proveedor")]
)
def test_los_errores_del_proveedor_no_revelan_la_clave_ni_su_respuesta(status, kind):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, json={"error": {"message": f"detalle interno {FAKE_KEY}"}})

    with pytest.raises(ProviderHttpError) as error:
        OpenAIClient(client_factory=_client(handler)).list_models(FAKE_KEY)
    assert error.value.kind == kind
    assert FAKE_KEY not in error.value.message and "detalle interno" not in error.value.message


def test_un_fallo_de_red_o_una_respuesta_ilegible_se_informan():
    def offline(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("sin red")

    with pytest.raises(ProviderHttpError) as error:
        AnthropicClient("2026-10-21", client_factory=_client(offline)).list_models(FAKE_KEY)
    assert error.value.kind == "red"

    def garbage(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"<html>no es json</html>")

    with pytest.raises(ProviderHttpError) as error:
        OpenAIClient(client_factory=_client(garbage)).list_models(FAKE_KEY)
    assert error.value.kind == "proveedor" and json.dumps(error.value.message)


# --- Ejecución, consumo y límite mensual -------------------------------------------------


@pytest.fixture
def ready(admin, providers) -> dict:
    """Anthropic con clave, habilitado y con un modelo asignado a la evaluación."""
    admin.put("/api/v1/ai/providers/ANTHROPIC/key", json={"api_key": FAKE_KEY})
    admin.post("/api/v1/ai/providers/ANTHROPIC/test")
    admin.put("/api/v1/ai/providers/ANTHROPIC", json={"enabled": True})
    model = next(
        m for m in admin.get("/api/v1/ai/models").json() if m["model_id"] == "modelo-grande-1"
    )
    admin.put("/api/v1/ai/assignments/EVALUACION_DOCUMENTAL", json={"model_id": model["id"]})
    return model


def usage(client) -> dict:
    return client.get("/api/v1/ai/usage", params={"year": 2026, "month": 11}).json()


def run(admin, **kwargs):
    context = admin.app.state.context
    with context.require_backend().transaction() as repos:
        return context.ai_settings(repos).execute(
            Operation.EVALUACION_DOCUMENTAL, system="s", user="u", **kwargs
        )


def test_los_precios_los_captura_el_administrador(admin, ready, recruiter_client):
    url = f"/api/v1/ai/models/{ready['id']}/prices"
    assert ready["input_price"] is None and ready["output_price"] is None
    assert (
        recruiter_client.put(url, json={"input_price": "3", "output_price": "15"}).status_code
        == 403
    )
    assert admin.put(url, json={"input_price": "3"}).status_code == 422  # los dos o ninguno
    assert admin.put(url, json={"input_price": "-1", "output_price": "1"}).status_code == 422
    saved = admin.put(url, json={"input_price": "3", "output_price": "15"}).json()
    assert (saved["input_price"], saved["output_price"]) == ("3.0000", "15.0000")
    # Probar la conexión de nuevo no borra los precios.
    admin.post("/api/v1/ai/providers/ANTHROPIC/test")
    again = next(m for m in admin.get("/api/v1/ai/models").json() if m["id"] == ready["id"])
    assert again["input_price"] == "3.0000"
    assert audit(admin, "ia.precio_actualizado")[0]["details"]["entrada_usd"] == "3.0000"


def test_probar_un_modelo_registra_tokens_y_costo_sin_guardar_contenido(
    admin, ready, providers, backend
):
    admin.put(
        f"/api/v1/ai/models/{ready['id']}/prices", json={"input_price": "3", "output_price": "15"}
    )
    result = admin.post(f"/api/v1/ai/models/{ready['id']}/test").json()
    assert result == {
        "ok": True,
        "error": None,
        "reply": "OK",
        "input_tokens": 1000,
        "output_tokens": 500,
        # 1000 × 3 / 1 000 000 + 500 × 15 / 1 000 000
        "estimated_cost_usd": "0.010500",
        "attempts": 1,
    }
    (model, system, user) = providers[ProviderCode.ANTHROPIC].prompts[0]
    assert model == "modelo-grande-1" and "OK" in system and "Prueba" in user
    report = usage(admin)
    assert report["rows"] == [
        {
            "provider_code": "ANTHROPIC",
            "provider_name": "Anthropic",
            "model_id": "modelo-grande-1",
            "operation": "PRUEBA",
            "calls": 1,
            "failures": 0,
            "input_tokens": 1000,
            "output_tokens": 500,
            "estimated_cost_usd": "0.010500",
        }
    ]
    assert report["providers"][0] == {
        "code": "ANTHROPIC",
        "name": "Anthropic",
        "spent_usd": "0.010500",
        "limit_usd": None,
    }
    # Otro mes no tiene consumo.
    assert admin.get("/api/v1/ai/usage", params={"year": 2026, "month": 12}).json()["rows"] == []
    # El registro no tiene columnas para el contenido enviado ni para la respuesta.
    from app.modules.ai_settings.infrastructure.orm import AiExecutionRow

    assert not {"prompt", "system", "user", "text", "reply", "content"} & set(
        AiExecutionRow.__table__.columns.keys()
    )


def test_los_fallos_pasajeros_se_reintentan_y_los_definitivos_quedan_registrados(
    admin, ready, providers
):
    fake = providers[ProviderCode.ANTHROPIC]
    fake.script = [
        ProviderError("red", "No se pudo conectar con el proveedor."),
        ProviderError("limite", "El proveedor limitó las solicitudes."),
        Generation("resultado", 10, 5, True),
    ]
    result = run(admin)
    assert (result.ok, result.text, result.attempts) == (True, "resultado", 3)

    # Una clave rechazada no se reintenta.
    fake.script = [ProviderError("clave", "El proveedor rechazó la clave.")]
    rejected = run(admin)
    assert (rejected.ok, rejected.attempts, rejected.error) == (
        False,
        1,
        "El proveedor rechazó la clave.",
    )
    # Tras agotar los reintentos el fallo se informa; no es una excepción.
    fake.script = [ProviderError("red", "No se pudo conectar con el proveedor.")] * 3
    exhausted = run(admin)
    assert (exhausted.ok, exhausted.attempts) == (False, 3)

    (row,) = usage(admin)["rows"]
    assert (row["calls"], row["failures"], row["input_tokens"]) == (3, 2, 10)
    assert row["estimated_cost_usd"] is None  # sin precio capturado no hay costo estimado


def test_el_limite_mensual_detiene_las_llamadas(admin, ready, clock):
    prices = f"/api/v1/ai/models/{ready['id']}/prices"
    admin.put("/api/v1/ai/providers/ANTHROPIC", json={"enabled": True, "monthly_limit_usd": "0.02"})
    # Con límite pero sin precio no se puede aplicar: se rechaza antes de llamar.
    with pytest.raises(Exception, match="precio capturado"):
        run(admin)
    admin.put(prices, json={"input_price": "3", "output_price": "15"})
    assert run(admin).estimated_cost_usd is not None  # 0.0105
    assert run(admin).ok  # 0.0210: se llega al límite
    with pytest.raises(Exception, match="límite de gasto mensual de Anthropic"):
        run(admin)
    assert usage(admin)["providers"][0]["spent_usd"] == "0.021000"
    assert usage(admin)["rows"][0]["calls"] == 2

    # Al mes siguiente el gasto empieza de cero.
    clock.advance(days=30)
    assert run(admin).ok


def test_fuera_de_produccion_no_se_envian_documentos_sin_autorizacion(
    seeded, backend, hasher, clock, providers, master_key, admin, ready
):
    with pytest.raises(Exception, match="no está autorizado enviar documentos"):
        run(admin, carries_document=True)
    assert providers[ProviderCode.ANTHROPIC].prompts is None
    assert usage(admin)["rows"] == []

    allowed = login(
        _app(seeded, backend, hasher, clock, providers, master_key, ai_allow_real_documents=True),
        ADMIN_EMAIL,
        ADMIN_PASSWORD,
    )
    assert run(allowed, carries_document=True).ok


def test_una_operacion_sin_modelo_o_con_el_proveedor_deshabilitado_no_se_ejecuta(admin, ready):
    context = admin.app.state.context
    with pytest.raises(Exception, match="no tiene un modelo asignado"):
        with context.require_backend().transaction() as repos:
            context.ai_settings(repos).execute(Operation.EXTRACCION_CV, system="s", user="u")
    admin.put("/api/v1/ai/providers/ANTHROPIC", json={"enabled": False})
    with pytest.raises(Exception, match="proveedor está deshabilitado"):
        run(admin)


def test_los_clientes_generan_texto_y_leen_el_consumo():
    def anthropic(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        assert request.url.path == "/v1/messages"
        assert request.headers["authorization"] == f"Bearer {FAKE_KEY}"
        assert body == {
            "model": "m-1",
            "max_tokens": 300,
            "system": "sistema",
            "messages": [{"role": "user", "content": "usuario"}],
        }
        return httpx.Response(
            200,
            json={
                "content": [{"type": "text", "text": "hola "}, {"type": "text", "text": "mundo"}],
                "stop_reason": "max_tokens",
                "usage": {"input_tokens": 12, "output_tokens": 7},
            },
        )

    generation = AnthropicClient("2026-10-21", client_factory=_client(anthropic)).generate(
        FAKE_KEY, "m-1", system="sistema", user="usuario", max_output_tokens=300
    )
    assert (generation.text, generation.input_tokens, generation.output_tokens) == (
        "hola mundo",
        12,
        7,
    )
    assert generation.complete is False  # el proveedor cortó la respuesta

    def openai(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        assert request.url.path == "/v1/responses"
        assert body == {
            "model": "m-2",
            "instructions": "sistema",
            "input": "usuario",
            "max_output_tokens": 300,
            "store": False,
        }
        return httpx.Response(
            200,
            json={
                "status": "completed",
                "error": None,
                "output": [
                    {"type": "reasoning"},
                    {"type": "message", "content": [{"type": "output_text", "text": "listo"}]},
                ],
                "usage": {"input_tokens": 20, "output_tokens": 3},
            },
        )

    generation = OpenAIClient(client_factory=_client(openai)).generate(
        FAKE_KEY, "m-2", system="sistema", user="usuario", max_output_tokens=300
    )
    assert (generation.text, generation.input_tokens, generation.complete) == ("listo", 20, True)

    def malformed(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"inesperado": True})

    for client in (
        AnthropicClient("2026-10-21", client_factory=_client(malformed)),
        OpenAIClient(client_factory=_client(malformed)),
    ):
        with pytest.raises(ProviderHttpError) as error:
            client.generate(FAKE_KEY, "m", system="s", user="u", max_output_tokens=10)
        assert error.value.kind == "proveedor"
