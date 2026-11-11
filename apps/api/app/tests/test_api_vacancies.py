"""Vacantes, compartición y transferencias a través de la API.

Incluye las comprobaciones de seguridad 1 a 4, 6 y 7 de la sección 32.3 del
documento maestro.
"""

from __future__ import annotations

import uuid

from app.tests.conftest import (
    RECRUITER_EMAIL,
    RECRUITER_PASSWORD,
    VACANCY,
    share,
)


def _names(client, **params) -> list[str]:
    return [v["name"] for v in client.get("/api/v1/vacancies", params=params).json()["items"]]


# --- Alta y edición ------------------------------------------------------------------


def test_una_vacante_nace_privada_en_borrador_y_con_su_creador_como_responsable(
    seeded, vacancy, recruiter_client
):
    assert vacancy["status"] == "BORRADOR"
    assert vacancy["my_access"] == "RESPONSABLE"
    assert vacancy["owner"]["id"] == str(seeded[2].id)
    assert vacancy["version"] == 1
    assert recruiter_client.get(f"/api/v1/vacancies/{vacancy['id']}/members").json() == []
    history = recruiter_client.get(f"/api/v1/vacancies/{vacancy['id']}/ownership-history").json()
    assert len(history) == 1
    assert history[0]["previous_owner"] is None
    assert history[0]["reason"] == "Creación de la vacante"


def test_se_validan_los_datos_de_la_vacante(recruiter_client):
    assert (
        recruiter_client.post("/api/v1/vacancies", json={**VACANCY, "name": "   "}).status_code
        == 422
    )
    assert (
        recruiter_client.post("/api/v1/vacancies", json={**VACANCY, "positions": 0}).status_code
        == 422
    )
    assert (
        recruiter_client.post(
            "/api/v1/vacancies", json={**VACANCY, "work_mode": "LUNAR"}
        ).status_code
        == 422
    )


def test_editar_aumenta_la_version_y_rechaza_una_version_antigua(vacancy, recruiter_client):
    url = f"/api/v1/vacancies/{vacancy['id']}"
    updated = recruiter_client.put(url, json={**VACANCY, "positions": 3, "version": 1})
    assert updated.status_code == 200
    assert updated.json()["positions"] == 3
    assert updated.json()["version"] == 2
    # Otra pestaña que aún tenía la versión 1 no puede pisar el cambio.
    stale = recruiter_client.put(url, json={**VACANCY, "positions": 9, "version": 1})
    assert stale.status_code == 409
    assert recruiter_client.get(url).json()["positions"] == 3


def test_los_cambios_de_estado_siguen_las_transiciones_permitidas(vacancy, recruiter_client):
    url = f"/api/v1/vacancies/{vacancy['id']}/status"
    opened = recruiter_client.post(url, json={"status": "ABIERTA", "version": 1}).json()
    assert opened["status"] == "ABIERTA" and opened["opened_at"] is not None
    # De abierta no se puede archivar directamente.
    invalid = recruiter_client.post(url, json={"status": "ARCHIVADA", "version": 2})
    assert invalid.status_code == 409
    closed = recruiter_client.post(url, json={"status": "CERRADA", "version": 2}).json()
    assert closed["closed_at"] is not None
    # Una vacante cerrada puede reabrirse para otro periodo y conserva su primera apertura.
    reopened = recruiter_client.post(url, json={"status": "ABIERTA", "version": 3}).json()
    assert reopened["opened_at"] == opened["opened_at"] and reopened["closed_at"] is None


# --- Seguridad 1 y 4: privacidad y acceso directo por UUID -----------------------------


def test_seguridad_1_una_reclutadora_no_ve_las_vacantes_privadas_de_otra(vacancy, other):
    other_client, _ = other
    assert _names(other_client) == []
    assert other_client.get("/api/v1/vacancies", params={"search": "nómina"}).json()["total"] == 0


