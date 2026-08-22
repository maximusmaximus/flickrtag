"""Pytest fixtures for flickr-autotagger tests."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from flickr_autotagger.config import Settings
from flickr_autotagger.db import StateDB


@pytest.fixture
def tmp_settings(tmp_path: Path) -> Settings:
    """Create a Settings instance pointing at a temp directory."""
    return Settings(
        FLICKR_API_KEY="test_key_123",
        FLICKR_API_SECRET="test_secret_456",
        DATA_DIR=tmp_path / "data",
    )


@pytest.fixture
def tmp_db(tmp_path: Path) -> StateDB:
    """Create an initialized StateDB in a temp directory."""
    db_path = tmp_path / "test_state.db"
    db = StateDB(db_path)
    db.init_db()
    return db


@pytest.fixture
def sample_photo_data() -> dict[str, Any]:
    """Return a sample photo data dict matching the photos table schema."""
    return {
        "flickr_id": "12345678901",
        "title": "Beautiful Sunset",
        "description": "A gorgeous sunset over the ocean",
        "original_url": "https://farm1.staticflickr.com/123/12345678901_abcdef_o.jpg",
        "farm": "1",
        "server": "123",
        "secret": "abcdef",
        "date_taken": "2026-01-15 18:30:00",
        "date_uploaded": "1737000000",
        "last_synced": "2026-08-22T12:00:00+00:00",
    }
