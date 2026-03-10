"""Application configuration via Pydantic Settings."""

from __future__ import annotations

from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Global application settings loaded from environment variables."""

    # --- LLM Providers ---
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    google_api_key: str = ""
    github_token: str = ""
    github_owner: str = ""
    github_owner_type: str = "user"
    github_api_url: str = "https://api.github.com"
    github_repo_visibility: str = "private"
    github_environment_name: str = "production"
    github_actions_ci_workflow_name: str = "CI"
    github_actions_deploy_workflow_name: str = "Deploy"
    git_author_name: str = "Automatron Bot"
    git_author_email: str = "automatron@example.local"

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

    # --- Deploy ---
    deploy_ssh_key_path: str = ""
    deploy_ssh_options: str = ""

    # --- Database ---
    sqlite_db_path: str = "./data/automatron.db"
    checkpoint_db_path: str = "./data/checkpoints.db"

    # --- Server ---
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = False

    @field_validator("debug", mode="before")
    @classmethod
    def _parse_debug_flag(cls, value: object) -> object:
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"1", "true", "yes", "on", "debug", "dev", "development"}:
                return True
            if normalized in {"0", "false", "no", "off", "release", "prod", "production"}:
                return False
        return value

    @property
    def sqlite_db_dir(self) -> Path:
        path = Path(self.sqlite_db_path).parent
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def workspace_base_dir(self) -> Path:
        path = Path(self.workspace_base_path)
        path.mkdir(parents=True, exist_ok=True)
        return path

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
