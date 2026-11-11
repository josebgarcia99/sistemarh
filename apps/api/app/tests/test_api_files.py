"""Documentos a través de la API.

Cubre las comprobaciones de almacenamiento de la sección 32.4 del documento
maestro y la comprobación de seguridad 8 (permiso adicional para documentos
sensibles). Todos los archivos son sintéticos.
"""

from __future__ import annotations

import hashlib
import os
import uuid

import pytest
from fastapi.testclient import TestClient

from app.core.config.settings import Environment, Settings
from app.infrastructure.antivirus.scanner import ScannerUnavailableError, ScanResult
from app.main import create_app
from app.modules.file_management.domain.models import DocumentType, FileStatus
from app.tests.conftest import ADMIN_EMAIL, ADMIN_PASSWORD, login, share
from app.tests.support import sample_files


def upload(client, vacancy_id, content=sample_files.PDF, name="cv.pdf", document_type="CV"):
    return client.post(
        f"/api/v1/vacancies/{vacancy_id}/files",
        params={"document_type": document_type, "filename": name},
        content=content,
        headers={"Content-Type": "application/octet-stream"},
    )


def audit_actions(admin_client, action: str) -> list[dict]:
    return admin_client.get(
        "/api/v1/audit/events", params={"action": action, "page_size": 100}
    ).json()["items"]


def stored_files(storage) -> list[str]:
    return list(storage.iter_keys())


def temp_files(storage) -> list[str]:
    return [name for name, _ in storage.iter_temp()]


def asset_status(seeded, file_id) -> FileStatus:
    with seeded[0].state.context.require_backend().transaction() as repos:
        return repos.files.get(uuid.UUID(file_id)).status


def all_assets(seeded):
    with seeded[0].state.context.require_backend().transaction() as repos:
        return [asset for status in FileStatus for asset in repos.files.list_by_status(status)]


# --- Carga -----------------------------------------------------------------------------


def test_cargar_un_cv_lo_guarda_en_el_disco_con_sus_metadatos(
    seeded, vacancy, recruiter_client, admin_client, storage, tmp_path
):
    response = upload(recruiter_client, vacancy["id"], name="CV Ana López.pdf")
    assert response.status_code == 201, response.text
    body = response.json()
    file = body["file"]
    assert body["duplicates"] == []
    assert file["original_name"] == "CV Ana López.pdf"
    assert file["document_type"] == "CV" and file["sensitive"] is False
    assert file["size_bytes"] == len(sample_files.PDF)
    assert file["sha256"] == hashlib.sha256(sample_files.PDF).hexdigest()
    assert file["content_type"] == "application/pdf"
    assert file["malware_scan"] == "NO_ANALIZADO"
    assert file["uploaded_by_name"] == "Reclutadora de Prueba"
    # La respuesta no revela dónde está el archivo.
    assert "storage" not in response.text and str(tmp_path) not in response.text

    # En el disco: nombre UUID, sin el nombre de la persona, y sin temporales.
    assert stored_files(storage) == [f"private/cv/{file['id'][0:2]}/{file['id'][2:4]}/{file['id']}"]
    assert temp_files(storage) == []
    assert b"".join(storage.read_chunks(stored_files(storage)[0])) == sample_files.PDF

    listed = recruiter_client.get(f"/api/v1/vacancies/{vacancy['id']}/files").json()
    assert [item["id"] for item in listed] == [file["id"]]
    assert recruiter_client.get(f"/api/v1/files/{file['id']}").json() == file

    (event,) = audit_actions(admin_client, "documento.cargado")
    assert event["resource_id"] == file["id"]
    assert event["details"]["tipo"] == "CV" and event["details"]["duplicados"] == 0


@pytest.mark.parametrize(
    ("name", "content", "fragment"),
    [
        ("virus.exe", b"MZ\x90\x00", "Formato no permitido"),
        ("cv.pdf", b"MZ\x90\x00 no es un PDF", "no corresponde a un PDF"),
        ("cv.docx", sample_files.docx(macros=True), "macros"),
        ("cv.pdf", b"", "vacío"),
    ],
)
def test_un_archivo_no_valido_se_rechaza_y_no_se_guarda(
    seeded, vacancy, recruiter_client, storage, name, content, fragment
):
    response = upload(recruiter_client, vacancy["id"], content=content, name=name)
    assert response.status_code == 422
    assert fragment in response.json()["detail"]
    assert stored_files(storage) == [] and temp_files(storage) == []
    assert recruiter_client.get(f"/api/v1/vacancies/{vacancy['id']}/files").json() == []
    assert all(asset.status is FileStatus.RECHAZADO for asset in all_assets(seeded))


