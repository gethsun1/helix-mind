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

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
