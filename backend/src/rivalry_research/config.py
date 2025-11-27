"""Configuration management using Pydantic Settings."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings from environment or .env file."""

    google_api_key: str
    rivalry_model: str = "google-gla:gemini-2.5-flash"
    
    # Storage paths
    data_dir: Path = Path("data")
    sources_db_path: Path = Path("data/sources.db")
    raw_sources_dir: Path = Path("data/raw_sources")
    analyses_dir: Path = Path("data/analyses")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()

