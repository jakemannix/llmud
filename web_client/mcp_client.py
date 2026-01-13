"""MCP client connection and tool conversion for LangChain."""

from typing import Any
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field, create_model


def json_schema_to_pydantic(schema: dict[str, Any], name: str = "Input") -> type[BaseModel]:
    """Convert JSON Schema to a Pydantic model for LangChain tools."""
    if not schema or schema.get("type") != "object":
        return create_model(name)
    
    properties = schema.get("properties", {})
    required = set(schema.get("required", []))
    
    fields = {}
    for prop_name, prop_schema in properties.items():
        prop_type = prop_schema.get("type", "string")
        description = prop_schema.get("description", "")
        
        # Map JSON schema types to Python types
        type_map = {
            "string": str,
            "integer": int,
            "number": float,
            "boolean": bool,
            "array": list,
            "object": dict,
        }
        python_type = type_map.get(prop_type, Any)
        
        if prop_name in required:
            fields[prop_name] = (python_type, Field(description=description))
        else:
            fields[prop_name] = (python_type | None, Field(default=None, description=description))
    
    return create_model(name, **fields)


def create_tool_function(session: ClientSession, tool_name: str):
    """Create an async function that calls an MCP tool."""
    async def call_tool(**kwargs) -> str:
        result = await session.call_tool(tool_name, kwargs)
        # Extract text content from MCP response
        if hasattr(result, "content") and result.content:
            texts = []
            for item in result.content:
                if hasattr(item, "text"):
                    texts.append(item.text)
                else:
                    texts.append(str(item))
            return "\n".join(texts)
        return str(result)
    
    # Set function name for better debugging
    call_tool.__name__ = tool_name
    call_tool.__qualname__ = tool_name
    return call_tool


class McpConnection:
    """Manages a persistent MCP connection with tools."""
    
    def __init__(self, server_url: str):
        self.server_url = server_url
        self._session: ClientSession | None = None
        self._tools: list[StructuredTool] = []
        self._context_stack = None
        self._read_stream = None
        self._write_stream = None
    
    async def connect(self) -> list[StructuredTool]:
        """Connect to the MCP server and return available tools."""
        from contextlib import AsyncExitStack
        
        self._context_stack = AsyncExitStack()
        await self._context_stack.__aenter__()
        
        # Enter the streamable HTTP context
        client_ctx = streamablehttp_client(self.server_url)
        self._read_stream, self._write_stream, _ = await self._context_stack.enter_async_context(client_ctx)
        
        # Create and enter the session context
        self._session = await self._context_stack.enter_async_context(
            ClientSession(self._read_stream, self._write_stream)
        )
        
        # Initialize
        await self._session.initialize()
        
        # Load tools
        tools_response = await self._session.list_tools()
        
        self._tools = []
        for mcp_tool in tools_response.tools:
            input_schema = mcp_tool.inputSchema or {}
            args_schema = json_schema_to_pydantic(
                input_schema,
                f"{mcp_tool.name.title().replace('_', '')}Input"
            )
            
            # Create actual function (not callable object) for LangGraph compatibility
            tool_func = create_tool_function(self._session, mcp_tool.name)
            
            tool = StructuredTool.from_function(
                coroutine=tool_func,
                name=mcp_tool.name,
                description=mcp_tool.description or f"MCP tool: {mcp_tool.name}",
                args_schema=args_schema,
            )
            self._tools.append(tool)
        
        return self._tools
    
    async def close(self):
        """Close the MCP connection."""
        if self._context_stack:
            await self._context_stack.aclose()
            self._context_stack = None
            self._session = None
    
    @property
    def tools(self) -> list[StructuredTool]:
        return self._tools
    
    @property
    def session(self) -> ClientSession | None:
        return self._session
