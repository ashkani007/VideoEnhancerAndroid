"""Runtime configuration. Every secret comes from the environment; nothing is hard-coded."""
from __future__ import annotations

from functools import lru_cache

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="VRV_", env_file=".env", extra="ignore")

    environment: str = "development"
    # Comma-separated client API keys issued by the operator. Required; there is no default key.
    api_keys: SecretStr = SecretStr("")
    token_secret: SecretStr = SecretStr("")
    token_ttl_seconds: int = 900

    database_url: str = "sqlite:///./vrvision.db"
    redis_url: str = "redis://localhost:6379/0"
    # "local" (filesystem, development/tests) or "s3" (S3-compatible, e.g. MinIO, AWS, R2).
    storage_backend: str = "local"
    local_storage_dir: str = "./data/objects"
    upload_staging_dir: str = "./data/uploads"
    work_dir: str = "./data/work"
    s3_endpoint_url: str | None = None
    s3_bucket: str = "vrvision"
    s3_region: str = "us-east-1"
    s3_access_key_id: SecretStr | None = None
    s3_secret_access_key: SecretStr | None = None

    # Quotas and limits per job.
    max_upload_bytes: int = 4 * 1024**3
    max_duration_ms: int = 30 * 60 * 1000
    max_source_pixels: int = 8192 * 4320
    max_output_width: int = 8192
    max_output_height: int = 8192
    max_active_jobs_per_client: int = 2
    preview_duration_ms: int = 10_000
    upload_chunk_bytes: int = 8 * 1024 * 1024
    allowed_video_codecs: str = "h264,hevc,vp9,av1,mpeg4"
    allowed_containers: str = "mov,mp4,m4a,3gp,3g2,mj2,matroska,webm"

    # Retention: sources and outputs are deleted this long after the job finishes (or at
    # once via DELETE /v1/jobs/{id}); unfinished uploads expire after upload_expiry_hours.
    retention_hours: int = 24
    upload_expiry_hours: int = 6

    # Super-resolution engine for the worker: "onnx" (CPU/GPU via onnxruntime) or "torch".
    sr_engine: str = "onnx"
    model_dir: str = "./models"
    tile: int = 192
    tile_overlap: int = 16
    encode_preset: str = "slow"
    encode_crf: int = 18
    encode_codec: str = "libx265"

    # Optional cost estimate shown to users; None means the operator publishes no price.
    price_per_gpu_minute: float | None = None
    currency: str | None = None
    # Measured throughput of this deployment's worker (source megapixels per second).
    # Used for quotes; set it from your own benchmark (tools/benchmark in backend/README).
    throughput_mp_per_s: float = 0.5

    require_https: bool = Field(default=False, description="Reject plain HTTP requests (behind a TLS proxy use X-Forwarded-Proto).")

    def api_key_list(self) -> list[str]:
        return [k.strip() for k in self.api_keys.get_secret_value().split(",") if k.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
