"""Venice.ai vision LLM tagger — Structured Scene Analyst.

Uses Venice.ai's OpenAI-compatible API with Qwen3-VL-235B to analyze
photos and produce rich structured metadata: tags, descriptions,
mood, technique, location guesses, and more.
"""

from __future__ import annotations

import base64
import json
import time
from pathlib import Path
from typing import Any

import structlog

from flickr_autotagger.config import Settings

logger = structlog.get_logger()

# Structured JSON schema for Venice.ai response_format
PHOTO_ANALYSIS_SCHEMA = {
    "type": "json_schema",
    "json_schema": {
        "name": "photo_analysis",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "title_suggestion": {
                    "type": "string",
                    "description": "A concise, evocative title for this photo",
                },
                "description": {
                    "type": "string",
                    "description": "2-3 sentence rich description of the scene, mood, and story",
                },
                "tags": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "10-20 specific, searchable tags",
                },
                "objects": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Specific things/subjects visible in the photo",
                },
                "scene_type": {
                    "type": "string",
                    "description": "Primary scene category",
                },
                "mood": {
                    "type": "string",
                    "description": "Emotional tone or atmosphere",
                },
                "colors": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "2-3 dominant colors",
                },
                "technique": {
                    "type": "string",
                    "description": "Photography technique used",
                },
                "location_guess": {
                    "type": "string",
                    "description": "Best guess at location, or 'unknown'",
                },
                "time_of_day": {
                    "type": "string",
                    "description": "Time of day: golden hour, night, midday, etc.",
                },
                "season_guess": {
                    "type": "string",
                    "description": "Best guess at season, or 'unknown'",
                },
            },
            "required": [
                "title_suggestion",
                "description",
                "tags",
                "objects",
                "scene_type",
                "mood",
                "colors",
                "technique",
                "location_guess",
                "time_of_day",
                "season_guess",
            ],
            "additionalProperties": False,
        },
    },
}

SYSTEM_PROMPT = """You are an expert photo analyst and Flickr tag specialist.
Analyze the photograph and return structured JSON describing it in detail.

Guidelines for tags:
- Provide 10-20 specific, searchable tags
- Include both broad discovery tags (e.g., "landscape") AND specific niche tags (e.g., "alpine meadow")
- Prefer tags that real Flickr users would search for
- Include relevant photography technique tags when applicable
- Use lowercase for tags
- If you can identify a specific location, landmark, or species, include it

Guidelines for descriptions:
- Write 2-3 vivid sentences describing the scene, mood, and story
- Be specific about what makes this photo interesting
- Mention notable composition, lighting, or technical qualities

Be honest — if you can't identify something, say "unknown" rather than guessing wildly."""


def _encode_image_base64(image_path: Path) -> str:
    """Read an image file and return its base64-encoded content."""
    data = image_path.read_bytes()
    return base64.b64encode(data).decode("utf-8")


def _get_mime_type(image_path: Path) -> str:
    """Determine the MIME type from the file extension."""
    ext = image_path.suffix.lower()
    mime_map = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".gif": "image/gif",
        ".webp": "image/webp",
        ".tiff": "image/tiff",
        ".tif": "image/tiff",
        ".bmp": "image/bmp",
    }
    return mime_map.get(ext, "image/jpeg")


