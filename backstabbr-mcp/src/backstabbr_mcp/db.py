"""SQLite state layer for Backstabbr MCP server.

Stores scraped game snapshots, press threads, and session cookies on a
Modal Volume so state persists across serverless invocations.
"""

from __future__ import annotations

import json
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

# Default path — overridden by Modal Volume mount
DEFAULT_DB_PATH = Path("/data/backstabbr.db")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS kv (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS game_snapshots (
    game_id    TEXT NOT NULL,
    slug       TEXT NOT NULL,
    year       INTEGER,
    season     TEXT,
    data       TEXT NOT NULL,
    fetched_at REAL NOT NULL,
    PRIMARY KEY (game_id, year, season)
);

CREATE TABLE IF NOT EXISTS press_threads (
    game_id    TEXT NOT NULL,
    thread_id  TEXT NOT NULL,
    data       TEXT NOT NULL,
    fetched_at REAL NOT NULL,
    PRIMARY KEY (game_id, thread_id)
);

CREATE TABLE IF NOT EXISTS press_messages (
    game_id    TEXT NOT NULL,
    thread_id  TEXT NOT NULL,
    data       TEXT NOT NULL,
    fetched_at REAL NOT NULL,
    PRIMARY KEY (game_id, thread_id)
);

CREATE TABLE IF NOT EXISTS game_list (
    user_key   TEXT NOT NULL DEFAULT 'default',
    data       TEXT NOT NULL,
    fetched_at REAL NOT NULL,
    PRIMARY KEY (user_key)
);
"""


class StateDB:
    """SQLite-backed state store for cached Backstabbr data."""

    def __init__(self, db_path: Path | str = DEFAULT_DB_PATH) -> None:
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn: sqlite3.Connection | None = None

    def _get_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(str(self._db_path))
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.executescript(_SCHEMA)
        return self._conn

    @contextmanager
    def _tx(self) -> Iterator[sqlite3.Connection]:
        conn = self._get_conn()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None

    # ── Key-value store (session cookies, config) ─────────────────────

    def get_kv(self, key: str) -> str | None:
        row = self._get_conn().execute(
            "SELECT value FROM kv WHERE key = ?", (key,)
        ).fetchone()
        return row["value"] if row else None

    def set_kv(self, key: str, value: str) -> None:
        with self._tx() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO kv (key, value, updated_at) VALUES (?, ?, ?)",
                (key, value, time.time()),
            )

    # ── Session cookie ────────────────────────────────────────────────

    def get_session_cookie(self) -> str | None:
        return self.get_kv("session_cookie")

    def set_session_cookie(self, cookie: str) -> None:
        self.set_kv("session_cookie", cookie)

    # ── Game list cache ───────────────────────────────────────────────

    def get_cached_game_list(self, max_age_secs: float = 300) -> list[dict] | None:
        row = self._get_conn().execute(
            "SELECT data, fetched_at FROM game_list WHERE user_key = 'default'"
        ).fetchone()
        if row and (time.time() - row["fetched_at"]) < max_age_secs:
            return json.loads(row["data"])
        return None

    def cache_game_list(self, games: list[dict]) -> None:
        with self._tx() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO game_list (user_key, data, fetched_at) VALUES (?, ?, ?)",
                ("default", json.dumps(games), time.time()),
            )

    # ── Game snapshot cache ───────────────────────────────────────────

    def get_cached_game_state(self, game_id: str, year: int | None = None,
                              season: str | None = None,
                              max_age_secs: float = 120) -> dict | None:
        row = self._get_conn().execute(
            "SELECT data, fetched_at FROM game_snapshots "
            "WHERE game_id = ? AND year IS ? AND season IS ?",
            (game_id, year, season),
        ).fetchone()
        if row and (time.time() - row["fetched_at"]) < max_age_secs:
            return json.loads(row["data"])
        return None

    def cache_game_state(self, game_id: str, slug: str,
                         year: int | None, season: str | None,
                         data: dict) -> None:
        with self._tx() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO game_snapshots "
                "(game_id, slug, year, season, data, fetched_at) VALUES (?, ?, ?, ?, ?, ?)",
                (game_id, slug, year, season, json.dumps(data), time.time()),
            )

    # ── Press cache ───────────────────────────────────────────────────

    def get_cached_press_threads(self, game_id: str,
                                 max_age_secs: float = 120) -> list[dict] | None:
        row = self._get_conn().execute(
            "SELECT data, fetched_at FROM press_threads WHERE game_id = ?",
            (game_id,),
        ).fetchone()
        if row and (time.time() - row["fetched_at"]) < max_age_secs:
            return json.loads(row["data"])
        return None

    def cache_press_threads(self, game_id: str, threads: list[dict]) -> None:
        with self._tx() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO press_threads (game_id, thread_id, data, fetched_at) "
                "VALUES (?, ?, ?, ?)",
                (game_id, "_list", json.dumps(threads), time.time()),
            )

    def get_cached_press_messages(self, game_id: str, thread_id: str,
                                  max_age_secs: float = 60) -> list[dict] | None:
        row = self._get_conn().execute(
            "SELECT data, fetched_at FROM press_messages "
            "WHERE game_id = ? AND thread_id = ?",
            (game_id, thread_id),
        ).fetchone()
        if row and (time.time() - row["fetched_at"]) < max_age_secs:
            return json.loads(row["data"])
        return None

    def cache_press_messages(self, game_id: str, thread_id: str,
                             messages: list[dict]) -> None:
        with self._tx() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO press_messages "
                "(game_id, thread_id, data, fetched_at) VALUES (?, ?, ?, ?)",
                (game_id, thread_id, json.dumps(messages), time.time()),
            )

    # ── Game history (all snapshots for a game) ───────────────────────

    def get_game_history(self, game_id: str) -> list[dict]:
        rows = self._get_conn().execute(
            "SELECT year, season, data, fetched_at FROM game_snapshots "
            "WHERE game_id = ? ORDER BY year, season",
            (game_id,),
        ).fetchall()
        return [
            {"year": r["year"], "season": r["season"],
             "data": json.loads(r["data"]), "fetched_at": r["fetched_at"]}
            for r in rows
        ]
