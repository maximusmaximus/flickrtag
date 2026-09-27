"""Unit tests for spatial-serve CLI command."""

from click.testing import CliRunner
from flickr_autotagger.cli import cli


def test_spatial_serve_help():
    """Verify that spatial-serve command exists and displays options."""
    runner = CliRunner()
    result = runner.invoke(cli, ["spatial-serve", "--help"])
    assert result.exit_code == 0
    assert "Launch the 3D Spatial Exploration" in result.output
    assert "--port" in result.output
    assert "--host" in result.output
