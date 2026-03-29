# backstabbr-mcp

MCP server for interacting with [Backstabbr](https://www.backstabbr.com), the online Diplomacy platform.

## Status

**Early prototype / proof of concept.** Backstabbr has no official API, so this server works by scraping the web interface with authenticated session cookies. The HTML parsing is best-effort and will need to be refined by inspecting actual page structures.

## How it works

- **Authentication**: Backstabbr uses Firebase auth (Google sign-in). You sign in via your browser, then copy the `session` cookie from dev tools.
- **Scraping**: The server makes HTTP requests to backstabbr.com using your session cookie and parses the HTML responses with BeautifulSoup.
- **MCP tools**: Game state, order status, and press messages are exposed as MCP tools that an LLM can call.

## Setup

```bash
# Install dependencies
cd backstabbr-mcp
uv pip install -e .

# Set your session cookie (from browser dev tools after signing in)
export BACKSTABBR_SESSION_COOKIE="your-session-cookie-value"

# Run the server
backstabbr-mcp
```

## MCP Tools

| Tool | Description |
|------|-------------|
| `list_games` | List your active Diplomacy games |
| `game_state` | View country statuses and supply center counts |
| `order_status` | Check which countries have submitted orders |
| `list_press` | List press (message) threads in a game |
| `read_press` | Read messages in a press thread |
| `game_url` | Get the URL for a game page |

## Claude Desktop config

```json
{
  "mcpServers": {
    "backstabbr": {
      "command": "backstabbr-mcp",
      "env": {
        "BACKSTABBR_SESSION_COOKIE": "your-session-cookie-here"
      }
    }
  }
}
```

## Known limitations

- No official API — HTML parsing is fragile and will break when Backstabbr updates their frontend
- Read-only for now (no order submission, game creation, or press sending)
- Session cookies expire; you'll need to refresh them periodically
- The SVG map data is rendered client-side via JavaScript and can't be scraped with simple HTTP requests

## Architecture notes (from reverse engineering)

- Backstabbr's Firebase project ID: `tilegames2`
- Auth domain: `auth.backstabbr.com`
- Game URL pattern: `/game/{slug}/{game_id}/{year}/{season}`
- Press thread paths: `/game/{slug}/{game_id}/pressthread/{thread_id}`
- Game state (countries, SCs, orders) is in the HTML sidebar/legend
- Map is SVG rendered via JS (not accessible via HTTP scraping)

## References

- [backstabbr-api](https://github.com/afkhurana/backstabbr_api) — existing Python web scraper (MIT)
- [backstabbr-helper](https://github.com/alxwrd/backstabbr-helper) — browser extension
- [Backstabbr GIF article](https://thebackend.dev/backstabbr-gifs) — reverse engineering the SVG map
