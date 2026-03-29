"""Backstabbr MCP Server.

Exposes tools for interacting with Backstabbr Diplomacy games via the
Model Context Protocol. Runs as an HTTP (streamable) server, designed to
be deployed on Modal with SQLite state on a persistent Volume.

Since Backstabbr has no official API, this server scrapes the web interface
using authenticated session cookies, caching results in SQLite.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict
from pathlib import Path

from fastmcp import FastMCP

from backstabbr_mcp.client import BackstabbrClient
from backstabbr_mcp.db import StateDB

# DB path — on Modal this is a Volume mount, locally falls back to ./data/
DB_PATH = Path(os.environ.get("BACKSTABBR_DB_PATH", "/data/backstabbr.db"))

mcp = FastMCP(
    "backstabbr",
    instructions=(
        "MCP server for the Backstabbr online Diplomacy platform. "
        "Use these tools to view game state, check order submissions, "
        "read press messages, and monitor your Diplomacy games. "
        "State is cached in SQLite on a persistent volume. "
        "Use set_session_cookie to configure authentication."
    ),
)

_db: StateDB | None = None
_client: BackstabbrClient | None = None


def _get_db() -> StateDB:
    global _db
    if _db is None:
        _db = StateDB(DB_PATH)
    return _db


def _get_client() -> BackstabbrClient:
    global _client
    db = _get_db()
    cookie = db.get_session_cookie()
    if not cookie:
        # Fall back to env var for initial setup
        cookie = os.environ.get("BACKSTABBR_SESSION_COOKIE", "")
    if not cookie:
        raise RuntimeError(
            "No session cookie configured. Use the set_session_cookie tool "
            "to provide your backstabbr.com session cookie, or set the "
            "BACKSTABBR_SESSION_COOKIE environment variable."
        )
    if _client is None:
        _client = BackstabbrClient(cookie)
    return _client


def _reset_client() -> None:
    """Force re-creation of the HTTP client (e.g. after cookie update)."""
    global _client
    if _client is not None:
        # fire-and-forget close; we're sync here
        _client = None


# ── Session management ────────────────────────────────────────────────


@mcp.tool()
async def set_session_cookie(cookie: str) -> str:
    """Store a Backstabbr session cookie for authentication.

    Get this by signing into backstabbr.com in your browser, opening dev tools
    (Application > Cookies), and copying the value of the 'session' cookie.

    Args:
        cookie: The session cookie value from backstabbr.com
    """
    db = _get_db()
    db.set_session_cookie(cookie)
    _reset_client()
    return "Session cookie saved. You can now use the other tools to interact with Backstabbr."


@mcp.tool()
async def check_auth() -> str:
    """Check if a valid session cookie is configured."""
    db = _get_db()
    cookie = db.get_session_cookie()
    if cookie:
        return f"Session cookie is set (length: {len(cookie)} chars). Use list_games to verify it works."
    env_cookie = os.environ.get("BACKSTABBR_SESSION_COOKIE", "")
    if env_cookie:
        return "Using session cookie from BACKSTABBR_SESSION_COOKIE env var."
    return "No session cookie configured. Use set_session_cookie to provide one."


# ── Game tools ────────────────────────────────────────────────────────


@mcp.tool()
async def list_games(force_refresh: bool = False) -> str:
    """List your active Backstabbr Diplomacy games.

    Returns a summary of all games you're currently participating in,
    including game names, IDs, and current phase (year/season).
    Results are cached for 5 minutes.

    Args:
        force_refresh: Skip cache and fetch fresh data from backstabbr.com
    """
    db = _get_db()

    if not force_refresh:
        cached = db.get_cached_game_list()
        if cached is not None:
            lines = ["(cached)"]
            for g in cached:
                phase_str = ""
                if g.get("phase"):
                    p = g["phase"]
                    phase_str = f" — {p['season'].title()} {p['year']}"
                lines.append(f"• {g['name']} (id: {g['game_id']}, slug: {g['slug']}){phase_str}")
            return "\n".join(lines)

    client = _get_client()
    games = await client.list_my_games()
    if not games:
        return "No active games found."

    games_data = [asdict(g) for g in games]
    # Serialize enum values for JSON storage
    for g in games_data:
        if g.get("phase") and g["phase"].get("season"):
            g["phase"]["season"] = g["phase"]["season"]
    db.cache_game_list(games_data)

    lines = []
    for g in games:
        phase_str = f" — {g.phase.season.value.title()} {g.phase.year}" if g.phase else ""
        lines.append(f"• {g.name} (id: {g.game_id}, slug: {g.slug}){phase_str}")
    return "\n".join(lines)


@mcp.tool()
async def game_state(slug: str, game_id: str,
                     year: int | None = None,
                     season: str | None = None,
                     force_refresh: bool = False) -> str:
    """Get the current state of a Backstabbr Diplomacy game.

    Shows each country's supply center count and order submission status.
    Results are cached for 2 minutes.

    Args:
        slug: The game's URL slug (e.g. "My-Cool-Game")
        game_id: The game's numeric ID
        year: Optional specific year to view
        season: Optional season ("spring", "fall", "winter")
        force_refresh: Skip cache and fetch fresh data
    """
    db = _get_db()

    if not force_refresh:
        cached = db.get_cached_game_state(game_id, year, season)
        if cached is not None:
            return _format_game_state(cached, cached=True)

    client = _get_client()
    state = await client.get_game_state(slug, game_id, year, season)
    state_data = asdict(state)
    db.cache_game_state(game_id, slug, year, season, state_data)

    return _format_game_state(state_data, cached=False)


def _format_game_state(data: dict, cached: bool = False) -> str:
    phase = data.get("phase", {})
    season_str = phase.get("season", "spring")
    if isinstance(season_str, str):
        season_str = season_str.title()
    year = phase.get("year", "?")

    prefix = "(cached) " if cached else ""
    lines = [f"{prefix}**{data.get('name', '?')}** — {season_str} {year}", ""]

    countries = data.get("countries", [])
    for c in countries:
        status_val = c.get("order_status", "not_submitted")
        status_icon = {
            "submitted": "✅",
            "not_submitted": "⏳",
            "eliminated": "💀",
        }.get(status_val, "❓")
        lines.append(f"{status_icon} {c['name']}: {c.get('supply_centers', 0)} SCs ({status_val})")

    if not countries:
        lines.append("(Could not parse country data from page — HTML structure may have changed)")

    return "\n".join(lines)


@mcp.tool()
async def order_status(slug: str, game_id: str) -> str:
    """Check which countries have submitted orders in a game.

    Useful for knowing who you're still waiting on before adjudication.

    Args:
        slug: The game's URL slug
        game_id: The game's numeric ID
    """
    client = _get_client()
    statuses = await client.get_order_status(slug, game_id)

    if not statuses:
        return "Could not determine order status — page structure may have changed."

    lines = []
    for country, status in sorted(statuses.items()):
        icon = "✅" if status.value == "submitted" else "⏳"
        lines.append(f"{icon} {country}: {status.value}")
    return "\n".join(lines)


# ── Press tools ───────────────────────────────────────────────────────


@mcp.tool()
async def list_press(slug: str, game_id: str,
                     force_refresh: bool = False) -> str:
    """List press (message) threads in a Backstabbr game.

    Press is the in-game messaging system for diplomatic communications.
    Results are cached for 2 minutes.

    Args:
        slug: The game's URL slug
        game_id: The game's numeric ID
        force_refresh: Skip cache and fetch fresh data
    """
    db = _get_db()

    if not force_refresh:
        cached = db.get_cached_press_threads(game_id)
        if cached is not None:
            return _format_press_threads(cached, cached=True)

    client = _get_client()
    threads = await client.list_press_threads(slug, game_id)

    if not threads:
        return "No press threads found."

    threads_data = [asdict(t) for t in threads]
    db.cache_press_threads(game_id, threads_data)

    return _format_press_threads(threads_data, cached=False)


def _format_press_threads(threads: list[dict], cached: bool = False) -> str:
    if not threads:
        return "No press threads found."
    prefix = "(cached) " if cached else ""
    lines = [f"{prefix}Press threads:"]
    for t in threads:
        recipients = ", ".join(t.get("recipients", [])) or "unknown recipients"
        lines.append(f"• [{t['thread_id']}] {t.get('subject', '?')} ({recipients})")
    return "\n".join(lines)


@mcp.tool()
async def read_press(slug: str, game_id: str, thread_id: str,
                     force_refresh: bool = False) -> str:
    """Read messages in a press thread. Cached for 1 minute.

    Args:
        slug: The game's URL slug
        game_id: The game's numeric ID
        thread_id: The press thread ID
        force_refresh: Skip cache and fetch fresh data
    """
    db = _get_db()

    if not force_refresh:
        cached = db.get_cached_press_messages(game_id, thread_id)
        if cached is not None:
            return _format_press_messages(cached, cached=True)

    client = _get_client()
    messages = await client.get_press_thread(slug, game_id, thread_id)

    if not messages:
        return "No messages found in this thread."

    messages_data = [asdict(m) for m in messages]
    db.cache_press_messages(game_id, thread_id, messages_data)

    return _format_press_messages(messages_data, cached=False)


def _format_press_messages(messages: list[dict], cached: bool = False) -> str:
    if not messages:
        return "No messages found in this thread."
    prefix = "(cached) " if cached else ""
    lines = [prefix.strip()] if cached else []
    for m in messages:
        header = f"**{m.get('author', 'Unknown')}**"
        if m.get("date"):
            header += f" ({m['date']})"
        lines.append(f"{header}:\n{m.get('body', '')}\n")
    return "\n".join(lines)


# ── Utility tools ─────────────────────────────────────────────────────


@mcp.tool()
async def game_url(slug: str, game_id: str,
                   year: int | None = None,
                   season: str | None = None) -> str:
    """Get the URL for a Backstabbr game page.

    Args:
        slug: The game's URL slug
        game_id: The game's numeric ID
        year: Optional specific year
        season: Optional season
    """
    url = f"https://www.backstabbr.com/game/{slug}/{game_id}"
    if year and season:
        url += f"/{year}/{season}"
    return url


@mcp.tool()
async def game_history(game_id: str) -> str:
    """View cached historical snapshots for a game.

    Shows all previously fetched game states from the local database.
    Useful for tracking how a game has evolved over time.

    Args:
        game_id: The game's numeric ID
    """
    db = _get_db()
    history = db.get_game_history(game_id)
    if not history:
        return "No cached history for this game. Fetch game_state first to start building history."

    lines = [f"Cached snapshots for game {game_id}:", ""]
    for entry in history:
        phase = f"{entry.get('season', '?')} {entry.get('year', '?')}"
        countries = entry["data"].get("countries", [])
        sc_summary = ", ".join(
            f"{c['name']}: {c.get('supply_centers', 0)}"
            for c in countries
        )
        lines.append(f"• {phase} — {sc_summary or '(no country data)'}")
    return "\n".join(lines)


@mcp.tool()
async def debug_page(path: str) -> str:
    """Fetch a raw Backstabbr page and return a summary of its HTML structure.

    Useful for reverse-engineering the site when parsers break. Returns the
    page's tag structure, CSS classes, and any embedded JavaScript variables.

    Args:
        path: URL path to fetch (e.g. "/game/My-Game/12345" or "/sandbox/12345")
    """
    client = _get_client()
    soup = await client._get(path)

    lines = ["## Page structure", ""]

    title = soup.select_one("title")
    if title:
        lines.append(f"**Title**: {title.get_text(strip=True)}")

    lines.append("")
    lines.append("### Key elements (class names)")
    seen_classes: set[str] = set()
    for el in soup.select("[class]"):
        classes = " ".join(el.get("class", []))
        if classes and classes not in seen_classes:
            seen_classes.add(classes)
            text_preview = el.get_text(strip=True)[:80]
            if text_preview:
                lines.append(f"- `<{el.name} class=\"{classes}\">` — {text_preview}")
    if len(lines) > 100:
        lines = lines[:100]
        lines.append("... (truncated)")

    js_state = client._parse_js_game_state(soup)
    if js_state:
        lines.append("")
        lines.append("### Embedded JS variables")
        for k, v in js_state.items():
            preview = v[:200] if len(v) > 200 else v
            lines.append(f"- `{k}` = {preview}")

    return "\n".join(lines)


# ── Entry points ──────────────────────────────────────────────────────


def main() -> None:
    """Entry point for local development (stdio transport)."""
    mcp.run()


def create_http_app():
    """Create the HTTP ASGI app for deployment (Modal, uvicorn, etc.)."""
    return mcp.http_app()


if __name__ == "__main__":
    main()
