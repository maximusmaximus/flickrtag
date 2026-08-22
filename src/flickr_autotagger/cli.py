"""CLI entrypoint for flickr-autotagger."""

from __future__ import annotations

from pathlib import Path

import click
import structlog

from flickr_autotagger import __version__
from flickr_autotagger.config import get_settings
from flickr_autotagger.db import StateDB

logger = structlog.get_logger()


def _init() -> tuple:
    """Initialize settings and database. Returns (settings, db)."""
    settings = get_settings()
    db = StateDB(settings.db_path)
    db.init_db()
    return settings, db


@click.group()
@click.version_option(version=__version__)
def cli() -> None:
    """🏷️ flickr-autotagger — AI-powered Flickr photo tagger using CLIP."""
    structlog.configure(
        processors=[
            structlog.dev.ConsoleRenderer(colors=True),
        ],
    )


@cli.command()
def auth() -> None:
    """Authenticate with Flickr via OAuth (opens browser)."""
    from flickr_autotagger.auth import authenticate

    settings = get_settings()
    flickr = authenticate(settings)
    click.echo("✅ Authentication successful!")

    from flickr_autotagger.auth import get_user_id

    user_id = get_user_id(flickr)
    click.echo(f"👤 Logged in as: {user_id}")


@cli.command()
def sync() -> None:
    """Sync photo metadata from Flickr into the local database."""
    from flickr_autotagger.auth import authenticate, get_user_id
    from flickr_autotagger.flickr_client import FlickrClient

    settings, db = _init()
    flickr = authenticate(settings)

    user_id = settings.FLICKR_USER_ID or get_user_id(flickr)
    client = FlickrClient(flickr, db)
    count = client.sync_photos(user_id)

    click.echo(f"✅ Synced {count} photos from Flickr.")


@cli.command()
@click.option("--concurrency", "-c", default=None, type=int, help="Download concurrency.")
def download(concurrency: int | None) -> None:
    """Download original images (resumable, incremental)."""
    from flickr_autotagger.auth import authenticate
    from flickr_autotagger.flickr_client import FlickrClient

    settings, db = _init()
    flickr = authenticate(settings)
    conc = concurrency or settings.DOWNLOAD_CONCURRENCY

    client = FlickrClient(flickr, db)
    stats = client.download_photos(settings.image_dir, conc)

    click.echo(
        f"✅ Downloaded: {stats['downloaded']}  "
        f"Skipped: {stats['skipped']}  "
        f"Failed: {stats['failed']}"
    )


@cli.command()
@click.option("--threshold", "-t", default=None, type=float, help="Min confidence threshold.")
@click.option("--max-tags", "-m", default=None, type=int, help="Max tags per photo.")
@click.option("--custom-tags", type=click.Path(exists=True), help="Path to custom tags YAML.")
def tag(threshold: float | None, max_tags: int | None, custom_tags: str | None) -> None:
    """Run AI tagging on all un-tagged images using CLIP."""
    from flickr_autotagger.models.tags import DEFAULT_TAGS
    from flickr_autotagger.tagger import Tagger

    settings, db = _init()
    thresh = threshold or settings.TAG_THRESHOLD
    mt = max_tags or settings.MAX_TAGS_PER_PHOTO

    candidate_tags = DEFAULT_TAGS
    if custom_tags:
        import yaml

        with open(custom_tags) as f:
            data = yaml.safe_load(f)
        candidate_tags = data.get("tags", DEFAULT_TAGS)
        click.echo(f"📋 Loaded {len(candidate_tags)} custom tags.")

    tagger = Tagger(model_name="ViT-B-32", pretrained="openai")
    stats = tagger.tag_all_pending(db, settings.image_dir, candidate_tags, thresh, mt)

    click.echo(
        f"✅ Tagged: {stats['tagged']}  Failed: {stats['failed']}  Skipped: {stats['skipped']}"
    )


