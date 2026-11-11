"""Comandos de administración.

Crear el usuario maestro (primer administrador):

    python -m app.cli create-admin

El comando pregunta correo, nombre completo y contraseña. La contraseña no se
muestra al escribirla, no se guarda en ningún archivo y no queda en el
historial de la terminal. Para instalaciones sin terminal interactiva:

    echo "$CLAVE" | python -m app.cli create-admin --email a@b.mx --name "Nombre" --password-stdin

Almacenamiento documental:

    python -m app.cli storage-check [--verify-hashes none|sample|all]
        Concilia SQL Server con el disco. Código de salida 2 si hay inconsistencias.
    python -m app.cli storage-manifest --output manifiesto.jsonl
        Lista de documentos confirmados (clave, tamaño y SHA-256) para un respaldo.
    python -m app.cli storage-verify --manifest manifiesto.jsonl --root /ruta/copia [--full]
        Verifica una copia o una restauración contra un manifiesto. No usa la base.

Clave maestra (cifra las API keys de IA y los documentos sensibles):

    python -m app.cli generate-master-key --output /ruta/fuera/del/repositorio/clave
"""

from __future__ import annotations

import argparse
import getpass
import sys
from pathlib import Path

from app.composition.backend import Backend
from app.composition.context import AppContext
from app.core.clock import utc_now
from app.core.config.settings import get_settings
from app.core.exceptions.errors import AppError
from app.core.security.passwords import Argon2Hasher
from app.modules.authentication.domain.models import AuthPolicy


def create_admin(context: AppContext, *, email: str, full_name: str, password: str) -> str:
    with context.require_backend().transaction() as repos:
        user = context.user_service(repos).create_master_user(
            email=email, full_name=full_name, password=password
        )
    return user.email


def _build_context(backend: Backend | None = None) -> AppContext:
    from app.composition.bootstrap import build_master_key, build_sql_backend, build_storage

    settings = get_settings()
    return AppContext(
        settings=settings,
        backend=backend if backend is not None else build_sql_backend(settings),
        hasher=Argon2Hasher(),
        clock=utc_now,
        auth_policy=AuthPolicy(),
        storage=build_storage(settings),
        master_key=build_master_key(settings),
    )


SCHEMA_VERSION = "0009"
_SAMPLE_SIZE = 200


def storage_check(context: AppContext, verify: str) -> int:
    """Concilia el disco con la base e imprime el resultado."""
    amount = {"none": 0, "sample": _SAMPLE_SIZE, "all": None}[verify]
    with context.require_backend().transaction() as repos:
        report = context.reconciler(repos).run(verify_hashes=amount)
    print(f"Documentos confirmados revisados: {report.confirmed_checked}")
    print(f"Hashes SHA-256 verificados:       {report.hashes_verified}")
    print(f"Cargas interrumpidas cerradas:    {report.stale_uploads_failed}")
    print(f"Temporales limpiados:             {report.temp_files_removed}")
    print(f"Borrados pendientes terminados:   {report.deleted_files_removed}")
    print(f"Archivos sin registro (a cuarentena): {len(report.orphans_quarantined)}")
    for name in report.orphans_quarantined:
        print(f"  cuarentena: {name}")
    for label, ids in (
        ("FALTANTE", report.missing_files),
        ("TAMAÑO DISTINTO", report.size_mismatches),
        ("HASH DISTINTO", report.hash_mismatches),
    ):
        for file_id in ids:
            print(f"  {label}: documento {file_id}")
    print("Resultado: " + ("coherente" if report.consistent else "CON INCONSISTENCIAS"))
    return 0 if report.consistent else 2


def storage_manifest(context: AppContext, output: Path) -> int:
    from app.infrastructure.storage.manifest import ManifestEntry, write_manifest
    from app.modules.file_management.domain.models import FileStatus

    context.require_storage()
    with context.require_backend().transaction() as repos:
        assets = repos.files.list_by_status(FileStatus.CONFIRMADO)
    count = write_manifest(
        output,
        # Lo que hay en el disco: la copia se verifica sin necesitar la clave maestra.
        (
            ManifestEntry(a.storage_key, a.stored_size_bytes or 0, a.stored_sha256 or "")
            for a in assets
        ),
        generated_at=context.clock().isoformat(),
        schema_version=SCHEMA_VERSION,
    )
    print(f"Manifiesto escrito con {count} documentos: {output}")
    return 0


