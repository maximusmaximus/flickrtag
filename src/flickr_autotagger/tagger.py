"""CLIP inference pipeline for zero-shot image tagging."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import structlog
import torch
from PIL import Image

logger = structlog.get_logger()

# Lazy-loaded globals to avoid import overhead
_model: Any = None
_preprocess: Any = None
_tokenizer: Any = None


def _load_model(model_name: str = "ViT-B-32", pretrained: str = "openai") -> None:
    """Load the CLIP model, preprocessing, and tokenizer (once)."""
    global _model, _preprocess, _tokenizer
    if _model is not None:
        return

    import open_clip

    logger.info("clip_loading", model=model_name, pretrained=pretrained)
    _model, _, _preprocess = open_clip.create_model_and_transforms(
        model_name, pretrained=pretrained
    )
    _tokenizer = open_clip.get_tokenizer(model_name)
    _model.eval()
    logger.info("clip_loaded", model=model_name)


class Tagger:
    """CLIP-based zero-shot image tagger."""

    def __init__(
        self,
        model_name: str = "ViT-B-32",
        pretrained: str = "openai",
    ) -> None:
        self.model_name = model_name
        self.pretrained = pretrained
        _load_model(model_name, pretrained)

    def predict(
        self,
        image_path: Path,
        candidate_tags: list[str],
        threshold: float = 0.25,
        max_tags: int = 15,
    ) -> list[tuple[str, float]]:
        """Predict tags for a single image using CLIP zero-shot classification.

        Args:
            image_path: Path to the image file.
            candidate_tags: List of candidate tag strings.
            threshold: Minimum confidence score (0.0–1.0) to include a tag.
            max_tags: Maximum number of tags to return.

        Returns:
            List of (tag, confidence) tuples, sorted by confidence descending.
        """
        assert _model is not None and _preprocess is not None and _tokenizer is not None

        try:
            image = Image.open(image_path).convert("RGB")
        except Exception as exc:
            logger.warning("image_load_failed", path=str(image_path), error=str(exc))
            return []

        image_input = _preprocess(image).unsqueeze(0)  # type: ignore[union-attr]

        # Prepare text prompts: "a photo of {tag}"
        text_prompts = [f"a photo of {tag}" for tag in candidate_tags]
        text_tokens = _tokenizer(text_prompts)

        with torch.no_grad():
            image_features = _model.encode_image(image_input)
            text_features = _model.encode_text(text_tokens)

            # Normalize features
            image_features = image_features / image_features.norm(dim=-1, keepdim=True)
            text_features = text_features / text_features.norm(dim=-1, keepdim=True)

            # Compute similarity (cosine)
            similarity = (image_features @ text_features.T).squeeze(0)
            probs = similarity.softmax(dim=-1).cpu().numpy()

        # Collect results above threshold
        results: list[tuple[str, float]] = []
        for tag, score in zip(candidate_tags, probs):
            if score >= threshold:
                results.append((tag, float(score)))

        # Sort by confidence descending and limit
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:max_tags]

    def tag_all_pending(
        self,
        db: Any,
        image_dir: Path,
        candidate_tags: list[str],
        threshold: float = 0.25,
        max_tags: int = 15,
    ) -> dict[str, int]:
        """Process all un-tagged photos in the database.

        Args:
            db: StateDB instance.
            image_dir: Directory containing downloaded images.
            candidate_tags: List of candidate tag strings.
            threshold: Minimum confidence score.
            max_tags: Maximum tags per photo.

        Returns:
            Dict with counts: {'tagged': N, 'failed': N, 'skipped': N}.
        """
        pending = db.get_photos_by_status(tag_status="pending", download_status="done")
        stats = {"tagged": 0, "failed": 0, "skipped": 0}

        if not pending:
            logger.info("tag_nothing_pending")
            return stats

        logger.info("tagging_starting", count=len(pending))

        for photo in pending:
            flickr_id = photo["flickr_id"]

            # Find the downloaded image
            image_path = self._find_image(image_dir, flickr_id)
            if image_path is None:
                logger.warning("tag_image_not_found", flickr_id=flickr_id)
                stats["skipped"] += 1
                continue

            try:
                tags = self.predict(image_path, candidate_tags, threshold, max_tags)
                if tags:
                    db.add_predicted_tags(photo["id"], tags)
                    logger.info(
                        "tagged",
                        flickr_id=flickr_id,
                        count=len(tags),
                        top_tag=tags[0][0],
                        top_conf=f"{tags[0][1]:.3f}",
                    )
                else:
                    db.update_tag_status(photo["id"], "done")
                    logger.info("tagged_no_matches", flickr_id=flickr_id)
                stats["tagged"] += 1
            except Exception as exc:
                logger.error("tag_failed", flickr_id=flickr_id, error=str(exc))
                db.update_tag_status(photo["id"], "error")
                stats["failed"] += 1

        logger.info("tagging_complete", **stats)
        return stats

    @staticmethod
    def _find_image(image_dir: Path, flickr_id: str) -> Path | None:
        """Find a downloaded image by flickr_id (checks common extensions)."""
        for ext in (".jpg", ".jpeg", ".png", ".gif", ".tiff", ".webp"):
            candidate = image_dir / f"{flickr_id}{ext}"
            if candidate.exists():
                return candidate
        return None
