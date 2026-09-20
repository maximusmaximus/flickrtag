"""SQLite state management for tracking photos, tags, and sync status."""

from __future__ import annotations

import sqlite3
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import structlog

logger = structlog.get_logger()

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS photos (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    flickr_id       TEXT    UNIQUE NOT NULL,
    title           TEXT,
    description     TEXT,
    original_url    TEXT,
    farm            TEXT,
    server          TEXT,
    secret          TEXT,
    date_taken      TEXT,
    date_uploaded   TEXT,
    last_synced     TEXT,
    download_status TEXT    DEFAULT 'pending',
    tag_status      TEXT    DEFAULT 'pending',
    push_status     TEXT    DEFAULT 'pending',
    local_path      TEXT,
    -- Venice.ai analysis fields
    venice_status   TEXT    DEFAULT 'pending',
    ai_title        TEXT,
    ai_description  TEXT,
    scene_type      TEXT,
    mood            TEXT,
    technique       TEXT,
    colors          TEXT,
    location_guess  TEXT,
    time_of_day     TEXT,
    season_guess    TEXT,
    objects         TEXT
);

CREATE TABLE IF NOT EXISTS existing_tags (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    photo_id    INTEGER NOT NULL REFERENCES photos(id) ON DELETE CASCADE,
    tag         TEXT    NOT NULL,
    machine_tag INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS predicted_tags (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    photo_id    INTEGER NOT NULL REFERENCES photos(id) ON DELETE CASCADE,
    tag         TEXT    NOT NULL,
    confidence  REAL    NOT NULL,
    approved    INTEGER DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_photos_flickr_id ON photos(flickr_id);
CREATE INDEX IF NOT EXISTS idx_photos_download_status ON photos(download_status);
CREATE INDEX IF NOT EXISTS idx_photos_tag_status ON photos(tag_status);
CREATE INDEX IF NOT EXISTS idx_photos_push_status ON photos(push_status);
CREATE INDEX IF NOT EXISTS idx_existing_tags_photo ON existing_tags(photo_id);
CREATE INDEX IF NOT EXISTS idx_predicted_tags_photo ON predicted_tags(photo_id);
"""

# Migration SQL for existing databases that don't have Venice columns yet
MIGRATION_VENICE_SQL = """
ALTER TABLE photos ADD COLUMN venice_status TEXT DEFAULT 'pending';
ALTER TABLE photos ADD COLUMN ai_title TEXT;
ALTER TABLE photos ADD COLUMN ai_description TEXT;
ALTER TABLE photos ADD COLUMN scene_type TEXT;
ALTER TABLE photos ADD COLUMN mood TEXT;
ALTER TABLE photos ADD COLUMN technique TEXT;
ALTER TABLE photos ADD COLUMN colors TEXT;
ALTER TABLE photos ADD COLUMN location_guess TEXT;
ALTER TABLE photos ADD COLUMN time_of_day TEXT;
ALTER TABLE photos ADD COLUMN season_guess TEXT;
ALTER TABLE photos ADD COLUMN objects TEXT;
"""


class StateDB:
    """SQLite-backed state database for tracking the full photo pipeline."""

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self._conn: sqlite3.Connection | None = None

    def connect(self) -> sqlite3.Connection:
        """Return a connection to the SQLite database (lazy, reusable)."""
        if self._conn is None:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            self._conn = sqlite3.connect(str(self.db_path))
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA foreign_keys=ON")
        return self._conn

    @contextmanager
    def transaction(self) -> Generator[sqlite3.Connection, None, None]:
        """Context manager for atomic database writes."""
        conn = self.connect()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    def init_db(self) -> None:
        """Create database tables if they don't exist, and apply migrations."""
        with self.transaction() as conn:
            conn.executescript(SCHEMA_SQL)

        # Apply Venice migration for existing databases
        self._migrate_venice()
        logger.info("database_initialized", path=str(self.db_path))

    def _migrate_venice(self) -> None:
        """Add Venice columns to existing databases (idempotent)."""
        conn = self.connect()
        # Check if venice_status column exists
        cursor = conn.execute("PRAGMA table_info(photos)")
        existing_cols = {row["name"] for row in cursor.fetchall()}

        if "venice_status" not in existing_cols:
            logger.info("migrating_venice_columns")
            for stmt in MIGRATION_VENICE_SQL.strip().split(";"):
                stmt = stmt.strip()
                if stmt:
                    try:
                        conn.execute(stmt)
                    except Exception:
                        pass  # Column may already exist
            conn.commit()
            # Create index if missing
            try:
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_photos_venice_status "
                    "ON photos(venice_status)"
                )
                conn.commit()
            except Exception:
                pass

    def upsert_photo(self, photo_data: dict[str, Any]) -> int:
        """Insert or update a photo record. Returns the internal photo ID."""
        with self.transaction() as conn:
            conn.execute(
                """
                INSERT INTO photos (flickr_id, title, description, original_url,
                                    farm, server, secret, date_taken, date_uploaded, last_synced)
                VALUES (:flickr_id, :title, :description, :original_url,
                        :farm, :server, :secret, :date_taken, :date_uploaded, :last_synced)
                ON CONFLICT(flickr_id) DO UPDATE SET
                    title = excluded.title,
                    description = excluded.description,
                    original_url = excluded.original_url,
                    farm = excluded.farm,
                    server = excluded.server,
                    secret = excluded.secret,
                    date_taken = excluded.date_taken,
                    date_uploaded = excluded.date_uploaded,
                    last_synced = excluded.last_synced
                """,
                photo_data,
            )
            row = conn.execute(
                "SELECT id FROM photos WHERE flickr_id = ?", (photo_data["flickr_id"],)
            ).fetchone()
            return int(row["id"])

    def get_photos_by_status(
        self,
        *,
        download_status: str | None = None,
        tag_status: str | None = None,
        push_status: str | None = None,
        venice_status: str | None = None,
    ) -> list[dict[str, Any]]:
        """Retrieve photos filtered by one or more status fields."""
        conditions: list[str] = []
        params: list[str] = []
        if download_status is not None:
            conditions.append("download_status = ?")
            params.append(download_status)
        if tag_status is not None:
            conditions.append("tag_status = ?")
            params.append(tag_status)
        if push_status is not None:
            conditions.append("push_status = ?")
            params.append(push_status)
        if venice_status is not None:
            conditions.append("venice_status = ?")
            params.append(venice_status)

        where_clause = " AND ".join(conditions) if conditions else "1=1"
        conn = self.connect()
        rows = conn.execute(f"SELECT * FROM photos WHERE {where_clause}", params).fetchall()
        return [dict(row) for row in rows]

    def get_photo_by_flickr_id(self, flickr_id: str) -> dict[str, Any] | None:
        """Retrieve a single photo by its Flickr ID."""
        conn = self.connect()
        row = conn.execute("SELECT * FROM photos WHERE flickr_id = ?", (flickr_id,)).fetchone()
        return dict(row) if row else None

    def add_existing_tags(self, photo_id: int, tags: list[dict[str, Any]]) -> None:
        """Store existing Flickr tags for a photo (replaces previous)."""
        with self.transaction() as conn:
            conn.execute("DELETE FROM existing_tags WHERE photo_id = ?", (photo_id,))
            conn.executemany(
                "INSERT INTO existing_tags (photo_id, tag, machine_tag) VALUES (?, ?, ?)",
                [(photo_id, t["tag"], int(t.get("machine_tag", False))) for t in tags],
            )

    def add_predicted_tags(self, photo_id: int, tags: list[tuple[str, float]]) -> None:
        """Store AI-predicted tags for a photo (replaces previous predictions)."""
        with self.transaction() as conn:
            conn.execute("DELETE FROM predicted_tags WHERE photo_id = ?", (photo_id,))
            conn.executemany(
                "INSERT INTO predicted_tags (photo_id, tag, confidence) VALUES (?, ?, ?)",
                [(photo_id, tag, confidence) for tag, confidence in tags],
            )
            conn.execute("UPDATE photos SET tag_status = 'done' WHERE id = ?", (photo_id,))

    def approve_tags(self, photo_id: int, tag_names: list[str] | None = None) -> None:
        """Approve predicted tags for pushing. If tag_names is None, approve all."""
        with self.transaction() as conn:
            if tag_names is None:
                conn.execute(
                    "UPDATE predicted_tags SET approved = 1 WHERE photo_id = ?",
                    (photo_id,),
                )
            else:
                placeholders = ",".join("?" * len(tag_names))
                conn.execute(
                    f"UPDATE predicted_tags SET approved = 1 "
                    f"WHERE photo_id = ? AND tag IN ({placeholders})",
                    [photo_id, *tag_names],
                )

    def get_approved_tags(self, photo_id: int) -> list[dict[str, Any]]:
        """Get all approved predicted tags for a photo."""
        conn = self.connect()
        rows = conn.execute(
            "SELECT tag, confidence FROM predicted_tags WHERE photo_id = ? AND approved = 1",
            (photo_id,),
        ).fetchall()
        return [dict(row) for row in rows]

    def get_existing_tags(self, photo_id: int) -> list[dict[str, Any]]:
        """Get all existing Flickr tags for a photo."""
        conn = self.connect()
        rows = conn.execute(
            "SELECT tag, machine_tag FROM existing_tags WHERE photo_id = ?",
            (photo_id,),
        ).fetchall()
        return [dict(row) for row in rows]

    def get_predicted_tags(self, photo_id: int) -> list[dict[str, Any]]:
        """Get all predicted tags for a photo."""
        conn = self.connect()
        rows = conn.execute(
            "SELECT tag, confidence, approved FROM predicted_tags WHERE photo_id = ?",
            (photo_id,),
        ).fetchall()
        return [dict(row) for row in rows]

    def mark_pushed(self, photo_id: int) -> None:
        """Mark a photo's tags as pushed to Flickr."""
        with self.transaction() as conn:
            conn.execute("UPDATE photos SET push_status = 'pushed' WHERE id = ?", (photo_id,))

    def update_download_status(self, photo_id: int, status: str) -> None:
        """Update the download status of a photo."""
        with self.transaction() as conn:
            conn.execute("UPDATE photos SET download_status = ? WHERE id = ?", (status, photo_id))

    def update_tag_status(self, photo_id: int, status: str) -> None:
        """Update the tag status of a photo."""
        with self.transaction() as conn:
            conn.execute("UPDATE photos SET tag_status = ? WHERE id = ?", (status, photo_id))

    def get_all_photos(self) -> list[dict[str, Any]]:
        """Retrieve all photos."""
        conn = self.connect()
        rows = conn.execute("SELECT * FROM photos ORDER BY id").fetchall()
        return [dict(row) for row in rows]

    def get_stats(self) -> dict[str, Any]:
        """Get summary statistics about the database state."""
        conn = self.connect()
        stats: dict[str, Any] = {}

        row = conn.execute("SELECT COUNT(*) as total FROM photos").fetchone()
        stats["total_photos"] = row["total"] if row else 0

        for status_col in ("download_status", "tag_status", "push_status"):
            rows = conn.execute(
                f"SELECT {status_col} as status, COUNT(*) as count "
                f"FROM photos GROUP BY {status_col}"
            ).fetchall()
            stats[status_col] = {row["status"]: row["count"] for row in rows}

        row = conn.execute(
            "SELECT COUNT(*) as count FROM predicted_tags WHERE approved = 1"
        ).fetchone()
        stats["approved_tags"] = row["count"] if row else 0

        return stats

    def close(self) -> None:
        """Close the database connection."""
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    # ── Venice.ai analysis methods ──────────────────────────────────────

    def store_venice_analysis(self, photo_id: int, analysis: dict[str, Any]) -> None:
        """Store Venice.ai structured analysis results for a photo."""
        import json as _json

        with self.transaction() as conn:
            conn.execute(
                """
                UPDATE photos SET
                    venice_status = 'done',
                    ai_title = ?,
                    ai_description = ?,
                    scene_type = ?,
                    mood = ?,
                    technique = ?,
                    colors = ?,
                    location_guess = ?,
                    time_of_day = ?,
                    season_guess = ?,
                    objects = ?,
                    tag_status = 'done'
                WHERE id = ?
                """,
                (
                    analysis.get("title_suggestion", ""),
                    analysis.get("description", ""),
                    analysis.get("scene_type", ""),
                    analysis.get("mood", ""),
                    analysis.get("technique", ""),
                    _json.dumps(analysis.get("colors", [])),
                    analysis.get("location_guess", ""),
                    analysis.get("time_of_day", ""),
                    analysis.get("season_guess", ""),
                    _json.dumps(analysis.get("objects", [])),
                    photo_id,
                ),
            )

    def get_photos_needing_venice(self) -> list[dict[str, Any]]:
        """Get all downloaded photos that haven't been analyzed by Venice yet."""
        conn = self.connect()
        rows = conn.execute(
            "SELECT * FROM photos WHERE download_status = 'done' "
            "AND (venice_status = 'pending' OR venice_status IS NULL) "
            "ORDER BY id"
        ).fetchall()
        return [dict(row) for row in rows]

    def update_venice_status(self, photo_id: int, status: str) -> None:
        """Update the Venice analysis status of a photo."""
        with self.transaction() as conn:
            conn.execute(
                "UPDATE photos SET venice_status = ? WHERE id = ?", (status, photo_id)
            )

    def get_venice_analysis(self, photo_id: int) -> dict[str, Any] | None:
        """Get the Venice analysis fields for a photo."""
        import json as _json

        conn = self.connect()
        row = conn.execute(
            "SELECT ai_title, ai_description, scene_type, mood, technique, "
            "colors, location_guess, time_of_day, season_guess, objects "
            "FROM photos WHERE id = ?",
            (photo_id,),
        ).fetchone()

        if row is None:
            return None

        result = dict(row)
        # Parse JSON fields
        for json_field in ("colors", "objects"):
            val = result.get(json_field)
            if val and isinstance(val, str):
                try:
                    result[json_field] = _json.loads(val)
                except _json.JSONDecodeError:
                    result[json_field] = []
        return result
