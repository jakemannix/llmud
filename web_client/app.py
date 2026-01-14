"""FastHTML web UI for RPG DM Tools."""

import argparse
import json
import os
import re
import uvicorn
from fasthtml.common import *

# Will be initialized on startup
mcp_connection = None
game_agent = None
mcp_url_global = "http://localhost:8000/mcp"

# Chat history for display
chat_messages: list[dict] = []

# Debug mode state
debug_enabled = False

# Initialization state
initialized = False


async def ensure_initialized():
    """Lazily initialize the MCP connection and agent on first request."""
    global mcp_connection, game_agent, chat_messages, initialized
    
    if initialized:
        return True
    
    from web_client.mcp_client import McpConnection
    from web_client.agent import GameAgent
    
    print(f"Connecting to MCP server at {mcp_url_global}...")
    
    try:
        mcp_connection = McpConnection(mcp_url_global)
        tools = await mcp_connection.connect()
        
        print(f"✓ Connected! Loaded {len(tools)} tools:")
        for t in tools:
            print(f"  • {t.name}")
        
        game_agent = GameAgent(tools)
        print(f"✓ Agent ready (using {game_agent.provider})")
        
        # Generate initial greeting
        print("Generating initial greeting...")
        result = await game_agent.chat(
            "Greet me as a new adventurer arriving at a tavern in Willowdale Village. Be welcoming and ask what kind of adventure I seek.",
            mode="ic",
            debug=False
        )
        chat_messages.append({
            "role": "assistant",
            "content": result.response,
            "mode": "ic",
            "debug_events": []
        })
        print("✓ Ready to play!")
        initialized = True
        return True
    except Exception as e:
        print(f"Error initializing: {e}")
        return False


