"""Tests for the CLI module."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from flickr_autotagger.cli import cli


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


class TestCliVersion:
    """Test version flag."""

    def test_version(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, ["--version"])
        assert result.exit_code == 0
        assert "0.1.0" in result.output


class TestCliStatus:
    """Test status command."""

    @patch("flickr_autotagger.cli.get_settings")
    def test_status(self, mock_settings: MagicMock, runner: CliRunner, tmp_path: Path) -> None:
        from flickr_autotagger.config import Settings

        settings = Settings(
            FLICKR_API_KEY="k",
            FLICKR_API_SECRET="s",
            DATA_DIR=tmp_path / "data",
        )
        mock_settings.return_value = settings

        result = runner.invoke(cli, ["status"])
        assert result.exit_code == 0
        assert "flickr-autotagger Status" in result.output
        assert "Total photos: 0" in result.output


class TestCliReview:
    """Test review command."""

    @patch("flickr_autotagger.cli.get_settings")
    def test_review_no_photos(
        self, mock_settings: MagicMock, runner: CliRunner, tmp_path: Path
    ) -> None:
        from flickr_autotagger.config import Settings

        settings = Settings(
            FLICKR_API_KEY="k",
            FLICKR_API_SECRET="s",
            DATA_DIR=tmp_path / "data",
        )
        mock_settings.return_value = settings

        result = runner.invoke(cli, ["review"])
        assert result.exit_code == 0
        assert "No tagged photos" in result.output

    @patch("flickr_autotagger.cli.get_settings")
    def test_review_auto_approve(
        self, mock_settings: MagicMock, runner: CliRunner, tmp_path: Path
    ) -> None:
        from flickr_autotagger.config import Settings
        from flickr_autotagger.db import StateDB

        settings = Settings(
            FLICKR_API_KEY="k",
            FLICKR_API_SECRET="s",
            DATA_DIR=tmp_path / "data",
        )
        mock_settings.return_value = settings

        # Set up DB with a tagged photo
        db = StateDB(settings.db_path)
        db.init_db()
        photo_id = db.upsert_photo(
            {
                "flickr_id": "111",
                "title": "Test",
                "description": "",
                "original_url": "",
                "farm": "1",
                "server": "1",
                "secret": "a",
                "date_taken": "",
                "date_uploaded": "",
                "last_synced": "",
            }
        )
        db.add_predicted_tags(photo_id, [("sunset", 0.9)])

        result = runner.invoke(cli, ["review", "--auto-approve"])
        assert result.exit_code == 0
        assert "Reviewed" in result.output


class TestCliExport:
    """Test export command."""

    @patch("flickr_autotagger.cli.get_settings")
    def test_export_json(self, mock_settings: MagicMock, runner: CliRunner, tmp_path: Path) -> None:
        from flickr_autotagger.config import Settings

        settings = Settings(
            FLICKR_API_KEY="k",
            FLICKR_API_SECRET="s",
            DATA_DIR=tmp_path / "data",
        )
        mock_settings.return_value = settings

        out_file = tmp_path / "out.json"
        result = runner.invoke(cli, ["export", "--format", "json", "-o", str(out_file)])
        assert result.exit_code == 0
        assert "Exported" in result.output
        assert out_file.exists()

    @patch("flickr_autotagger.cli.get_settings")
    def test_export_csv(self, mock_settings: MagicMock, runner: CliRunner, tmp_path: Path) -> None:
        from flickr_autotagger.config import Settings

        settings = Settings(
            FLICKR_API_KEY="k",
            FLICKR_API_SECRET="s",
            DATA_DIR=tmp_path / "data",
        )
        mock_settings.return_value = settings

        out_file = tmp_path / "out.csv"
        result = runner.invoke(cli, ["export", "--format", "csv", "-o", str(out_file)])
        assert result.exit_code == 0
        assert "Exported" in result.output

    @patch("flickr_autotagger.cli.get_settings")
    def test_export_xmp(self, mock_settings: MagicMock, runner: CliRunner, tmp_path: Path) -> None:
        from flickr_autotagger.config import Settings

        settings = Settings(
            FLICKR_API_KEY="k",
            FLICKR_API_SECRET="s",
            DATA_DIR=tmp_path / "data",
        )
        mock_settings.return_value = settings

        out_dir = tmp_path / "xmp_out"
        result = runner.invoke(cli, ["export", "--format", "xmp", "-o", str(out_dir)])
        assert result.exit_code == 0
        assert "XMP sidecar" in result.output


class TestCliStatusWithData:
    """Test status command with actual data."""

    @patch("flickr_autotagger.cli.get_settings")
    def test_status_with_photos(
        self, mock_settings: MagicMock, runner: CliRunner, tmp_path: Path
    ) -> None:
        from flickr_autotagger.config import Settings
        from flickr_autotagger.db import StateDB

        settings = Settings(
            FLICKR_API_KEY="k",
            FLICKR_API_SECRET="s",
            DATA_DIR=tmp_path / "data",
        )
        mock_settings.return_value = settings

        db = StateDB(settings.db_path)
        db.init_db()
        db.upsert_photo(
            {
                "flickr_id": "111",
                "title": "Test",
                "description": "",
                "original_url": "",
                "farm": "1",
                "server": "1",
                "secret": "a",
                "date_taken": "",
                "date_uploaded": "",
                "last_synced": "",
            }
        )

        result = runner.invoke(cli, ["status"])
        assert result.exit_code == 0
        assert "Total photos: 1" in result.output
        assert "Downloads" in result.output


class TestCliInit:
    """Test _init helper."""

    @patch("flickr_autotagger.cli.get_settings")
    def test_init_returns_settings_and_db(self, mock_settings: MagicMock, tmp_path: Path) -> None:
        from flickr_autotagger.cli import _init
        from flickr_autotagger.config import Settings

        settings = Settings(
            FLICKR_API_KEY="k",
            FLICKR_API_SECRET="s",
            DATA_DIR=tmp_path / "data",
        )
        mock_settings.return_value = settings

        s, db = _init()
        assert s == settings
        assert db is not None