def test_seguridad_4_cambiar_el_uuid_en_la_url_no_da_acceso(vacancy, other, recruiter_client):
    other_client, other_id = other
    base = f"/api/v1/vacancies/{vacancy['id']}"
    put_body = {**VACANCY, "version": 1}
    attempts = [
        other_client.get(base),
        other_client.put(base, json=put_body),
        other_client.post(f"{base}/status", json={"status": "ABIERTA", "version": 1}),
        other_client.get(f"{base}/members"),
        other_client.put(f"{base}/members/{other_id}", json={"access_type": "COLABORACION"}),
        other_client.delete(f"{base}/members/{other_id}"),
        other_client.put(
            f"{base}/members/{other_id}/sensitive-grants", json={"document_classes": []}
        ),
        other_client.get(f"{base}/ownership-history"),
    ]
    # Sin acceso se responde igual que si la vacante no existiera.
    missing = other_client.get(f"/api/v1/vacancies/{uuid.uuid4()}")
    for response in attempts:
        assert response.status_code == 404
        assert response.json()["detail"] == missing.json()["detail"]
    assert recruiter_client.get(base).json()["version"] == 1


def test_los_accesos_denegados_a_vacantes_quedan_auditados(
    vacancy, other, recruiter_client, admin_client
):
    other_client, other_id = other
    base = f"/api/v1/vacancies/{vacancy['id']}"

    def denials() -> list[dict]:
        return admin_client.get(
            "/api/v1/audit/events", params={"action": "acceso.denegado", "page_size": 100}
        ).json()["items"]

    # Una vacante que no existe no es un acceso denegado.
    assert other_client.get(f"/api/v1/vacancies/{uuid.uuid4()}").status_code == 404
    assert denials() == []

    # Sin acceso: responde "no encontrado", pero el intento queda registrado.
    assert other_client.get(base).status_code == 404
    hidden = denials()
    assert len(hidden) == 1
    assert hidden[0]["result"] == "DENEGADO"
    assert hidden[0]["actor_user_id"] == other_id
    assert hidden[0]["details"] == {"metodo": "GET", "ruta": base, "motivo": "no_encontrado"}

    # Con acceso de lectura, intentar modificar también queda registrado.
    assert share(recruiter_client, vacancy["id"], other_id, "LECTURA").status_code == 204
    status_url = f"{base}/status"
    assert (
        other_client.post(status_url, json={"status": "ABIERTA", "version": 1}).status_code == 403
    )
    assert len(denials()) == 2
    # El reloj de las pruebas no avanza solo: se busca por motivo, no por orden.
    (last,) = [event for event in denials() if event["details"]["motivo"] == "sin_permiso"]
    assert last["actor_user_id"] == other_id
    assert last["details"] == {"metodo": "POST", "ruta": status_url, "motivo": "sin_permiso"}
    assert recruiter_client.get(base).json()["status"] == "BORRADOR"


# --- Seguridad 2 y 3: compartir y revocar ------------------------------------------------


def test_seguridad_2_lectura_permite_consultar_pero_no_modificar(vacancy, other, recruiter_client):
    other_client, other_id = other
    base = f"/api/v1/vacancies/{vacancy['id']}"
    assert share(recruiter_client, vacancy["id"], other_id, "LECTURA").status_code == 204

    seen = other_client.get(base)
    assert seen.status_code == 200 and seen.json()["my_access"] == "LECTURA"
    assert _names(other_client, scope="shared") == ["Analista de Nómina"]
    assert _names(other_client, scope="mine") == []
    assert len(other_client.get(f"{base}/members").json()) == 1

    # Tiene acceso, así que la respuesta es "no permitido", no "no encontrado".
    assert other_client.put(base, json={**VACANCY, "version": 1}).status_code == 403
    assert (
        other_client.post(f"{base}/status", json={"status": "ABIERTA", "version": 1}).status_code
        == 403
    )
    assert share(other_client, vacancy["id"], other_id, "COLABORACION").status_code == 403


