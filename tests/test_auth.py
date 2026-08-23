"""Tests for the auth module."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from flickr_autotagger.auth import authenticate, get_flickr_client, get_user_id, verify_auth
from flickr_autotagger.config import Settings


class TestGetFlickrClient:
    """Test get_flickr_client factory."""

    @patch("flickr_autotagger.auth.flickrapi.FlickrAPI")
    def test_creates_client(self, mock_flickr_cls: MagicMock, tmp_path: Path) -> None:
        settings = Settings(
            FLICKR_API_KEY="test_key",
            FLICKR_API_SECRET="test_secret",
            DATA_DIR=tmp_path / "data",
        )
        get_flickr_client(settings)
        mock_flickr_cls.assert_called_once_with(
            "test_key",
            "test_secret",
            format="parsed-json",
            token_cache_location=str(tmp_path / "data" / "auth_token"),
        )


class TestAuthenticate:
    """Test authenticate flow."""

    @patch("flickr_autotagger.auth.flickrapi.FlickrAPI")
    def test_already_authenticated(self, mock_flickr_cls: MagicMock, tmp_path: Path) -> None:
        mock_flickr = MagicMock()
        mock_flickr.token_valid.return_value = True
        mock_flickr_cls.return_value = mock_flickr

        settings = Settings(
            FLICKR_API_KEY="k",
            FLICKR_API_SECRET="s",
            DATA_DIR=tmp_path / "data",
        )
        result = authenticate(settings)
        assert result == mock_flickr
        mock_flickr.get_request_token.assert_not_called()

    @patch("builtins.input", return_value="12345")
    @patch("flickr_autotagger.auth.flickrapi.FlickrAPI")
    def test_new_auth_flow(
        self, mock_flickr_cls: MagicMock, mock_input: MagicMock, tmp_path: Path
    ) -> None:
        mock_flickr = MagicMock()
        mock_flickr.token_valid.return_value = False
        mock_flickr.auth_url.return_value = "https://flickr.com/auth"
        mock_flickr_cls.return_value = mock_flickr

        settings = Settings(
            FLICKR_API_KEY="k",
            FLICKR_API_SECRET="s",
            DATA_DIR=tmp_path / "data",
        )
        result = authenticate(settings)
        assert result == mock_flickr
        mock_flickr.get_request_token.assert_called_once_with(oauth_callback="oob")
        mock_flickr.get_access_token.assert_called_once_with("12345")


class TestVerifyAuth:
    """Test verify_auth checks."""

    @patch("flickr_autotagger.auth.flickrapi.FlickrAPI")
    def test_valid_token(self, mock_flickr_cls: MagicMock, tmp_path: Path) -> None:
        mock_flickr = MagicMock()
        mock_flickr.token_valid.return_value = True
        mock_flickr_cls.return_value = mock_flickr

        settings = Settings(
            FLICKR_API_KEY="k",
            FLICKR_API_SECRET="s",
            DATA_DIR=tmp_path / "data",
        )
        assert verify_auth(settings) is True

    @patch("flickr_autotagger.auth.flickrapi.FlickrAPI")
    def test_invalid_token(self, mock_flickr_cls: MagicMock, tmp_path: Path) -> None:
        mock_flickr = MagicMock()
        mock_flickr.token_valid.return_value = False
        mock_flickr_cls.return_value = mock_flickr

        settings = Settings(
            FLICKR_API_KEY="k",
            FLICKR_API_SECRET="s",
            DATA_DIR=tmp_path / "data",
        )
        assert verify_auth(settings) is False

    @patch("flickr_autotagger.auth.flickrapi.FlickrAPI", side_effect=Exception("fail"))
    def test_exception_returns_false(self, mock_flickr_cls: MagicMock, tmp_path: Path) -> None:
        settings = Settings(
            FLICKR_API_KEY="k",
            FLICKR_API_SECRET="s",
            DATA_DIR=tmp_path / "data",
        )
        assert verify_auth(settings) is False


class TestGetUserId:
    """Test get_user_id extraction."""

    def test_returns_user_id(self) -> None:
        mock_flickr = MagicMock()
        mock_flickr.test.login.return_value = {"user": {"id": "12345@N08"}}
        assert get_user_id(mock_flickr) == "12345@N08"
