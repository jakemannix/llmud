"""Backstabbr MCP Server.

Exposes tools for interacting with Backstabbr Diplomacy games via the
Model Context Protocol. Since Backstabbr has no official API, this server
scrapes the web interface using authenticated session cookies.

Usage:
    # Set your session cookie (grab from browser dev tools after signing in)
    export BACKSTABBR_SESSION_COOKIE="your-session-cookie-here"

    # Run the server
    backstabbr-mcp
"""

from __future__ import annotations

import os

from fastmcp import FastMCP

from backstabbr_mcp.client import BackstabbrClient

mcp = FastMCP(
    "backstabbr",
    instructions=(
        "MCP server for the Backstabbr online Diplomacy platform. "
        "Use these tools to view game state, check order submissions, "
        "read press messages, and monitor your Diplomacy games. "
        "Requires a valid session cookie from backstabbr.com."
    ),
)

_client: BackstabbrClient | None = None


def _get_client() -> BackstabbrClient:
    global _client
    if _client is None:
        cookie = os.environ.get("BACKSTABBR_SESSION_COOKIE", "")
        if not cookie:
            raise RuntimeError(
                "BACKSTABBR_SESSION_COOKIE environment variable is not set. "
                "Sign in to backstabbr.com in your browser, open dev tools, "
                "and copy the 'session' cookie value."
            )
        _client = BackstabbrClient(cookie)
    return _client


# ── Tools ─────────────────────────────────────────────────────────────


@mcp.tool()
async def list_games() -> str:
    """List your active Backstabbr Diplomacy games.

    Returns a summary of all games you're currently participating in,
    including game names, IDs, and current phase (year/season).
    """
    client = _get_client()
    games = await client.list_my_games()
    if not games:
        return "No active games found."

    lines = []
    for g in games:
        phase_str = f" — {g.phase.season.value.title()} {g.phase.year}" if g.phase else ""
        lines.append(f"• {g.name} (id: {g.game_id}, slug: {g.slug}){phase_str}")
    return "\n".join(lines)


@mcp.tool()
async def game_state(slug: str, game_id: str,
                     year: int | None = None,
                     season: str | None = None) -> str:
    """Get the current state of a Backstabbr Diplomacy game.

    Shows each country's supply center count and order submission status.

    Args:
        slug: The game's URL slug (e.g. "My-Cool-Game")
        game_id: The game's numeric ID
        year: Optional specific year to view
        season: Optional season ("spring", "fall", "winter")
    """
    client = _get_client()
    state = await client.get_game_state(slug, game_id, year, season)

    lines = [f"**{state.name}** — {state.phase.season.value.title()} {state.phase.year}", ""]
    for c in state.countries:
        status_icon = {
            "submitted": "✅",
            "not_submitted": "⏳",
            "eliminated": "💀",
        }.get(c.order_status.value, "❓")
        lines.append(f"{status_icon} {c.name}: {c.supply_centers} SCs ({c.order_status.value})")

    if not state.countries:
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


@mcp.tool()
async def list_press(slug: str, game_id: str) -> str:
    """List press (message) threads in a Backstabbr game.

    Press is the in-game messaging system for diplomatic communications.

    Args:
        slug: The game's URL slug
        game_id: The game's numeric ID
    """
    client = _get_client()
    threads = await client.list_press_threads(slug, game_id)

    if not threads:
        return "No press threads found."

    lines = []
    for t in threads:
        recipients = ", ".join(t.recipients) if t.recipients else "unknown recipients"
        lines.append(f"• [{t.thread_id}] {t.subject} ({recipients})")
    return "\n".join(lines)


@mcp.tool()
async def read_press(slug: str, game_id: str, thread_id: str) -> str:
    """Read messages in a press thread.

    Args:
        slug: The game's URL slug
        game_id: The game's numeric ID
        thread_id: The press thread ID
    """
    client = _get_client()
    messages = await client.get_press_thread(slug, game_id, thread_id)

    if not messages:
        return "No messages found in this thread."

    lines = []
    for m in messages:
        header = f"**{m.author}**" if m.author else "Unknown"
        if m.date:
            header += f" ({m.date})"
        lines.append(f"{header}:\n{m.body}\n")
    return "\n".join(lines)


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


def main() -> None:
    """Entry point for the backstabbr-mcp server."""
    mcp.run()


if __name__ == "__main__":
    main()