def test_un_archivo_mayor_al_limite_se_rechaza(seeded, vacancy, storage, backend, hasher, clock):
    small = Settings(environment=Environment.TEST, storage_min_free_bytes=0, max_upload_bytes=1024)
    app = create_app(
        settings=small,
        health_checks={"c": lambda: True},
        backend=backend,
        hasher=hasher,
        clock=clock,
        storage=storage,
    )
    client = login(app, ADMIN_EMAIL, ADMIN_PASSWORD)
    # Declarado en Content-Length: se rechaza antes de crear nada.
    big = sample_files.PDF + b"\n" * 2000
    assert upload(client, vacancy["id"], content=big).status_code == 422
    assert all_assets(seeded) == []

    # Sin tamaño declarado (envío por partes): se corta al superar el límite.
    def chunks():
        for _ in range(4):
            yield b"x" * 512

    response = client.post(
        f"/api/v1/vacancies/{vacancy['id']}/files",
        params={"document_type": "CV", "filename": "cv.pdf"},
        content=chunks(),
    )
    assert response.status_code == 422 and "límite" in response.json()["detail"]
    (asset,) = all_assets(seeded)
    assert asset.status is FileStatus.RECHAZADO and asset.failure_code == "tamano_excedido"
    assert stored_files(storage) == [] and temp_files(storage) == []


def test_un_documento_duplicado_se_guarda_y_se_avisa(vacancy, recruiter_client, storage):
    first = upload(recruiter_client, vacancy["id"], name="cv.pdf").json()["file"]
    second = upload(recruiter_client, vacancy["id"], name="cv copia.pdf")
    assert second.status_code == 201
    assert [item["id"] for item in second.json()["duplicates"]] == [first["id"]]
    # No se comparte el archivo físico: cada documento se conserva por separado.
    assert len(stored_files(storage)) == 2
    # El mismo contenido en otra vacante no es un duplicado.
    other_vacancy = recruiter_client.post(
        "/api/v1/vacancies",
        json={
            "name": "Otra",
            "department": "Finanzas",
            "location": "CDMX",
            "work_mode": "REMOTA",
            "contract_type": "Temporal",
            "description": "",
            "positions": 1,
            "notes": None,
        },
    ).json()
    assert upload(recruiter_client, other_vacancy["id"]).json()["duplicates"] == []


def test_sin_espacio_en_disco_la_carga_se_rechaza_de_forma_ordenada(
    seeded, vacancy, recruiter_client, storage, monkeypatch
):
    monkeypatch.setattr(type(storage), "free_bytes", lambda self: 1024)
    response = upload(recruiter_client, vacancy["id"])
    assert response.status_code == 503
    assert "espacio" in response.json()["detail"]
    assert all_assets(seeded) == [] and stored_files(storage) == []


# --- Antivirus ---------------------------------------------------------------------------


class _Scanner:
    def __init__(self, result: ScanResult | Exception) -> None:
        self._result = result

    def scan(self, path) -> ScanResult:
        if isinstance(self._result, Exception):
            raise self._result
        return self._result


def _app_with_scanner(settings, backend, hasher, clock, storage, scanner):
    return create_app(
        settings=settings,
        health_checks={"c": lambda: True},
        backend=backend,
        hasher=hasher,
        clock=clock,
        storage=storage,
        scanner=scanner,
    )


def test_un_archivo_infectado_no_se_guarda(
    seeded, vacancy, settings, backend, hasher, clock, storage
):
    scanner = _Scanner(ScanResult(clean=False, analyzed=True, signature="Eicar-Test-Signature"))
    client = login(
        _app_with_scanner(settings, backend, hasher, clock, storage, scanner),
        ADMIN_EMAIL,
        ADMIN_PASSWORD,
    )
    response = upload(client, vacancy["id"])
    assert response.status_code == 422 and "antivirus" in response.json()["detail"]
    (asset,) = all_assets(seeded)
    assert asset.status is FileStatus.RECHAZADO and asset.failure_code == "archivo_malicioso"
    assert stored_files(storage) == [] and temp_files(storage) == []


