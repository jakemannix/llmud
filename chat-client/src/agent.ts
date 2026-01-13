import { ChatOpenAI } from "@langchain/openai";
import { ChatAnthropic } from "@langchain/anthropic";
import { createReactAgent } from "@langchain/langgraph/prebuilt";
import { HumanMessage, AIMessage, ToolMessage, BaseMessage } from "@langchain/core/messages";
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

export type ModelProvider = "openai" | "anthropic";

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

function createModel(config: ModelConfig): BaseChatModel {
  switch (config.provider) {
    case "anthropic":
      return new ChatAnthropic({
        model: config.model || "claude-sonnet-4-20250514",
        temperature: 0.7,
      });
    case "openai":
    default:
      return new ChatOpenAI({
        model: config.model || "gpt-4o",
        temperature: 0.7,
      });
  }
}

export async function createGameAgent(
  tools: StructuredToolInterface[],
  config: ModelConfig = { provider: "openai" },
  debugCallbacks?: DebugCallbacks
): Promise<GameAgent> {
  const model = createModel(config);

  const agent = createReactAgent({
    llm: model,
    tools,
    messageModifier: SYSTEM_PROMPT,
  });

  let messageHistory: BaseMessage[] = [];

  return {
    chat: async (message: string): Promise<string> => {
      messageHistory.push(new HumanMessage(message));

      // Use streaming to capture intermediate steps
      const stream = await agent.stream(
        { messages: messageHistory },
        { streamMode: "updates" }
      );

      let finalResponse = "";
      const newMessages: BaseMessage[] = [];

      for await (const chunk of stream) {
        // Process agent node outputs (LLM responses)
        if (chunk.agent?.messages) {
          for (const msg of chunk.agent.messages) {
            newMessages.push(msg);
            
            if (msg instanceof AIMessage) {
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
              
              if (textContent && !msg.tool_calls?.length) {
                finalResponse = textContent;
              }
            }
          }
        }

        // Process tool node outputs (tool results)
        if (chunk.tools?.messages) {
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

      // Update message history with all new messages
      messageHistory = [...messageHistory, ...newMessages];

      return finalResponse;
    },

    getHistory: () => messageHistory,
  };
}