def create_app():
    """Create the FastHTML app."""
    
    app = FastHTML(
        hdrs=(
            Meta(charset="utf-8"),
            Meta(name="viewport", content="width=device-width, initial-scale=1"),
            Link(rel="preconnect", href="https://fonts.googleapis.com"),
            Link(rel="preconnect", href="https://fonts.gstatic.com", crossorigin=""),
            Link(rel="stylesheet", href="https://fonts.googleapis.com/css2?family=Cinzel:wght@400;700&family=Crimson+Text:ital,wght@0,400;0,600;1,400&family=JetBrains+Mono:wght@400&display=swap"),
            Script(src="https://unpkg.com/htmx.org@2.0.4"),
            Style(CSS),
        ),
    )
    
    # ==================== DEBUG/API ENDPOINTS ====================
    
    @app.get("/api/status")
    async def api_status():
        """Check server status - useful for debugging."""
        return JSONResponse({
            "status": "ok",
            "initialized": initialized,
            "agent_provider": game_agent.provider if game_agent else None,
            "message_count": len(chat_messages),
            "debug_enabled": debug_enabled,
        })
    
    @app.get("/api/messages")
    async def api_messages():
        """Get all messages as JSON."""
        return JSONResponse({
            "messages": [
                {
                    "role": m["role"],
                    "content": m["content"][:200] + "..." if len(m["content"]) > 200 else m["content"],
                    "mode": m.get("mode", "ic"),
                }
                for m in chat_messages
            ]
        })
    
    @app.post("/api/chat")
    async def api_chat(message: str, mode: str = "ic"):
        """Send a chat message and get JSON response - useful for debugging."""
        global game_agent, chat_messages, debug_enabled
        
        if not await ensure_initialized():
            return JSONResponse({"error": "Failed to initialize agent"}, status_code=500)
        
        if not message.strip():
            return JSONResponse({"error": "Empty message"}, status_code=400)
        
        try:
            result = await game_agent.chat(message.strip(), mode, debug=debug_enabled)
            
            # Add to history
            chat_messages.append({"role": "user", "content": message, "mode": mode})
            chat_messages.append({
                "role": "assistant", 
                "content": result.response, 
                "mode": mode,
                "debug_events": [{"type": e.type, "name": e.name, "content": e.content[:200]} for e in result.debug_events]
            })
            
            return JSONResponse({
                "response": result.response,
                "debug_events": [
                    {"type": e.type, "name": e.name, "content": e.content[:500]}
                    for e in result.debug_events
                ] if debug_enabled else []
            })
        except Exception as e:
            return JSONResponse({"error": str(e)}, status_code=500)
    
    @app.post("/api/debug")
    async def api_toggle_debug():
        """Toggle debug mode."""
        global debug_enabled
        debug_enabled = not debug_enabled
        return JSONResponse({"debug_enabled": debug_enabled})
    
    @app.post("/api/clear")
    async def api_clear():
        """Clear chat history."""
        global chat_messages, game_agent
        chat_messages = []
        if game_agent:
            game_agent.clear_history()
        return JSONResponse({"status": "cleared"})
    
    # ==================== HTML ENDPOINTS ====================
    
    @app.get("/")
    async def index():
        # Ensure we're initialized
        await ensure_initialized()
        
        return Html(
            Head(
                Title("LLMUD - RPG Adventure"),
                Meta(charset="utf-8"),
                Meta(name="viewport", content="width=device-width, initial-scale=1"),
                Link(rel="preconnect", href="https://fonts.googleapis.com"),
                Link(rel="preconnect", href="https://fonts.gstatic.com", crossorigin=""),
                Link(rel="stylesheet", href="https://fonts.googleapis.com/css2?family=Cinzel:wght@400;700&family=Crimson+Text:ital,wght@0,400;0,600;1,400&family=JetBrains+Mono:wght@400&display=swap"),
                Script(src="https://unpkg.com/htmx.org@2.0.4"),
                Style(CSS),
            ),
            Body(
                Div(
                    Header(
                        Div(
                            H1("⚔️ LLMUD"),
                            P("Large Language Multi-User Dungeon", cls="subtitle"),
                            cls="header-text"
                        ),
                        Div(
                            Label(
                                Input(
                                    type="checkbox",
                                    checked=debug_enabled,
                                    hx_post="/toggle-debug",
                                    hx_swap="none",
                                    cls="debug-checkbox"
                                ),
                                Span("🐛 Debug", cls="debug-label"),
                                cls="debug-toggle"
                            ),
                            cls="header-controls"
                        ),
                        cls="header"
                    ),
                    Div(
                        Div(
                            *[message_bubble(m) for m in chat_messages],
                            id="chat-messages",
                            cls="chat-messages"
                        ),
                        Div(
                            Form(
                                Div(
                                    Input(
                                        type="text",
                                        name="message",
                                        placeholder="Speak in-character, or start with > for OOC...",
                                        autocomplete="off",
                                        autofocus=True,
                                        cls="message-input"
                                    ),
                                    Button("Send", type="submit", cls="send-btn"),
                                    cls="input-row"
                                ),
                                Div(
                                    Span("💬 Type normally = ", cls="hint"),
                                    Span("In-Character", cls="ic-hint"),
                                    Span(" | ", cls="hint"),
                                    Span("> prefix = ", cls="hint"),
                                    Span("Out-of-Character", cls="ooc-hint"),
                                    cls="mode-hints"
                                ),
                                hx_post="/chat",
                                hx_target="#chat-messages",
                                hx_swap="beforeend",
                                hx_on__after_request="this.reset(); scrollToBottom();",
                                cls="chat-form"
                            ),
                            cls="input-area"
                        ),
                        cls="chat-container"
                    ),
                    cls="main-container"
                ),
                Script(JS),
            )
        )
    
    @app.post("/toggle-debug")
    async def toggle_debug():
        global debug_enabled
        debug_enabled = not debug_enabled
        return ""
    
    @app.post("/chat")
    async def chat(message: str):
        global game_agent, chat_messages, debug_enabled
        
        if not message.strip():
            return ""
        
        if not await ensure_initialized():
            from starlette.responses import HTMLResponse
            return HTMLResponse('<div class="error">Error: Failed to connect to game server</div>')
        
        # Detect mode
        is_ooc = message.strip().startswith(">")
        content = message.strip()[1:].strip() if is_ooc else message.strip()
        mode = "ooc" if is_ooc else "ic"
        
        # Add user message
        user_msg = {"role": "user", "content": content, "mode": mode}
        chat_messages.append(user_msg)
        
        # Get agent response
        debug_events = []
        if game_agent:
            try:
                result = await game_agent.chat(content, mode, debug=debug_enabled)
                response = result.response
                debug_events = result.debug_events
            except Exception as e:
                response = f"Error: {str(e)}"
        else:
            response = "Agent not connected. Please ensure the MCP server is running."
        
        # Add assistant message
        assistant_msg = {
            "role": "assistant", 
            "content": response, 
            "mode": mode,
            "debug_events": debug_events if debug_enabled else []
        }
        chat_messages.append(assistant_msg)
        
        # Return both messages as HTML fragment (not wrapped in full page)
        from starlette.responses import HTMLResponse
        html = to_xml(Div(
            message_bubble(user_msg),
            message_bubble(assistant_msg),
        ))
        return HTMLResponse(html)
    
    @app.post("/clear")
    async def clear():
        global chat_messages, game_agent
        chat_messages = []
        if game_agent:
            game_agent.clear_history()
        return RedirectResponse("/", status_code=303)
    
    return app