def test_seguridad_2_colaboracion_no_edita_la_vacante_ni_la_comparte(
    seeded, vacancy, other, recruiter_client
):
    other_client, other_id = other
    base = f"/api/v1/vacancies/{vacancy['id']}"
    share(recruiter_client, vacancy["id"], other_id, "COLABORACION")
    assert other_client.get(base).json()["my_access"] == "COLABORACION"
    assert other_client.put(base, json={**VACANCY, "version": 1}).status_code == 403
    assert share(other_client, vacancy["id"], str(seeded[1].id), "LECTURA").status_code == 403
    assert other_client.delete(f"{base}/members/{other_id}").status_code == 403


def test_compartir_no_cambia_al_responsable_y_se_puede_cambiar_el_tipo_de_acceso(
    seeded, vacancy, other, recruiter_client
):
    other_client, other_id = other
    share(recruiter_client, vacancy["id"], other_id, "LECTURA")
    share(recruiter_client, vacancy["id"], other_id, "COLABORACION")
    base = f"/api/v1/vacancies/{vacancy['id']}"
    assert recruiter_client.get(base).json()["owner"]["id"] == str(seeded[2].id)
    members = recruiter_client.get(f"{base}/members").json()
    assert [(m["user"]["id"], m["access_type"]) for m in members] == [(other_id, "COLABORACION")]


def test_seguridad_3_revocar_bloquea_la_siguiente_consulta(vacancy, other, recruiter_client):
    other_client, other_id = other
    base = f"/api/v1/vacancies/{vacancy['id']}"
    share(recruiter_client, vacancy["id"], other_id, "COLABORACION")
    assert other_client.get(base).status_code == 200
    assert recruiter_client.delete(f"{base}/members/{other_id}").status_code == 204
    assert other_client.get(base).status_code == 404
    assert _names(other_client) == []
    # Se puede volver a compartir: el acceso revocado se conserva como historial.
    assert share(recruiter_client, vacancy["id"], other_id, "LECTURA").status_code == 204
    assert other_client.get(base).json()["my_access"] == "LECTURA"


def test_no_se_comparte_con_usuarios_inexistentes_inactivos_ni_con_el_responsable(
    seeded, vacancy, other, recruiter_client, admin_client
):
    _, other_id = other
    owner_id = str(seeded[2].id)
    assert share(recruiter_client, vacancy["id"], str(uuid.uuid4()), "LECTURA").status_code == 404
    assert share(recruiter_client, vacancy["id"], owner_id, "LECTURA").status_code == 409
    admin_client.post(f"/api/v1/users/{other_id}/deactivate")
    assert share(recruiter_client, vacancy["id"], other_id, "LECTURA").status_code == 404


def test_seguridad_8_los_documentos_sensibles_exigen_un_permiso_adicional(
    vacancy, other, recruiter_client
):
    other_client, other_id = other
    base = f"/api/v1/vacancies/{vacancy['id']}"
    grants_url = f"{base}/members/{other_id}/sensitive-grants"
    # No se puede otorgar a quien no tiene acceso a la vacante.
    assert (
        recruiter_client.put(grants_url, json={"document_classes": ["PSICOMETRIA"]}).status_code
        == 404
    )
    share(recruiter_client, vacancy["id"], other_id, "COLABORACION")
    # Compartir no concede nada por sí solo.
    assert recruiter_client.get(f"{base}/members").json()[0]["sensitive_classes"] == []
    granted = recruiter_client.put(grants_url, json={"document_classes": ["PSICOMETRIA"]})
    assert granted.json() == {"document_classes": ["PSICOMETRIA"]}
    assert recruiter_client.get(f"{base}/members").json()[0]["sensitive_classes"] == ["PSICOMETRIA"]
    # El colaborador no puede otorgarse permisos a sí mismo.
    assert (
        other_client.put(
            grants_url, json={"document_classes": ["PSICOMETRIA", "ESTUDIO_SOCIOECONOMICO"]}
        ).status_code
        == 403
    )
    # Revocar el acceso retira también los permisos adicionales.
    recruiter_client.delete(f"{base}/members/{other_id}")
    share(recruiter_client, vacancy["id"], other_id, "COLABORACION")
    assert recruiter_client.get(f"{base}/members").json()[0]["sensitive_classes"] == []


