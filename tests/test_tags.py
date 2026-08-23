"""Tests for the models.tags module."""

from __future__ import annotations

from flickr_autotagger.models.tags import DEFAULT_TAGS


class TestDefaultTags:
    """Test DEFAULT_TAGS constant."""

    def test_default_tags_is_list(self) -> None:
        assert isinstance(DEFAULT_TAGS, list)

    def test_default_tags_not_empty(self) -> None:
        assert len(DEFAULT_TAGS) > 50

    def test_default_tags_are_strings(self) -> None:
        for tag in DEFAULT_TAGS:
            assert isinstance(tag, str)