def render_content_with_svg(content: str):
    """Render content, extracting and displaying SVG inline."""
    svg_pattern = r'(<svg[^>]*>.*?</svg>)'
    parts = re.split(svg_pattern, content, flags=re.DOTALL | re.IGNORECASE)
    
    if len(parts) == 1:
        return Div(content, cls="text-content")
    
    elements = []
    for part in parts:
        if part.strip():
            if part.strip().lower().startswith('<svg'):
                elements.append(Div(NotStr(part), cls="svg-container"))
            else:
                elements.append(Div(part.strip(), cls="text-content"))
    
    return Div(*elements)


def debug_event_bubble(event):
    """Create a debug event display."""
    if event.type == "thinking":
        return Div(
            Div("💭 Thinking", cls="debug-header thinking"),
            Div(event.content, cls="debug-content"),
            cls="debug-event thinking"
        )
    elif event.type == "tool_call":
        return Div(
            Div(f"🔧 {event.name}", cls="debug-header tool-call"),
            Pre(event.content, cls="debug-content code"),
            cls="debug-event tool-call"
        )
    elif event.type == "tool_result":
        content = event.content
        truncated = len(content) > 800
        display_content = content[:800] + "..." if truncated else content
        has_svg = '<svg' in content.lower()
        
        return Div(
            Div(f"📤 {event.name}", cls="debug-header tool-result"),
            render_content_with_svg(content) if has_svg else Pre(display_content, cls="debug-content code"),
            cls="debug-event tool-result"
        )
    return ""


def message_bubble(msg: dict):
    """Create a chat message bubble."""
    role = msg["role"]
    content = msg["content"]
    mode = msg.get("mode", "ic")
    debug_events = msg.get("debug_events", [])
    
    if role == "user":
        mode_label = "OOC" if mode == "ooc" else "IC"
        mode_cls = "ooc" if mode == "ooc" else "ic"
        return Div(
            Div(
                Span(mode_label, cls=f"mode-badge {mode_cls}"),
                Span("You", cls="sender"),
                cls="message-header"
            ),
            Div(content, cls="message-content"),
            cls=f"message user {mode_cls}"
        )
    else:
        sender = "GM" if mode == "ooc" else "DM"
        mode_cls = "ooc" if mode == "ooc" else "ic"
        
        debug_section = []
        if debug_events:
            debug_section = [
                Div(
                    *[debug_event_bubble(e) for e in debug_events],
                    cls="debug-events"
                )
            ]
        
        return Div(
            *debug_section,
            Div(
                Div(
                    Span(sender, cls="sender"),
                    cls="message-header"
                ),
                render_content_with_svg(content),
                cls=f"message assistant {mode_cls}"
            ),
        )


