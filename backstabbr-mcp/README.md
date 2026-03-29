# backstabbr-mcp

MCP server for interacting with [Backstabbr](https://www.backstabbr.com), the online Diplomacy platform. Deployed as a serverless HTTP endpoint on [Modal](https://modal.com) with SQLite state on a persistent Volume.

## Status

**Early prototype / proof of concept.** Backstabbr has no official API, so this server works by scraping the web interface with authenticated session cookies. The HTML parsing is best-effort and will need to be refined by inspecting actual page structures.

## Architecture

```
┌─────────────────────────────────────────────┐
│  Modal                                       │
│  ┌────────────────────┐  ┌────────────────┐ │
│  │  FastMCP HTTP       │  │  Modal Volume  │ │
│  │  (ASGI/streamable)  │──│  /data/        │ │
│  │                     │  │  backstabbr.db │ │
│  └─────────┬──────────┘  └────────────────┘ │
└────────────┼────────────────────────────────┘
             │ httpx (scraping)
             ▼
    ┌──────────────────┐
    │  backstabbr.com  │
    │  (Django/GAE)    │
    └──────────────────┘
```

- **HTTP MCP server** on Modal (streamable transport)
- **SQLite on a Modal Volume** caches game state, press messages, session cookies
- **No official API** — scrapes with session cookies + BeautifulSoup

## Deploy to Modal

```bash
pip install "backstabbr-mcp[modal]"

# Deploy
modal deploy src/backstabbr_mcp/modal_app.py

# Dev mode (hot-reload)
modal serve src/backstabbr_mcp/modal_app.py
```

## Local development

```bash
cd backstabbr-mcp
uv pip install -e .

# Set your session cookie
export BACKSTABBR_SESSION_COOKIE="your-session-cookie-value"

# For local dev, point DB at a local path
export BACKSTABBR_DB_PATH="./data/backstabbr.db"

# Run stdio transport (local)
backstabbr-mcp
```

## MCP Tools

| Tool | Description |
|------|-------------|
| `set_session_cookie` | Store your backstabbr.com session cookie |
| `check_auth` | Verify authentication is configured |
| `list_games` | List your active Diplomacy games (cached 5min) |
| `game_state` | View country statuses and supply center counts (cached 2min) |
| `order_status` | Check which countries have submitted orders |
| `list_press` | List press (message) threads in a game (cached 2min) |
| `read_press` | Read messages in a press thread (cached 1min) |
| `game_history` | View cached historical snapshots for a game |
| `game_url` | Get the URL for a game page |
| `debug_page` | Raw HTML structure dump (for reverse engineering) |

## Claude Desktop config (Modal deployment)

```json
{
  "mcpServers": {
    "backstabbr": {
      "type": "streamable-http",
      "url": "https://your-modal-app--backstabbr-mcp-mcp-server.modal.run/mcp"
    }
  }
}
```

## Claude Desktop config (local stdio)

```json
{
  "mcpServers": {
    "backstabbr": {
      "command": "backstabbr-mcp",
      "env": {
        "BACKSTABBR_SESSION_COOKIE": "your-session-cookie-here",
        "BACKSTABBR_DB_PATH": "/tmp/backstabbr.db"
      }
    }
  }
}
```

## State management

All state lives in a single SQLite database on the Modal Volume:

- **`kv`** — key-value store for session cookies and config
- **`game_snapshots`** — cached game state at each phase
- **`press_threads`** / **`press_messages`** — cached press data
- **`game_list`** — cached dashboard game listing

Cache TTLs: game list 5min, game state 2min, press threads 2min, press messages 1min. All tools accept `force_refresh=True` to bypass cache.

## Known limitations

- No official API — HTML parsing is fragile and will break when Backstabbr updates their frontend
- Read-only for now (no order submission, game creation, or press sending)
- Session cookies expire; you'll need to refresh them periodically via `set_session_cookie`
- The SVG map data is rendered client-side via JavaScript and can't be scraped with simple HTTP requests

## References

- [backstabbr-api](https://github.com/afkhurana/backstabbr_api) — existing Python web scraper (MIT)
- [backstabbr-helper](https://github.com/alxwrd/backstabbr-helper) — browser extension
- [Backstabbr GIF article](https://thebackend.dev/backstabbr-gifs) — reverse engineering the SVG map
