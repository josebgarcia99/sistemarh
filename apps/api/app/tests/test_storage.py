"""Almacenamiento físico, validación de archivos, antivirus y manifiesto."""

from __future__ import annotations

import hashlib
import socketserver
import struct
import threading
import uuid

import pytest

from app.infrastructure.antivirus.scanner import ClamdScanner, ScannerUnavailableError
from app.infrastructure.storage.local import (
    InvalidStorageKeyError,
    LocalFileStorage,
    StorageError,
    build_key,
)
from app.infrastructure.storage.manifest import (
    ManifestEntry,
    read_manifest,
    verify_tree,
    write_manifest,
)
from app.modules.file_management.domain.filetypes import (
    FileKind,
    FileRejectedError,
    inspect_file,
    sanitize_filename,
)
from app.tests.support import sample_files


def _store(storage: LocalFileStorage, content: bytes, folder: str = "cv") -> tuple[uuid.UUID, str]:
    file_id = uuid.uuid4()
    key = build_key("private", folder, file_id)
    with storage.open_temp(file_id) as handle:
        handle.write(content)
    storage.commit(file_id, key)
    return file_id, key


# --- Almacenamiento local ------------------------------------------------------------


def test_la_clave_usa_el_uuid_y_dos_niveles_de_carpetas():
    file_id = uuid.UUID("3fa91c2e-0000-4000-8000-000000000001")
    assert build_key("private", "cv", file_id) == f"private/cv/3f/a9/{file_id}"
    with pytest.raises(InvalidStorageKeyError):
        build_key("public", "cv", file_id)
    with pytest.raises(InvalidStorageKeyError):
        build_key("private", "../cv", file_id)


def test_guardar_mueve_el_temporal_a_su_lugar_y_se_puede_leer(storage, tmp_path):
    file_id, key = _store(storage, b"contenido de prueba")
    root = tmp_path / "almacenamiento"
    assert (root / key).read_bytes() == b"contenido de prueba"
    assert not (root / "processing" / "temporary" / f"{file_id}.part").exists()
    assert storage.size(key) == 19
    assert b"".join(storage.read_chunks(key)) == b"contenido de prueba"
    assert storage.sha256(key) == hashlib.sha256(b"contenido de prueba").hexdigest()


def test_un_archivo_definitivo_no_se_sobrescribe(storage):
    file_id, key = _store(storage, b"original")
    with storage.open_temp(file_id) as handle:
        handle.write(b"otro contenido")
    with pytest.raises(StorageError):
        storage.commit(file_id, key)
    assert b"".join(storage.read_chunks(key)) == b"original"


@pytest.mark.parametrize(
    "key",
    [
        "../../etc/passwd",
        "/etc/passwd",
        "private/cv/../../../etc/passwd",
        "private/cv/3f/a9/no-es-uuid",
        "quarantine/cv/3f/a9/3fa91c2e-0000-4000-8000-000000000001",
        "private/cv/3f/a9/3fa91c2e-0000-4000-8000-000000000001/extra",
        "",
    ],
)
def test_las_referencias_fuera_de_la_raiz_se_rechazan(storage, key):
    for operation in (storage.exists, storage.size, storage.open, storage.delete):
        with pytest.raises(InvalidStorageKeyError):
            operation(key)


def test_los_errores_no_revelan_rutas_fisicas(storage, tmp_path):
    missing = build_key("private", "cv", uuid.uuid4())
    with pytest.raises(StorageError) as error:
        storage.open(missing)
    assert str(tmp_path) not in str(error.value)


def test_la_raiz_debe_existir_y_ser_absoluta(tmp_path):
    with pytest.raises(StorageError):
        LocalFileStorage(tmp_path / "no-montado").prepare()
    with pytest.raises(StorageError):
        LocalFileStorage(tmp_path.relative_to(tmp_path.anchor))


def test_cuarentena_aparta_el_archivo_sin_borrarlo(storage, tmp_path):
    _, key = _store(storage, b"huerfano")
    name = storage.quarantine(key)
    assert not storage.exists(key)
    assert (tmp_path / "almacenamiento" / "quarantine" / name).read_bytes() == b"huerfano"


def test_los_documentos_sobreviven_a_un_reinicio(storage, tmp_path):
    """Una instancia nueva sobre la misma carpeta (reinicio de la aplicación o
    del contenedor) encuentra los mismos archivos."""
    _, key = _store(storage, b"persistente")
    restarted = LocalFileStorage(tmp_path / "almacenamiento")
    restarted.prepare()
    assert b"".join(restarted.read_chunks(key)) == b"persistente"
    assert list(restarted.iter_keys()) == [key]


# --- Validación de archivos ------------------------------------------------------------


def _inspect(tmp_path, name: str, content: bytes) -> FileKind:
    path = tmp_path / "archivo.part"
    path.write_bytes(content)
    return inspect_file(path, name)


@pytest.mark.parametrize(
    ("name", "content", "kind"),
    [
        ("cv.pdf", sample_files.PDF, FileKind.PDF),
        ("CV.PDF", sample_files.PDF, FileKind.PDF),
        ("cv.docx", sample_files.docx(), FileKind.DOCX),
        ("cv.doc", sample_files.doc(), FileKind.DOC),
        ("foto.png", sample_files.PNG, FileKind.PNG),
        ("foto.jpeg", sample_files.JPG, FileKind.JPG),
    ],
)
def test_se_aceptan_los_formatos_permitidos(tmp_path, name, content, kind):
    assert _inspect(tmp_path, name, content) is kind


