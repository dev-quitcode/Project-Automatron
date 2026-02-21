"""Application configuration via Pydantic Settings."""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Global application settings loaded from environment variables."""

    # --- LLM Providers ---
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    google_api_key: str = ""

    # --- Architect ---
    architect_model: str = "claude-opus-4-20250918"
    architect_prompt_version: str = "v1"

    # --- Builder ---
    builder_model: str = "anthropic/claude-sonnet-4-20250514"
    builder_cline_timeout: int = 300

    # --- Docker ---
    golden_image: str = "automatron/golden:latest"
    workspace_base_path: str = "/var/automatron/workspaces"
    port_range_start: int = 7000
    port_range_end: int = 7999

    # --- Database ---
    sqlite_db_path: str = "./data/automatron.db"
    checkpoint_db_path: str = "./data/checkpoints.db"

    # --- Server ---
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = False

    @property
    def sqlite_db_dir(self) -> Path:
        path = Path(self.sqlite_db_path).parent
        path.mkdir(parents=True, exist_ok=True)
        return path

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
