"""Tests for the config module."""

from __future__ import annotations

from pathlib import Path

from flickr_autotagger.config import Settings


class TestSettings:
    """Test Settings model."""

    def test_settings_with_required_fields(self, tmp_path: Path) -> None:
        settings = Settings(
            FLICKR_API_KEY="test_key",
            FLICKR_API_SECRET="test_secret",
            DATA_DIR=tmp_path / "data",
        )
        assert settings.FLICKR_API_KEY == "test_key"
        assert settings.FLICKR_API_SECRET == "test_secret"
        assert settings.FLICKR_USER_ID is None

    def test_settings_defaults(self, tmp_path: Path) -> None:
        settings = Settings(
            FLICKR_API_KEY="k",
            FLICKR_API_SECRET="s",
            DATA_DIR=tmp_path / "data",
        )
        assert settings.TAG_THRESHOLD == 0.25
        assert settings.MAX_TAGS_PER_PHOTO == 15
        assert settings.DOWNLOAD_CONCURRENCY == 4
        assert settings.TAG_MERGE_STRATEGY == "merge"

    def test_image_dir_property(self, tmp_path: Path) -> None:
        settings = Settings(
            FLICKR_API_KEY="k",
            FLICKR_API_SECRET="s",
            DATA_DIR=tmp_path / "data",
        )
        img_dir = settings.image_dir
        assert img_dir == tmp_path / "data" / "images"
        assert img_dir.exists()

    def test_db_path_property(self, tmp_path: Path) -> None:
        settings = Settings(
            FLICKR_API_KEY="k",
            FLICKR_API_SECRET="s",
            DATA_DIR=tmp_path / "data",
        )
        db_path = settings.db_path
        assert db_path == tmp_path / "data" / "state.db"
        assert db_path.parent.exists()

    def test_settings_with_user_id(self, tmp_path: Path) -> None:
        settings = Settings(
            FLICKR_API_KEY="k",
            FLICKR_API_SECRET="s",
            FLICKR_USER_ID="12345@N08",
            DATA_DIR=tmp_path / "data",
        )
        assert settings.FLICKR_USER_ID == "12345@N08"