def test_sin_antivirus_disponible_no_se_guarda_nada(
    seeded, vacancy, settings, backend, hasher, clock, storage
):
    scanner = _Scanner(ScannerUnavailableError("sin respuesta"))
    client = login(
        _app_with_scanner(settings, backend, hasher, clock, storage, scanner),
        ADMIN_EMAIL,
        ADMIN_PASSWORD,
    )
    assert upload(client, vacancy["id"]).status_code == 503
    (asset,) = all_assets(seeded)
    assert asset.status is FileStatus.FALLIDO and asset.failure_code == "antivirus_no_disponible"
    assert stored_files(storage) == [] and temp_files(storage) == []


def test_un_archivo_analizado_queda_marcado_como_limpio(
    seeded, vacancy, settings, backend, hasher, clock, storage
):
    scanner = _Scanner(ScanResult(clean=True, analyzed=True))
    client = login(
        _app_with_scanner(settings, backend, hasher, clock, storage, scanner),
        ADMIN_EMAIL,
        ADMIN_PASSWORD,
    )
    assert upload(client, vacancy["id"]).json()["file"]["malware_scan"] == "LIMPIO"


# --- Fallo durante la escritura y recuperación -------------------------------------------


def test_un_fallo_al_escribir_no_declara_guardado_el_documento(
    seeded, vacancy, recruiter_client, storage, monkeypatch
):
    def broken_commit(self, file_id, key):
        raise OSError("disco no disponible")

    monkeypatch.setattr(type(storage), "commit", broken_commit)
    response = upload(recruiter_client, vacancy["id"])
    assert response.status_code == 503
    (asset,) = all_assets(seeded)
    assert asset.status is FileStatus.FALLIDO and asset.failure_code == "escritura_fallida"
    assert stored_files(storage) == [] and temp_files(storage) == []
    assert recruiter_client.get(f"/api/v1/vacancies/{vacancy['id']}/files").json() == []


def test_la_conciliacion_recupera_una_carga_interrumpida(
    seeded, vacancy, recruiter_client, admin_client, storage, clock
):
    """Simula que el proceso murió después de mover el archivo y antes de
    confirmar el registro: queda un registro RECIBIENDO con su archivo."""
    context = seeded[0].state.context
    with context.require_backend().transaction() as repos:
        asset = context.file_service(repos).begin_upload(
            seeded[2],
            vacancy_id=uuid.UUID(vacancy["id"]),
            document_type=DocumentType.CV,
            original_name="cv.pdf",
            declared_size=None,
        )
    with storage.open_temp(asset.id) as handle:
        handle.write(sample_files.PDF)
    storage.commit(asset.id, asset.storage_key)
    # Otra carga que murió antes: solo dejó su temporal.
    with storage.open_temp(uuid.uuid4()) as handle:
        handle.write(b"a medias")

    # Mientras es reciente no se toca: podría seguir en curso.
    recent = admin_client.post("/api/v1/storage/reconciliation", json={}).json()
    assert recent["stale_uploads_failed"] == 0 and recent["consistent"] is True
    assert stored_files(storage) == [asset.storage_key]

    clock.advance(hours=2)
    admin_client = login(seeded[0], ADMIN_EMAIL, ADMIN_PASSWORD)
    # La fecha del temporal se fija respecto al reloj de la prueba.
    old = clock.now.timestamp() - 3 * 3600
    for name in temp_files(storage):
        os.utime(storage.temp_path(uuid.UUID(name.removesuffix(".part"))), (old, old))
    report = admin_client.post("/api/v1/storage/reconciliation", json={}).json()
    assert report["stale_uploads_failed"] == 1
    assert report["temp_files_removed"] == 1
    assert report["orphans_quarantined"] == 1
    assert asset_status(seeded, str(asset.id)) is FileStatus.FALLIDO
    assert stored_files(storage) == [] and temp_files(storage) == []
    # Tras la recuperación todo es coherente.
    assert admin_client.post("/api/v1/storage/reconciliation", json={}).json()["consistent"]


