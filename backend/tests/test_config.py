import pytest
from pydantic import ValidationError

from app.config import BACKEND_DIR
from tests.conftest import isolated_settings


def test_defaults_need_no_env_file_or_keys(monkeypatch):
    for name in ("MODEL_MODE", "OPENAI_API_KEY", "OLLAMA_BASE_URL", "DATABASE_PATH", "DEV_CONTROLS"):
        monkeypatch.delenv(name, raising=False)
    settings = isolated_settings()
    assert settings.model_mode == "mock"
    assert settings.openai_api_key is None
    assert settings.ollama_base_url == "http://localhost:11434"
    assert settings.resolved_database_path == BACKEND_DIR / "data" / "model-matchmakers.sqlite3"
    assert settings.dev_controls is False


def test_api_key_is_never_shown_in_settings_output(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-not-real")
    settings = isolated_settings()
    assert settings.openai_api_key.get_secret_value() == "sk-test-not-real"
    assert "sk-test-not-real" not in repr(settings)
    assert "sk-test-not-real" not in str(settings.model_dump())


def test_real_mode_is_rejected_until_model_adapters_exist(monkeypatch):
    monkeypatch.setenv("MODEL_MODE", "real")
    with pytest.raises(ValidationError):
        isolated_settings()


def test_health_never_includes_the_api_key(monkeypatch):
    from fastapi.testclient import TestClient
    from app.main import create_app

    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-not-real")
    response = TestClient(create_app(isolated_settings())).get("/api/health")
    assert "sk-test-not-real" not in response.text


def test_absolute_database_path_is_kept(tmp_path):
    path = tmp_path / "study.sqlite3"
    assert isolated_settings(database_path=path).resolved_database_path == path


def test_copied_env_example_keeps_mock_defaults(monkeypatch):
    for name in ("MODEL_MODE", "OPENAI_API_KEY", "OLLAMA_BASE_URL", "DATABASE_PATH", "DEV_CONTROLS"):
        monkeypatch.delenv(name, raising=False)
    from app.config import Settings

    settings = Settings(_env_file=BACKEND_DIR / ".env.example")
    assert settings.model_mode == "mock"
    assert settings.openai_api_key is None
    assert settings.dev_controls is False
    assert settings.resolved_database_path == BACKEND_DIR / "data" / "model-matchmakers.sqlite3"
