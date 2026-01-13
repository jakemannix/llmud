"""LangChain ReAct agent for the RPG game."""

import json
import os
from dataclasses import dataclass, field
from typing import Literal
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage, BaseMessage
from langchain_core.tools import StructuredTool
from langgraph.prebuilt import create_react_agent

SYSTEM_PROMPT = """You are an engaging Dungeon Master running a text-based RPG adventure.

## Communication Modes

Players communicate in TWO modes, indicated by message prefixes:

**[OOC]** (Out-of-Character) - The player is talking to YOU as the game master:
- Answer questions about game mechanics, available tools, rules
- Explain character stats, inventory, abilities
- Discuss strategy, give hints if asked
- Help with session management (creating sessions, checking state)
- Be helpful and informative, break the fourth wall freely
- List available actions or explain how things work

**[IC]** (In-Character) - The player is roleplaying as their character:
- Respond as the world and NPCs would
- Describe scenes, environments, and NPC reactions dramatically
- Stay fully immersed - never break character
- Narrate the results of their actions cinematically
- Roll dice when needed and describe outcomes vividly

## Your Role

- Create immersive descriptions of locations, NPCs, and events
- Guide players through the story using the available tools
- Roll dice for combat, skill checks, and random outcomes
- Keep track of the game state using sessions and character sheets
- Reference world lore for consistent storytelling

## Getting Started with a New Player

1. Create a session with create_session() if one doesn't exist
2. Show them the current map with get_current_map()
3. Describe their surroundings vividly
4. Ask what they'd like to do

When in IC mode, be descriptive, dramatic, and fun!
Use the lookup tools to reference lore and keep the world consistent.
When combat happens, use roll_dice and describe the action cinematically."""


ModelProvider = Literal["openai", "anthropic"]


@dataclass
class DebugEvent:
    """A debug event from the agent."""
    type: Literal["thinking", "tool_call", "tool_result"]
    name: str = ""
    content: str = ""


@dataclass 
class ChatResult:
    """Result from a chat interaction."""
    response: str
    debug_events: list[DebugEvent] = field(default_factory=list)


def create_model(provider: ModelProvider, model_name: str | None = None):
    """Create a chat model based on provider."""
    if provider == "anthropic":
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(
            model=model_name or "claude-sonnet-4-20250514",
            temperature=0.7,
        )
    else:
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=model_name or "gpt-4o",
            temperature=0.7,
        )


def detect_provider() -> tuple[ModelProvider, str | None]:
    """Auto-detect which provider to use based on environment variables."""
    explicit_provider = os.environ.get("LLM_PROVIDER", "").lower()
    explicit_model = os.environ.get("LLM_MODEL")
    
    if explicit_provider in ("anthropic", "openai"):
        return explicit_provider, explicit_model  # type: ignore
    
    has_anthropic = bool(os.environ.get("ANTHROPIC_API_KEY"))
    has_openai = bool(os.environ.get("OPENAI_API_KEY"))
    
    if has_anthropic and not has_openai:
        return "anthropic", explicit_model
    if has_openai and not has_anthropic:
        return "openai", explicit_model
    if has_anthropic and has_openai:
        return "anthropic", explicit_model  # Default to Anthropic
    
    return "openai", explicit_model


class GameAgent:
    """ReAct agent for running the RPG game."""
    
    def __init__(self, tools: list[StructuredTool], provider: ModelProvider | None = None, model_name: str | None = None):
        if provider is None:
            provider, model_name = detect_provider()
        
        self.provider = provider
        self.model_name = model_name
        self.model = create_model(provider, model_name)
        self.tools = tools
        
        self.agent = create_react_agent(
            model=self.model,
            tools=tools,
            prompt=SYSTEM_PROMPT,
        )
        
        self.message_history: list[BaseMessage] = []
    
    async def chat(self, message: str, mode: Literal["ic", "ooc"] = "ic", debug: bool = False) -> ChatResult:
        """Send a message and get a response with optional debug info."""
        # Format message with mode prefix
        prefix = "[OOC]" if mode == "ooc" else "[IC]"
        formatted = f"{prefix} {message}"
        
        self.message_history.append(HumanMessage(content=formatted))
        
        debug_events: list[DebugEvent] = []
        final_response = ""
        
        # Use streaming to capture intermediate steps
        stream = self.agent.astream(
            {"messages": self.message_history},
            stream_mode="updates"
        )
        
        new_messages: list[BaseMessage] = []
        
        async for chunk in stream:
            # Process agent node outputs (LLM responses)
            if "agent" in chunk and chunk["agent"].get("messages"):
                for msg in chunk["agent"]["messages"]:
                    new_messages.append(msg)
                    
                    if isinstance(msg, AIMessage):
                        # Check for thinking blocks (Anthropic extended thinking)
                        if debug:
                            content = msg.content
                            if isinstance(content, list):
                                for block in content:
                                    if isinstance(block, dict) and block.get("type") == "thinking":
                                        debug_events.append(DebugEvent(
                                            type="thinking",
                                            content=block.get("thinking", "")
                                        ))
                        
                        # Check for tool calls
                        if debug and msg.tool_calls:
                            for tool_call in msg.tool_calls:
                                debug_events.append(DebugEvent(
                                    type="tool_call",
                                    name=tool_call["name"],
                                    content=json.dumps(tool_call["args"], indent=2)
                                ))
                        
                        # Capture final text response
                        content = msg.content
                        if isinstance(content, str) and content and not msg.tool_calls:
                            final_response = content
                        elif isinstance(content, list):
                            texts = [c.get("text", "") for c in content 
                                    if isinstance(c, dict) and c.get("type") == "text"]
                            if texts and not msg.tool_calls:
                                final_response = "".join(texts)
            
            # Process tool node outputs (tool results)
            if "tools" in chunk and chunk["tools"].get("messages"):
                for msg in chunk["tools"]["messages"]:
                    new_messages.append(msg)
                    
                    if debug and isinstance(msg, ToolMessage):
                        content = msg.content if isinstance(msg.content, str) else json.dumps(msg.content)
                        debug_events.append(DebugEvent(
                            type="tool_result", 
                            name=msg.name or "unknown",
                            content=content
                        ))
        
        # Update message history
        self.message_history = [*self.message_history, *new_messages]
        
        return ChatResult(response=final_response or "(No response)", debug_events=debug_events)
    
    def clear_history(self):
        """Clear the conversation history."""
        self.message_history = []
