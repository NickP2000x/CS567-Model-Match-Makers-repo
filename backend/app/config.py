from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent
PROVIDERS = ("openai", "ollama")


def parse_model_spec(value: str) -> tuple[str, str]:
    """`provider:model`, split on the first colon (Ollama tags may contain colons)."""
    provider, _, name = value.strip().partition(":")
    if provider not in PROVIDERS or not name.strip():
        raise ValueError(f"Model must look like 'openai:<model>' or 'ollama:<model>', got {value!r}.")
    return provider, name.strip()


class Settings(BaseSettings):
    """Server-only configuration. Every value has a safe default, so no .env is needed."""

    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env", env_file_encoding="utf-8",
        # Blank values (as in a copied .env.example) keep the safe defaults.
        env_ignore_empty=True, extra="ignore", protected_namespaces=(),
    )

    # "mock" uses the simulated agent replies. "real" calls the configured models and
    # fails at startup when misconfigured; it never falls back to mock silently.
    model_mode: Literal["mock", "real"] = "mock"
    # Paper §5.2 defaults (GPT-4 Turbo large, Mixtral 8x7B Instruct small). Substitutions
    # need researcher approval; record them in docs/backend/verification.md.
    small_model: str = "ollama:mixtral:8x7b"
    large_model: str = "openai:gpt-4-turbo"
    # Server-only secret for OpenAI models. SecretStr keeps it out of reprs and logs.
    openai_api_key: SecretStr | None = None
    openai_base_url: str = "https://api.openai.com/v1"
    ollama_base_url: str = "http://localhost:11434"
    model_timeout_seconds: float = 60.0
    # Most model calls that may request tools for one participant message (one final
    # answer call is added when the limit is reached).
    agent_max_steps: int = 4
    # Relative paths resolve against backend/.
    database_path: Path = Path("data/model-matchmakers.sqlite3")
    # Development-only sequence selection/reset (#31 draft). Off unless explicitly enabled.
    dev_controls: bool = False
    # Comma-separated browser origins allowed to call the API (local Vite dev and preview).
    cors_origins: str = ("http://127.0.0.1:5173,http://localhost:5173,"
                         "http://127.0.0.1:4173,http://localhost:4173")

    @model_validator(mode="after")
    def check_real_mode(self) -> "Settings":
        if self.model_mode == "real":
            providers = {parse_model_spec(self.small_model)[0], parse_model_spec(self.large_model)[0]}
            if "openai" in providers and not (self.openai_api_key and self.openai_api_key.get_secret_value().strip()):
                raise ValueError("MODEL_MODE=real with an openai model needs OPENAI_API_KEY in backend/.env.")
        if self.agent_max_steps < 1 or self.model_timeout_seconds <= 0:
            raise ValueError("AGENT_MAX_STEPS must be at least 1 and MODEL_TIMEOUT_SECONDS positive.")
        return self

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def resolved_database_path(self) -> Path:
        path = self.database_path.expanduser()
        return path if path.is_absolute() else BACKEND_DIR / path


@lru_cache
def get_settings() -> Settings:
    return Settings()
