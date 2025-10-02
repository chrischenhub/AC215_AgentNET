#!/usr/bin/env node

class MCPServer {
  constructor({ name, description, version = "1.0.0" } = {}) {
    this.serverInfo = {
      name: name ?? "MCP Server",
      version,
      description: description ?? ""
    };
    this.tools = new Map();
  }

  registerTool(name, schema, handler) {
    if (typeof name !== "string" || !name.trim()) {
      throw new Error("Tool name must be a non-empty string");
    }
    if (typeof handler !== "function") {
      throw new Error(`Handler for tool "${name}" must be a function`);
    }

    this.tools.set(name, {
      schema: schema ?? {},
      handler
    });
  }

  async handle(message) {
    const responseBase = {
      jsonrpc: "2.0",
      id: message.id ?? null
    };

    if (message.jsonrpc !== "2.0") {
      return {
        ...responseBase,
        error: { code: -32600, message: "Invalid JSON-RPC version" }
      };
    }

    if (!message.method) {
      return {
        ...responseBase,
        error: { code: -32600, message: "Method is required" }
      };
    }

    if (message.method === "initialize") {
      const tools = {};

      for (const [name, { schema }] of this.tools.entries()) {
        tools[name] = {
          description: schema?.description ?? "",
          inputSchema: schema?.inputSchema ?? { type: "object", properties: {} }
        };
      }

      return {
        ...responseBase,
        result: {
          protocolVersion: "2024-11-05",
          capabilities: {
            tools: tools
          },
          serverInfo: this.serverInfo
        }
      };
    }

    if (message.method === "tools/list") {
      const tools = [];

      for (const [name, { schema }] of this.tools.entries()) {
        tools.push({
          name: name,
          description: schema?.description ?? "",
          inputSchema: schema?.inputSchema ?? { type: "object", properties: {} }
        });
      }

      return {
        ...responseBase,
        result: {
          tools: tools
        }
      };
    }

    if (message.method === "tools/call") {
      const toolName = message.params?.name;
      const tool = this.tools.get(toolName);

      if (!tool) {
        return {
          ...responseBase,
          error: { code: -32601, message: `Tool "${toolName}" not found` }
        };
      }

      try {
        const result = await tool.handler(message.params?.arguments ?? {});
        return {
          ...responseBase,
          result: {
            content: [
              {
                type: "text",
                text: JSON.stringify(result, null, 2)
              }
            ]
          }
        };
      } catch (error) {
        return {
          ...responseBase,
          error: {
            code: -32603,
            message: error?.message ?? "Internal server error"
          }
        };
      }
    }

    return {
      ...responseBase,
      error: { code: -32601, message: `Method "${message.method}" not found` }
    };
  }

  start() {
    process.stdin.setEncoding('utf8');
    
    let buffer = '';
    
    process.stdin.on('data', async (chunk) => {
      buffer += chunk;
      
      // Process complete JSON messages
      let newlineIndex;
      while ((newlineIndex = buffer.indexOf('\n')) !== -1) {
        const line = buffer.slice(0, newlineIndex).trim();
        buffer = buffer.slice(newlineIndex + 1);
        
        if (line) {
          try {
            const message = JSON.parse(line);
            const response = await this.handle(message);
            process.stdout.write(JSON.stringify(response) + '\n');
          } catch (error) {
            const errorResponse = {
              jsonrpc: "2.0",
              id: null,
              error: { code: -32700, message: "Parse error" }
            };
            process.stdout.write(JSON.stringify(errorResponse) + '\n');
          }
        }
      }
    });

    process.stdin.on('end', () => {
      process.exit(0);
    });

    // Send ready signal
    process.stderr.write('MCP server ready\n');
  }
}

// Create MCP server
const mcp = new MCPServer({
  name: "AgentNet",
  description: "Search for relevant MCP servers, APIs, or agents"
});

// Register the `search` tool
mcp.registerTool("search", {
  description: "Find MCP servers and APIs by natural language query",
  inputSchema: {
    type: "object",
    properties: {
      query: { type: "string", description: "Tool request in natural language" }
    },
    required: ["query"]
  }
}, async ({ query }) => {
  // Fake search result
  return {
    results: [
      {
        id: "notion_mcp",
        name: "Notion MCP",
        description: "Access Notion workspace tasks, notes, and projects",
        manifest_url: "https://mcp.notion.com/mcp"
      },
      {
        id: "github_mcp",
        name: "GitHub MCP",
        description: "Interact with GitHub repositories and issues",
        manifest_url: "https://mcp.github.com/mcp"
      }
    ]
  };
});

// Start the server
mcp.start();
