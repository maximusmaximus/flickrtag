"""Unit tests for geocoding functions and location cleaning."""

from flickr_autotagger.geocoder import clean_location_query


def test_clean_location_valid_places():
    """Verify that genuine geographic places are retained and cleaned."""
    assert clean_location_query("Seattle, Washington") == "Seattle, Washington"
    assert clean_location_query("San Francisco, California (unconfirmed)") == "San Francisco, California"
    assert clean_location_query("Portland, Oregon or similar PNW location") == "Portland, Oregon"


def test_clean_location_non_places():
    """Verify that non-geographic descriptors return None."""
    assert clean_location_query("unknown") is None
    assert clean_location_query("kitchen") is None
    assert clean_location_query("living room") is None
    assert clean_location_query("office") is None
    assert clean_location_query("") is None
    assert clean_location_query(None) is None
