#!/usr/bin/env node

const Database = require('./database.js');
const { spawn } = require('child_process');
const path = require('path');

class MCPServer {
  constructor({ name, description, version = "1.0.0" } = {}) {
    this.serverInfo = {
      name: name ?? "MCP Server",
      version,
      description: description ?? ""
    };
    this.tools = new Map();
    this.db = new Database();
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
      query: { type: "string", description: "Tool request in natural language" },
      limit: { type: "integer", description: "Maximum number of results to return", default: 10 }
    },
    required: ["query"]
  }
}, async ({ query, limit = 10 }) => {
  try {
    const results = await mcp.db.searchAgents(query, limit);
    
    return {
      results: results.map(agent => ({
        id: agent.id,
        name: agent.name,
        description: agent.description,
        provider: agent.provider,
        endpoint: agent.endpoint,
        capabilities: agent.capabilities,
        tags: agent.tags,
        auth_required: agent.auth_required,
        auth_method: agent.auth_method,
        auth_docs: agent.auth_docs,
        trust_verified: agent.trust_verified,
        trust_popularity: agent.trust_popularity,
        created_at: agent.created_at
      }))
    };
  } catch (error) {
    console.error('Search error:', error);
    throw new Error(`Search failed: ${error.message}`);
  }
});

// Register the `get_agent` tool
mcp.registerTool("get_agent", {
  description: "Get detailed information about a specific agent by ID",
  inputSchema: {
    type: "object",
    properties: {
      agent_id: { type: "string", description: "The unique identifier of the agent" }
    },
    required: ["agent_id"]
  }
}, async ({ agent_id }) => {
  try {
    const agent = await mcp.db.getAgentById(agent_id);
    
    if (!agent) {
      throw new Error(`Agent with ID "${agent_id}" not found`);
    }
    
    return {
      agent: {
        id: agent.id,
        name: agent.name,
        description: agent.description,
        provider: agent.provider,
        endpoint: agent.endpoint,
        capabilities: agent.capabilities,
        tags: agent.tags,
        auth_required: agent.auth_required,
        auth_method: agent.auth_method,
        auth_docs: agent.auth_docs,
        trust_verified: agent.trust_verified,
        trust_popularity: agent.trust_popularity,
        trust_source: agent.trust_source,
        created_at: agent.created_at,
        tools: agent.tools || []
      }
    };
  } catch (error) {
    console.error('Get agent error:', error);
    throw new Error(`Failed to get agent: ${error.message}`);
  }
});

// Register the `list_agents` tool
mcp.registerTool("list_agents", {
  description: "List all available agents with pagination",
  inputSchema: {
    type: "object",
    properties: {
      limit: { type: "integer", description: "Maximum number of agents to return", default: 50 },
      offset: { type: "integer", description: "Number of agents to skip for pagination", default: 0 }
    }
  }
}, async ({ limit = 50, offset = 0 }) => {
  try {
    const agents = await mcp.db.getAllAgents(limit, offset);
    
    return {
      agents: agents.map(agent => ({
        id: agent.id,
        name: agent.name,
        description: agent.description,
        provider: agent.provider,
        endpoint: agent.endpoint,
        capabilities: agent.capabilities,
        tags: agent.tags,
        auth_required: agent.auth_required,
        auth_method: agent.auth_method,
        trust_verified: agent.trust_verified,
        trust_popularity: agent.trust_popularity,
        created_at: agent.created_at,
        tool_count: parseInt(agent.tool_count)
      }))
    };
  } catch (error) {
    console.error('List agents error:', error);
    throw new Error(`Failed to list agents: ${error.message}`);
  }
});

// Register the `search_by_capability` tool
mcp.registerTool("search_by_capability", {
  description: "Find agents that have a specific capability",
  inputSchema: {
    type: "object",
    properties: {
      capability: { type: "string", description: "The capability to search for" },
      limit: { type: "integer", description: "Maximum number of results to return", default: 10 }
    },
    required: ["capability"]
  }
}, async ({ capability, limit = 10 }) => {
  try {
    const results = await mcp.db.searchByCapability(capability, limit);
    
    return {
      results: results.map(agent => ({
        id: agent.id,
        name: agent.name,
        description: agent.description,
        provider: agent.provider,
        endpoint: agent.endpoint,
        capabilities: agent.capabilities,
        tags: agent.tags,
        auth_required: agent.auth_required,
        trust_verified: agent.trust_verified,
        trust_popularity: agent.trust_popularity
      }))
    };
  } catch (error) {
    console.error('Search by capability error:', error);
    throw new Error(`Search by capability failed: ${error.message}`);
  }
});

// Register the `search_by_tag` tool
mcp.registerTool("search_by_tag", {
  description: "Find agents that have a specific tag",
  inputSchema: {
    type: "object",
    properties: {
      tag: { type: "string", description: "The tag to search for" },
      limit: { type: "integer", description: "Maximum number of results to return", default: 10 }
    },
    required: ["tag"]
  }
}, async ({ tag, limit = 10 }) => {
  try {
    const results = await mcp.db.searchByTag(tag, limit);
    
    return {
      results: results.map(agent => ({
        id: agent.id,
        name: agent.name,
        description: agent.description,
        provider: agent.provider,
        endpoint: agent.endpoint,
        capabilities: agent.capabilities,
        tags: agent.tags,
        auth_required: agent.auth_required,
        trust_verified: agent.trust_verified,
        trust_popularity: agent.trust_popularity
      }))
    };
  } catch (error) {
    console.error('Search by tag error:', error);
    throw new Error(`Search by tag failed: ${error.message}`);
  }
});

// Register the `semantic_search` tool
mcp.registerTool("semantic_search", {
  description: "Find agents using semantic similarity search with vector embeddings",
  inputSchema: {
    type: "object",
    properties: {
      query: { type: "string", description: "Natural language query for semantic search" },
      k: { type: "integer", description: "Number of results to return", default: 3 }
    },
    required: ["query"]
  }
}, async ({ query, k = 3 }) => {
  try {
    const results = await mcp.db.semanticSearch(query, k);
    
    return {
      results: results.map(result => ({
        id: result.id,
        name: result.name,
        description: result.description,
        provider: result.provider,
        endpoint: result.endpoint,
        capabilities: result.capabilities,
        tags: result.tags,
        similarity_score: result.similarity_score,
        reason: result.reason
      }))
    };
  } catch (error) {
    console.error('Semantic search error:', error);
    throw new Error(`Semantic search failed: ${error.message}`);
  }
});

// Start the server
mcp.start();