@pytest.mark.parametrize(
    ("name", "content", "code"),
    [
        ("programa.exe", b"MZ\x90\x00", "extension_no_permitida"),
        ("sin_extension", sample_files.PDF, "extension_no_permitida"),
        ("cv.pdf", b"MZ\x90\x00 ejecutable con otro nombre", "tipo_no_coincide"),
        ("cv.pdf", sample_files.docx(), "tipo_no_coincide"),
        ("cv.pdf", b"%PDF-1.4\nsin final", "archivo_danado"),
        ("cv.pdf", b"", "archivo_vacio"),
        ("cv.docx", sample_files.PDF, "tipo_no_coincide"),
        ("cv.docx", sample_files.zip_without_word(), "tipo_no_coincide"),
        ("cv.docx", sample_files.docx(macros=True), "contiene_macros"),
        ("cv.doc", sample_files.doc(macros=True), "contiene_macros"),
        ("cv.doc", sample_files.PDF, "tipo_no_coincide"),
        ("foto.png", sample_files.JPG, "tipo_no_coincide"),
        ("foto.jpg", sample_files.PNG, "tipo_no_coincide"),
    ],
)
def test_se_rechazan_archivos_no_permitidos_o_disfrazados(tmp_path, name, content, code):
    with pytest.raises(FileRejectedError) as rejected:
        _inspect(tmp_path, name, content)
    assert rejected.value.code == code


@pytest.mark.parametrize(
    ("raw", "clean"),
    [
        ("CV Ana López.pdf", "CV Ana López.pdf"),
        ("../../etc/passwd", "passwd"),
        ("C:\\Users\\ana\\cv.docx", "cv.docx"),
        ("  cv\x00\r\n.pdf  ", "cv.pdf"),
        ('cv<>:"|?*.pdf', "cv_______.pdf"),
        ("...", "documento"),
        ("a" * 300 + ".pdf", "a" * 196 + ".pdf"),
    ],
)
def test_el_nombre_original_se_sanea(raw, clean):
    assert sanitize_filename(raw) == clean


# --- Antivirus (clamd simulado) --------------------------------------------------------


class _FakeClamd(socketserver.BaseRequestHandler):
    def handle(self) -> None:
        assert self.request.recv(10) == b"zINSTREAM\0"
        received = b""
        while True:
            (length,) = struct.unpack("!L", self._exactly(4))
            if length == 0:
                break
            received += self._exactly(length)
        infected = b"EICAR" in received
        self.request.sendall(
            b"stream: Eicar-Test-Signature FOUND\0" if infected else b"stream: OK\0"
        )

    def _exactly(self, count: int) -> bytes:
        data = b""
        while len(data) < count:
            data += self.request.recv(count - len(data))
        return data


@pytest.fixture
def clamd_port():
    server = socketserver.TCPServer(("127.0.0.1", 0), _FakeClamd)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield server.server_address[1]
    server.shutdown()
    server.server_close()


def test_el_antivirus_distingue_limpio_de_infectado(tmp_path, clamd_port):
    scanner = ClamdScanner("127.0.0.1", clamd_port, timeout_seconds=5)
    clean = tmp_path / "limpio"
    clean.write_bytes(sample_files.PDF)
    infected = tmp_path / "infectado"
    infected.write_bytes(b"firma de prueba EICAR, no es malware real")

    assert scanner.scan(clean).clean is True
    result = scanner.scan(infected)
    assert (result.clean, result.analyzed, result.signature) == (
        False,
        True,
        "Eicar-Test-Signature",
    )


def test_si_el_antivirus_no_responde_se_avisa(tmp_path):
    path = tmp_path / "archivo"
    path.write_bytes(sample_files.PDF)
    with pytest.raises(ScannerUnavailableError):
        ClamdScanner("127.0.0.1", 1, timeout_seconds=1).scan(path)


# --- Manifiesto y verificación de una copia --------------------------------------------


def test_el_manifiesto_verifica_una_copia_restaurada(storage, tmp_path):
    entries = []
    for content in (b"uno", b"dos", b"tres"):
        _, key = _store(storage, content)
        entries.append(ManifestEntry(key, len(content), storage.sha256(key)))
    manifest = tmp_path / "manifiesto.jsonl"
    assert (
        write_manifest(
            manifest, entries, generated_at="2026-11-11T00:00:00Z", schema_version="0003"
        )
        == 3
    )
    listed = list(read_manifest(manifest))
    assert listed == entries

    root = tmp_path / "almacenamiento"
    assert verify_tree(root, listed, full=True).ok

    # Copia dañada: falta un archivo, otro cambió de tamaño, otro de contenido y sobra uno.
    (root / entries[0].key).unlink()
    (root / entries[1].key).write_bytes(b"dos y algo")
    (root / entries[2].key).write_bytes(b"tre5")
    _, extra = _store(storage, b"sobrante")
    report = verify_tree(root, listed, full=True)
    assert not report.ok
    assert report.missing == [entries[0].key]
    assert report.size_mismatch == [entries[1].key]
    assert report.hash_mismatch == [entries[2].key]
    assert report.unexpected == [extra]
    # Sin recalcular hashes, el cambio de contenido con el mismo tamaño no se detecta.
    assert verify_tree(root, listed).hash_mismatch == []
