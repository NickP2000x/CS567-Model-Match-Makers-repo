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


def test_unknown_model_mode_is_rejected(monkeypatch):
    monkeypatch.setenv("MODEL_MODE", "live")
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


def test_real_mode_with_openai_model_requires_a_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(ValidationError, match="OPENAI_API_KEY"):
        isolated_settings(model_mode="real")
    settings = isolated_settings(model_mode="real", openai_api_key="sk-test-not-real")
    assert settings.model_mode == "real" and settings.large_model == "openai:gpt-4-turbo"


def test_real_mode_with_only_ollama_needs_no_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    settings = isolated_settings(model_mode="real", small_model="ollama:mixtral:8x7b",
                                 large_model="ollama:llama3.1:70b")
    assert settings.openai_api_key is None


def test_model_specs_are_validated():
    from app.config import parse_model_spec

    assert parse_model_spec("ollama:mixtral:8x7b") == ("ollama", "mixtral:8x7b")
    assert parse_model_spec(" openai:gpt-4-turbo ") == ("openai", "gpt-4-turbo")
    for bad in ("gpt-4", "anthropic:x", "openai:", ""):
        with pytest.raises(ValueError):
            parse_model_spec(bad)
    with pytest.raises(ValidationError):
        isolated_settings(model_mode="real", small_model="mixtral", openai_api_key="k")
    with pytest.raises(ValidationError):
        isolated_settings(agent_max_steps=0)
