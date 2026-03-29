"""Modal deployment for the Backstabbr MCP server.

Runs the FastMCP server as an HTTP endpoint on Modal, with SQLite state
persisted on a Modal Volume.

Deploy:
    modal deploy src/backstabbr_mcp/modal_app.py

Dev (hot-reload):
    modal serve src/backstabbr_mcp/modal_app.py
"""

from __future__ import annotations

import modal

app = modal.App("backstabbr-mcp")

volume = modal.Volume.from_name("backstabbr-data", create_if_missing=True)

image = (
    modal.Image.debian_slim(python_version="3.12")
    .pip_install(
        "fastmcp>=2.0.0",
        "httpx>=0.27.0",
        "beautifulsoup4>=4.12.0",
        "uvicorn>=0.30.0",
    )
    .add_local_dir("src/backstabbr_mcp", remote_path="/app/backstabbr_mcp")
)


@app.function(
    image=image,
    volumes={"/data": volume},
    allow_concurrent_inputs=10,
    timeout=300,
)
@modal.asgi_app()
def mcp_server():
    """ASGI app serving the Backstabbr MCP server over HTTP."""
    import sys
    sys.path.insert(0, "/app")

    # Point the DB at the volume mount
    import os
    os.environ["BACKSTABBR_DB_PATH"] = "/data/backstabbr.db"

    from backstabbr_mcp.server import create_http_app
    return create_http_app()