def test_el_administrador_ve_todas_las_vacantes_y_puede_administrarlas(
    vacancy, admin_client, other
):
    _, other_id = other
    assert _names(admin_client) == ["Analista de Nómina"]
    assert _names(admin_client, scope="mine") == []
    base = f"/api/v1/vacancies/{vacancy['id']}"
    assert admin_client.get(base).json()["my_access"] == "ADMINISTRADOR"
    assert share(admin_client, vacancy["id"], other_id, "LECTURA").status_code == 204


def test_el_directorio_solo_da_lo_minimo_y_solo_usuarios_activos(
    seeded, recruiter_client, admin_client, other
):
    _, other_id = other
    found = recruiter_client.get("/api/v1/users/directory", params={"search": "segunda"}).json()
    assert found == [
        {"id": other_id, "full_name": "Segunda Reclutadora", "email": "segunda@ejemplo.test"}
    ]
    assert (
        recruiter_client.get("/api/v1/users/directory", params={"search": "s"}).status_code == 422
    )
    admin_client.post(f"/api/v1/users/{other_id}/deactivate")
    assert (
        recruiter_client.get("/api/v1/users/directory", params={"search": "segunda"}).json() == []
    )


# --- Seguridad 6 y 7: transferencias --------------------------------------------------------


def test_seguridad_6_y_7_el_administrador_transfiere_y_no_se_pierde_nada(
    seeded, vacancy, other, admin_client, recruiter_client, clock
):
    other_client, other_id = other
    base = f"/api/v1/vacancies/{vacancy['id']}"
    before = recruiter_client.get(base).json()
    clock.advance(minutes=5)
    share(recruiter_client, vacancy["id"], other_id, "COLABORACION")

    response = admin_client.post(
        "/api/v1/vacancy-transfers/individual",
        json={
            "vacancy_id": vacancy["id"],
            "to_user_id": other_id,
            "reason": "Reasignación de cartera",
            "keep_previous_as_collaborator": True,
        },
    )
    assert response.status_code == 204

    after = other_client.get(base).json()
    assert after["owner"]["id"] == other_id and after["my_access"] == "RESPONSABLE"
    for field in ("id", "name", "description", "positions", "status", "created_at"):
        assert after[field] == before[field]
    # La responsable anterior queda como colaboradora y la nueva ya no figura como tal.
    assert recruiter_client.get(base).json()["my_access"] == "COLABORACION"
    members = other_client.get(f"{base}/members").json()
    assert [m["user"]["id"] for m in members] == [str(seeded[2].id)]

    history = other_client.get(f"{base}/ownership-history").json()
    assert [h["reason"] for h in history] == ["Reasignación de cartera", "Creación de la vacante"]
    assert history[0]["previous_owner"]["id"] == str(seeded[2].id)
    assert history[0]["authorized_by"]["id"] == str(seeded[1].id)


