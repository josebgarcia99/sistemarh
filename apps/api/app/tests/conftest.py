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
