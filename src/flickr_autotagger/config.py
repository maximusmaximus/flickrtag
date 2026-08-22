"""Configuration management using pydantic-settings."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings, loaded from .env file or environment variables."""

    FLICKR_API_KEY: str
    FLICKR_API_SECRET: str
    FLICKR_USER_ID: str | None = None

    DATA_DIR: Path = Path("~/.flickr-autotagger").expanduser()

    CLIP_MODEL: str = "clip-vit-base-patch32"
    TAG_THRESHOLD: float = 0.25
    MAX_TAGS_PER_PHOTO: int = 15
    DOWNLOAD_CONCURRENCY: int = 4
    TAG_MERGE_STRATEGY: Literal["merge", "replace"] = "merge"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @property
    def image_dir(self) -> Path:
        """Get the directory where original images are stored."""
        path = self.DATA_DIR / "images"
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def db_path(self) -> Path:
        """Get the path to the SQLite database."""
        self.DATA_DIR.mkdir(parents=True, exist_ok=True)
        return self.DATA_DIR / "state.db"


@lru_cache
def get_settings() -> Settings:
    """Return a cached instance of the settings."""
    return Settings()
