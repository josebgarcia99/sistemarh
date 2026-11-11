from __future__ import annotations

import pytest

from app.cli import create_admin
from app.core.exceptions.errors import ConflictError, ValidationFailedError
from app.core.ids import new_sequential_uuid
from app.core.security.passwords import validate_password
from app.core.security.tokens import generate_token, hash_token
from app.modules.audit.application.service import AuditLog
from app.tests.support.sql_memory import build_test_backend


def _sql_server_sort_key(value) -> bytes:
    # SQL Server compara primero los últimos 6 bytes de un UNIQUEIDENTIFIER.
    return value.bytes[10:16]


def test_los_identificadores_crecen_en_el_orden_de_sql_server():
    ids = [new_sequential_uuid(now_ms=1_800_000_000_000 + i) for i in range(50)]
    assert sorted(ids, key=_sql_server_sort_key) == ids
    assert len(set(ids)) == 50


def test_dos_identificadores_del_mismo_milisegundo_son_distintos():
    assert new_sequential_uuid(now_ms=1) != new_sequential_uuid(now_ms=1)


def test_el_hasher_verifica_y_no_guarda_la_contrasena(hasher):
    hashed = hasher.hash("Clave-Maestra-2026")
    assert hashed.startswith("$argon2id$")
    assert "Clave-Maestra-2026" not in hashed
    assert hasher.verify(hashed, "Clave-Maestra-2026") is True
    assert hasher.verify(hashed, "otra-clave-000000") is False
    assert hasher.verify("no-es-un-hash", "x") is False


@pytest.mark.parametrize(
    "password",
    ["corta", "aaaaaaaaaaaaaaaa", "x" * 129, "persona@ejemplo.test"],
)
def test_la_politica_rechaza_contrasenas_debiles(password):
    with pytest.raises(ValidationFailedError):
        validate_password(password, email="persona@ejemplo.test")


def test_la_politica_acepta_una_contrasena_razonable():
    validate_password("Clave-Maestra-2026", email="persona@ejemplo.test")


def test_el_token_de_sesion_se_guarda_solo_como_hash():
    token = generate_token()
    assert len(token) >= 40
    assert token not in hash_token(token)
    assert len(hash_token(token)) == 64
    assert hash_token(token) == hash_token(token)


def test_la_auditoria_rechaza_campos_con_secretos(clock):
    backend = build_test_backend()
    with backend.transaction() as repos:
        log = AuditLog(repos.audit, clock)
        with pytest.raises(ValueError, match="no admite"):
            log.record("usuario.creado", details={"password": "x"})
        log.record("usuario.creado", details={"rol": "RECLUTADOR"})
        assert log.list(action=None, offset=0, limit=10)[1] == 1


def test_el_comando_crea_el_usuario_maestro_una_sola_vez(app_with_data):
    context = app_with_data.state.context
    email = create_admin(
        context,
        email="Maestro@Ejemplo.test",
        full_name="Usuario Maestro",
        password="Clave-Maestra-2026",
    )
    assert email == "maestro@ejemplo.test"
    with pytest.raises(ConflictError):
        create_admin(
            context, email="otro@ejemplo.test", full_name="Otro", password="Clave-Maestra-2026"
        )
