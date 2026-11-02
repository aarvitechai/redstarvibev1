"""Settings loaded from the environment. Secrets are never committed (see .env.example)."""
from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

INSECURE = "change-me"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "local"  # local | test | staging | production
    public_url: str = ""  # blank: derive from the request origin (local and tunnels)
    allowed_origins: str = "http://localhost:8080"

    database_url: str = "postgresql+asyncpg://rsv:rsv@localhost:5432/redstarvibe"
    database_replica_url: str = ""
    migrations_database_url: str = ""
    db_pool_size: int = 10
    db_max_overflow: int = 10
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = ""

    jwt_secret: str = INSECURE
    field_encryption_key: str = ""  # Fernet key for phone numbers and other sensitive PII
    access_token_minutes: int = 15
    refresh_token_days: int = 30
    cookie_secure: bool = False
    cookie_domain: str = ""

    breached_password_check: bool = True
    turnstile_secret: str = ""
    turnstile_site_key: str = ""

    google_client_id: str = ""
    google_client_secret: str = ""

    smtp_host: str = "localhost"
    smtp_port: int = 1025
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_tls: bool = False
    mail_from: str = "RedStarVibe <no-reply@redstarvibe.com>"

    s3_endpoint: str = "http://localhost:9000"  # R2: https://<account>.r2.cloudflarestorage.com
    s3_public_endpoint: str = ""  # used to sign browser uploads; blank: the request origin
    s3_access_key: str = "minioadmin"
    s3_secret_key: str = "minioadmin"
    s3_region: str = "auto"
    s3_raw_bucket: str = "rsv-raw"
    s3_public_bucket: str = "rsv-public"
    media_public_base: str = "/rsv-public"  # e.g. https://media.redstarvibe.com in production
    max_image_bytes: int = 20 * 1024 * 1024
    max_video_bytes: int = 512 * 1024 * 1024
    max_audio_bytes: int = 20 * 1024 * 1024
    max_voice_seconds: int = 300
    max_reel_seconds: int = 90
    max_post_video_seconds: int = 600
    clamav_host: str = ""
    clamav_port: int = 3310

    livekit_url: str = "ws://localhost:7880"
    livekit_api_key: str = "devkey"
    livekit_api_secret: str = "secret"  # noqa: S105

    vapid_public_key: str = ""
    vapid_private_key: str = ""
    vapid_subject: str = "mailto:admin@redstarvibe.com"

    anthropic_api_key: str = ""
    anthropic_model: str = "claude-opus-5-5"
    ai_daily_quota: int = 50
    embedding_provider: str = "hash"  # hash | bge
    clip_enabled: bool = False
    whisper_enabled: bool = False
    whisper_model: str = "small"
    embedding_dim: int = 512

    celebrity_threshold: int = 10_000
    feed_max_items: int = 800
    feed_ttl_seconds: int = 7 * 86400
    object_cache_seconds: int = 600

    allow_test_data: bool = False  # production only; always allowed in local and staging
    admin_ip_allowlist: str = ""  # comma separated, blank allows all (local only)
    sentry_dsn: str = ""
    otlp_endpoint: str = ""
    log_level: str = "INFO"

    mcp_issuer: str = ""

    @property
    def is_prod(self) -> bool:
        return self.app_env in {"staging", "production"}

    @property
    def origins(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]

    @model_validator(mode="after")
    def _refuse_insecure_production(self) -> "Settings":
        if self.is_prod:
            problems = []
            if self.jwt_secret == INSECURE or len(self.jwt_secret) < 32:
                problems.append("JWT_SECRET")
            if not self.field_encryption_key:
                problems.append("FIELD_ENCRYPTION_KEY")
            if not self.cookie_secure:
                problems.append("COOKIE_SECURE must be true")
            if self.s3_secret_key == "minioadmin":
                problems.append("S3_SECRET_KEY")
            if self.livekit_api_secret == "secret":  # noqa: S105
                problems.append("LIVEKIT_API_SECRET")
            if not self.admin_ip_allowlist:
                problems.append("ADMIN_IP_ALLOWLIST")
            if problems:
                raise ValueError(f"Insecure production settings: {', '.join(problems)}")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
