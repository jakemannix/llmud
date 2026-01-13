import * as readline from "readline";
import chalk from "chalk";
import { connectToMcpServer, loadMcpToolsAsLangChainTools } from "./mcp-tools.js";
import { createGameAgent, type ModelProvider, type DebugCallbacks } from "./agent.js";

const DEFAULT_SERVER_URL = "http://localhost:8000/mcp";

function parseArgs(): { debug: boolean } {
  const args = process.argv.slice(2);
  return {
    debug: args.includes("--debug") || args.includes("-d"),
  };
}

function detectModelConfig(): { provider: ModelProvider; model?: string } {
  const explicitProvider = process.env.LLM_PROVIDER?.toLowerCase();
  const explicitModel = process.env.LLM_MODEL;

  // If provider explicitly set, use it
  if (explicitProvider === "anthropic" || explicitProvider === "openai") {
    return { provider: explicitProvider, model: explicitModel };
  }

  // Auto-detect based on available API keys
  const hasAnthropic = !!process.env.ANTHROPIC_API_KEY;
  const hasOpenAI = !!process.env.OPENAI_API_KEY;

  if (hasAnthropic && !hasOpenAI) {
    return { provider: "anthropic", model: explicitModel };
  }
  if (hasOpenAI && !hasAnthropic) {
    return { provider: "openai", model: explicitModel };
  }
  if (hasAnthropic && hasOpenAI) {
    // Default to Anthropic when both available
    return { provider: "anthropic", model: explicitModel };
  }

  // Neither key set
  return { provider: "openai", model: explicitModel };
}

function createDebugCallbacks(): DebugCallbacks {
  return {
    onThinking: (text: string) => {
      console.log(chalk.magenta.dim("┌─ 💭 Thinking ─────────────────────────────"));
      const lines = text.split("\n");
      for (const line of lines) {
        console.log(chalk.magenta.dim("│ ") + chalk.magenta(line));
      }
      console.log(chalk.magenta.dim("└───────────────────────────────────────────"));
    },
    onToolCall: (name: string, input: Record<string, unknown>) => {
      console.log(chalk.blue.dim("┌─ 🔧 Tool Call ─────────────────────────────"));
      console.log(chalk.blue.dim("│ ") + chalk.blue.bold(name));
      const inputStr = JSON.stringify(input, null, 2);
      for (const line of inputStr.split("\n")) {
        console.log(chalk.blue.dim("│   ") + chalk.gray(line));
      }
      console.log(chalk.blue.dim("└───────────────────────────────────────────"));
    },
    onToolResult: (name: string, result: string) => {
      console.log(chalk.green.dim("┌─ 📤 Tool Result ───────────────────────────"));
      console.log(chalk.green.dim("│ ") + chalk.green.bold(name));
      // Truncate long results
      const maxLen = 500;
      const displayResult = result.length > maxLen 
        ? result.slice(0, maxLen) + chalk.gray("... (truncated)")
        : result;
      for (const line of displayResult.split("\n")) {
        console.log(chalk.green.dim("│   ") + chalk.gray(line));
      }
      console.log(chalk.green.dim("└───────────────────────────────────────────"));
    },
  };
}

