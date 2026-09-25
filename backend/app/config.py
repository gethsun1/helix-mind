from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings loaded only from HelixMind's own environment."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="HELIXMIND_",
        extra="ignore",
    )

    environment: str = "development"
    host: str = "127.0.0.1"
    port: int = 8401
    cors_origins: str = "https://helix-mind-green.vercel.app"
    database_url: str = "postgresql+psycopg:///helixmind"
    redis_url: str = "redis://127.0.0.1:6381/0"
    literature_max_results: int = 10
    literature_page_size: int = 20
    literature_timeout_seconds: float = 20.0
    literature_retries: int = 2
    ncbi_tool: str = "helixmind"
    ncbi_email: str | None = None
    ncbi_api_key: str | None = None
    auth_secret: str = ""
    auth_sync_secret: str = ""
    admin_email: str = "gethsun09@gmail.com"
    omegaclaw_timeout_seconds: int = 60
    artifact_root: str = "/opt/HelixMind/.artifacts"

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