CSS = """
:root {
    --bg-dark: #1a1a2e;
    --bg-card: #16213e;
    --bg-input: #0f3460;
    --gold: #d4af37;
    --gold-light: #f4d03f;
    --text: #e8e8e8;
    --text-dim: #a0a0a0;
    --ic-color: #4ade80;
    --ooc-color: #fbbf24;
    --user-bg: #1e3a5f;
    --assistant-bg: #2d1f3d;
    --debug-thinking: #a855f7;
    --debug-tool-call: #3b82f6;
    --debug-tool-result: #22c55e;
}

* { box-sizing: border-box; margin: 0; padding: 0; }

body {
    font-family: 'Crimson Text', Georgia, serif;
    background: linear-gradient(135deg, var(--bg-dark) 0%, #0f0f23 100%);
    color: var(--text);
    min-height: 100vh;
}

.main-container {
    max-width: 900px;
    margin: 0 auto;
    height: 100vh;
    display: flex;
    flex-direction: column;
}

.header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 1rem 1.5rem;
    border-bottom: 2px solid var(--gold);
    background: linear-gradient(180deg, rgba(212, 175, 55, 0.1) 0%, transparent 100%);
}

.header-text { text-align: left; }

.header h1 {
    font-family: 'Cinzel', serif;
    font-size: 2rem;
    color: var(--gold);
    text-shadow: 0 0 20px rgba(212, 175, 55, 0.3);
    margin-bottom: 0.1rem;
}

.header .subtitle {
    color: var(--text-dim);
    font-style: italic;
    font-size: 0.95rem;
}

.header-controls { display: flex; align-items: center; gap: 1rem; }

.debug-toggle {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    cursor: pointer;
    padding: 0.5rem 0.75rem;
    border-radius: 6px;
    background: rgba(168, 85, 247, 0.1);
    border: 1px solid rgba(168, 85, 247, 0.3);
    transition: all 0.2s;
}

.debug-toggle:hover { background: rgba(168, 85, 247, 0.2); }
.debug-checkbox { width: 16px; height: 16px; accent-color: var(--debug-thinking); }
.debug-label { font-family: 'JetBrains Mono', monospace; font-size: 0.85rem; color: var(--debug-thinking); }

.chat-container { flex: 1; display: flex; flex-direction: column; overflow: hidden; }

.chat-messages {
    flex: 1;
    overflow-y: auto;
    padding: 1.5rem;
    display: flex;
    flex-direction: column;
    gap: 1rem;
}

.message {
    max-width: 85%;
    padding: 1rem 1.25rem;
    border-radius: 12px;
    animation: fadeIn 0.3s ease;
}

@keyframes fadeIn {
    from { opacity: 0; transform: translateY(10px); }
    to { opacity: 1; transform: translateY(0); }
}

.message.user {
    align-self: flex-end;
    background: var(--user-bg);
    border: 1px solid rgba(255, 255, 255, 0.1);
}

.message.assistant {
    align-self: flex-start;
    background: var(--assistant-bg);
    border-left: 3px solid var(--gold);
}

.message.assistant.ooc { border-left-color: var(--ooc-color); }

.message-header {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    margin-bottom: 0.5rem;
    font-size: 0.85rem;
}

.sender { font-family: 'Cinzel', serif; font-weight: 700; color: var(--gold); }
.message.assistant .sender { color: var(--gold-light); }
.message.assistant.ooc .sender { color: var(--ooc-color); }

.mode-badge {
    font-size: 0.7rem;
    padding: 0.15rem 0.5rem;
    border-radius: 4px;
    font-family: sans-serif;
    font-weight: 600;
    text-transform: uppercase;
}

.mode-badge.ic { background: rgba(74, 222, 128, 0.2); color: var(--ic-color); }
.mode-badge.ooc { background: rgba(251, 191, 36, 0.2); color: var(--ooc-color); }

.message-content, .text-content {
    line-height: 1.6;
    font-size: 1.05rem;
    white-space: pre-wrap;
}

.debug-events {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
    margin-bottom: 0.75rem;
    max-width: 85%;
}

.debug-event {
    border-radius: 8px;
    overflow: hidden;
    font-size: 0.85rem;
    animation: fadeIn 0.2s ease;
}

.debug-event.thinking { background: rgba(168, 85, 247, 0.1); border: 1px solid rgba(168, 85, 247, 0.3); }
.debug-event.tool-call { background: rgba(59, 130, 246, 0.1); border: 1px solid rgba(59, 130, 246, 0.3); }
.debug-event.tool-result { background: rgba(34, 197, 94, 0.1); border: 1px solid rgba(34, 197, 94, 0.3); }

.debug-header {
    padding: 0.4rem 0.75rem;
    font-family: 'JetBrains Mono', monospace;
    font-weight: 600;
    font-size: 0.8rem;
}

.debug-header.thinking { background: rgba(168, 85, 247, 0.2); color: var(--debug-thinking); }
.debug-header.tool-call { background: rgba(59, 130, 246, 0.2); color: var(--debug-tool-call); }
.debug-header.tool-result { background: rgba(34, 197, 94, 0.2); color: var(--debug-tool-result); }

.debug-content {
    padding: 0.5rem 0.75rem;
    color: var(--text-dim);
    white-space: pre-wrap;
    word-break: break-word;
}

.debug-content.code {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.75rem;
    background: rgba(0, 0, 0, 0.2);
    margin: 0;
    max-height: 200px;
    overflow-y: auto;
}

.svg-container {
    margin: 1rem 0;
    padding: 1rem;
    background: rgba(0, 0, 0, 0.3);
    border-radius: 8px;
    display: flex;
    justify-content: center;
    overflow: auto;
}

.svg-container svg { max-width: 100%; height: auto; }

.input-area {
    padding: 1rem 1.5rem 1.5rem;
    background: var(--bg-card);
    border-top: 1px solid rgba(212, 175, 55, 0.3);
}

.chat-form { display: flex; flex-direction: column; gap: 0.75rem; }
.input-row { display: flex; gap: 0.75rem; }

.message-input {
    flex: 1;
    padding: 0.875rem 1rem;
    font-size: 1rem;
    font-family: 'Crimson Text', Georgia, serif;
    background: var(--bg-input);
    border: 1px solid rgba(212, 175, 55, 0.3);
    border-radius: 8px;
    color: var(--text);
    outline: none;
    transition: border-color 0.2s, box-shadow 0.2s;
}

.message-input:focus {
    border-color: var(--gold);
    box-shadow: 0 0 0 2px rgba(212, 175, 55, 0.2);
}

.message-input::placeholder { color: var(--text-dim); font-style: italic; }

.send-btn {
    padding: 0.875rem 1.5rem;
    font-family: 'Cinzel', serif;
    font-size: 0.95rem;
    font-weight: 700;
    background: linear-gradient(135deg, var(--gold) 0%, #b8960c 100%);
    color: var(--bg-dark);
    border: none;
    border-radius: 8px;
    cursor: pointer;
    transition: transform 0.1s, box-shadow 0.2s;
}

.send-btn:hover {
    transform: translateY(-1px);
    box-shadow: 0 4px 12px rgba(212, 175, 55, 0.4);
}

.send-btn:active { transform: translateY(0); }

.mode-hints { text-align: center; font-size: 0.85rem; color: var(--text-dim); }
.hint { color: var(--text-dim); }
.ic-hint { color: var(--ic-color); font-weight: 600; }
.ooc-hint { color: var(--ooc-color); font-weight: 600; }

.chat-messages::-webkit-scrollbar, .debug-content.code::-webkit-scrollbar { width: 8px; }
.chat-messages::-webkit-scrollbar-track, .debug-content.code::-webkit-scrollbar-track { background: var(--bg-dark); }
.chat-messages::-webkit-scrollbar-thumb, .debug-content.code::-webkit-scrollbar-thumb { background: var(--gold); border-radius: 4px; }
.chat-messages::-webkit-scrollbar-thumb:hover, .debug-content.code::-webkit-scrollbar-thumb:hover { background: var(--gold-light); }

.error { color: #ef4444; padding: 1rem; background: rgba(239, 68, 68, 0.1); border-radius: 8px; }
"""

