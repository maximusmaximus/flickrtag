"""Tests for the StateDB module."""

from __future__ import annotations

from typing import Any

import pytest

from flickr_autotagger.db import StateDB


class TestStateDB:
    """Tests for StateDB CRUD operations."""

    def test_init_db_creates_tables(self, tmp_db: StateDB) -> None:
        """init_db should create photos, existing_tags, and predicted_tags tables."""
        conn = tmp_db.connect()
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
        table_names = {row["name"] for row in tables}
        assert "photos" in table_names
        assert "existing_tags" in table_names
        assert "predicted_tags" in table_names

    def test_upsert_photo_insert(
        self, tmp_db: StateDB, sample_photo_data: dict[str, Any]
    ) -> None:
        """upsert_photo should insert a new photo and return its ID."""
        photo_id = tmp_db.upsert_photo(sample_photo_data)
        assert photo_id >= 1

        photo = tmp_db.get_photo_by_flickr_id(sample_photo_data["flickr_id"])
        assert photo is not None
        assert photo["title"] == "Beautiful Sunset"
        assert photo["download_status"] == "pending"

    def test_upsert_photo_update(
        self, tmp_db: StateDB, sample_photo_data: dict[str, Any]
    ) -> None:
        """upsert_photo should update an existing photo on conflict."""
        tmp_db.upsert_photo(sample_photo_data)

        updated = {**sample_photo_data, "title": "Updated Title"}
        tmp_db.upsert_photo(updated)

        photo = tmp_db.get_photo_by_flickr_id(sample_photo_data["flickr_id"])
        assert photo is not None
        assert photo["title"] == "Updated Title"

    def test_get_photos_by_status(
        self, tmp_db: StateDB, sample_photo_data: dict[str, Any]
    ) -> None:
        """get_photos_by_status should filter by status fields."""
        tmp_db.upsert_photo(sample_photo_data)

        pending = tmp_db.get_photos_by_status(download_status="pending")
        assert len(pending) == 1

        done = tmp_db.get_photos_by_status(download_status="done")
        assert len(done) == 0

    def test_add_and_get_predicted_tags(
        self, tmp_db: StateDB, sample_photo_data: dict[str, Any]
    ) -> None:
        """add_predicted_tags should store tags, retrievable via get_predicted_tags."""
        photo_id = tmp_db.upsert_photo(sample_photo_data)

        tags = [("sunset", 0.92), ("ocean", 0.85), ("landscape", 0.71)]
        tmp_db.add_predicted_tags(photo_id, tags)

        result = tmp_db.get_predicted_tags(photo_id)
        assert len(result) == 3
        assert result[0]["tag"] == "sunset"
        assert result[0]["confidence"] == pytest.approx(0.92)
        assert result[0]["approved"] == 0

    def test_approve_tags_all(
        self, tmp_db: StateDB, sample_photo_data: dict[str, Any]
    ) -> None:
        """approve_tags with no tag_names should approve all tags."""
        photo_id = tmp_db.upsert_photo(sample_photo_data)
        tmp_db.add_predicted_tags(photo_id, [("sunset", 0.9), ("beach", 0.8)])

        tmp_db.approve_tags(photo_id)

        approved = tmp_db.get_approved_tags(photo_id)
        assert len(approved) == 2

    def test_approve_tags_selective(
        self, tmp_db: StateDB, sample_photo_data: dict[str, Any]
    ) -> None:
        """approve_tags with specific tag_names should only approve those."""
        photo_id = tmp_db.upsert_photo(sample_photo_data)
        tmp_db.add_predicted_tags(photo_id, [("sunset", 0.9), ("beach", 0.8), ("sky", 0.7)])

        tmp_db.approve_tags(photo_id, ["sunset", "sky"])

        approved = tmp_db.get_approved_tags(photo_id)
        assert len(approved) == 2
        tag_names = {t["tag"] for t in approved}
        assert tag_names == {"sunset", "sky"}

    def test_existing_tags(
        self, tmp_db: StateDB, sample_photo_data: dict[str, Any]
    ) -> None:
        """add_existing_tags and get_existing_tags should roundtrip correctly."""
        photo_id = tmp_db.upsert_photo(sample_photo_data)

        tags = [{"tag": "sunset", "machine_tag": False}, {"tag": "nature", "machine_tag": False}]
        tmp_db.add_existing_tags(photo_id, tags)

        result = tmp_db.get_existing_tags(photo_id)
        assert len(result) == 2

    def test_mark_pushed(
        self, tmp_db: StateDB, sample_photo_data: dict[str, Any]
    ) -> None:
        """mark_pushed should update the push_status to 'pushed'."""
        photo_id = tmp_db.upsert_photo(sample_photo_data)
        tmp_db.mark_pushed(photo_id)

        photo = tmp_db.get_photo_by_flickr_id(sample_photo_data["flickr_id"])
        assert photo is not None
        assert photo["push_status"] == "pushed"

    def test_get_stats(
        self, tmp_db: StateDB, sample_photo_data: dict[str, Any]
    ) -> None:
        """get_stats should return correct summary counts."""
        photo_id = tmp_db.upsert_photo(sample_photo_data)
        tmp_db.add_predicted_tags(photo_id, [("tag1", 0.9)])
        tmp_db.approve_tags(photo_id)

        stats = tmp_db.get_stats()
        assert stats["total_photos"] == 1
        assert stats["approved_tags"] == 1
        assert stats["download_status"]["pending"] == 1

    def test_get_all_photos(
        self, tmp_db: StateDB, sample_photo_data: dict[str, Any]
    ) -> None:
        """get_all_photos should return all photos in order."""
        tmp_db.upsert_photo(sample_photo_data)

        second = {**sample_photo_data, "flickr_id": "99999999999", "title": "Second Photo"}
        tmp_db.upsert_photo(second)

        photos = tmp_db.get_all_photos()
        assert len(photos) == 2
        assert photos[0]["flickr_id"] == sample_photo_data["flickr_id"]
