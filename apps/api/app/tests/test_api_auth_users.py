"""Sesiones, usuarios y permisos a través de la API (repositorios de prueba)."""

from __future__ import annotations

import uuid

from fastapi.testclient import TestClient

from app.modules.authentication.api.dependencies import CSRF_HEADER, SESSION_COOKIE
from app.tests.conftest import (
    ADMIN_EMAIL,
    ADMIN_PASSWORD,
    RECRUITER_EMAIL,
    RECRUITER_PASSWORD,
    login,
    new_client,
)

NEW_USER = {
    "email": "Nueva.Persona@Ejemplo.test",
    "full_name": "  Nueva   Persona ",
    "password": "Clave-Inicial-2026",
    "role": "RECLUTADOR",
}


def _audit_actions(client: TestClient) -> list[str]:
    items = client.get("/api/v1/audit/events", params={"page_size": 100}).json()["items"]
    return [item["action"] for item in items]


# --- Inicio de sesión ------------------------------------------------------------


def test_login_correcto_entrega_cookie_httponly_y_token_csrf(seeded):
    client = new_client(seeded[0])
    response = client.post(
        "/api/v1/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["user"]["email"] == ADMIN_EMAIL
    assert body["user"]["role"] == "ADMINISTRADOR"
    assert len(body["csrf_token"]) >= 32
    cookie = response.headers["set-cookie"].lower()
    assert "httponly" in cookie
    assert "samesite=lax" in cookie
    assert "secure" in cookie  # el entorno de prueba no es "development"


def test_la_respuesta_nunca_incluye_el_hash_de_la_contrasena(admin_client):
    for path in ("/api/v1/auth/me", "/api/v1/users"):
        response = admin_client.get(path)
        assert response.status_code == 200
        text = response.text
        assert "password" not in text
        assert "argon2" not in text


def test_login_con_contrasena_incorrecta_responde_401_sin_dar_pistas(seeded):
    client = new_client(seeded[0])
    wrong_password = client.post(
        "/api/v1/auth/login", json={"email": ADMIN_EMAIL, "password": "incorrecta-000000"}
    )
    unknown_user = client.post(
        "/api/v1/auth/login", json={"email": "nadie@ejemplo.test", "password": "incorrecta-000000"}
    )
    assert wrong_password.status_code == unknown_user.status_code == 401
    # Mismo cuerpo para correo inexistente y contraseña errónea.
    for field in ("code", "title", "detail"):
        assert wrong_password.json()[field] == unknown_user.json()[field]
    assert SESSION_COOKIE not in client.cookies


def test_cinco_intentos_fallidos_bloquean_la_cuenta_quince_minutos(seeded, clock):
    client = new_client(seeded[0])
    credentials = {"email": RECRUITER_EMAIL, "password": "incorrecta-000000"}
    for _ in range(5):
        assert client.post("/api/v1/auth/login", json=credentials).status_code == 401
    good = {"email": RECRUITER_EMAIL, "password": RECRUITER_PASSWORD}
    assert client.post("/api/v1/auth/login", json=good).status_code == 401
    clock.advance(minutes=16)
    assert client.post("/api/v1/auth/login", json=good).status_code == 200


def test_los_intentos_fallidos_quedan_en_auditoria_sin_el_correo_tecleado(seeded, admin_client):
    new_client(seeded[0]).post(
        "/api/v1/auth/login", json={"email": "secreto@otro.test", "password": "incorrecta-000000"}
    )
    response = admin_client.get("/api/v1/audit/events", params={"action": "sesion.inicio_fallido"})
    assert response.json()["total"] == 1
    assert "secreto@otro.test" not in response.text


def test_sin_sesion_no_hay_acceso(seeded):
    client = new_client(seeded[0])
    assert client.get("/api/v1/auth/me").status_code == 401
    assert client.get("/api/v1/users").status_code == 401


def test_una_cookie_inventada_no_da_acceso(seeded):
    client = new_client(seeded[0])
    client.cookies.set(SESSION_COOKIE, "token-inventado-000000000000")
    assert client.get("/api/v1/auth/me").status_code == 401


def test_la_sesion_caduca_por_inactividad(admin_client, clock):
    clock.advance(minutes=29)
    assert admin_client.get("/api/v1/auth/me").status_code == 200
    clock.advance(minutes=31)
    assert admin_client.get("/api/v1/auth/me").status_code == 401


def test_la_sesion_caduca_a_las_doce_horas_aunque_haya_actividad(admin_client, clock):
    for _ in range(47):
        clock.advance(minutes=15)
        assert admin_client.get("/api/v1/auth/me").status_code == 200
    clock.advance(minutes=20)
    assert admin_client.get("/api/v1/auth/me").status_code == 401


def test_cerrar_sesion_invalida_el_token(admin_client):
    token = admin_client.cookies.get(SESSION_COOKIE)
    assert admin_client.post("/api/v1/auth/logout").status_code == 204
    admin_client.cookies.set(SESSION_COOKIE, token)
    assert admin_client.get("/api/v1/auth/me").status_code == 401


# --- CSRF ------------------------------------------------------------------------


def test_modificar_sin_token_csrf_se_rechaza(admin_client):
    del admin_client.headers[CSRF_HEADER]
    response = admin_client.post("/api/v1/users", json=NEW_USER)
    assert response.status_code == 403
    assert response.json()["code"] == "csrf"


def test_modificar_con_token_csrf_equivocado_se_rechaza(admin_client):
    admin_client.headers[CSRF_HEADER] = "otro-token"
    assert admin_client.post("/api/v1/users", json=NEW_USER).status_code == 403


# --- Permisos --------------------------------------------------------------------


def test_un_reclutador_no_administra_usuarios_y_el_intento_se_audita(
    recruiter_client, admin_client
):
    assert recruiter_client.get("/api/v1/users").status_code == 403
    assert recruiter_client.post("/api/v1/users", json=NEW_USER).status_code == 403
    assert recruiter_client.get("/api/v1/audit/events").status_code == 403
    assert _audit_actions(admin_client).count("acceso.denegado") == 3


# --- Administración de usuarios ----------------------------------------------------


def test_el_administrador_crea_un_usuario_que_puede_entrar_con_esa_contrasena(seeded, admin_client):
    response = admin_client.post("/api/v1/users", json=NEW_USER)
    assert response.status_code == 201
    created = response.json()
    assert created["email"] == "nueva.persona@ejemplo.test"
    assert created["full_name"] == "Nueva Persona"
    assert created["is_active"] is True
    # Sin cambio obligatorio: entra directamente con la contraseña asignada.
    client = login(seeded[0], "nueva.persona@ejemplo.test", NEW_USER["password"])
    assert client.get("/api/v1/auth/me").json()["user"]["role"] == "RECLUTADOR"
    assert "usuario.creado" in _audit_actions(admin_client)


def test_no_se_admiten_correos_duplicados(admin_client):
    assert admin_client.post("/api/v1/users", json=NEW_USER).status_code == 201
    response = admin_client.post("/api/v1/users", json={**NEW_USER, "email": NEW_USER["email"]})
    assert response.status_code == 409


def test_se_rechazan_contrasenas_cortas_y_correos_invalidos(admin_client):
    short = admin_client.post("/api/v1/users", json={**NEW_USER, "password": "corta"})
    assert short.status_code == 422
    assert "12 caracteres" in short.json()["detail"]
    bad_email = admin_client.post("/api/v1/users", json={**NEW_USER, "email": "sin-arroba"})
    assert bad_email.status_code == 422


def test_la_lista_se_puede_buscar_y_paginar(admin_client):
    admin_client.post("/api/v1/users", json=NEW_USER)
    everyone = admin_client.get("/api/v1/users").json()
    assert everyone["total"] == 3
    found = admin_client.get("/api/v1/users", params={"search": "nueva"}).json()
    assert [u["email"] for u in found["items"]] == ["nueva.persona@ejemplo.test"]
    page = admin_client.get("/api/v1/users", params={"page": 2, "page_size": 2}).json()
    assert len(page["items"]) == 1 and page["total"] == 3


def test_restablecer_contrasena_cierra_las_sesiones_y_cambia_el_acceso(
    seeded, admin_client, recruiter_client
):
    recruiter_id = str(seeded[2].id)
    response = admin_client.post(
        f"/api/v1/users/{recruiter_id}/reset-password", json={"new_password": "Clave-Nueva-2026!"}
    )
    assert response.status_code == 200
    assert response.json() == {"sessions_closed": 1}
    assert recruiter_client.get("/api/v1/auth/me").status_code == 401
    old = {"email": RECRUITER_EMAIL, "password": RECRUITER_PASSWORD}
    assert new_client(seeded[0]).post("/api/v1/auth/login", json=old).status_code == 401
    login(seeded[0], RECRUITER_EMAIL, "Clave-Nueva-2026!")
    assert "Clave-Nueva-2026!" not in admin_client.get("/api/v1/audit/events").text


def test_un_usuario_desactivado_pierde_sus_sesiones_y_no_puede_entrar(
    seeded, admin_client, recruiter_client
):
    recruiter_id = str(seeded[2].id)
    response = admin_client.post(f"/api/v1/users/{recruiter_id}/deactivate")
    assert response.status_code == 200
    assert response.json()["is_active"] is False
    assert response.json()["deactivated_at"] is not None
    assert recruiter_client.get("/api/v1/auth/me").status_code == 401
    credentials = {"email": RECRUITER_EMAIL, "password": RECRUITER_PASSWORD}
    assert new_client(seeded[0]).post("/api/v1/auth/login", json=credentials).status_code == 401
    # El usuario no se borra: sigue en la lista y se puede reactivar.
    assert admin_client.get("/api/v1/users").json()["total"] == 2
    assert admin_client.post(f"/api/v1/users/{recruiter_id}/activate").json()["is_active"] is True
    login(seeded[0], RECRUITER_EMAIL, RECRUITER_PASSWORD)


def test_el_administrador_no_puede_desactivarse_ni_quitarse_el_rol(seeded, admin_client):
    admin_id = str(seeded[1].id)
    assert admin_client.post(f"/api/v1/users/{admin_id}/deactivate").status_code == 409
    response = admin_client.patch(f"/api/v1/users/{admin_id}", json={"role": "RECLUTADOR"})
    assert response.status_code == 409


def test_siempre_queda_un_administrador_activo(seeded, admin_client):
    second = admin_client.post(
        "/api/v1/users",
        json={**NEW_USER, "email": "otra.admin@ejemplo.test", "role": "ADMINISTRADOR"},
    ).json()
    other_admin = login(seeded[0], "otra.admin@ejemplo.test", NEW_USER["password"])
    first_id = str(seeded[1].id)
    # La segunda administradora puede dar de baja a la primera...
    assert other_admin.post(f"/api/v1/users/{first_id}/deactivate").status_code == 200
    # ...pero entonces ya nadie puede quitarle el rol a la única que queda.
    assert (
        other_admin.patch(f"/api/v1/users/{second['id']}", json={"role": "RECLUTADOR"}).status_code
        == 409
    )


def test_se_puede_editar_nombre_y_rol(seeded, admin_client):
    recruiter_id = str(seeded[2].id)
    response = admin_client.patch(
        f"/api/v1/users/{recruiter_id}",
        json={"full_name": "Nombre Corregido", "role": "ADMINISTRADOR"},
    )
    assert response.status_code == 200
    assert response.json()["full_name"] == "Nombre Corregido"
    assert response.json()["role"] == "ADMINISTRADOR"


def test_un_identificador_inexistente_responde_404(admin_client):
    assert admin_client.get(f"/api/v1/users/{uuid.uuid4()}").status_code == 404
    assert admin_client.post(f"/api/v1/users/{uuid.uuid4()}/deactivate").status_code == 404


def test_sin_base_de_datos_configurada_la_api_responde_503(client):
    response = client.post(
        "/api/v1/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
    )
    assert response.status_code == 503
    assert response.json()["code"] == "servicio_no_disponible"


def test_un_error_a_mitad_de_la_operacion_no_deja_cambios(seeded, admin_client, monkeypatch):
    from app.modules.audit.application.service import AuditLog

    def broken(*args, **kwargs):
        raise RuntimeError("fallo simulado al auditar")

    before = admin_client.get("/api/v1/users").json()["total"]
    monkeypatch.setattr(AuditLog, "record", broken)
    assert admin_client.post("/api/v1/users", json=NEW_USER).status_code == 500
    monkeypatch.undo()
    assert admin_client.get("/api/v1/users").json()["total"] == before