def test_solo_el_administrador_transfiere_y_solo_a_usuarios_activos(
    seeded, vacancy, other, admin_client, recruiter_client
):
    _, other_id = other
    body = {"vacancy_id": vacancy["id"], "to_user_id": other_id, "reason": "Prueba"}
    assert (
        recruiter_client.post("/api/v1/vacancy-transfers/individual", json=body).status_code == 403
    )
    assert (
        admin_client.post(
            "/api/v1/vacancy-transfers/individual", json={**body, "reason": "  "}
        ).status_code
        == 422
    )
    same_owner = {**body, "to_user_id": str(seeded[2].id)}
    assert (
        admin_client.post("/api/v1/vacancy-transfers/individual", json=same_owner).status_code
        == 409
    )
    admin_client.post(f"/api/v1/users/{other_id}/deactivate")
    assert admin_client.post("/api/v1/vacancy-transfers/individual", json=body).status_code == 409
    assert recruiter_client.get(f"/api/v1/vacancies/{vacancy['id']}").json()["owner"]["id"] == str(
        seeded[2].id
    )


def _mass(admin_client, from_id, to_id, *, operation_id=None, token=None, reason="Baja"):
    preview = admin_client.post(
        "/api/v1/vacancy-transfers/mass/preview",
        json={"from_user_id": from_id, "to_user_id": to_id},
    )
    assert preview.status_code == 200, preview.text
    return preview.json(), admin_client.post(
        "/api/v1/vacancy-transfers/mass",
        json={
            "operation_id": operation_id or str(uuid.uuid4()),
            "from_user_id": from_id,
            "to_user_id": to_id,
            "reason": reason,
            "preview_token": token or preview.json()["preview_token"],
        },
    )


def test_la_baja_de_un_reclutador_transfiere_todo_y_no_pierde_informacion(
    seeded, other, admin_client, recruiter_client, clock
):
    other_client, other_id = other
    leaving_id = str(seeded[2].id)
    first = recruiter_client.post("/api/v1/vacancies", json=VACANCY).json()
    second = recruiter_client.post(
        "/api/v1/vacancies", json={**VACANCY, "name": "Auxiliar Contable"}
    ).json()
    # Una vacante de B compartida con A, con permiso sensible: debe revocarse.
    theirs = other_client.post(
        "/api/v1/vacancies", json={**VACANCY, "name": "Jefe de Turno"}
    ).json()
    share(other_client, theirs["id"], leaving_id, "COLABORACION")
    other_client.put(
        f"/api/v1/vacancies/{theirs['id']}/members/{leaving_id}/sensitive-grants",
        json={"document_classes": ["PSICOMETRIA"]},
    )
    # B ya colaboraba en una vacante de A: al recibirla deja de figurar como colaboradora.
    share(recruiter_client, first["id"], other_id, "LECTURA")

    clock.advance(minutes=5)
    operation_id = str(uuid.uuid4())
    preview, result = _mass(admin_client, leaving_id, other_id, operation_id=operation_id)
    assert sorted(v["name"] for v in preview["vacancies"]) == [
        "Analista de Nómina",
        "Auxiliar Contable",
    ]
    assert preview["memberships_to_revoke"] == 1 and preview["grants_to_revoke"] == 1
    assert result.status_code == 200, result.text
    summary = result.json()
    assert summary["vacancies_transferred"] == 2
    assert summary["memberships_revoked"] == 1 and summary["grants_revoked"] == 1
    assert summary["user_deactivated"] is True

    # Las vacantes siguen existiendo, ahora con B como responsable.
    assert sorted(_names(other_client, scope="mine")) == [
        "Analista de Nómina",
        "Auxiliar Contable",
        "Jefe de Turno",
    ]
    for item in (first, second):
        moved = other_client.get(f"/api/v1/vacancies/{item['id']}").json()
        assert moved["owner"]["id"] == other_id
        assert moved["description"] == item["description"]
        history = other_client.get(f"/api/v1/vacancies/{item['id']}/ownership-history").json()
        assert history[0]["part_of_mass_transfer"] is True
        assert history[0]["reason"] == "Baja"
    assert other_client.get(f"/api/v1/vacancies/{first['id']}/members").json() == []
    assert other_client.get(f"/api/v1/vacancies/{theirs['id']}/members").json() == []

    # El usuario saliente pierde la sesión y el acceso, pero no se borra.
    assert recruiter_client.get("/api/v1/auth/me").status_code == 401
    credentials = {"email": RECRUITER_EMAIL, "password": RECRUITER_PASSWORD}
    assert recruiter_client.post("/api/v1/auth/login", json=credentials).status_code == 401
    leaving = admin_client.get(f"/api/v1/users/{leaving_id}").json()
    assert leaving["is_active"] is False

    # Repetir la misma operación no duplica nada.
    again = admin_client.post(
        "/api/v1/vacancy-transfers/mass",
        json={
            "operation_id": operation_id,
            "from_user_id": leaving_id,
            "to_user_id": other_id,
            "reason": "Baja",
            "preview_token": preview["preview_token"],
        },
    )
    assert again.status_code == 200 and again.json() == summary
    history = other_client.get(f"/api/v1/vacancies/{first['id']}/ownership-history").json()
    assert len(history) == 2

    actions = [
        e["action"]
        for e in admin_client.get("/api/v1/audit/events", params={"page_size": 100}).json()["items"]
    ]
    assert actions.count("transferencia_masiva.completada") == 1
    assert "usuario.desactivado" in actions


