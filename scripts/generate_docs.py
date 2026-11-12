"""Genera la documentación que se deriva del código.

    python scripts/generate_docs.py           # escribe los archivos
    python scripts/generate_docs.py --check   # falla si alguno está desactualizado

- ``docs/api/contratos_api.md``: todas las rutas de la API, a partir de su
  contrato OpenAPI.
- ``docs/database/diagrama_entidad_relacion.md``: tablas y relaciones, a
  partir del modelo de datos.

No necesita base de datos ni servidores.
"""

# ruff: noqa: E402  (las importaciones de la API van después de ajustar la ruta)
from __future__ import annotations

import os
import sys
from pathlib import Path

for _name in [name for name in os.environ if name.startswith("RECLU_")]:
    del os.environ[_name]
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))

import app.composition.sql_backend  # noqa: F401  (carga todas las tablas)
from app.cli import SCHEMA_VERSION
from app.core.config.settings import Environment, Settings
from app.infrastructure.database.base import Base
from app.main import create_app

PUBLIC = {
    ("GET", "/api/v1/health/live"),
    ("GET", "/api/v1/health/ready"),
    ("POST", "/api/v1/auth/login"),
}
METHOD_ORDER = {"GET": 0, "POST": 1, "PUT": 2, "PATCH": 3, "DELETE": 4}
SCHEMA_TITLES = {
    "auth": "Identidad",
    "vacancy": "Vacantes y acceso",
    "files": "Documentos",
    "ai": "Inteligencia artificial",
    "recruitment": "Reclutamiento",
    "ops": "Operación",
}


def _schema_name(node: dict | None) -> str:
    if not node:
        return "—"
    if "$ref" in node:
        return f"`{node['$ref'].rsplit('/', 1)[-1]}`"
    if node.get("type") == "array":
        return f"lista de {_schema_name(node.get('items'))}"
    return node.get("type", "—")


def api_contracts() -> str:
    app = create_app(settings=Settings(environment=Environment.TEST))
    spec = app.openapi()
    groups: dict[str, list[tuple[str, str, dict]]] = {}
    for path, operations in spec["paths"].items():
        for method, operation in operations.items():
            tag = (operation.get("tags") or ["otras"])[0]
            groups.setdefault(tag, []).append((method.upper(), path, operation))
    total = sum(len(items) for items in groups.values())
    lines = [
        "# Contratos de la API",
        "",
        "> Generado por `scripts/generate_docs.py` a partir del contrato OpenAPI. "
        "No editar a mano.",
        "",
        f"Versión de la API: `{spec['info']['version']}`. Rutas: {total}. "
        "Todas cuelgan de `/api/v1`.",
        "",
        "**Reglas comunes**",
        "",
        "- Solo tres rutas responden sin sesión (marcadas como «Pública»). Las demás exigen la "
        "cookie de sesión y, si modifican algo, la cabecera `X-CSRF-Token`.",
        "- Tener sesión no basta: cada operación comprueba el permiso sobre el objeto concreto "
        "(ver `docs/permissions/matriz_permisos.md`). Un recurso ajeno responde 404, igual que "
        "si no existiera.",
        "- Los errores usan el formato `application/problem+json` con `code`, `detail` y "
        "`correlation_id`.",
        "- Las fechas van en UTC (ISO 8601). Los identificadores son UUID.",
        "- Fuera de producción, el contrato completo y navegable está en `/api/v1/docs`.",
        "",
    ]
    for tag in sorted(groups):
        lines += [
            f"## {tag.capitalize()}",
            "",
            "| Método | Ruta | Qué hace | Entrada | Respuesta |",
        ]
        lines.append("| --- | --- | --- | --- | --- |")
        for method, path, operation in sorted(
            groups[tag], key=lambda item: (item[1], METHOD_ORDER.get(item[0], 9))
        ):
            body = operation.get("requestBody", {}).get("content", {})
            request = _schema_name(body.get("application/json", {}).get("schema"))
            if not body:
                request = "—"
            elif "application/json" not in body:
                request = "archivo"
            success = next(
                (code for code in sorted(operation.get("responses", {})) if code.startswith("2")),
                "200",
            )
            content = operation["responses"].get(success, {}).get("content", {})
            response = _schema_name(content.get("application/json", {}).get("schema"))
            summary = operation.get("summary", "").replace("|", "/")
            if (method, path) in PUBLIC:
                summary += " (Pública)"
            short = path.removeprefix("/api/v1")
            lines.append(f"| {method} | `{short}` | {summary} | {request} | {success} {response} |")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _entity(table) -> str:  # noqa: ANN001
    return f"{table.schema}_{table.name}"


def er_diagram() -> str:
    tables = sorted(Base.metadata.tables.values(), key=lambda t: (t.schema, t.name))
    lines = [
        "# Diagrama entidad-relación",
        "",
        "> Generado por `scripts/generate_docs.py` a partir del modelo de datos. No editar a mano.",
        "",
        f"Versión del esquema: `{SCHEMA_VERSION}`. Tablas: {len(tables)}. El detalle de cada "
        "columna está en [`diccionario_datos.md`](diccionario_datos.md).",
        "",
        "Cada diagrama muestra las tablas de un esquema y sus relaciones, también con tablas "
        "de otros esquemas. Para que se lean, se omiten las columnas de autoría (quién creó, "
        "modificó o aprobó algo), que apuntan todas a `auth.users`.",
        "",
    ]
    for schema in sorted({table.schema for table in tables}, key=list(SCHEMA_TITLES).index):
        own = [table for table in tables if table.schema == schema]
        lines += [f"## {SCHEMA_TITLES[schema]} (`{schema}`)", "", "```mermaid", "erDiagram"]
        relations = []
        for table in own:
            lines.append(f"  {_entity(table)} {{")
            for column in table.columns:
                if column.primary_key:
                    lines.append(f"    {column.type.__class__.__name__.lower()} {column.name} PK")
            lines.append("  }")
            for key in sorted(table.foreign_key_constraints, key=lambda k: k.column_keys[0]):
                column = key.column_keys[0]
                authorship = key.referred_table.fullname == "auth.users" and (
                    column.endswith("_by") or column == "actor_user_id"
                )
                if not authorship:
                    relations.append(
                        f"  {_entity(key.referred_table)} ||--o{{ {_entity(table)} : {column}"
                    )
        lines += relations + ["```", ""]
    return "\n".join(lines).rstrip() + "\n"


TARGETS = {
    ROOT / "docs" / "api" / "contratos_api.md": api_contracts,
    ROOT / "docs" / "database" / "diagrama_entidad_relacion.md": er_diagram,
}


def main() -> int:
    check = "--check" in sys.argv[1:]
    stale = []
    for path, build in TARGETS.items():
        content = build()
        if check:
            if not path.exists() or path.read_text() != content:
                stale.append(path.relative_to(ROOT))
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content)
            print(f"{path.relative_to(ROOT)}  ({len(content.splitlines())} líneas)")
    if stale:
        print("Desactualizados: " + ", ".join(map(str, stale)))
        print("Ejecuta: python scripts/generate_docs.py")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