async function main() {
  const { debug } = parseArgs();
  const serverUrl = process.env.MCP_SERVER_URL || DEFAULT_SERVER_URL;
  const modelConfig = detectModelConfig();

  console.log(chalk.hex("#8B4513").bold("\n═══════════════════════════════════════════"));
  console.log(chalk.hex("#DAA520").bold("        ⚔️  LLMUD - RPG Chat Client  ⚔️"));
  console.log(chalk.hex("#8B4513").bold("═══════════════════════════════════════════\n"));

  if (debug) {
    console.log(chalk.magenta("🐛 Debug mode enabled\n"));
  }

  // Check for API key
  const hasValidKey =
    (modelConfig.provider === "openai" && process.env.OPENAI_API_KEY) ||
    (modelConfig.provider === "anthropic" && process.env.ANTHROPIC_API_KEY);

  if (!hasValidKey) {
    console.log(chalk.red("Error: No API key found for the selected provider"));
    console.log(chalk.gray("\nSet one of the following:"));
    console.log(chalk.cyan("  export OPENAI_API_KEY=your-key-here"));
    console.log(chalk.cyan("  export ANTHROPIC_API_KEY=your-key-here"));
    console.log(chalk.gray("\nOptionally set LLM_PROVIDER to force a specific provider:"));
    console.log(chalk.cyan('  export LLM_PROVIDER=anthropic  # or "openai"'));
    console.log(chalk.gray("\nOptionally set LLM_MODEL to use a specific model:"));
    console.log(chalk.cyan("  export LLM_MODEL=claude-sonnet-4-20250514\n"));
    process.exit(1);
  }

  const modelName = modelConfig.model || (modelConfig.provider === "anthropic" ? "claude-sonnet-4-20250514" : "gpt-4o");
  console.log(chalk.gray(`Using ${modelConfig.provider} model: ${modelName}`));
  console.log(chalk.gray(`Connecting to MCP server at ${serverUrl}...`));

  let client;
  try {
    client = await connectToMcpServer(serverUrl);
    console.log(chalk.green("✓ Connected to MCP server\n"));
  } catch (error) {
    console.log(chalk.red(`✗ Failed to connect to MCP server at ${serverUrl}`));
    console.log(chalk.gray("Make sure the RPG DM Tools server is running:"));
    console.log(chalk.cyan("  uv run rpg-dm-tools --port 8000\n"));
    process.exit(1);
  }

  // Load tools
  console.log(chalk.gray("Loading MCP tools..."));
  const tools = await loadMcpToolsAsLangChainTools(client);
  console.log(chalk.green(`✓ Loaded ${tools.length} tools:`));
  tools.forEach((t) => console.log(chalk.gray(`  • ${t.name}`)));
  console.log();

  // Create agent with optional debug callbacks
  console.log(chalk.gray("Initializing ReAct agent..."));
  const debugCallbacks = debug ? createDebugCallbacks() : undefined;
  const agent = await createGameAgent(tools, modelConfig, debugCallbacks);
  console.log(chalk.green("✓ Agent ready!\n"));

  console.log(chalk.hex("#DAA520")("━".repeat(45)));
  console.log(chalk.white.bold("Welcome, adventurer!"));
  console.log();
  console.log(chalk.gray("  Type normally to speak ") + chalk.cyan("in-character") + chalk.gray(" (IC)"));
  console.log(chalk.gray("  Start with ") + chalk.yellow(">") + chalk.gray(" to talk to the GM ") + chalk.yellow("out-of-character") + chalk.gray(" (OOC)"));
  console.log();
  console.log(chalk.gray('  Type "quit" or "exit" to end the session.'));
  console.log(chalk.hex("#DAA520")("━".repeat(45)));
  console.log();

  // Create readline interface
  const rl = readline.createInterface({
    input: process.stdin,
    output: process.stdout,
  });

  const prompt = () => {
    rl.question(chalk.cyan.bold("You: "), async (input) => {
      const trimmed = input.trim();

      if (!trimmed) {
        prompt();
        return;
      }

      if (trimmed.toLowerCase() === "quit" || trimmed.toLowerCase() === "exit") {
        console.log(chalk.hex("#DAA520")("\nFarewell, brave adventurer! Until next time... ⚔️\n"));
        rl.close();
        process.exit(0);
      }

      // Detect OOC mode (starts with ">")
      const isOOC = trimmed.startsWith(">");
      const messageContent = isOOC ? trimmed.slice(1).trim() : trimmed;
      const formattedMessage = isOOC ? `[OOC] ${messageContent}` : `[IC] ${messageContent}`;

      try {
        if (isOOC) {
          console.log(chalk.yellow("\n  [OOC → GM thinking...]\n"));
        } else {
          console.log(chalk.gray("\n  [thinking...]\n"));
        }
        
        const response = await agent.chat(formattedMessage);
        
        if (isOOC) {
          console.log(chalk.yellow.bold("GM: ") + chalk.white(response));
        } else {
          console.log(chalk.hex("#90EE90").bold("DM: ") + chalk.white(response));
        }
        console.log();
      } catch (error) {
        console.log(chalk.red("Error: ") + chalk.gray((error as Error).message));
        console.log();
      }

      prompt();
    });
  };

  // Start with an initial greeting from the DM (IC mode)
  try {
    console.log(chalk.gray("  [The Dungeon Master prepares...]\n"));
    const greeting = await agent.chat(
      "[IC] Greet me as a new adventurer arriving at a tavern in Willowdale Village. Be welcoming and ask what kind of adventure I seek."
    );
    console.log(chalk.hex("#90EE90").bold("DM: ") + chalk.white(greeting));
    console.log();
  } catch (error) {
    console.log(chalk.yellow("Could not generate initial greeting, but you can still chat!"));
    console.log();
  }

  prompt();
}

main().catch((error) => {
  console.error(chalk.red("Fatal error:"), error);
  process.exit(1);
});
