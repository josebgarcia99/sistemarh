from __future__ import annotations

from collections.abc import Callable, Mapping

import pytest
from fastapi.testclient import TestClient

from app.core.config.settings import Environment, Settings
from app.main import create_app
from app.modules.system.application.health import HealthCheck


@pytest.fixture
def settings() -> Settings:
    return Settings(environment=Environment.TEST)


@pytest.fixture
def make_client(settings: Settings) -> Callable[..., TestClient]:
    def _make(health_checks: Mapping[str, HealthCheck] | None = None) -> TestClient:
        checks = health_checks if health_checks is not None else {"componente": lambda: True}
        app = create_app(settings=settings, health_checks=checks)
        return TestClient(app)

    return _make


@pytest.fixture
def client(make_client: Callable[..., TestClient]) -> TestClient:
    return make_client()


# --- Soporte para pruebas con usuarios y sesiones ------------------------------

from dataclasses import dataclass, field  # noqa: E402
from datetime import UTC, datetime, timedelta  # noqa: E402

from app.core.security.passwords import Argon2Hasher  # noqa: E402
from app.modules.authentication.api.dependencies import CSRF_HEADER  # noqa: E402
from app.tests.support.memory_backend import MemoryBackend  # noqa: E402

ADMIN_EMAIL = "admin@ejemplo.test"
ADMIN_PASSWORD = "Clave-Maestra-2026"
RECRUITER_EMAIL = "reclutadora@ejemplo.test"
RECRUITER_PASSWORD = "Clave-Reclutadora-2026"


@dataclass
class FakeClock:
    now: datetime = field(default_factory=lambda: datetime(2026, 11, 10, 15, 0, tzinfo=UTC))

    def __call__(self) -> datetime:
        return self.now

    def advance(self, **delta: float) -> None:
        self.now += timedelta(**delta)


@pytest.fixture(scope="session")
def hasher() -> Argon2Hasher:
    # Parámetros mínimos: las pruebas no necesitan el costo real de Argon2.
    return Argon2Hasher(time_cost=1, memory_cost=8, parallelism=1)


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


@pytest.fixture
def backend() -> MemoryBackend:
    return MemoryBackend()


@pytest.fixture
def app_with_data(settings, backend, hasher, clock):
    return create_app(
        settings=settings,
        health_checks={"componente": lambda: True},
        backend=backend,
        hasher=hasher,
        clock=clock,
    )


@pytest.fixture
def seeded(app_with_data):
    """Aplicación con un administrador y una reclutadora ya creados."""
    context = app_with_data.state.context
    with context.require_backend().transaction() as repos:
        service = context.user_service(repos)
        admin = service.create_master_user(
            email=ADMIN_EMAIL, full_name="Administradora de Prueba", password=ADMIN_PASSWORD
        )
        from app.modules.users.domain.models import Role

        recruiter = service.create_user(
            admin,
            email=RECRUITER_EMAIL,
            full_name="Reclutadora de Prueba",
            password=RECRUITER_PASSWORD,
            role=Role.RECLUTADOR,
        )
    return app_with_data, admin, recruiter


def new_client(app) -> TestClient:
    # HTTPS: la cookie de sesión es "Secure" y no viajaría por HTTP.
    return TestClient(app, base_url="https://testserver")


def login(app, email: str, password: str) -> TestClient:
    """Cliente con sesión iniciada y la cabecera CSRF ya configurada."""
    client = new_client(app)
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    client.headers[CSRF_HEADER] = response.json()["csrf_token"]
    return client


@pytest.fixture
def admin_client(seeded) -> TestClient:
    return login(seeded[0], ADMIN_EMAIL, ADMIN_PASSWORD)


@pytest.fixture
def recruiter_client(seeded) -> TestClient:
    return login(seeded[0], RECRUITER_EMAIL, RECRUITER_PASSWORD)
