"""Denegación por omisión: ninguna ruta responde sin sesión salvo las permitidas."""

from __future__ import annotations

import re

from app.tests.conftest import new_client

# Únicas rutas accesibles sin sesión. Añadir una aquí debe ser una decisión consciente.
PUBLIC_ROUTES = {
    ("GET", "/api/v1/health/live"),
    ("GET", "/api/v1/health/ready"),
    ("POST", "/api/v1/auth/login"),
}


def _declared_routes(app) -> set[tuple[str, str]]:
    # El contrato OpenAPI lista todas las rutas de la API, también las incluidas
    # desde los módulos.
    return {
        (method.upper(), path)
        for path, operations in app.openapi()["paths"].items()
        for method in operations
    }


def _concrete(path: str) -> str:
    return re.sub(r"\{[^}]+\}", "00000000-0000-0000-0000-000000000000", path)


def test_todas_las_rutas_exigen_sesion_salvo_las_publicas(seeded):
    app = seeded[0]
    client = new_client(app)
    protected = _declared_routes(app) - PUBLIC_ROUTES
    assert len(protected) >= 9
    for method, path in sorted(protected):
        response = client.request(method, _concrete(path), json={})
        assert response.status_code == 401, f"{method} {path} respondió sin sesión"


def test_las_rutas_publicas_declaradas_existen(seeded):
    assert PUBLIC_ROUTES <= _declared_routes(seeded[0])