def generate_master_key(output: Path) -> int:
    """Crea el archivo de la clave maestra. Nunca sobrescribe uno existente:
    perder la clave anterior dejaría ilegible todo lo cifrado con ella."""
    import os

    from app.core.security.master_key import MasterKey, generate_key_text

    try:
        descriptor = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        print("Ya existe un archivo en esa ruta. No se sobrescribe.", file=sys.stderr)
        return 1
    text = generate_key_text()
    with os.fdopen(descriptor, "w", encoding="ascii") as handle:
        handle.write(text + "\n")
    print(f"Clave maestra creada. Identificador: {MasterKey.from_text(text).key_id}")
    print("Respáldala por separado de la base de datos: sin ella no se puede leer lo cifrado.")
    return 0


def storage_verify(manifest: Path, root: Path, *, full: bool) -> int:
    """Verifica un árbol de archivos contra un manifiesto. No necesita la base."""
    from app.infrastructure.storage.manifest import read_manifest, verify_tree

    report = verify_tree(root, read_manifest(manifest), full=full)
    print(f"Archivos del manifiesto revisados: {report.checked}")
    print(f"Hashes SHA-256 verificados:        {report.hashes_checked}")
    for label, keys in (
        ("FALTANTE", report.missing),
        ("TAMAÑO DISTINTO", report.size_mismatch),
        ("HASH DISTINTO", report.hash_mismatch),
        ("no listado en el manifiesto", report.unexpected),
    ):
        for key in keys:
            print(f"  {label}: {key}")
    print("Resultado: " + ("la copia coincide con el manifiesto" if report.ok else "CON ERRORES"))
    return 0 if report.ok else 2


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    commands = parser.add_subparsers(dest="command", required=True)
    admin = commands.add_parser("create-admin", help="Crea el usuario maestro")
    admin.add_argument("--email")
    admin.add_argument("--name")
    admin.add_argument(
        "--password-stdin", action="store_true", help="Lee la contraseña de la entrada estándar"
    )
    check = commands.add_parser("storage-check", help="Concilia SQL Server con el disco")
    check.add_argument("--verify-hashes", choices=("none", "sample", "all"), default="sample")
    manifest = commands.add_parser("storage-manifest", help="Manifiesto para respaldos")
    manifest.add_argument("--output", type=Path, required=True)
    verify = commands.add_parser("storage-verify", help="Verifica una copia de los documentos")
    verify.add_argument("--manifest", type=Path, required=True)
    verify.add_argument("--root", type=Path, required=True)
    verify.add_argument("--full", action="store_true", help="Recalcula el SHA-256 de cada archivo")
    keygen = commands.add_parser("generate-master-key", help="Crea el archivo de la clave maestra")
    keygen.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)

    if args.command == "generate-master-key":
        return generate_master_key(args.output)
    if args.command == "storage-verify":
        return storage_verify(args.manifest, args.root, full=args.full)
    if args.command in {"storage-check", "storage-manifest"}:
        try:
            context = _build_context()
            if args.command == "storage-check":
                return storage_check(context, args.verify_hashes)
            return storage_manifest(context, args.output)
        except AppError as error:
            print(f"No se pudo completar: {error.detail}", file=sys.stderr)
            return 1

    email = args.email or input("Correo: ")
    full_name = args.name or input("Nombre completo: ")
    if args.password_stdin:
        password = sys.stdin.readline().rstrip("\r\n")
    else:
        password = getpass.getpass("Contraseña (no se muestra): ")
        if getpass.getpass("Repite la contraseña: ") != password:
            print("Las contraseñas no coinciden.", file=sys.stderr)
            return 1

    try:
        created = create_admin(
            _build_context(), email=email, full_name=full_name, password=password
        )
    except AppError as error:
        print(f"No se creó el usuario: {error.detail}", file=sys.stderr)
        return 1
    print(f"Usuario maestro creado: {created}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
