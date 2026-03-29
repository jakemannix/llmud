"""HTTP client for scraping Backstabbr game data.

Backstabbr has no official API. This module reverse-engineers the web interface
by making authenticated HTTP requests and parsing the HTML responses.

Authentication uses Firebase (Google accounts) with session cookies.
Game URLs follow the pattern: /game/{name}/{id}/{year}/{season}
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum

import httpx
from bs4 import BeautifulSoup

BASE_URL = "https://www.backstabbr.com"


class Season(str, Enum):
    SPRING = "spring"
    FALL = "fall"
    WINTER = "winter"


class OrderStatus(str, Enum):
    SUBMITTED = "submitted"
    NOT_SUBMITTED = "not_submitted"
    ELIMINATED = "eliminated"


@dataclass
class Country:
    name: str
    supply_centers: int = 0
    order_status: OrderStatus = OrderStatus.NOT_SUBMITTED


@dataclass
class GamePhase:
    year: int
    season: Season


@dataclass
class GameSummary:
    """Summary of a game from the game list or lobby."""
    name: str
    game_id: str
    slug: str
    phase: GamePhase | None = None
    players: int = 0


@dataclass
class GameState:
    """Full state of a game at a particular phase."""
    name: str
    game_id: str
    phase: GamePhase
    countries: list[Country] = field(default_factory=list)


@dataclass
class PressThread:
    thread_id: str
    recipients: list[str] = field(default_factory=list)
    subject: str = ""


@dataclass
class PressMessage:
    author: str
    date: str
    body: str


class BackstabbrClient:
    """HTTP client for interacting with Backstabbr via web scraping.

    Requires a valid session cookie obtained by signing in via the browser.
    """

    def __init__(self, session_cookie: str) -> None:
        self._http = httpx.AsyncClient(
            base_url=BASE_URL,
            cookies={"session": session_cookie},
            headers={
                "User-Agent": "backstabbr-mcp/0.1.0",
            },
            follow_redirects=True,
            timeout=30.0,
        )

    async def close(self) -> None:
        await self._http.aclose()

    async def _get(self, path: str) -> BeautifulSoup:
        """Fetch a page and return parsed HTML."""
        resp = await self._http.get(path)
        resp.raise_for_status()
        return BeautifulSoup(resp.text, "html.parser")

    # ── Game listing ──────────────────────────────────────────────────

    async def list_my_games(self) -> list[GameSummary]:
        """List games the authenticated user is participating in."""
        soup = await self._get("/")
        games: list[GameSummary] = []
        # Look for game links on the dashboard/home page
        for link in soup.select("a[href^='/game/']"):
            href = link.get("href", "")
            parts = href.strip("/").split("/")
            if len(parts) >= 3:
                # /game/{slug}/{id}[/{year}/{season}]
                slug = parts[1]
                game_id = parts[2]
                name = link.get_text(strip=True) or slug
                phase = None
                if len(parts) >= 5:
                    try:
                        phase = GamePhase(
                            year=int(parts[3]),
                            season=Season(parts[4].lower()),
                        )
                    except (ValueError, KeyError):
                        pass
                games.append(GameSummary(
                    name=name,
                    game_id=game_id,
                    slug=slug,
                    phase=phase,
                ))
        return games

    # ── Game state ────────────────────────────────────────────────────

    async def get_game_state(self, slug: str, game_id: str,
                             year: int | None = None,
                             season: str | None = None) -> GameState:
        """Fetch the current state of a game (countries, supply centers, order status)."""
        path = f"/game/{slug}/{game_id}"
        if year and season:
            path += f"/{year}/{season}"

        soup = await self._get(path)

        game_name = slug  # fallback
        title_el = soup.select_one("title")
        if title_el:
            game_name = title_el.get_text(strip=True).split("|")[0].strip()

        # Parse phase from page if not specified
        phase = GamePhase(year=year or 1901, season=Season(season or "spring"))

        countries = self._parse_countries(soup)

        return GameState(
            name=game_name,
            game_id=game_id,
            phase=phase,
            countries=countries,
        )

    def _parse_countries(self, soup: BeautifulSoup) -> list[Country]:
        """Extract country information from the game page HTML."""
        countries: list[Country] = []

        # Backstabbr renders a legend/sidebar with country info
        # Look for player list elements with country names and status
        for el in soup.select("[class*='player'], [class*='country'], [class*='legend']"):
            text = el.get_text(strip=True)
            if not text:
                continue

            # Try to extract country name and supply center count
            # Patterns vary, this handles common cases
            name_match = re.search(
                r"(Austria|England|France|Germany|Italy|Russia|Turkey)", text, re.IGNORECASE
            )
            if not name_match:
                continue

            country_name = name_match.group(1).title()
            sc_match = re.search(r"(\d+)\s*(?:SC|supply|center)", text, re.IGNORECASE)
            sc_count = int(sc_match.group(1)) if sc_match else 0

            status = OrderStatus.NOT_SUBMITTED
            if "submitted" in text.lower():
                status = OrderStatus.SUBMITTED
            elif "eliminated" in text.lower() or "defeated" in text.lower():
                status = OrderStatus.ELIMINATED

            countries.append(Country(
                name=country_name,
                supply_centers=sc_count,
                order_status=status,
            ))

        return countries

    # ── Press / messaging ─────────────────────────────────────────────

    async def list_press_threads(self, slug: str, game_id: str) -> list[PressThread]:
        """List press (message) threads for a game."""
        path = f"/game/{slug}/{game_id}/pressthread"
        soup = await self._get(path)
        threads: list[PressThread] = []

        for link in soup.select("a[href*='pressthread']"):
            href = link.get("href", "")
            thread_match = re.search(r"/pressthread/(\w+)", href)
            if thread_match:
                thread_id = thread_match.group(1)
                subject = link.get_text(strip=True) or f"Thread {thread_id}"
                threads.append(PressThread(
                    thread_id=thread_id,
                    subject=subject,
                ))

        return threads

    async def get_press_thread(self, slug: str, game_id: str,
                               thread_id: str) -> list[PressMessage]:
        """Fetch messages in a press thread."""
        path = f"/game/{slug}/{game_id}/pressthread/{thread_id}"
        soup = await self._get(path)
        messages: list[PressMessage] = []

        for msg_el in soup.select("[class*='message'], [class*='press']"):
            author = ""
            date = ""
            body = ""

            author_el = msg_el.select_one("[class*='author'], [class*='sender']")
            if author_el:
                author = author_el.get_text(strip=True)

            date_el = msg_el.select_one("[class*='date'], [class*='time']")
            if date_el:
                date = date_el.get_text(strip=True)

            body_el = msg_el.select_one("[class*='body'], [class*='content']")
            if body_el:
                body = body_el.get_text(strip=True)
            elif not author_el:
                body = msg_el.get_text(strip=True)

            if body:
                messages.append(PressMessage(author=author, date=date, body=body))

        return messages

    # ── Submitted orders check ────────────────────────────────────────

    async def get_order_status(self, slug: str, game_id: str) -> dict[str, OrderStatus]:
        """Check which countries have submitted orders."""
        state = await self.get_game_state(slug, game_id)
        return {c.name: c.order_status for c in state.countries}
