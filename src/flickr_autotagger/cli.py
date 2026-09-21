"""CLI entrypoint for flickr-autotagger."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import click
import structlog

from flickr_autotagger import __version__
from flickr_autotagger.config import Settings, get_settings
from flickr_autotagger.db import StateDB

logger = structlog.get_logger()


def _init() -> tuple[Settings, StateDB]:
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

    # Venice status
    try:
        conn = db.connect()
        row = conn.execute(
            "SELECT venice_status, COUNT(*) as count "
            "FROM photos GROUP BY venice_status"
        ).fetchall()
        if row:
            parts = [f"{r['count']} {r['venice_status'] or 'null'}" for r in row]
            click.echo(f"   Venice AI: {', '.join(parts)}")
    except Exception:
        pass

    click.echo()


@cli.command("venice-tag")
@click.option("--retag", is_flag=True, help="Re-analyze all photos, not just pending ones.")
@click.option("--limit", "-n", default=0, type=int, help="Max photos to process (0 = all).")
@click.option("--auto-approve", is_flag=True, default=True, help="Auto-approve Venice tags.")
def venice_tag(retag: bool, limit: int, auto_approve: bool) -> None:
    """Analyze photos using Venice.ai vision LLM (Qwen3-VL-235B).

    Generates rich structured metadata: tags, descriptions, mood,
    technique, location guesses, and title suggestions.
    """
    from flickr_autotagger.venice_tagger import VeniceTagger

    settings, db = _init()

    if not settings.VENICE_API_KEY:
        click.echo("❌ VENICE_API_KEY not set. Add it to your .env file.")
        click.echo("   Get your key at: https://venice.ai/settings/api")
        raise SystemExit(1)

    tagger = VeniceTagger(settings)

    # Get photos to process
    if retag:
        photos = db.get_photos_by_status(download_status="done")
    else:
        photos = db.get_photos_needing_venice()

    if limit > 0:
        photos = photos[:limit]

    if not photos:
        click.echo("📭 No photos need Venice analysis.")
        return

    click.echo(f"🔬 Analyzing {len(photos)} photos with Venice.ai ({settings.VENICE_MODEL})...")

    stats = {"tagged": 0, "failed": 0, "skipped": 0}

    for i, photo in enumerate(photos):
        flickr_id = photo["flickr_id"]
        image_path = tagger._find_image(settings.image_dir, flickr_id)

        if image_path is None:
            logger.warning("venice_image_not_found", flickr_id=flickr_id)
            stats["skipped"] += 1
            continue

        try:
            analysis = tagger.analyze_photo(image_path)
            db.store_venice_analysis(photo["id"], analysis)

            # Store and optionally auto-approve tags
            tags = [(tag, 1.0) for tag in analysis.get("tags", [])]
            if tags:
                db.add_predicted_tags(photo["id"], tags)
                if auto_approve:
                    db.approve_tags(photo["id"])

            stats["tagged"] += 1

            # Progress output
            done = stats["tagged"] + stats["failed"] + stats["skipped"]
            title_preview = (analysis.get("title_suggestion", "") or "")[:40]
            tag_count = len(analysis.get("tags", []))
            click.echo(
                f"   [{done}/{len(photos)}] ✅ {flickr_id} → "
                f"\"{title_preview}\" ({tag_count} tags, {analysis.get('scene_type', '?')})"
            )

        except Exception as exc:
            db.update_venice_status(photo["id"], "error")
            stats["failed"] += 1
            click.echo(f"   [{i+1}/{len(photos)}] ❌ {flickr_id}: {exc}")

        # Brief pause between requests
        import time
        time.sleep(0.5)

    click.echo(
        f"\n✅ Venice analysis complete: "
        f"{stats['tagged']} tagged, {stats['failed']} failed, {stats['skipped']} skipped"
    )


@cli.command("venice-push")
@click.option("--dry-run", is_flag=True, help="Show what would be pushed without doing it.")
@click.option("--update-titles", is_flag=True, help="Also update Flickr titles with AI suggestions.")
@click.option("--update-descriptions", is_flag=True, default=True, help="Also update Flickr descriptions.")
@click.option(
    "--strategy",
    type=click.Choice(["merge", "replace"]),
    default=None,
    help="Tag merge strategy.",
)
def venice_push(dry_run: bool, update_titles: bool, update_descriptions: bool, strategy: str | None) -> None:
    """Push Venice.ai tags and descriptions back to Flickr.

    Unlike the basic push, this can also update photo titles and descriptions
    with the AI-generated content.
    """
    import time

    from flickr_autotagger.auth import authenticate
    from flickr_autotagger.flickr_client import FlickrClient

    settings, db = _init()
    flickr = authenticate(settings)
    merge_strategy = strategy or settings.TAG_MERGE_STRATEGY

    client = FlickrClient(flickr, db)

    # Get all Venice-analyzed photos with approved tags
    photos = db.get_photos_by_status(venice_status="done")
    stats = {"pushed": 0, "skipped": 0, "failed": 0}

    if not photos:
        click.echo("📭 No Venice-analyzed photos to push.")
        return

    click.echo(f"🚀 Pushing {len(photos)} photos to Flickr...")

    for photo in photos:
        approved = db.get_approved_tags(photo["id"])
        venice = db.get_venice_analysis(photo["id"])

        if not approved and not venice:
            stats["skipped"] += 1
            continue

        if dry_run:
            tag_names = [t["tag"] for t in approved] if approved else []
            click.echo(
                f"   [DRY RUN] {photo['flickr_id']}: "
                f"{len(tag_names)} tags"
                + (f", title: \"{venice.get('ai_title', '')[:30]}\"" if venice and update_titles else "")
                + (f", desc: \"{venice.get('ai_description', '')[:40]}...\"" if venice and update_descriptions else "")
            )
            stats["pushed"] += 1
            continue

        try:
            # Push tags
            if approved:
                tag_names = [t["tag"] for t in approved]
                client.push_tags(photo["flickr_id"], tag_names, merge_strategy)

            # Update title and/or description via Flickr API
            if venice and (update_titles or update_descriptions):
                meta_kwargs: dict[str, Any] = {"photo_id": photo["flickr_id"]}
                if update_titles and venice.get("ai_title"):
                    meta_kwargs["title"] = venice["ai_title"]
                if update_descriptions and venice.get("ai_description"):
                    meta_kwargs["description"] = venice["ai_description"]

                if len(meta_kwargs) > 1:  # More than just photo_id
                    flickr.photos.setMeta(**meta_kwargs)

            db.mark_pushed(photo["id"])
            stats["pushed"] += 1

            # Rate limit
            time.sleep(1.5)

        except Exception as exc:
            error_str = str(exc)
            if "429" in error_str:
                click.echo(f"   ⚠️ Rate limited on {photo['flickr_id']}, sleeping 60s...")
                time.sleep(60)
            logger.error("venice_push_failed", flickr_id=photo["flickr_id"], error=error_str)
            stats["failed"] += 1

    prefix = "[DRY RUN] " if dry_run else ""
    click.echo(
        f"\n{prefix}✅ Pushed: {stats['pushed']}  "
        f"Skipped: {stats['skipped']}  "
        f"Failed: {stats['failed']}"
    )


@cli.command("geocode")
def geocode_cmd() -> None:
    """Geocode Venice.ai location guesses to lat/long coordinates.

    Uses OpenStreetMap Nominatim (free, no API key needed).
    Rate limited to 1 request/second.
    """
    from flickr_autotagger.geocoder import geocode_all_pending

    _settings, db = _init()
    click.echo("🌍 Geocoding location guesses...")
    stats = geocode_all_pending(db)

    click.echo(
        f"\n✅ Geocoded: {stats['geocoded']}  "
        f"No location: {stats['no_location']}  "
        f"Failed: {stats['failed']}  "
        f"Skipped: {stats['skipped']}"
    )


@cli.command("geo-push")
@click.option("--dry-run", is_flag=True, help="Show what would be pushed without doing it.")
def geo_push(dry_run: bool) -> None:
    """Push geocoded lat/long and indoor/outdoor context to Flickr.

    Your photos will appear on Flickr's world map!
    """
    from flickr_autotagger.auth import authenticate
    from flickr_autotagger.geocoder import push_geo_to_flickr

    settings, db = _init()
    flickr = authenticate(settings)

    click.echo("📍 Pushing geolocation data to Flickr...")
    stats = push_geo_to_flickr(flickr, db, dry_run=dry_run)

    prefix = "[DRY RUN] " if dry_run else ""
    click.echo(
        f"\n{prefix}✅ Pushed: {stats['pushed']}  "
        f"Skipped: {stats['skipped']}  "
        f"Failed: {stats['failed']}"
    )


@cli.command("auto-albums")
@click.option("--dry-run", is_flag=True, help="Show album plan without creating anything.")
@click.option("--min-photos", default=5, type=int, help="Minimum photos per album.")
@click.option("--max-albums", default=50, type=int, help="Maximum albums to create.")
def auto_albums(dry_run: bool, min_photos: int, max_albums: int) -> None:
    """Create smart Flickr albums based on AI analysis.

    Groups photos by location and scene type, then creates
    Flickr photosets automatically.
    """
    from flickr_autotagger.albums import build_album_plan, create_albums_on_flickr
    from flickr_autotagger.auth import authenticate

    settings, db = _init()

    click.echo("📁 Building album plan from Venice.ai analysis...")
    albums = build_album_plan(db, min_photos=min_photos)

    if not albums:
        click.echo("📭 Not enough analyzed photos to create albums yet.")
        return

    # Show the plan
    click.echo(f"\n📋 Album plan ({len(albums)} albums):\n")
    location_albums = [a for a in albums if a["type"] == "location"]
    scene_albums = [a for a in albums if a["type"] == "scene"]

    if location_albums:
        click.echo("   📍 By Location:")
        for a in location_albums[:20]:
            click.echo(f"      {a['name']} ({a['count']} photos)")

    if scene_albums:
        click.echo("\n   🎨 By Scene Type:")
        for a in scene_albums[:20]:
            click.echo(f"      {a['name']} ({a['count']} photos)")

    click.echo(f"\n   Total: {sum(a['count'] for a in albums)} photo placements across {len(albums)} albums")

    if dry_run:
        click.echo("\n[DRY RUN] No albums created.")
        return

    if not click.confirm("\n🚀 Create these albums on Flickr?"):
        click.echo("Cancelled.")
        return

    flickr = authenticate(settings)
    stats = create_albums_on_flickr(flickr, albums, max_albums=max_albums)

    click.echo(
        f"\n✅ Created: {stats['created']}  "
        f"Photos added: {stats['photos_added']}  "
        f"Skipped: {stats['skipped']}  "
        f"Failed: {stats['failed']}"
    )


if __name__ == "__main__":
    cli()
