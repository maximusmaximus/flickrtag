"""Tests for the tagger module."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from flickr_autotagger.tagger import Tagger


class TestTaggerFindImage:
    """Test Tagger._find_image static method."""

    def test_finds_jpg(self, tmp_path: Path) -> None:
        (tmp_path / "12345.jpg").write_bytes(b"fake")
        result = Tagger._find_image(tmp_path, "12345")
        assert result == tmp_path / "12345.jpg"

    def test_finds_png(self, tmp_path: Path) -> None:
        (tmp_path / "12345.png").write_bytes(b"fake")
        result = Tagger._find_image(tmp_path, "12345")
        assert result == tmp_path / "12345.png"

    def test_returns_none_missing(self, tmp_path: Path) -> None:
        result = Tagger._find_image(tmp_path, "99999")
        assert result is None

    def test_finds_webp(self, tmp_path: Path) -> None:
        (tmp_path / "12345.webp").write_bytes(b"fake")
        result = Tagger._find_image(tmp_path, "12345")
        assert result == tmp_path / "12345.webp"


class TestTaggerTagAllPending:
    """Test tag_all_pending with mocked CLIP model."""

    @patch("flickr_autotagger.tagger._load_model")
    def test_nothing_pending(self, mock_load: MagicMock) -> None:
        mock_db = MagicMock()
        mock_db.get_photos_by_status.return_value = []

        tagger = Tagger.__new__(Tagger)
        tagger.model_name = "ViT-B-32"
        tagger.pretrained = "openai"

        stats = tagger.tag_all_pending(mock_db, Path("/fake"), ["tag1"])
        assert stats == {"tagged": 0, "failed": 0, "skipped": 0}

    @patch("flickr_autotagger.tagger._load_model")
    def test_image_not_found_skipped(self, mock_load: MagicMock, tmp_path: Path) -> None:
        mock_db = MagicMock()
        mock_db.get_photos_by_status.return_value = [
            {"id": 1, "flickr_id": "99999"},
        ]

        tagger = Tagger.__new__(Tagger)
        tagger.model_name = "ViT-B-32"
        tagger.pretrained = "openai"

        stats = tagger.tag_all_pending(mock_db, tmp_path, ["tag1"])
        assert stats["skipped"] == 1

    @patch("flickr_autotagger.tagger._load_model")
    def test_tag_failure_counted(self, mock_load: MagicMock, tmp_path: Path) -> None:
        (tmp_path / "111.jpg").write_bytes(b"fake")
        mock_db = MagicMock()
        mock_db.get_photos_by_status.return_value = [
            {"id": 1, "flickr_id": "111"},
        ]

        tagger = Tagger.__new__(Tagger)
        tagger.model_name = "ViT-B-32"
        tagger.pretrained = "openai"

        with patch.object(tagger, "predict", side_effect=Exception("CLIP error")):
            stats = tagger.tag_all_pending(mock_db, tmp_path, ["tag1"])
        assert stats["failed"] == 1

    @patch("flickr_autotagger.tagger._load_model")
    def test_tag_no_matches(self, mock_load: MagicMock, tmp_path: Path) -> None:
        (tmp_path / "111.jpg").write_bytes(b"fake")
        mock_db = MagicMock()
        mock_db.get_photos_by_status.return_value = [
            {"id": 1, "flickr_id": "111"},
        ]

        tagger = Tagger.__new__(Tagger)
        tagger.model_name = "ViT-B-32"
        tagger.pretrained = "openai"

        with patch.object(tagger, "predict", return_value=[]):
            stats = tagger.tag_all_pending(mock_db, tmp_path, ["tag1"])
        assert stats["tagged"] == 1
        mock_db.update_tag_status.assert_called_once_with(1, "done")

    @patch("flickr_autotagger.tagger._load_model")
    def test_tag_with_matches(self, mock_load: MagicMock, tmp_path: Path) -> None:
        (tmp_path / "111.jpg").write_bytes(b"fake")
        mock_db = MagicMock()
        mock_db.get_photos_by_status.return_value = [
            {"id": 1, "flickr_id": "111"},
        ]

        tagger = Tagger.__new__(Tagger)
        tagger.model_name = "ViT-B-32"
        tagger.pretrained = "openai"

        with patch.object(tagger, "predict", return_value=[("sunset", 0.9), ("nature", 0.8)]):
            stats = tagger.tag_all_pending(mock_db, tmp_path, ["sunset", "nature"])
        assert stats["tagged"] == 1
        mock_db.add_predicted_tags.assert_called_once_with(1, [("sunset", 0.9), ("nature", 0.8)])


class TestTaggerPredict:
    """Test predict method with mocked globals."""

    @patch("flickr_autotagger.tagger._load_model")
    def test_predict_bad_image_returns_empty(self, mock_load: MagicMock, tmp_path: Path) -> None:
        bad_file = tmp_path / "bad.jpg"
        bad_file.write_bytes(b"not a real image")

        tagger = Tagger.__new__(Tagger)
        tagger.model_name = "ViT-B-32"
        tagger.pretrained = "openai"

        # _model must not be None for assert to pass, but PIL will fail first
        import flickr_autotagger.tagger as tagger_mod

        old_model = tagger_mod._model
        tagger_mod._model = MagicMock()
        tagger_mod._preprocess = MagicMock()
        tagger_mod._tokenizer = MagicMock()

        try:
            # PIL.Image.open on garbage bytes can raise various errors
            result = tagger.predict(bad_file, ["tag1", "tag2"])
            # Should return [] on bad images
            assert result == []
        finally:
            tagger_mod._model = old_model
