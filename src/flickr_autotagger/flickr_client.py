"""Flickr API operations: sync metadata, download images, push tags."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import aiohttp
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
        """Download all pending photos concurrently.

        Returns a dict with counts: {'downloaded': N, 'failed': N, 'skipped': N}.
        """
        # Reset previously errored photos so they get retried
        conn = self.db.connect()
        conn.execute(
            "UPDATE photos SET download_status = 'pending' WHERE download_status = 'error'"
        )
        conn.commit()

        return asyncio.run(self._download_async(image_dir, concurrency))

    async def _download_async(self, image_dir: Path, concurrency: int) -> dict[str, int]:
        """Async download implementation using aiohttp with rate-limit backoff.

        Downloads in small batches to avoid flooding Flickr's API.
        """
        image_dir.mkdir(parents=True, exist_ok=True)
        pending = self.db.get_photos_by_status(download_status="pending")

        if not pending:
            logger.info("download_nothing_pending")
            return {"downloaded": 0, "failed": 0, "skipped": 0}

        logger.info("download_starting", count=len(pending), concurrency=concurrency)
        stats = {"downloaded": 0, "failed": 0, "skipped": 0}

        # Shared rate-limit state
        rate_limit_lock = asyncio.Lock()
        backoff_until = [0.0]

        batch_size = concurrency * 5  # process in small batches
        semaphore = asyncio.Semaphore(concurrency)

        async with aiohttp.ClientSession() as session:
            for i in range(0, len(pending), batch_size):
                batch = pending[i : i + batch_size]

                # Check global rate-limit before starting batch
                now = asyncio.get_event_loop().time()
                wait_time = backoff_until[0] - now
                if wait_time > 0:
                    logger.info("rate_limit_batch_wait", seconds=round(wait_time, 1))
                    await asyncio.sleep(wait_time)

                tasks = [
                    self._download_one(
                        session, semaphore, photo, image_dir, stats, rate_limit_lock, backoff_until
                    )
                    for photo in batch
                ]
                await asyncio.gather(*tasks)

                done = stats["downloaded"] + stats["skipped"]
                if done > 0 and done % 100 < batch_size:
                    logger.info(
                        "download_progress",
                        downloaded=stats["downloaded"],
                        failed=stats["failed"],
                        skipped=stats["skipped"],
                        remaining=len(pending) - i - len(batch),
                    )

                # Small pause between batches to be polite
                await asyncio.sleep(1.0)

        logger.info("download_complete", **stats)
        return stats

    async def _download_one(
        self,
        session: aiohttp.ClientSession,
        semaphore: asyncio.Semaphore,
        photo: dict[str, Any],
        image_dir: Path,
        stats: dict[str, int],
        rate_limit_lock: asyncio.Lock,
        backoff_until: list[float],
    ) -> None:
        """Download a single photo with retry on 429 rate limits."""
        url = photo.get("original_url", "")
        if not url:
            # Build URL from farm/server/id/secret if original_url not available
            url = (
                f"https://farm{photo['farm']}.staticflickr.com/"
                f"{photo['server']}/{photo['flickr_id']}_{photo['secret']}_b.jpg"
            )

        ext = Path(url).suffix or ".jpg"
        dest = image_dir / f"{photo['flickr_id']}{ext}"

        if dest.exists():
            self.db.update_download_status(photo["id"], "done")
            stats["skipped"] += 1
            return

        max_retries = 5
        base_delay = 30.0  # start with 30s backoff on 429

        for attempt in range(max_retries):
            # Wait if we're in a global rate-limit backoff
            now = asyncio.get_event_loop().time()
            wait_time = backoff_until[0] - now
            if wait_time > 0:
                logger.debug("rate_limit_waiting", seconds=round(wait_time, 1))
                await asyncio.sleep(wait_time)

            async with semaphore:
                try:
                    async with session.get(url, timeout=aiohttp.ClientTimeout(total=120)) as resp:
                        if resp.status == 429:
                            # Rate limited — set global backoff
                            retry_after = resp.headers.get("Retry-After")
                            delay = float(retry_after) if retry_after else base_delay * (2**attempt)
                            async with rate_limit_lock:
                                new_until = asyncio.get_event_loop().time() + delay
                                if new_until > backoff_until[0]:
                                    backoff_until[0] = new_until
                                    logger.warning(
                                        "rate_limited",
                                        delay=round(delay, 1),
                                        attempt=attempt + 1,
                                    )
                            await asyncio.sleep(delay)
                            continue  # retry

                        if resp.status != 200:
                            logger.warning(
                                "download_failed",
                                flickr_id=photo["flickr_id"],
                                status=resp.status,
                            )
                            self.db.update_download_status(photo["id"], "error")
                            stats["failed"] += 1
                            return

                        data = await resp.read()
                        dest.write_bytes(data)

                    self.db.update_download_status(photo["id"], "done")
                    logger.debug("downloaded", flickr_id=photo["flickr_id"], path=str(dest))
                    stats["downloaded"] += 1
                    return  # success

                except Exception as exc:
                    if attempt < max_retries - 1:
                        delay = base_delay * (2**attempt)
                        logger.warning(
                            "download_retry",
                            flickr_id=photo["flickr_id"],
                            error=str(exc),
                            delay=round(delay, 1),
                            attempt=attempt + 1,
                        )
                        await asyncio.sleep(delay)
                    else:
                        logger.warning(
                            "download_error",
                            flickr_id=photo["flickr_id"],
                            error=str(exc),
                        )
                        self.db.update_download_status(photo["id"], "error")
                        stats["failed"] += 1

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
