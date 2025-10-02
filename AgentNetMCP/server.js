import express from "express";

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
      const capabilities = {};

      for (const [name, { schema }] of this.tools.entries()) {
        capabilities[name] = {
          description: schema?.description ?? "",
          inputSchema: schema?.inputSchema ?? { type: "object", properties: {} },
          outputSchema: schema?.outputSchema ?? null
        };
      }

      return {
        ...responseBase,
        result: {
          capabilities,
          serverInfo: this.serverInfo
        }
      };
    }

    const tool = this.tools.get(message.method);

    if (!tool) {
      return {
        ...responseBase,
        error: { code: -32601, message: `Method "${message.method}" not found` }
      };
    }

    try {
      const result = await tool.handler(message.params ?? {});
      return {
        ...responseBase,
        result
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
}

const app = express();
app.use(express.json());

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
  },
  outputSchema: {
    type: "object",
    properties: {
      results: {
        type: "array",
        items: {
          type: "object",
          properties: {
            id: { type: "string" },
            name: { type: "string" },
            description: { type: "string" },
            manifest_url: { type: "string" }
          }
        }
      }
    }
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
      }
    ]
  };
});

// Bind MCP to Express
app.post("/mcp", async (req, res) => {
  try {
    const response = await mcp.handle(req.body);
    res.json(response);
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: err.message });
  }
});

// Start server
app.listen(3000, () => {
  console.log("AgentNet MCP running at http://localhost:3000/mcp");
});