# --- Descarga ----------------------------------------------------------------------------


def test_descarga_autorizada_devuelve_el_archivo_integro(vacancy, recruiter_client, admin_client):
    file = upload(recruiter_client, vacancy["id"], name="CV Ana López.pdf").json()["file"]
    response = recruiter_client.get(f"/api/v1/files/{file['id']}/download")
    assert response.status_code == 200
    assert response.content == sample_files.PDF
    assert hashlib.sha256(response.content).hexdigest() == file["sha256"]
    headers = response.headers
    assert headers["content-type"] == "application/pdf"
    assert headers["content-length"] == str(len(sample_files.PDF))
    assert headers["x-content-type-options"] == "nosniff"
    assert headers["cache-control"] == "no-store"
    assert headers["content-disposition"] == (
        "attachment; filename=\"CV Ana L_pez.pdf\"; filename*=UTF-8''CV%20Ana%20L%C3%B3pez.pdf"
    )
    (event,) = audit_actions(admin_client, "documento.descargado")
    assert event["resource_id"] == file["id"] and event["result"] == "PERMITIDO"


def test_descarga_denegada_sin_acceso_a_la_vacante(vacancy, other, recruiter_client, admin_client):
    other_client, other_id = other
    file = upload(recruiter_client, vacancy["id"]).json()["file"]
    for path in (
        f"/api/v1/files/{file['id']}/download",
        f"/api/v1/files/{file['id']}",
        f"/api/v1/vacancies/{vacancy['id']}/files",
    ):
        assert other_client.get(path).status_code == 404, path
    # Tampoco puede cargar en una vacante ajena.
    assert upload(other_client, vacancy["id"]).status_code == 404
    denied = audit_actions(admin_client, "acceso.denegado")
    assert len(denied) == 4 and {event["actor_user_id"] for event in denied} == {other_id}
    assert audit_actions(admin_client, "documento.descargado") == []
    # Un identificador inexistente responde igual y no es un acceso denegado.
    assert other_client.get(f"/api/v1/files/{uuid.uuid4()}/download").status_code == 404
    assert len(audit_actions(admin_client, "acceso.denegado")) == 4


def test_sin_sesion_no_hay_descarga(seeded, vacancy, recruiter_client):
    file = upload(recruiter_client, vacancy["id"]).json()["file"]
    anonymous = TestClient(seeded[0], base_url="https://testserver")
    assert anonymous.get(f"/api/v1/files/{file['id']}/download").status_code == 401


def test_el_acceso_de_lectura_descarga_pero_no_carga(vacancy, other, recruiter_client):
    other_client, other_id = other
    file = upload(recruiter_client, vacancy["id"]).json()["file"]
    share(recruiter_client, vacancy["id"], other_id, "LECTURA")
    assert other_client.get(f"/api/v1/files/{file['id']}/download").status_code == 200
    assert upload(other_client, vacancy["id"]).status_code == 403
    share(recruiter_client, vacancy["id"], other_id, "COLABORACION")
    assert upload(other_client, vacancy["id"], name="otro.pdf").status_code == 201


def test_revocar_el_acceso_bloquea_la_descarga_de_lo_ya_cargado(vacancy, other, recruiter_client):
    other_client, other_id = other
    file = upload(recruiter_client, vacancy["id"]).json()["file"]
    share(recruiter_client, vacancy["id"], other_id, "LECTURA")
    assert other_client.get(f"/api/v1/files/{file['id']}/download").status_code == 200
    recruiter_client.delete(f"/api/v1/vacancies/{vacancy['id']}/members/{other_id}")
    assert other_client.get(f"/api/v1/files/{file['id']}/download").status_code == 404


