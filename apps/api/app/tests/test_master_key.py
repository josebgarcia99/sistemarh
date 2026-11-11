"""Clave maestra: cifrado de textos y de archivos."""

from __future__ import annotations

import io

import pytest

from app.core.security.master_key import (
    DecryptionError,
    MasterKey,
    MasterKeyError,
    generate_key_text,
)


@pytest.fixture
def key() -> MasterKey:
    return MasterKey.from_text(generate_key_text())


def _encrypt(key: MasterKey, data: bytes) -> bytes:
    target = io.BytesIO()
    key.encrypt_stream(io.BytesIO(data), target)
    return target.getvalue()


def _decrypt(key: MasterKey, sealed: bytes, piece: int = 7919) -> bytes:
    pieces = (sealed[i : i + piece] for i in range(0, len(sealed), piece))
    return b"".join(key.decrypt_chunks(pieces))


def test_un_texto_se_recupera_solo_con_la_misma_clave_y_el_mismo_contexto(key):
    token = key.encrypt_text("valor-ficticio-0000", context="proveedor:ANTHROPIC")
    assert "valor-ficticio" not in token
    assert key.decrypt_text(token, context="proveedor:ANTHROPIC") == "valor-ficticio-0000"
    # Cada cifrado es distinto aunque el texto sea el mismo.
    assert token != key.encrypt_text("valor-ficticio-0000", context="proveedor:ANTHROPIC")
    with pytest.raises(DecryptionError):
        key.decrypt_text(token, context="proveedor:OPENAI")
    with pytest.raises(DecryptionError):
        MasterKey.from_text(generate_key_text()).decrypt_text(token, context="proveedor:ANTHROPIC")
    with pytest.raises(DecryptionError):
        key.decrypt_text(token[:-4] + "AAAA", context="proveedor:ANTHROPIC")


@pytest.mark.parametrize("size", [0, 1, 1024 * 1024 - 1, 1024 * 1024, 2 * 1024 * 1024 + 5])
def test_un_archivo_cifrado_se_recupera_integro(key, size):
    data = bytes(range(256)) * (size // 256) + bytes(size % 256)
    sealed = _encrypt(key, data)
    assert data[:64] not in sealed or size < 16
    assert _decrypt(key, sealed) == data
    assert _decrypt(key, sealed, piece=1024 * 1024 * 4) == data


def test_un_archivo_cifrado_alterado_recortado_o_de_otra_clave_se_detecta(key):
    data = b"documento sensible ficticio " * 100_000  # varios bloques
    sealed = _encrypt(key, data)

    altered = bytearray(sealed)
    altered[len(sealed) // 2] ^= 1
    for broken in (
        bytes(altered),
        sealed[: len(sealed) // 2],  # recortado a la mitad
        sealed[: 13 + 4 + 1024 * 1024 + 16],  # recortado justo al final de un bloque
        sealed + b"extra",
        b"no cifrado",
        b"",
    ):
        with pytest.raises(DecryptionError):
            _decrypt(key, broken)
    with pytest.raises(DecryptionError):
        _decrypt(MasterKey.from_text(generate_key_text()), sealed)


def test_la_clave_se_carga_de_un_archivo_y_nunca_se_muestra(tmp_path):
    text = generate_key_text()
    path = tmp_path / "clave"
    path.write_text(text + "\n")
    loaded = MasterKey.load(path)
    assert loaded.key_id == MasterKey.from_text(text).key_id
    assert len(loaded.key_id) == 16 and loaded.key_id not in text
    assert text not in repr(loaded) and text not in str(loaded)
    assert MasterKey.from_text(generate_key_text()).key_id != loaded.key_id


@pytest.mark.parametrize("content", ["", "no es base64 !!", "YWJj"])
def test_una_clave_invalida_se_rechaza_sin_revelarla(tmp_path, content):
    path = tmp_path / "clave"
    path.write_text(content)
    with pytest.raises(MasterKeyError) as error:
        MasterKey.load(path)
    assert content == "" or content not in str(error.value)
    with pytest.raises(MasterKeyError):
        MasterKey.load(tmp_path / "no-existe")
