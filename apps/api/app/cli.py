"""Comandos de administración.

Crear el usuario maestro (primer administrador):

    python -m app.cli create-admin

El comando pregunta correo, nombre completo y contraseña. La contraseña no se
muestra al escribirla, no se guarda en ningún archivo y no queda en el
historial de la terminal. Para instalaciones sin terminal interactiva:

    echo "$CLAVE" | python -m app.cli create-admin --email a@b.mx --name "Nombre" --password-stdin
"""

from __future__ import annotations

import argparse
import getpass
import sys

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
    from app.main import build_sql_backend

    settings = get_settings()
    return AppContext(
        settings=settings,
        backend=backend if backend is not None else build_sql_backend(settings),
        hasher=Argon2Hasher(),
        clock=utc_now,
        auth_policy=AuthPolicy(),
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    commands = parser.add_subparsers(dest="command", required=True)
    admin = commands.add_parser("create-admin", help="Crea el usuario maestro")
    admin.add_argument("--email")
    admin.add_argument("--name")
    admin.add_argument(
        "--password-stdin", action="store_true", help="Lee la contraseña de la entrada estándar"
    )
    args = parser.parse_args(argv)

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
