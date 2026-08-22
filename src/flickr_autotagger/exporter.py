"""Export tags in various formats: JSON, CSV, and XMP sidecar."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

import structlog

from flickr_autotagger.db import StateDB

logger = structlog.get_logger()


def export_json(db: StateDB, output_path: Path) -> int:
    """Export all photo data with tags as JSON.

    Returns the number of photos exported.
    """
    photos = db.get_all_photos()
    export_data: list[dict[str, Any]] = []

    for photo in photos:
        pid = photo["id"]
        entry = {
            "flickr_id": photo["flickr_id"],
            "title": photo["title"],
            "description": photo["description"],
            "date_taken": photo["date_taken"],
            "existing_tags": [t["tag"] for t in db.get_existing_tags(pid)],
            "predicted_tags": [
                {"tag": t["tag"], "confidence": t["confidence"], "approved": bool(t["approved"])}
                for t in db.get_predicted_tags(pid)
            ],
            "download_status": photo["download_status"],
            "tag_status": photo["tag_status"],
            "push_status": photo["push_status"],
        }
        export_data.append(entry)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(export_data, f, indent=2, ensure_ascii=False)

    logger.info("export_json", path=str(output_path), count=len(export_data))
    return len(export_data)


def export_csv(db: StateDB, output_path: Path) -> int:
    """Export a flat CSV table of photos and their tags.

    Returns the number of rows exported.
    """
    photos = db.get_all_photos()

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "flickr_id",
                "title",
                "existing_tags",
                "predicted_tags",
                "predicted_confidences",
                "approved_tags",
                "download_status",
                "tag_status",
                "push_status",
            ]
        )

        for photo in photos:
            pid = photo["id"]
            existing = [t["tag"] for t in db.get_existing_tags(pid)]
            predicted = db.get_predicted_tags(pid)
            predicted_tags = [t["tag"] for t in predicted]
            confidences = [f"{t['confidence']:.3f}" for t in predicted]
            approved = [t["tag"] for t in predicted if t["approved"]]

            writer.writerow(
                [
                    photo["flickr_id"],
                    photo["title"],
                    "; ".join(existing),
                    "; ".join(predicted_tags),
                    "; ".join(confidences),
                    "; ".join(approved),
                    photo["download_status"],
                    photo["tag_status"],
                    photo["push_status"],
                ]
            )

    logger.info("export_csv", path=str(output_path), count=len(photos))
    return len(photos)


def export_xmp_sidecars(db: StateDB, image_dir: Path, output_dir: Path | None = None) -> int:
    """Generate XMP sidecar files for Lightroom/Darktable compatibility.

    Sidecar files are placed alongside the images (or in output_dir if specified).
    Returns the number of sidecar files created.
    """
    if output_dir is None:
        output_dir = image_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    photos = db.get_all_photos()
    count = 0

    for photo in photos:
        pid = photo["id"]
        predicted = db.get_predicted_tags(pid)
        approved = [t for t in predicted if t["approved"]]
        if not approved:
            continue

        flickr_id = photo["flickr_id"]
        tags = [t["tag"] for t in approved]

        xmp_content = _build_xmp(
            title=photo.get("title", ""),
            description=photo.get("description", ""),
            tags=tags,
        )

        # Find the image file to determine sidecar name
        sidecar_name = f"{flickr_id}.xmp"
        for ext in (".jpg", ".jpeg", ".png", ".gif", ".tiff", ".webp"):
            candidate = image_dir / f"{flickr_id}{ext}"
            if candidate.exists():
                sidecar_name = f"{flickr_id}{ext}.xmp"
                break

        sidecar_path = output_dir / sidecar_name
        sidecar_path.write_text(xmp_content, encoding="utf-8")
        count += 1

    logger.info("export_xmp", path=str(output_dir), count=count)
    return count


def _build_xmp(title: str, description: str, tags: list[str]) -> str:
    """Build an XMP sidecar XML string."""
    # XMP namespace declarations
    xmp = '<?xml version="1.0" encoding="UTF-8"?>\n'
    xmp += '<x:xmpmeta xmlns:x="adobe:ns:meta/">\n'
    xmp += ' <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">\n'
    xmp += "  <rdf:Description\n"
    xmp += '   xmlns:dc="http://purl.org/dc/elements/1.1/"\n'
    xmp += '   xmlns:lr="http://ns.adobe.com/lightroom/1.0/">\n'

    # Title
    if title:
        xmp += "   <dc:title>\n"
        xmp += "    <rdf:Alt>\n"
        xmp += f'     <rdf:li xml:lang="x-default">{_xml_escape(title)}</rdf:li>\n'
        xmp += "    </rdf:Alt>\n"
        xmp += "   </dc:title>\n"

    # Description
    if description:
        xmp += "   <dc:description>\n"
        xmp += "    <rdf:Alt>\n"
        xmp += f'     <rdf:li xml:lang="x-default">{_xml_escape(description)}</rdf:li>\n'
        xmp += "    </rdf:Alt>\n"
        xmp += "   </dc:description>\n"

    # Tags as dc:subject
    xmp += "   <dc:subject>\n"
    xmp += "    <rdf:Bag>\n"
    for tag in tags:
        xmp += f"     <rdf:li>{_xml_escape(tag)}</rdf:li>\n"
    xmp += "    </rdf:Bag>\n"
    xmp += "   </dc:subject>\n"

    xmp += "  </rdf:Description>\n"
    xmp += " </rdf:RDF>\n"
    xmp += "</x:xmpmeta>\n"

    return xmp


def _xml_escape(text: str) -> str:
    """Escape special XML characters."""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )
