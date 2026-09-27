"""Unit tests for album creation and normalization."""

from flickr_autotagger.albums import _normalize_location, _normalize_scene


def test_normalize_location():
    """Verify city and region extraction."""
    assert _normalize_location("Downtown Seattle, King County, Washington") == "Seattle, King County"
    assert _normalize_location("Portland, Oregon, USA") == "Portland, Oregon"
    assert _normalize_location("kitchen") is None
    assert _normalize_location(None) is None


def test_normalize_scene():
    """Verify scene normalization mappings."""
    assert _normalize_scene("urban street scene") == "street"
    assert _normalize_scene("cathedral building architecture") == "architecture"
    assert _normalize_scene("portrait of person") == "portrait"
    assert _normalize_scene("mountain lake landscape") == "landscape"
    assert _normalize_scene("indoor") is None
    assert _normalize_scene(None) is None
