import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


def isolated_settings(**overrides) -> Settings:
    # Ignore any developer .env so tests always run in key-free mock mode.
    return Settings(_env_file=None, **overrides)


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app(isolated_settings()))
