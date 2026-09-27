"""Unit tests for spatial mathematics and 3D coordinate transformations."""

import math
from flickr_autotagger.spatial_nft.backend.spatial_math import (
    to_globe_coords,
    to_semantic_cosmos_coords,
    to_color_torus_coords,
    to_chronos_helix_coords,
    GEO_ANCHORS,
    SEMANTIC_CLUSTERS,
)


def test_to_globe_coords_with_exact_gps():
    """Verify that exact GPS coordinates map to expected Cartesian coordinates."""
    lat, lng = 45.5152, -122.6784  # Portland, OR
    x, y, z = to_globe_coords(lat, lng, None, "test_1", radius=100.0)

    # Calculate expected sphere radius
    r = math.sqrt(x**2 + y**2 + z**2)
    assert 95.0 <= r <= 105.0
    assert isinstance(x, float)
    assert isinstance(y, float)
    assert isinstance(z, float)


def test_to_globe_coords_with_location_guess():
    """Verify that location guesses map to geo anchor centroids."""
    x, y, z = to_globe_coords(None, None, "Downtown Seattle, Washington", "test_seattle", radius=100.0)
    r = math.sqrt(x**2 + y**2 + z**2)
    assert 95.0 <= r <= 105.0


def test_to_globe_coords_fallback():
    """Verify fallback behavior when coordinates and location are unknown."""
    x, y, z = to_globe_coords(None, None, None, "unknown_photo", radius=100.0)
    r = math.sqrt(x**2 + y**2 + z**2)
    assert 95.0 <= r <= 105.0


def test_to_semantic_cosmos_coords():
    """Verify clustering based on scene types and mood tags."""
    # Street Noir photo
    x1, y1, z1 = to_semantic_cosmos_coords("p1", scene="urban", mood="noir, gritty", tags_count=10)
    # Nature photo
    x2, y2, z2 = to_semantic_cosmos_coords("p2", scene="nature", mood="serene", tags_count=5)

    # Street noir and nature should be in distinct sectors
    dist = math.sqrt((x1 - x2)**2 + (y1 - y2)**2 + (z1 - z2)**2)
    assert dist > 30.0


def test_to_semantic_cosmos_unmatched():
    """Verify dispersion for unmatched semantic descriptors."""
    x, y, z = to_semantic_cosmos_coords("p_rand", None, None, 0)
    assert isinstance(x, float)
    assert isinstance(y, float)
    assert isinstance(z, float)


def test_to_color_torus_coords():
    """Verify color torus placement based on dominant color palette."""
    red_coords = to_color_torus_coords(["red", "orange"], "p_red")
    blue_coords = to_color_torus_coords(["blue", "cyan"], "p_blue")

    # Red and blue should be separated on the torus ring
    dist = math.sqrt(sum((a - b)**2 for a, b in zip(red_coords, blue_coords)))
    assert dist > 20.0


def test_to_color_torus_empty_colors():
    """Verify fallback torus placement when colors array is empty."""
    x, y, z = to_color_torus_coords([], "p_empty")
    assert isinstance(x, float)
    assert isinstance(y, float)
    assert isinstance(z, float)


def test_to_chronos_helix_coords():
    """Verify that photos ascend vertically along the time spiral."""
    # Earlier photo (2016)
    x1, y1, z1 = to_chronos_helix_coords("2016-05-12 14:00:00", 0, total=100)
    # Later photo (2025)
    x2, y2, z2 = to_chronos_helix_coords("2025-08-20 18:00:00", 99, total=100)

    # Later photo should have a significantly higher Y elevation
    assert y2 > y1
