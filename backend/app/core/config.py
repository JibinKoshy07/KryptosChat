"""Application configuration via environment variables.

All secrets must be provided through environment variables / .env file.
NEVER hardcode secrets in source code.
"""
from functools import lru_cache
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- General ---
    app_name: str = "Krypte"
    debug: bool = False
    api_v1_prefix: str = "/api/v1"
    public_origin: str = "http://localhost"
    use_https: bool = False
    log_level: str = "INFO"

    # --- Cookies / auth ---
    cookie_name: str = "krypte_refresh"
    cookie_secure: bool = False
    cookie_max_age_seconds: int = 60 * 60 * 24 * 7

    # --- Secrets (from environment) ---
    jwt_secret: str = Field(...)
    session_secret: str = Field(...)
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7

    # Message encryption keys (base64, 32 bytes each)
    message_encryption_key_base64: str = Field(...)
    message_master_key_base64: str = Field(...)

    # Media encryption keys (base64, 32 bytes each)
    media_kdf_master_key_base64: str = Field(...)
    media_kdf_auth_key_base64: str = Field(...)

    # --- Database ---
    database_url: str = Field(default="postgresql+asyncpg://postgres:postgres@localhost:5432/krypte")

    # --- Redis ---
    redis_url: str = Field(default="redis://localhost:6379/0")

    # --- CORS ---
    cors_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:3000"]
    )

    # --- Rate limiting / security ---
    login_max_attempts: int = 5
    login_lockout_minutes: int = 15

    # --- Media ---
    max_upload_size_bytes: int = 100 * 1024 * 1024  # 100 MB
    allowed_media_types: list[str] = Field(
        default_factory=lambda: [
            "image/jpeg", "image/png", "image/webp", "image/gif",
            "video/mp4", "video/webm", "video/quicktime",
            "application/pdf", "text/plain", "application/zip",
        ]
    )
    media_storage_backend: str = "local"  # local | s3
    media_local_path: str = "/data/media"
    media_chunk_size: int = 1024 * 1024  # 1 MiB streaming chunks
    # S3 / MinIO (only used if media_storage_backend == "s3")
    s3_endpoint_url: Optional[str] = None
    s3_bucket: Optional[str] = None
    s3_access_key: Optional[str] = None
    s3_secret_key: Optional[str] = None

    # --- Initial admin (seed) ---
    admin_username: Optional[str] = None
    admin_password: Optional[str] = None
    admin_display_name: Optional[str] = None

    # --- Observability ---
    otlp_exporter_endpoint: Optional[str] = None

    @field_validator("allowed_media_types", mode="before")
    @classmethod
    def _split_media_types(cls, v):
        if isinstance(v, str):
            return [item.strip() for item in v.split(",") if item.strip()]
        return v

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_cors(cls, v):
        if isinstance(v, str):
            return [item.strip() for item in v.split(",") if item.strip()]
        return v


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
