"""Tests for the flickr_client module."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from flickr_autotagger.db import StateDB
from flickr_autotagger.flickr_client import FlickrClient


@pytest.fixture
def mock_flickr() -> MagicMock:
    return MagicMock()


@pytest.fixture
def client(mock_flickr: MagicMock, tmp_db: StateDB) -> FlickrClient:
    return FlickrClient(mock_flickr, tmp_db)


class TestSyncPhotos:
    """Test sync_photos method."""

    def test_sync_single_page(self, client: FlickrClient, mock_flickr: MagicMock) -> None:
        mock_flickr.people.getPhotos.return_value = {
            "photos": {
                "page": 1,
                "pages": 1,
                "photo": [
                    {
                        "id": "111",
                        "title": "Sunset",
                        "description": {"_content": "Pretty"},
                        "url_o": "https://example.com/111.jpg",
                        "farm": "1",
                        "server": "100",
                        "secret": "abc",
                        "datetaken": "2026-01-01 12:00:00",
                        "dateupload": "1700000000",
                        "tags": "nature sunset",
                    },
                ],
            }
        }
        count = client.sync_photos("user@N08")
        assert count == 1

    def test_sync_empty(self, client: FlickrClient, mock_flickr: MagicMock) -> None:
        mock_flickr.people.getPhotos.return_value = {"photos": {"page": 1, "pages": 1, "photo": []}}
        count = client.sync_photos("user@N08")
        assert count == 0

    def test_sync_multiple_pages(self, client: FlickrClient, mock_flickr: MagicMock) -> None:
        def side_effect(**kwargs: Any) -> dict[str, Any]:
            page = kwargs.get("page", 1)
            if page == 1:
                return {
                    "photos": {
                        "page": 1,
                        "pages": 2,
                        "photo": [
                            {
                                "id": "111",
                                "title": "Photo1",
                                "description": "",
                                "url_o": "",
                                "farm": "1",
                                "server": "1",
                                "secret": "a",
                                "datetaken": "",
                                "dateupload": "",
                                "tags": "",
                            }
                        ],
                    }
                }
            return {
                "photos": {
                    "page": 2,
                    "pages": 2,
                    "photo": [
                        {
                            "id": "222",
                            "title": "Photo2",
                            "description": "",
                            "url_o": "",
                            "farm": "1",
                            "server": "1",
                            "secret": "b",
                            "datetaken": "",
                            "dateupload": "",
                            "tags": "",
                        }
                    ],
                }
            }

        mock_flickr.people.getPhotos.side_effect = side_effect
        count = client.sync_photos("user@N08")
        assert count == 2


class TestPushTags:
    """Test push_tags method."""

    def test_merge_strategy(self, client: FlickrClient, mock_flickr: MagicMock) -> None:
        client.push_tags("111", ["sunset", "nature"], "merge")
        mock_flickr.photos.addTags.assert_called_once()

    def test_replace_strategy(self, client: FlickrClient, mock_flickr: MagicMock) -> None:
        client.push_tags("111", ["sunset", "nature"], "replace")
        mock_flickr.photos.setTags.assert_called_once()

    def test_multi_word_tags_quoted(self, client: FlickrClient, mock_flickr: MagicMock) -> None:
        client.push_tags("111", ["golden hour", "nature"], "merge")
        call_args = mock_flickr.photos.addTags.call_args
        tag_string = call_args[1]["tags"]
        assert '"golden hour"' in tag_string
        assert "nature" in tag_string


class TestPushAllApproved:
    """Test push_all_approved method."""

    def test_dry_run(
        self, client: FlickrClient, tmp_db: StateDB, sample_photo_data: dict[str, Any]
    ) -> None:
        photo_id = tmp_db.upsert_photo(sample_photo_data)
        tmp_db.add_predicted_tags(photo_id, [("sunset", 0.9), ("nature", 0.8)])
        tmp_db.approve_tags(photo_id)

        stats = client.push_all_approved(dry_run=True)
        assert stats["pushed"] == 1
        assert stats["failed"] == 0

    def test_skips_unapproved(
        self, client: FlickrClient, tmp_db: StateDB, sample_photo_data: dict[str, Any]
    ) -> None:
        tmp_db.upsert_photo(sample_photo_data)
        stats = client.push_all_approved()
        assert stats["skipped"] == 1
        assert stats["pushed"] == 0

    def test_push_failure_counted(
        self,
        client: FlickrClient,
        mock_flickr: MagicMock,
        tmp_db: StateDB,
        sample_photo_data: dict[str, Any],
    ) -> None:
        photo_id = tmp_db.upsert_photo(sample_photo_data)
        tmp_db.add_predicted_tags(photo_id, [("sunset", 0.9)])
        tmp_db.approve_tags(photo_id)
        mock_flickr.photos.addTags.side_effect = Exception("API error")

        stats = client.push_all_approved()
        assert stats["failed"] == 1


class TestDownloadPhotos:
    """Test download_photos method."""

    def test_nothing_pending(self, client: FlickrClient, tmp_path: Path) -> None:
        stats = client.download_photos(tmp_path / "images", concurrency=1)
        assert stats["downloaded"] == 0
        assert stats["failed"] == 0

    def test_download_skips_existing(
        self,
        client: FlickrClient,
        tmp_db: StateDB,
        sample_photo_data: dict[str, Any],
        tmp_path: Path,
    ) -> None:
        tmp_db.upsert_photo(sample_photo_data)
        image_dir = tmp_path / "images"
        image_dir.mkdir()
        # Create a file that already exists
        (image_dir / f"{sample_photo_data['flickr_id']}.jpg").write_bytes(b"existing")

        stats = client.download_photos(image_dir, concurrency=1)
        assert stats["skipped"] == 1
        assert stats["downloaded"] == 0

    @patch("requests.get")
    @patch("time.sleep")
    def test_download_success(
        self,
        mock_sleep: MagicMock,
        mock_requests_get: MagicMock,
        client: FlickrClient,
        mock_flickr: MagicMock,
        tmp_db: StateDB,
        sample_photo_data: dict[str, Any],
        tmp_path: Path,
    ) -> None:
        tmp_db.upsert_photo(sample_photo_data)
        image_dir = tmp_path / "images"

        # Mock getSizes response
        mock_flickr.photos.getSizes.return_value = {
            "sizes": {
                "size": [
                    {"label": "Original", "source": "https://example.com/photo.jpg"},
                ]
            }
        }
        # Mock HTTP response
        mock_resp = MagicMock()
        mock_resp.content = b"fake image data"
        mock_resp.raise_for_status = MagicMock()
        mock_requests_get.return_value = mock_resp

        stats = client.download_photos(image_dir, concurrency=1)
        assert stats["downloaded"] == 1
        assert (image_dir / f"{sample_photo_data['flickr_id']}.jpg").exists()

    @patch("requests.get")
    @patch("time.sleep")
    def test_download_api_error(
        self,
        mock_sleep: MagicMock,
        mock_requests_get: MagicMock,
        client: FlickrClient,
        mock_flickr: MagicMock,
        tmp_db: StateDB,
        sample_photo_data: dict[str, Any],
        tmp_path: Path,
    ) -> None:
        tmp_db.upsert_photo(sample_photo_data)
        image_dir = tmp_path / "images"

        mock_flickr.photos.getSizes.side_effect = Exception("API error")

        stats = client.download_photos(image_dir, concurrency=1)
        assert stats["failed"] == 1
