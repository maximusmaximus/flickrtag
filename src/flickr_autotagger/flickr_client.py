"""Flickr API operations: sync metadata, download images, push tags."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import structlog

from flickr_autotagger.db import StateDB

logger = structlog.get_logger()


class FlickrClient:
    """High-level Flickr operations backed by the state database."""

    def __init__(self, flickr: Any, db: StateDB) -> None:
        self.flickr = flickr
        self.db = db

    def sync_photos(self, user_id: str) -> int:
        """Sync all photo metadata from Flickr into the local database.

        Uses paginated iteration to fetch all photos. Existing records are
        updated; new photos are inserted. Returns the number of photos synced.
        """
        page = 1
        total_synced = 0
        now = datetime.now(UTC).isoformat()

        while True:
            logger.info("sync_page", page=page)
            result = self.flickr.people.getPhotos(
                user_id=user_id,
                extras="date_taken,date_upload,url_o,description,tags",
                per_page=500,
                page=page,
            )

            photos = result["photos"]["photo"]
            if not photos:
                break

            for photo in photos:
                desc = photo.get("description", {})
                if isinstance(desc, dict):
                    desc = desc.get("_content", "")

                photo_data = {
                    "flickr_id": str(photo["id"]),
                    "title": photo.get("title", ""),
                    "description": desc,
                    "original_url": photo.get("url_o", ""),
                    "farm": str(photo.get("farm", "")),
                    "server": str(photo.get("server", "")),
                    "secret": photo.get("secret", ""),
                    "date_taken": photo.get("datetaken", ""),
                    "date_uploaded": photo.get("dateupload", ""),
                    "last_synced": now,
                }

                photo_id = self.db.upsert_photo(photo_data)

                # Store existing tags from Flickr
                existing_tags_str = photo.get("tags", "")
                if existing_tags_str:
                    tags = [
                        {"tag": t.strip(), "machine_tag": False}
                        for t in existing_tags_str.split(" ")
                        if t.strip()
                    ]
                    self.db.add_existing_tags(photo_id, tags)

                total_synced += 1

            total_pages = int(result["photos"]["pages"])
            if page >= total_pages:
                break
            page += 1

        logger.info("sync_complete", total=total_synced)
        return total_synced

    def download_photos(self, image_dir: Path, concurrency: int = 4) -> dict[str, int]:
        """Download all pending photos using Flickr API for URLs.

        Uses flickr.photos.getSizes to get proper CDN URLs instead of
        constructing static URLs which get rate-limited aggressively.
        Implements exponential backoff on 429 rate limits.

        Returns a dict with counts: {'downloaded': N, 'failed': N, 'skipped': N}.
        """
        import time

        import requests

        image_dir.mkdir(parents=True, exist_ok=True)
        pending = self.db.get_photos_by_status(download_status="pending")

        if not pending:
            logger.info("download_nothing_pending")
            return {"downloaded": 0, "failed": 0, "skipped": 0}

        stats = {"downloaded": 0, "failed": 0, "skipped": 0}
        consecutive_429s = 0
        base_delay = 2.0  # seconds between requests (slow and steady)
        logger.info("download_starting", count=len(pending))

        for photo in pending:
            flickr_id = photo["flickr_id"]

            # Check if already downloaded (any extension)
            existing = list(image_dir.glob(f"{flickr_id}.*"))
            if existing:
                self.db.update_download_status(photo["id"], "done")
                stats["skipped"] += 1
                continue

            # If we've hit too many 429s in a row, do a long cooldown
            if consecutive_429s >= 5:
                cooldown = min(300 * (consecutive_429s // 5), 1800)  # 5-30 min
                logger.warning(
                    "rate_limit_cooldown",
                    consecutive_429s=consecutive_429s,
                    cooldown_seconds=cooldown,
                )
                time.sleep(cooldown)
                consecutive_429s = 0  # reset after cooldown

            try:
                # Use Flickr API to get available sizes/URLs (with retry on 429)
                sizes = None
                for api_attempt in range(3):
                    try:
                        sizes_resp = self.flickr.photos.getSizes(photo_id=flickr_id)
                        sizes = sizes_resp["sizes"]["size"]
                        break
                    except Exception as api_err:
                        if "429" in str(api_err):
                            backoff = 2 ** (api_attempt + 2) * 15  # 60s, 120s, 240s
                            logger.info(
                                "api_429_backoff",
                                flickr_id=flickr_id,
                                attempt=api_attempt + 1,
                                backoff_seconds=backoff,
                            )
                            time.sleep(backoff)
                            consecutive_429s += 1
                            continue
                        raise

                if sizes is None:
                    consecutive_429s += 1
                    logger.warning("api_429_exhausted", flickr_id=flickr_id)
                    # Leave as pending for next run
                    continue

                # Prefer Large over Original (smaller files, less CDN load)
                url = None
                ext = ".jpg"
                for preferred in (
                    "Large 2048",
                    "Large 1600",
                    "Large",
                    "Original",
                    "Medium 800",
                ):
                    for s in sizes:
                        if s["label"] == preferred:
                            url = s["source"]
                            ext = Path(url).suffix or ".jpg"
                            break
                    if url:
                        break

                if not url and sizes:
                    url = sizes[-1]["source"]
                    ext = Path(url).suffix or ".jpg"

                if not url:
                    logger.warning("no_download_url", flickr_id=flickr_id)
                    self.db.update_download_status(photo["id"], "error")
                    stats["failed"] += 1
                    continue

                # Download with retry on 429
                dest = image_dir / f"{flickr_id}{ext}"
                max_retries = 3
                for attempt in range(max_retries):
                    resp = requests.get(url, timeout=120)
                    if resp.status_code == 429:
                        retry_after = int(resp.headers.get("Retry-After", 0))
                        backoff = max(retry_after, 2 ** (attempt + 2) * 5)  # 20s, 40s, 80s
                        logger.info(
                            "download_429_backoff",
                            flickr_id=flickr_id,
                            attempt=attempt + 1,
                            backoff_seconds=backoff,
                        )
                        time.sleep(backoff)
                        continue
                    resp.raise_for_status()
                    dest.write_bytes(resp.content)
                    self.db.update_download_status(photo["id"], "done")
                    stats["downloaded"] += 1
                    consecutive_429s = 0  # reset on success
                    break
                else:
                    # All retries exhausted — still 429'd
                    consecutive_429s += 1
                    logger.warning(
                        "download_429_exhausted",
                        flickr_id=flickr_id,
                        consecutive_429s=consecutive_429s,
                    )
                    # Don't mark as error; leave as pending for next cron run
                    continue

            except Exception as exc:
                logger.warning("download_error", flickr_id=flickr_id, error=str(exc))
                self.db.update_download_status(photo["id"], "error")
                stats["failed"] += 1
                consecutive_429s = 0

            # Progress logging every 25 photos
            done = stats["downloaded"] + stats["skipped"] + stats["failed"]
            if done % 25 == 0:
                logger.info(
                    "download_progress",
                    downloaded=stats["downloaded"],
                    skipped=stats["skipped"],
                    failed=stats["failed"],
                    remaining=len(pending) - done,
                )

            # Pace: 2 seconds between requests
            time.sleep(base_delay)

        logger.info("download_complete", **stats)
        return stats

    def push_tags(
        self,
        flickr_id: str,
        tags: list[str],
        merge_strategy: str = "merge",
    ) -> None:
        """Push tags to a single Flickr photo.

        Args:
            flickr_id: The Flickr photo ID.
            tags: List of tag strings to set.
            merge_strategy: 'merge' to append, 'replace' to overwrite.
        """
        tag_string = " ".join(f'"{t}"' if " " in t else t for t in tags)

        if merge_strategy == "replace":
            self.flickr.photos.setTags(photo_id=flickr_id, tags=tag_string)
        else:
            self.flickr.photos.addTags(photo_id=flickr_id, tags=tag_string)

        logger.info(
            "tags_pushed",
            flickr_id=flickr_id,
            count=len(tags),
            strategy=merge_strategy,
        )

    def push_all_approved(
        self,
        merge_strategy: str = "merge",
        dry_run: bool = False,
    ) -> dict[str, int]:
        """Push all approved tags to Flickr.

        Returns a dict with counts: {'pushed': N, 'skipped': N, 'failed': N}.
        """
        all_photos = self.db.get_all_photos()
        stats = {"pushed": 0, "skipped": 0, "failed": 0}

        for photo in all_photos:
            approved = self.db.get_approved_tags(photo["id"])
            if not approved:
                stats["skipped"] += 1
                continue

            tag_names = [t["tag"] for t in approved]

            if dry_run:
                logger.info(
                    "push_dry_run",
                    flickr_id=photo["flickr_id"],
                    tags=tag_names,
                )
                stats["pushed"] += 1
                continue

            try:
                self.push_tags(photo["flickr_id"], tag_names, merge_strategy)
                self.db.mark_pushed(photo["id"])
                stats["pushed"] += 1
            except Exception as exc:
                logger.error(
                    "push_failed",
                    flickr_id=photo["flickr_id"],
                    error=str(exc),
                )
                stats["failed"] += 1

        logger.info("push_complete", **stats)
        return stats
