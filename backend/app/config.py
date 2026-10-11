from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """Server-only configuration. Every value has a safe default, so no .env is needed."""

    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env", env_file_encoding="utf-8",
        # Blank values (as in a copied .env.example) keep the safe defaults.
        env_ignore_empty=True, extra="ignore", protected_namespaces=(),
    )

    # Mock is the only mode until the real model adapters in #35. Real mode will be
    # an explicit opt-in that fails clearly when misconfigured, never a silent switch.
    model_mode: Literal["mock"] = "mock"
    # Server-only secret for optional real calls (#35). SecretStr keeps it out of reprs.
    openai_api_key: SecretStr | None = None
    ollama_base_url: str = "http://localhost:11434"
    # Relative paths resolve against backend/. The catalog/session database arrives in #33/#34.
    database_path: Path = Path("data/model-matchmakers.sqlite3")
    # Development-only sequence selection/reset (#31 draft). Off unless explicitly enabled.
    dev_controls: bool = False
    # Comma-separated browser origins allowed to call the API (local Vite dev and preview).
    cors_origins: str = ("http://127.0.0.1:5173,http://localhost:5173,"
                         "http://127.0.0.1:4173,http://localhost:4173")

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