def test_la_baja_exige_una_vista_previa_vigente(seeded, other, admin_client, recruiter_client):
    _, other_id = other
    leaving_id = str(seeded[2].id)
    recruiter_client.post("/api/v1/vacancies", json=VACANCY)
    preview = admin_client.post(
        "/api/v1/vacancy-transfers/mass/preview",
        json={"from_user_id": leaving_id, "to_user_id": other_id},
    ).json()
    # Entre la vista previa y la confirmación aparece otra vacante.
    recruiter_client.post("/api/v1/vacancies", json={**VACANCY, "name": "Vacante nueva"})
    _, result = _mass(admin_client, leaving_id, other_id, token=preview["preview_token"])
    assert result.status_code == 409
    assert "vista previa" in result.json()["detail"]
    assert admin_client.get(f"/api/v1/users/{leaving_id}").json()["is_active"] is True
    assert len(_names(recruiter_client, scope="mine")) == 2


def test_la_baja_no_admite_receptor_inactivo_ni_darse_de_baja_a_uno_mismo(
    seeded, other, admin_client
):
    _, other_id = other
    admin_id, leaving_id = str(seeded[1].id), str(seeded[2].id)
    url = "/api/v1/vacancy-transfers/mass/preview"
    same = admin_client.post(url, json={"from_user_id": leaving_id, "to_user_id": leaving_id})
    assert same.status_code == 422
    yourself = admin_client.post(url, json={"from_user_id": admin_id, "to_user_id": other_id})
    assert yourself.status_code == 409
    admin_client.post(f"/api/v1/users/{other_id}/deactivate")
    inactive = admin_client.post(url, json={"from_user_id": leaving_id, "to_user_id": other_id})
    assert inactive.status_code == 409


def test_si_la_baja_falla_a_la_mitad_no_cambia_nada(
    seeded, other, admin_client, recruiter_client, monkeypatch
):
    from app.modules.users.application.service import UserService

    _, other_id = other
    leaving_id = str(seeded[2].id)
    created = recruiter_client.post("/api/v1/vacancies", json=VACANCY).json()

    def broken(*args, **kwargs):
        raise RuntimeError("fallo simulado al desactivar")

    monkeypatch.setattr(UserService, "deactivate", broken)
    _, result = _mass(admin_client, leaving_id, other_id)
    assert result.status_code == 500
    monkeypatch.undo()
    # La vacante ya se había movido dentro de la transacción; debe haberse revertido.
    unchanged = recruiter_client.get(f"/api/v1/vacancies/{created['id']}").json()
    assert unchanged["owner"]["id"] == leaving_id and unchanged["version"] == 1
    history = recruiter_client.get(f"/api/v1/vacancies/{created['id']}/ownership-history").json()
    assert len(history) == 1