JS = """
function scrollToBottom() {
    const messages = document.getElementById('chat-messages');
    setTimeout(() => { messages.scrollTop = messages.scrollHeight; }, 50);
}
document.addEventListener('DOMContentLoaded', scrollToBottom);
document.body.addEventListener('htmx:afterSwap', function(evt) {
    if (evt.detail.target.id === 'chat-messages') { scrollToBottom(); }
});
"""


def main():
    """Main entry point."""
    global mcp_url_global
    
    parser = argparse.ArgumentParser(description="LLMUD Web Client")
    parser.add_argument("--port", type=int, default=5001, help="Port to run web UI on")
    parser.add_argument("--mcp-url", type=str, default="http://localhost:8000/mcp", 
                        help="URL of the MCP server")
    args = parser.parse_args()
    
    # Check for API keys
    if not os.environ.get("ANTHROPIC_API_KEY") and not os.environ.get("OPENAI_API_KEY") and not os.environ.get("OPENROUTER_API_KEY"):
        print("Error: No API key found.")
        print("Set ANTHROPIC_API_KEY, OPENAI_API_KEY, or OPENROUTER_API_KEY environment variable.")
        return
    
    mcp_url_global = args.mcp_url
    
    app = create_app()
    
    print(f"""
╔══════════════════════════════════════════════════════════════╗
║  LLMUD Web Client                                            ║
╠══════════════════════════════════════════════════════════════╣
║  Web UI:     http://localhost:{args.port:<5}                         ║
║  MCP Server: {mcp_url_global:<47} ║
╠══════════════════════════════════════════════════════════════╣
║  Debug API Endpoints:                                        ║
║    GET  /api/status   - Check server status                  ║
║    GET  /api/messages - Get chat history as JSON             ║
║    POST /api/chat     - Send message (params: message, mode) ║
║    POST /api/debug    - Toggle debug mode                    ║
║    POST /api/clear    - Clear chat history                   ║
╚══════════════════════════════════════════════════════════════╝
""")
    
    uvicorn.run(app, host="0.0.0.0", port=args.port)


if __name__ == "__main__":
    main()
