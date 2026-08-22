"""Tests for the exporter module."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from flickr_autotagger.db import StateDB
from flickr_autotagger.exporter import export_csv, export_json, export_xmp_sidecars


def _seed_db(db: StateDB) -> int:
    """Insert a photo with tags and return its internal ID."""
    photo_data = {
        "flickr_id": "55555555555",
        "title": "Test Photo",
        "description": "A test photo",
        "original_url": "https://example.com/photo.jpg",
        "farm": "1",
        "server": "100",
        "secret": "abc123",
        "date_taken": "2026-06-01 12:00:00",
        "date_uploaded": "1735600000",
        "last_synced": "2026-08-01T00:00:00+00:00",
    }
    photo_id = db.upsert_photo(photo_data)

    db.add_existing_tags(photo_id, [{"tag": "nature", "machine_tag": False}])
    db.add_predicted_tags(photo_id, [("sunset", 0.95), ("landscape", 0.82)])
    db.approve_tags(photo_id, ["sunset"])

    return photo_id


class TestExportJson:
    """Tests for JSON export."""

    def test_export_json_creates_file(self, tmp_db: StateDB, tmp_path: Path) -> None:
        """export_json should create a valid JSON file."""
        _seed_db(tmp_db)
        output = tmp_path / "output" / "tags.json"
        count = export_json(tmp_db, output)

        assert count == 1
        assert output.exists()

        data = json.loads(output.read_text())
        assert len(data) == 1
        assert data[0]["flickr_id"] == "55555555555"
        assert data[0]["existing_tags"] == ["nature"]
        assert len(data[0]["predicted_tags"]) == 2

    def test_export_json_empty_db(self, tmp_db: StateDB, tmp_path: Path) -> None:
        """export_json on an empty DB should create a valid empty JSON array."""
        output = tmp_path / "empty.json"
        count = export_json(tmp_db, output)

        assert count == 0
        data = json.loads(output.read_text())
        assert data == []


class TestExportCsv:
    """Tests for CSV export."""

    def test_export_csv_creates_file(self, tmp_db: StateDB, tmp_path: Path) -> None:
        """export_csv should create a valid CSV with headers and data."""
        _seed_db(tmp_db)
        output = tmp_path / "tags.csv"
        count = export_csv(tmp_db, output)

        assert count == 1
        assert output.exists()

        with open(output) as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        assert len(rows) == 1
        assert rows[0]["flickr_id"] == "55555555555"
        assert "sunset" in rows[0]["predicted_tags"]

    def test_export_csv_empty_db(self, tmp_db: StateDB, tmp_path: Path) -> None:
        """export_csv on an empty DB should create a CSV with only headers."""
        output = tmp_path / "empty.csv"
        count = export_csv(tmp_db, output)

        assert count == 0
        with open(output) as f:
            reader = csv.reader(f)
            rows = list(reader)
        assert len(rows) == 1  # header only


class TestExportXmp:
    """Tests for XMP sidecar export."""

    def test_export_xmp_creates_sidecar(self, tmp_db: StateDB, tmp_path: Path) -> None:
        """export_xmp_sidecars should create XMP files for photos with approved tags."""
        _seed_db(tmp_db)

        # Create a fake image so the sidecar picks up the extension
        image_dir = tmp_path / "images"
        image_dir.mkdir()
        (image_dir / "55555555555.jpg").write_bytes(b"fake")

        output_dir = tmp_path / "xmp_out"
        count = export_xmp_sidecars(tmp_db, image_dir, output_dir)

        assert count == 1
        sidecar = output_dir / "55555555555.jpg.xmp"
        assert sidecar.exists()

        content = sidecar.read_text()
        assert "sunset" in content
        assert "dc:subject" in content
