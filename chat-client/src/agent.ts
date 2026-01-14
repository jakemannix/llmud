import { ChatOpenAI } from "@langchain/openai";
import { ChatAnthropic } from "@langchain/anthropic";
import { createReactAgent } from "@langchain/langgraph/prebuilt";
import { HumanMessage, AIMessage, AIMessageChunk, ToolMessage, BaseMessage } from "@langchain/core/messages";
import type { StructuredToolInterface } from "@langchain/core/tools";
import type { BaseChatModel } from "@langchain/core/language_models/chat_models";


const SYSTEM_PROMPT = `You are an engaging Dungeon Master running a text-based RPG adventure.

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
When combat happens, use roll_dice and describe the action cinematically.`;

export type ModelProvider = "openai" | "anthropic" | "openrouter";

export interface ModelConfig {
  provider: ModelProvider;
  model?: string;
}

export interface DebugCallbacks {
  onThinking?: (text: string) => void;
  onToolCall?: (name: string, input: Record<string, unknown>) => void;
  onToolResult?: (name: string, result: string) => void;
}

export interface GameAgent {
  chat: (message: string) => Promise<string>;
  getHistory: () => BaseMessage[];
}

// Debug logging helper
const DEBUG = process.env.DEBUG_AGENT === "true";
function debugLog(stage: string, ...args: unknown[]) {
  if (DEBUG) {
    console.log(`[DEBUG ${new Date().toISOString()}] ${stage}:`, ...args);
  }
}

function createModel(config: ModelConfig): BaseChatModel {
  debugLog("createModel", "Creating model with config:", config);
  
  switch (config.provider) {
    case "anthropic":
      debugLog("createModel", "Using Anthropic provider");
      return new ChatAnthropic({
        model: config.model || "claude-sonnet-4-20250514",
        temperature: 0.7,
      });
    case "openrouter":
      debugLog("createModel", "Using OpenRouter provider with baseURL:", "https://openrouter.ai/api/v1");
      debugLog("createModel", "API key present:", !!process.env.OPENROUTER_API_KEY);
      debugLog("createModel", "Model:", config.model || "xiaomi/mimo-v2-flash:free");
      return new ChatOpenAI({
        model: config.model || "xiaomi/mimo-v2-flash:free",
        temperature: 0.7,
        streaming: true,
        apiKey: process.env.OPENROUTER_API_KEY,
        configuration: {
          baseURL: "https://openrouter.ai/api/v1",
        },
      });
    case "openai":
    default:
      debugLog("createModel", "Using OpenAI provider");
      return new ChatOpenAI({
        model: config.model || "gpt-4o",
        temperature: 0.7,
      });
  }
}

