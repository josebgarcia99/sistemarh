"""Comprobaciones del paquete que se entrega a Sistemas (Fase 8).

No prueban funcionalidad: evitan que la documentación, las dependencias y los
archivos de despliegue se queden atrás respecto del código.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

from app.core.schema_version import SCHEMA_VERSION

REPO_ROOT = Path(__file__).resolve().parents[4]

# Sección 36 del documento maestro.
REQUIRED_DOCS = [
    "README.md",
    "docs/architecture/arquitectura_general.md",
    "docs/architecture/estructura_modular.md",
    "docs/architecture/decisiones_arquitectonicas.md",
    "docs/requirements/requisitos_funcionales.md",
    "docs/requirements/reglas_negocio.md",
    "docs/permissions/matriz_permisos.md",
    "docs/database/modelo_relacional.md",
    "docs/database/diccionario_datos.md",
    "docs/security/modelo_seguridad.md",
    "docs/security/modelo_amenazas.md",
    "docs/api/contratos_api.md",
    "docs/deployment/instalacion_local.md",
    "docs/deployment/almacenamiento_documental.md",
    "docs/deployment/respaldos_y_restauracion.md",
    "docs/testing/plan_pruebas.md",
    "docs/manuals/manual_administrador.md",
    "docs/manuals/manual_reclutador.md",
    "docs/roadmap.md",
    "docs/estado_proyecto.md",
]
# Secciones que el documento maestro exige en el estado del proyecto.
STATUS_SECTIONS = [
    "Fase actual",
    "Funcionalidades terminadas",
    "Funcionalidades pendientes",
    "Pruebas ejecutadas",
    "Problemas conocidos",
    "Cambios recientes",
    "Próximos pasos",
    "Decisiones pendientes",
]


def _pins(path: Path) -> dict[str, str]:
    pins = {}
    for line in path.read_text().splitlines():
        if line and not line.startswith("#"):
            name, version = line.split("==")
            pins[name.lower().replace("_", "-")] = version
    return pins


def test_existe_toda_la_documentacion_obligatoria():
    missing = [name for name in REQUIRED_DOCS if not (REPO_ROOT / name).is_file()]
    assert not missing, f"Faltan: {missing}"
    status = (REPO_ROOT / "docs" / "estado_proyecto.md").read_text()
    assert not [section for section in STATUS_SECTIONS if f"## {section}" not in status]
    for name in REQUIRED_DOCS:
        assert len((REPO_ROOT / name).read_text()) > 500, f"{name} está casi vacío"


def test_la_documentacion_generada_esta_al_dia():
    """Contratos de la API y diagrama entidad-relación salen del código."""
    # Argumentos fijos, sin entrada externa: ejecuta un script del propio repositorio.
    result = subprocess.run(  # noqa: S603
        [sys.executable, str(REPO_ROOT / "scripts" / "generate_docs.py"), "--check"],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr[-500:]


def test_las_dependencias_de_produccion_son_un_subconjunto_fijo_de_las_de_desarrollo():
    api = REPO_ROOT / "apps" / "api"
    everything, production = _pins(api / "requirements.lock"), _pins(api / "requirements-prod.lock")
    assert production and set(production) < set(everything)
    assert all(everything[name] == version for name, version in production.items())
    # Las herramientas de desarrollo no entran en la imagen de producción.
    assert not {"pytest", "ruff", "import-linter", "sqlglot"} & set(production)
    # Y lo que la aplicación declara como dependencia sí está fijado.
    declared = re.findall(r'^    "([A-Za-z0-9_.\-]+)', (api / "pyproject.toml").read_text(), re.M)
    runtime = [name.lower().replace("_", "-") for name in declared]
    missing = [name for name in runtime if name not in everything]
    assert not missing, missing
    dockerfile = (REPO_ROOT / "infrastructure" / "docker" / "python.Dockerfile").read_text()
    assert "requirements-prod.lock" in dockerfile and "--no-access-log" in dockerfile


def test_los_scripts_para_sistemas_corresponden_a_la_version_actual():
    folder = REPO_ROOT / "database" / "sqlserver"
    previous = f"{int(SCHEMA_VERSION) - 1:04d}"
    for name in (
        "instalacion_completa.sql",
        f"actualizacion_{previous}_a_{SCHEMA_VERSION}.sql",
        "permisos_usuario_aplicacion.sql",
        "validaciones_integridad.sql",
        "reversion_completa.sql",
    ):
        assert (folder / name).is_file(), name
    assert f"'{SCHEMA_VERSION}'" in (folder / "instalacion_completa.sql").read_text()
    guide = (REPO_ROOT / "docs" / "deployment" / "instalacion_local.md").read_text()
    assert f"actualizacion_{previous}_a_{SCHEMA_VERSION}.sql" in guide
    dictionary = (REPO_ROOT / "docs" / "database" / "diccionario_datos.md").read_text()
    assert f"versión de esquema `{SCHEMA_VERSION}`" in dictionary


def test_el_despliegue_de_produccion_no_publica_servicios_internos_ni_trae_secretos():
    yaml = pytest.importorskip("yaml")
    infrastructure = REPO_ROOT / "infrastructure"
    compose = yaml.safe_load((infrastructure / "docker" / "docker-compose.prod.yml").read_text())
    services = compose["services"]
    assert set(services) == {"proxy", "api", "worker", "web", "redis", "clamav"}
    # Solo el proxy publica puertos; SQL Server no forma parte del despliegue.
    assert [name for name, service in services.items() if service.get("ports")] == ["proxy"]
    for name in ("api", "worker"):
        mounts = {volume["target"]: volume for volume in services[name]["volumes"]}
        assert mounts["/run/secrets/clave_maestra"]["read_only"] is True
        assert "/srv/reclutamiento/storage" in mounts
    # Los ejemplos de variables no contienen valores reales.
    for example in sorted((infrastructure / "env").glob("*.env.example")):
        text = example.read_text()
        assert "<CONTRASENA>" in text and "RECLU_AI_ALLOW_REAL_DOCUMENTS=false" in text
        assert not re.search(r"sk-[A-Za-z0-9]{8,}", text)
    ignored = (REPO_ROOT / ".gitignore").read_text()
    assert "infrastructure/env/*.env" in ignored and ".env" in ignored
    proxy = (infrastructure / "nginx" / "reclutamiento.conf").read_text()
    assert "return 301 https://" in proxy and "client_max_body_size 25m" in proxy