def test_seguridad_8_los_documentos_sensibles_exigen_el_permiso_adicional(
    vacancy, other, recruiter_client, admin_client
):
    other_client, other_id = other
    base = f"/api/v1/vacancies/{vacancy['id']}"
    cv = upload(recruiter_client, vacancy["id"]).json()["file"]
    sensitive = upload(
        recruiter_client, vacancy["id"], name="resultado.pdf", document_type="PSICOMETRIA"
    ).json()["file"]
    assert sensitive["sensitive"] is True
    share(recruiter_client, vacancy["id"], other_id, "COLABORACION")

    # Compartir la vacante no da acceso al documento sensible.
    assert [f["id"] for f in other_client.get(f"{base}/files").json()] == [cv["id"]]
    assert other_client.get(f"/api/v1/files/{sensitive['id']}/download").status_code == 403
    assert other_client.get(f"/api/v1/files/{sensitive['id']}").status_code == 403
    assert (
        upload(other_client, vacancy["id"], name="p.pdf", document_type="PSICOMETRIA").status_code
        == 403
    )

    # Con el permiso de esa clase, sí; el de otra clase no sirve.
    grants = f"{base}/members/{other_id}/sensitive-grants"
    recruiter_client.put(grants, json={"document_classes": ["ESTUDIO_SOCIOECONOMICO"]})
    assert other_client.get(f"/api/v1/files/{sensitive['id']}/download").status_code == 403
    recruiter_client.put(grants, json={"document_classes": ["PSICOMETRIA"]})
    assert other_client.get(f"/api/v1/files/{sensitive['id']}/download").status_code == 200
    assert len(other_client.get(f"{base}/files").json()) == 2

    # Al quitar el permiso se bloquea de nuevo.
    recruiter_client.put(grants, json={"document_classes": []})
    assert other_client.get(f"/api/v1/files/{sensitive['id']}/download").status_code == 403
    # La administradora no necesita el permiso adicional.
    assert admin_client.get(f"/api/v1/files/{sensitive['id']}/download").status_code == 200


def test_los_documentos_sensibles_no_se_aceptan_sin_cifrado(
    seeded, vacancy, storage, backend, hasher, clock
):
    """Configuración por omisión: hasta que exista el cifrado por archivo."""
    default = Settings(environment=Environment.TEST, storage_min_free_bytes=0)
    app = create_app(
        settings=default,
        health_checks={"c": lambda: True},
        backend=backend,
        hasher=hasher,
        clock=clock,
        storage=storage,
    )
    client = login(app, ADMIN_EMAIL, ADMIN_PASSWORD)
    response = upload(client, vacancy["id"], document_type="ESTUDIO_SOCIOECONOMICO")
    assert response.status_code == 422 and "cifrado" in response.json()["detail"]
    assert all_assets(seeded) == [] and stored_files(storage) == []


def test_una_transferencia_no_pierde_los_documentos(
    seeded, vacancy, other, recruiter_client, admin_client, storage
):
    """Seguridad 7: tras transferir la vacante, los documentos siguen disponibles
    para el nuevo responsable y dejan de estarlo para el anterior."""
    other_client, other_id = other
    file = upload(recruiter_client, vacancy["id"]).json()["file"]
    transfer = admin_client.post(
        "/api/v1/vacancy-transfers/individual",
        json={
            "vacancy_id": vacancy["id"],
            "to_user_id": other_id,
            "reason": "Reasignación de carga",
            "keep_previous_as_collaborator": False,
        },
    )
    assert transfer.status_code == 204, transfer.text
    assert other_client.get(f"/api/v1/files/{file['id']}/download").content == sample_files.PDF
    assert recruiter_client.get(f"/api/v1/files/{file['id']}/download").status_code == 404
    assert len(stored_files(storage)) == 1


# --- Integridad y consistencia -----------------------------------------------------------


def test_un_archivo_faltante_se_reporta_y_no_se_descarga(
    vacancy, recruiter_client, admin_client, storage
):
    file = upload(recruiter_client, vacancy["id"]).json()["file"]
    storage.delete(stored_files(storage)[0])

    response = recruiter_client.get(f"/api/v1/files/{file['id']}/download")
    assert response.status_code == 503 and "no está disponible" in response.json()["detail"]
    (event,) = audit_actions(admin_client, "documento.no_disponible")
    assert event["resource_id"] == file["id"] and event["result"] == "FALLIDO"

    report = admin_client.post("/api/v1/storage/reconciliation", json={}).json()
    assert report["consistent"] is False and report["missing_files"] == [file["id"]]
    (audit,) = audit_actions(admin_client, "almacenamiento.conciliado")
    assert audit["result"] == "FALLIDO" and audit["details"]["archivos_faltantes"] == 1


