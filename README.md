# llmud

Large Language Multi-User Dungeon — an MCP server providing tools for running text-based roleplaying games.

## Quick Start

### Prerequisites

Install [uv](https://docs.astral.sh/uv/) if you haven't already:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### Installation

```bash
# Clone the repo
git clone https://github.com/your-username/llmud.git
cd llmud

# Sync dependencies and create venv
uv sync

# Run the server
uv run rpg-dm-tools --port 8000
```

The MCP server will be available at `http://localhost:8000/mcp`

### Development

```bash
# Run the server directly without installing
uv run python rpg-dm-tools/rpg_server.py --port 8000

# Run tests
uv run python rpg-dm-tools/test_server.py
```

## What's Included

The RPG DM Tools MCP server provides:

| Tool | Description |
|------|-------------|
| `roll_dice` | Roll dice using standard notation (e.g., `2d6+3`, `d20`) |
| `lookup_geography` | Get info about regions, villages, forests |
| `lookup_npc` | Look up NPC details, personality, knowledge |
| `lookup_creature` | Get creature stats for combat encounters |
| `lookup_scenario` | Retrieve pre-written adventure hooks |
| `create_session` | Start a new game session |
| `get_session_state` | Check current game state |
| `read_character` | View a character sheet |
| `update_character` | Modify character stats, inventory, gold |
| `get_current_map` | See current location with SVG map |
| `move_character` | Navigate between rooms |

## Chat Modes

Both clients support two communication modes:

- **In-Character (IC)** — Type normally to roleplay as your character
- **Out-of-Character (OOC)** — Start with `>` to talk to the GM about mechanics, ask questions, etc.

## CLI Chat Client (TypeScript)

The `chat-client/` directory contains a TypeScript CLI that connects to the MCP server using a LangChain ReAct agent. Supports both **OpenAI** and **Anthropic** models.

### Running the CLI Client

```bash
# Terminal 1: Start the MCP server
uv run rpg-dm-tools --port 8000

# Terminal 2: Run the chat client
cd chat-client
npm install

# Use Anthropic (Claude)
export ANTHROPIC_API_KEY=your-key-here
npm run dev

# Or use OpenAI
export OPENAI_API_KEY=your-key-here
npm run dev

# Enable debug mode to see tool calls
npm run dev:debug
```

### Debug Mode

Run with `--debug` to see LLM reasoning and tool calls:

```bash
npm run dev:debug
# or
npm run dev -- --debug
```

Shows:
- 💭 **Thinking** — LLM reasoning tokens
- 🔧 **Tool Call** — Tool name + input arguments  
- 📤 **Tool Result** — Tool output

### Model Configuration

| Variable | Description |
|----------|-------------|
| `ANTHROPIC_API_KEY` | Anthropic API key (uses Claude) |
| `OPENAI_API_KEY` | OpenAI API key (uses GPT-4o) |
| `LLM_PROVIDER` | Force provider: `anthropic` or `openai` |
| `LLM_MODEL` | Specific model name (e.g., `claude-sonnet-4-20250514`, `gpt-4o-mini`) |

When both API keys are set, Anthropic is used by default.

## Web Client (FastHTML)

A browser-based chat interface built with FastHTML (Python). Beautiful dark fantasy theme with the same features as the CLI client.

### Running the Web Client

```bash
# Install with web dependencies
uv sync --all-extras

# Terminal 1: Start the MCP server
uv run rpg-dm-tools --port 8000

# Terminal 2: Start the web UI
export ANTHROPIC_API_KEY=your-key  # or OPENAI_API_KEY
uv run rpg-web-client --port 5001
```

Then open http://localhost:5001 in your browser.

### Features

- 🎨 Dark fantasy themed UI with gold accents
- 🐛 Debug toggle to show tool calls in colored panels
- 🗺️ SVG map rendering inline
- 💬 IC/OOC mode support (prefix with `>` for OOC)

### Debug API Endpoints

The web client exposes REST endpoints for debugging:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/status` | GET | Check server status, init state |
| `/api/messages` | GET | Get chat history as JSON |
| `/api/chat` | POST | Send message, get JSON response |
| `/api/debug` | POST | Toggle debug mode |
| `/api/clear` | POST | Clear chat history |

Test with curl:
```bash
curl http://localhost:5001/api/status
curl -X POST http://localhost:5001/api/chat -d "message=hello&mode=ic"
```

## Usage with Claude Desktop

Add this to your Claude Desktop MCP config (`~/Library/Application Support/Claude/claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "rpg-dm-tools": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/llmud", "rpg-dm-tools", "--port", "8000"],
      "env": {}
    }
  }
}
```

## Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  Claude Desktop │     │   CLI Client    │     │   Web Client    │
│                 │     │  (TypeScript)   │     │   (FastHTML)    │
└────────┬────────┘     └────────┬────────┘     └────────┬────────┘
         │                       │                       │
         │ MCP                   │ MCP/HTTP              │ MCP/HTTP
         │                       │                       │
         └───────────────────────┴───────────────────────┘
                                 │
                    ┌────────────┴────────────┐
                    │    RPG DM Tools MCP     │
                    │    Server (FastMCP)     │
                    │    localhost:8000/mcp   │
                    └─────────────────────────┘
```

## License

MIT
