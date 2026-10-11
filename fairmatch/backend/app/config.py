"""Process-level settings (secrets, URLs). Product tunables live in services/app_config.py."""
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

_DEV_SECRET = "dev-only-insecure-secret-change-me-0123456789"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="FM_", extra="ignore")

    env: str = "development"  # development | test | production
    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/fairmatch"
    redis_url: str | None = None

    jwt_secret: str = _DEV_SECRET
    access_token_minutes: int = 15
    refresh_token_days: int = 30

    # Media
    storage_backend: str = "local"  # local | s3
    local_media_dir: str = "./media"
    media_url_secret: str = _DEV_SECRET
    public_base_url: str = "http://localhost:8000"
    s3_bucket: str | None = None
    s3_endpoint_url: str | None = None

    # AI
    ai_provider: str = "mock"  # mock | anthropic
    anthropic_model: str = "claude-opus-5-5"
    ai_effort: str = "low"

    # Billing
    billing_mode: str = "dev"  # dev | google_play
    google_play_package_name: str = "app.fairmatch"
    google_service_account_file: str | None = None
    rtdn_shared_secret: str | None = None

    # Push
    push_provider: str = "log"  # log | fcm
    fcm_project_id: str | None = None

    cors_origins: list[str] = Field(default_factory=lambda: ["*"])
    run_background_jobs: bool = True

    @property
    def is_production(self) -> bool:
        return self.env == "production"

    def validate_for_production(self) -> None:
        if not self.is_production:
            return
        problems = []
        if self.jwt_secret == _DEV_SECRET or len(self.jwt_secret) < 32:
            problems.append("FM_JWT_SECRET must be set to a strong secret")
        if self.media_url_secret == _DEV_SECRET:
            problems.append("FM_MEDIA_URL_SECRET must be set")
        if self.billing_mode == "dev":
            problems.append("FM_BILLING_MODE=dev is not allowed in production")
        if "*" in self.cors_origins:
            problems.append("FM_CORS_ORIGINS must not be '*' in production")
        if problems:
            raise RuntimeError("Unsafe production configuration: " + "; ".join(problems))


@lru_cache
def get_settings() -> Settings:
    return Settings()