def test_la_verificacion_sha256_detecta_un_archivo_alterado(
    vacancy, recruiter_client, admin_client, storage, tmp_path
):
    file = upload(recruiter_client, vacancy["id"]).json()["file"]
    path = tmp_path / "almacenamiento" / stored_files(storage)[0]
    path.write_bytes(sample_files.PDF.replace(b"ficticio", b"alterado"))  # mismo tamaño

    quick = admin_client.post(
        "/api/v1/storage/reconciliation", json={"verify_hashes": "none"}
    ).json()
    assert quick["consistent"] is True and quick["hashes_verified"] == 0
    full = admin_client.post("/api/v1/storage/reconciliation", json={"verify_hashes": "all"}).json()
    assert full["consistent"] is False and full["hash_mismatches"] == [file["id"]]
    assert full["hashes_verified"] == 1

    # Si cambió de tamaño se detecta sin recalcular el hash, y no se entrega.
    path.write_bytes(b"%PDF-1.4 recortado %%EOF")
    assert admin_client.post(
        "/api/v1/storage/reconciliation", json={"verify_hashes": "none"}
    ).json()["size_mismatches"] == [file["id"]]
    assert recruiter_client.get(f"/api/v1/files/{file['id']}/download").status_code == 503


def test_un_archivo_sin_registro_va_a_cuarentena_y_no_se_borra(
    vacancy, recruiter_client, admin_client, storage, tmp_path
):
    kept = upload(recruiter_client, vacancy["id"]).json()["file"]
    root = tmp_path / "almacenamiento"
    orphan = root / "private" / "cv" / "zz" / "archivo-suelto.pdf"
    orphan.parent.mkdir(parents=True)
    orphan.write_bytes(b"sin registro")

    report = admin_client.post("/api/v1/storage/reconciliation", json={}).json()
    assert report["orphans_quarantined"] == 1 and report["consistent"] is False
    assert not orphan.exists()
    quarantined = list((root / "quarantine").iterdir())
    assert len(quarantined) == 1 and quarantined[0].read_bytes() == b"sin registro"
    # El documento legítimo no se toca.
    assert recruiter_client.get(f"/api/v1/files/{kept['id']}/download").status_code == 200


# --- Eliminación autorizada y controlada -------------------------------------------------


def test_solo_un_administrador_elimina_y_debe_dar_un_motivo(
    seeded, vacancy, recruiter_client, admin_client, storage
):
    file = upload(recruiter_client, vacancy["id"]).json()["file"]
    url = f"/api/v1/files/{file['id']}/deletion"
    reason = {"reason": "Solicitud de eliminación del titular"}

    assert recruiter_client.post(url, json=reason).status_code == 403
    assert admin_client.post(url, json={"reason": "corto"}).status_code == 422
    assert admin_client.post(url, json={}).status_code == 422
    assert len(stored_files(storage)) == 1

    assert admin_client.post(url, json=reason).status_code == 204
    assert stored_files(storage) == []
    assert recruiter_client.get(f"/api/v1/files/{file['id']}/download").status_code == 404
    assert recruiter_client.get(f"/api/v1/vacancies/{vacancy['id']}/files").json() == []
    assert admin_client.post(url, json=reason).status_code == 404

    # Se conservan los metadatos y el rastro de quién, cuándo y por qué.
    (asset,) = all_assets(seeded)
    assert asset.status is FileStatus.ELIMINADO
    assert asset.deleted_by == seeded[1].id and asset.deletion_reason == reason["reason"]
    assert asset.sha256 == file["sha256"]
    (event,) = audit_actions(admin_client, "documento.eliminado")
    assert event["details"]["motivo"] == reason["reason"]
    assert event["details"]["sha256"] == file["sha256"]


def test_si_el_borrado_fisico_falla_la_conciliacion_lo_termina(
    vacancy, recruiter_client, admin_client, storage, monkeypatch
):
    file = upload(recruiter_client, vacancy["id"]).json()["file"]
    original_delete = type(storage).delete

    def failing_delete(self, key):
        raise OSError("disco ocupado")

    monkeypatch.setattr(type(storage), "delete", failing_delete)
    response = admin_client.post(
        f"/api/v1/files/{file['id']}/deletion", json={"reason": "Solicitud del titular"}
    )
    assert response.status_code == 204
    # El archivo sigue en el disco, pero ya nadie puede descargarlo.
    assert len(stored_files(storage)) == 1
    assert admin_client.get(f"/api/v1/files/{file['id']}/download").status_code == 404

    monkeypatch.setattr(type(storage), "delete", original_delete)
    report = admin_client.post("/api/v1/storage/reconciliation", json={}).json()
    assert report["deleted_files_removed"] == 1 and report["consistent"] is True
    assert stored_files(storage) == []