class VeniceTagger:
    """Venice.ai vision LLM tagger using Qwen3-VL for structured scene analysis."""

    def __init__(self, settings: Settings) -> None:
        from openai import OpenAI

        self.settings = settings

        if not settings.VENICE_API_KEY:
            raise ValueError(
                "VENICE_API_KEY is required. Set it in your .env file or environment."
            )

        self.client = OpenAI(
            api_key=settings.VENICE_API_KEY,
            base_url="https://api.venice.ai/api/v1",
        )
        self.model = settings.VENICE_MODEL
        self.max_retries = 3
        self.base_delay = 1.0  # seconds between requests

    def analyze_photo(self, image_path: Path) -> dict[str, Any]:
        """Analyze a single photo and return structured metadata.

        Returns a dict with keys: title_suggestion, description, tags, objects,
        scene_type, mood, colors, technique, location_guess, time_of_day, season_guess.
        """
        if not image_path.exists():
            raise FileNotFoundError(f"Image not found: {image_path}")

        image_b64 = _encode_image_base64(image_path)
        mime_type = _get_mime_type(image_path)
        data_url = f"data:{mime_type};base64,{image_b64}"

        for attempt in range(self.max_retries):
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "image_url",
                                    "image_url": {"url": data_url},
                                },
                                {
                                    "type": "text",
                                    "text": "Analyze this photograph.",
                                },
                            ],
                        },
                    ],
                    response_format=PHOTO_ANALYSIS_SCHEMA,
                    max_tokens=1024,
                    temperature=0.3,
                )

                content = response.choices[0].message.content
                if content is None:
                    raise ValueError("Empty response from Venice.ai")

                result = json.loads(content)
                return result

            except json.JSONDecodeError as exc:
                logger.warning(
                    "venice_json_parse_error",
                    image=str(image_path),
                    attempt=attempt + 1,
                    error=str(exc),
                    raw_content=content[:200] if content else "None",
                )
                if attempt < self.max_retries - 1:
                    time.sleep(2 ** (attempt + 1))
                    continue
                raise

            except Exception as exc:
                error_str = str(exc)
                is_rate_limit = "429" in error_str or "rate" in error_str.lower()

                if is_rate_limit and attempt < self.max_retries - 1:
                    backoff = 2 ** (attempt + 2) * 5  # 20s, 40s, 80s
                    logger.info(
                        "venice_rate_limit",
                        image=str(image_path),
                        attempt=attempt + 1,
                        backoff_seconds=backoff,
                    )
                    time.sleep(backoff)
                    continue

                if attempt < self.max_retries - 1:
                    backoff = 2 ** (attempt + 1)
                    logger.warning(
                        "venice_api_error",
                        image=str(image_path),
                        attempt=attempt + 1,
                        error=error_str,
                        backoff_seconds=backoff,
                    )
                    time.sleep(backoff)
                    continue

                raise

        # Should never reach here, but just in case
        raise RuntimeError(f"All {self.max_retries} attempts failed for {image_path}")

    def tag_all_pending(
        self,
        db: Any,
        image_dir: Path,
        *,
        retag: bool = False,
    ) -> dict[str, int]:
        """Process all un-tagged (or all, if retag=True) photos using Venice.ai.

        Args:
            db: StateDB instance.
            image_dir: Directory containing downloaded images.
            retag: If True, re-analyze all photos regardless of current tag_status.

        Returns:
            Dict with counts: {'tagged': N, 'failed': N, 'skipped': N}.
        """
        if retag:
            # Get all downloaded photos
            pending = db.get_photos_by_status(download_status="done")
        else:
            # Only photos with venice_status pending
            pending = db.get_photos_needing_venice()

        stats = {"tagged": 0, "failed": 0, "skipped": 0}

        if not pending:
            logger.info("venice_nothing_pending")
            return stats

        logger.info("venice_tagging_starting", count=len(pending))

        for i, photo in enumerate(pending):
            flickr_id = photo["flickr_id"]

            # Find the downloaded image
            image_path = self._find_image(image_dir, flickr_id)
            if image_path is None:
                logger.warning("venice_image_not_found", flickr_id=flickr_id)
                stats["skipped"] += 1
                continue

            try:
                analysis = self.analyze_photo(image_path)

                # Store the Venice analysis in the database
                db.store_venice_analysis(photo["id"], analysis)

                # Also store predicted tags (with confidence=1.0 since LLM doesn't give scores)
                tags = [(tag, 1.0) for tag in analysis.get("tags", [])]
                if tags:
                    db.add_predicted_tags(photo["id"], tags)

                logger.info(
                    "venice_tagged",
                    flickr_id=flickr_id,
                    tag_count=len(analysis.get("tags", [])),
                    scene=analysis.get("scene_type", "?"),
                    mood=analysis.get("mood", "?"),
                    title=analysis.get("title_suggestion", "")[:50],
                )
                stats["tagged"] += 1

            except Exception as exc:
                logger.error(
                    "venice_tag_failed",
                    flickr_id=flickr_id,
                    error=str(exc),
                )
                db.update_venice_status(photo["id"], "error")
                stats["failed"] += 1

            # Progress logging every 25 photos
            done = stats["tagged"] + stats["failed"] + stats["skipped"]
            if done % 25 == 0:
                logger.info(
                    "venice_progress",
                    tagged=stats["tagged"],
                    failed=stats["failed"],
                    skipped=stats["skipped"],
                    remaining=len(pending) - done,
                )

            # Pace requests to stay within rate limits
            time.sleep(self.base_delay)

        logger.info("venice_tagging_complete", **stats)
        return stats

    @staticmethod
    def _find_image(image_dir: Path, flickr_id: str) -> Path | None:
        """Find a downloaded image by flickr_id (checks common extensions)."""
        for ext in (".jpg", ".jpeg", ".png", ".gif", ".tiff", ".webp"):
            candidate = image_dir / f"{flickr_id}{ext}"
            if candidate.exists():
                return candidate
        return None