@cli.command()
@click.option("--auto-approve", is_flag=True, help="Approve all predicted tags without review.")
def review(auto_approve: bool) -> None:
    """Review predicted tags and approve them for pushing."""
    _settings, db = _init()
    photos = db.get_photos_by_status(tag_status="done")

    if not photos:
        click.echo("📭 No tagged photos to review.")
        return

    approved_count = 0
    for photo in photos:
        predicted = db.get_predicted_tags(photo["id"])
        if not predicted:
            continue

        if auto_approve:
            db.approve_tags(photo["id"])
            approved_count += 1
            continue

        click.echo(f"\n📷 {photo['title'] or photo['flickr_id']}")
        click.echo("   Predicted tags:")
        for i, t in enumerate(predicted, 1):
            status = "✓" if t["approved"] else " "
            click.echo(f"   [{status}] {i}. {t['tag']} ({t['confidence']:.3f})")

        action = click.prompt(
            "   [a]pprove all / [s]elect / [n]ext / [q]uit",
            type=click.Choice(["a", "s", "n", "q"]),
            default="a",
        )

        if action == "q":
            break
        elif action == "a":
            db.approve_tags(photo["id"])
            approved_count += 1
            click.echo("   ✅ All approved!")
        elif action == "s":
            indices = click.prompt("   Enter tag numbers to approve (comma-separated)")
            try:
                selected = [int(x.strip()) - 1 for x in indices.split(",")]
                tag_names = [predicted[i]["tag"] for i in selected if 0 <= i < len(predicted)]
                db.approve_tags(photo["id"], tag_names)
                approved_count += 1
                click.echo(f"   ✅ Approved {len(tag_names)} tags.")
            except (ValueError, IndexError):
                click.echo("   ⚠️ Invalid selection, skipping.")

    click.echo(f"\n✅ Reviewed {approved_count} photos.")


@cli.command()
@click.option("--dry-run", is_flag=True, help="Show what would be pushed without doing it.")
@click.option(
    "--strategy",
    type=click.Choice(["merge", "replace"]),
    default=None,
    help="Tag merge strategy.",
)
def push(dry_run: bool, strategy: str | None) -> None:
    """Push approved tags back to Flickr."""
    from flickr_autotagger.auth import authenticate
    from flickr_autotagger.flickr_client import FlickrClient

    settings, db = _init()
    flickr = authenticate(settings)
    merge_strategy = strategy or settings.TAG_MERGE_STRATEGY

    client = FlickrClient(flickr, db)
    stats = client.push_all_approved(merge_strategy, dry_run)

    prefix = "[DRY RUN] " if dry_run else ""
    click.echo(
        f"{prefix}✅ Pushed: {stats['pushed']}  "
        f"Skipped: {stats['skipped']}  "
        f"Failed: {stats['failed']}"
    )


@cli.command("export")
@click.option(
    "--format",
    "fmt",
    type=click.Choice(["json", "csv", "xmp"]),
    required=True,
    help="Export format.",
)
@click.option("--output", "-o", type=click.Path(), help="Output file or directory path.")
def export_cmd(fmt: str, output: str | None) -> None:
    """Export tags in various formats (JSON, CSV, XMP sidecar)."""
    from flickr_autotagger import exporter

    settings, db = _init()

    if fmt == "json":
        out = Path(output) if output else Path("tags.json")
        count = exporter.export_json(db, out)
        click.echo(f"✅ Exported {count} photos to {out}")

    elif fmt == "csv":
        out = Path(output) if output else Path("tags.csv")
        count = exporter.export_csv(db, out)
        click.echo(f"✅ Exported {count} photos to {out}")

    elif fmt == "xmp":
        out_dir = Path(output) if output else None
        count = exporter.export_xmp_sidecars(db, settings.image_dir, out_dir)
        click.echo(f"✅ Created {count} XMP sidecar files")


@cli.command()
def status() -> None:
    """Show database statistics and pipeline status."""
    settings, db = _init()
    stats = db.get_stats()

    click.echo("\n📊 flickr-autotagger Status")
    click.echo(f"   Database: {settings.db_path}")
    click.echo(f"   Images:   {settings.image_dir}")
    click.echo(f"\n   Total photos: {stats['total_photos']}")

    if stats["total_photos"] > 0:
        for label, key in [
            ("Downloads", "download_status"),
            ("Tagging", "tag_status"),
            ("Push", "push_status"),
        ]:
            breakdown = stats.get(key, {})
            parts = [f"{v} {k}" for k, v in breakdown.items()]
            click.echo(f"   {label}: {', '.join(parts)}")

        click.echo(f"   Approved tags: {stats['approved_tags']}")
    click.echo()


if __name__ == "__main__":
    cli()
