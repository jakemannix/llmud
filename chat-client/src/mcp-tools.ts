import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { StreamableHTTPClientTransport } from "@modelcontextprotocol/sdk/client/streamableHttp.js";
import { tool } from "@langchain/core/tools";
import { z } from "zod";

/**
 * Connect to an MCP server via HTTP and return a client
 */
export async function connectToMcpServer(url: string): Promise<Client> {
  const transport = new StreamableHTTPClientTransport(new URL(url));
  const client = new Client(
    { name: "rpg-chat-client", version: "0.1.0" },
    { capabilities: {} }
  );

  await client.connect(transport);
  return client;
}

/**
 * Convert JSON Schema to Zod schema for LangChain tools
 */
function jsonSchemaToZod(schema: any): z.ZodTypeAny {
  if (!schema || typeof schema !== "object") {
    return z.any();
  }

  switch (schema.type) {
    case "string":
      return z.string().describe(schema.description || "");
    case "number":
    case "integer":
      return z.number().describe(schema.description || "");
    case "boolean":
      return z.boolean().describe(schema.description || "");
    case "array":
      return z
        .array(jsonSchemaToZod(schema.items || {}))
        .describe(schema.description || "");
    case "object":
      if (schema.properties) {
        const shape: Record<string, z.ZodTypeAny> = {};
        const required = schema.required || [];
        for (const [key, value] of Object.entries(schema.properties)) {
          const fieldSchema = jsonSchemaToZod(value as any);
          shape[key] = required.includes(key)
            ? fieldSchema
            : fieldSchema.optional();
        }
        return z.object(shape).describe(schema.description || "");
      }
      return z.record(z.any()).describe(schema.description || "");
    default:
      return z.any();
  }
}

/**
 * Load tools from an MCP server and convert them to LangChain tools
 */
export async function loadMcpToolsAsLangChainTools(client: Client) {
  const { tools: mcpTools } = await client.listTools();

  const langchainTools = mcpTools.map((mcpTool) => {
    const inputSchema = mcpTool.inputSchema as any;
    const zodSchema = jsonSchemaToZod(inputSchema);

    return tool(
      async (input: Record<string, any>) => {
        const result = await client.callTool({
          name: mcpTool.name,
          arguments: input,
        });

        // Handle text content from MCP response
        if (Array.isArray(result.content)) {
          return result.content
            .map((c: any) => (c.type === "text" ? c.text : JSON.stringify(c)))
            .join("\n");
        }
        return JSON.stringify(result.content);
      },
      {
        name: mcpTool.name,
        description: mcpTool.description || `MCP tool: ${mcpTool.name}`,
        schema: zodSchema as z.ZodObject<any>,
      }
    );
  });

  return langchainTools;
}