# --- Administración ----------------------------------------------------------------------


def test_el_estado_del_almacenamiento_es_solo_para_administradores(
    vacancy, recruiter_client, admin_client
):
    upload(recruiter_client, vacancy["id"])
    upload(recruiter_client, vacancy["id"], content=b"no es pdf")
    assert recruiter_client.get("/api/v1/storage/status").status_code == 403
    assert recruiter_client.post("/api/v1/storage/reconciliation", json={}).status_code == 403
    status = admin_client.get("/api/v1/storage/status").json()
    assert status["files_by_status"]["CONFIRMADO"] == 1
    assert status["files_by_status"]["RECHAZADO"] == 1
    assert status["free_bytes"] > 0 and status["antivirus"] == "disabled"


def test_sin_almacenamiento_configurado_las_rutas_avisan(
    seeded, vacancy, settings, backend, hasher, clock
):
    app = create_app(
        settings=settings,
        health_checks={"c": lambda: True},
        backend=backend,
        hasher=hasher,
        clock=clock,
    )
    client = login(app, ADMIN_EMAIL, ADMIN_PASSWORD)
    for response in (
        upload(client, vacancy["id"]),
        client.get(f"/api/v1/vacancies/{vacancy['id']}/files"),
        client.get("/api/v1/storage/status"),
    ):
        assert response.status_code == 503
        assert "RECLU_STORAGE_ROOT" in response.json()["detail"]


# --- Respaldo y restauración -------------------------------------------------------------


def test_respaldo_y_restauracion_con_manifiesto(
    seeded, vacancy, recruiter_client, storage, tmp_path, capsys
):
    """El manifiesto sale de la base; una copia de los archivos se verifica contra
    él sin la base, y una copia dañada se detecta."""
    import shutil

    from app import cli

    context = seeded[0].state.context
    upload(recruiter_client, vacancy["id"], name="uno.pdf")
    upload(recruiter_client, vacancy["id"], content=sample_files.docx(), name="dos.docx")
    upload(recruiter_client, vacancy["id"], content=b"no es pdf", name="malo.pdf")  # rechazado

    manifest = tmp_path / "manifiesto.jsonl"
    assert cli.storage_manifest(context, manifest) == 0
    assert "2 documentos" in capsys.readouterr().out
    assert str(tmp_path / "almacenamiento") not in manifest.read_text()

    # "Respaldo": copia del disco. "Restauración": se verifica la copia.
    restored = tmp_path / "restaurado"
    shutil.copytree(tmp_path / "almacenamiento", restored)
    assert cli.main(["storage-verify", "--manifest", str(manifest), "--root", str(restored)]) == 0
    assert (
        cli.main(["storage-verify", "--manifest", str(manifest), "--root", str(restored), "--full"])
        == 0
    )

    damaged = next(path for path in (restored / "private").rglob("*") if path.is_file())
    damaged.write_bytes(damaged.read_bytes()[:-1] + b"X")
    capsys.readouterr()
    assert (
        cli.main(["storage-verify", "--manifest", str(manifest), "--root", str(restored), "--full"])
        == 2
    )
    assert "HASH DISTINTO" in capsys.readouterr().out


def test_el_comando_de_conciliacion_informa_y_devuelve_codigo(
    seeded, vacancy, recruiter_client, storage, capsys
):
    from app import cli

    context = seeded[0].state.context
    upload(recruiter_client, vacancy["id"])
    assert cli.storage_check(context, "all") == 0
    assert "coherente" in capsys.readouterr().out
    storage.delete(stored_files(storage)[0])
    assert cli.storage_check(context, "none") == 2
    output = capsys.readouterr().out
    assert "FALTANTE" in output and "CON INCONSISTENCIAS" in output