export async function createGameAgent(
  tools: StructuredToolInterface[],
  config: ModelConfig = { provider: "openrouter" },
  debugCallbacks?: DebugCallbacks
): Promise<GameAgent> {
  debugLog("createGameAgent", "Starting agent creation with provider:", config.provider);
  debugLog("createGameAgent", "Number of tools:", tools.length);
  
  const model = createModel(config);
  debugLog("createGameAgent", "Model created successfully");

  debugLog("createGameAgent", "Creating ReAct agent...");
  const agent = createReactAgent({
    llm: model,
    tools,
    messageModifier: SYSTEM_PROMPT,
  });
  debugLog("createGameAgent", "ReAct agent created successfully");

  let messageHistory: BaseMessage[] = [];

  return {
    chat: async (message: string): Promise<string> => {
      debugLog("chat", "Starting chat with message:", message.slice(0, 100) + "...");
      messageHistory.push(new HumanMessage(message));

      debugLog("chat", "Calling agent.stream()...");
      // Use streaming to capture intermediate steps
      let stream;
      try {
        stream = await agent.stream(
          { messages: messageHistory },
          { streamMode: "updates" }
        );
      } catch (streamError: unknown) {
        debugLog("chat", "ERROR in agent.stream():", streamError);
        // Try to extract more details from the error
        const err = streamError as Error & { 
          response?: { status?: number; statusText?: string; data?: unknown };
          cause?: unknown;
          code?: string;
        };
        if (DEBUG) {
          console.error("[STREAM ERROR] Message:", err.message);
          console.error("[STREAM ERROR] Code:", err.code);
          console.error("[STREAM ERROR] Cause:", err.cause);
          if (err.response) {
            console.error("[STREAM ERROR] Response status:", err.response.status, err.response.statusText);
            console.error("[STREAM ERROR] Response data:", JSON.stringify(err.response.data, null, 2));
          }
          console.error("[STREAM ERROR] Full error:", err);
        }
        throw streamError;
      }
      debugLog("chat", "agent.stream() returned, starting iteration...");

      let finalResponse = "";
      const newMessages: BaseMessage[] = [];
      let chunkCount = 0;

      try {
      for await (const chunk of stream) {
        chunkCount++;
        debugLog("stream", `Received chunk #${chunkCount}:`, JSON.stringify(Object.keys(chunk)));
        
        // Process agent node outputs (LLM responses)
        if (chunk.agent?.messages) {
          debugLog("stream", `Processing ${chunk.agent.messages.length} agent messages`);
          for (const msg of chunk.agent.messages) {
            newMessages.push(msg);
            
            // Log raw message for debugging
            if (DEBUG) {
              debugLog("stream", "Raw message type:", msg.constructor.name);
              debugLog("stream", "Raw message content:", JSON.stringify(msg.content, null, 2));
              if ('tool_calls' in msg) {
                debugLog("stream", "Tool calls:", JSON.stringify((msg as AIMessage).tool_calls, null, 2));
              }
            }
            
            if (msg instanceof AIMessage || msg instanceof AIMessageChunk) {
              debugLog("stream", "AIMessage received, tool_calls:", msg.tool_calls?.length || 0);
              debugLog("stream", "AIMessage content type:", typeof msg.content, Array.isArray(msg.content) ? `(array of ${msg.content.length})` : "");
              
              // Check for thinking/reasoning in the message
              if (debugCallbacks?.onThinking) {
                // Handle extended thinking blocks (Anthropic)
                const content = msg.content;
                if (Array.isArray(content)) {
                  for (const block of content) {
                    if (typeof block === "object" && block !== null) {
                      if ("type" in block && block.type === "thinking" && "thinking" in block) {
                        debugCallbacks.onThinking(block.thinking as string);
                      }
                    }
                  }
                }
              }

              // Check for tool calls
              if (debugCallbacks?.onToolCall && msg.tool_calls) {
                for (const toolCall of msg.tool_calls) {
                  debugCallbacks.onToolCall(toolCall.name, toolCall.args as Record<string, unknown>);
                }
              }

              // Capture final text response
              const textContent = typeof msg.content === "string" 
                ? msg.content 
                : Array.isArray(msg.content)
                  ? msg.content
                      .filter((c): c is { type: "text"; text: string } => 
                        typeof c === "object" && c !== null && "type" in c && c.type === "text"
                      )
                      .map(c => c.text)
                      .join("")
                  : "";
              
              debugLog("stream", "Extracted text content length:", textContent.length);
              
              if (textContent && !msg.tool_calls?.length) {
                finalResponse = textContent;
                debugLog("stream", "Set finalResponse, length:", finalResponse.length);
              }
            }
          }
        }

        // Process tool node outputs (tool results)
        if (chunk.tools?.messages) {
          debugLog("stream", `Processing ${chunk.tools.messages.length} tool messages`);
          for (const msg of chunk.tools.messages) {
            newMessages.push(msg);
            
            if (msg instanceof ToolMessage && debugCallbacks?.onToolResult) {
              const content = typeof msg.content === "string" 
                ? msg.content 
                : JSON.stringify(msg.content);
              debugCallbacks.onToolResult(msg.name || "unknown", content);
            }
          }
        }
      }
      } catch (iterError) {
        debugLog("chat", "ERROR during stream iteration:", iterError);
        console.error("[ITERATION ERROR]", iterError);
        throw iterError;
      }

      debugLog("chat", `Stream complete. Total chunks: ${chunkCount}, finalResponse length: ${finalResponse.length}`);
      
      // Update message history with all new messages
      messageHistory = [...messageHistory, ...newMessages];

      return finalResponse;
    },

    getHistory: () => messageHistory,
  };
}
