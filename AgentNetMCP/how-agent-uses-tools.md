# How the Agent Knows When to Use Your Search Tool

## 🧠 Tool Discovery Process

When Cursor starts up and connects to your MCP server, here's what happens:

### 1. **Initialization & Tool Registration**
```json
// Cursor sends this to your MCP server:
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "initialize",
  "params": {}
}

// Your server responds with available tools:
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "capabilities": {
      "tools": {
        "search": {
          "description": "Find MCP servers and APIs by natural language query",
          "inputSchema": {
            "type": "object",
            "properties": {
              "query": {
                "type": "string", 
                "description": "Tool request in natural language"
              }
            },
            "required": ["query"]
          }
        }
      }
    }
  }
}
```

### 2. **Tool List Discovery**
```json
// Cursor also calls tools/list to get detailed tool info:
{
  "jsonrpc": "2.0",
  "id": 2,
  "method": "tools/list"
}

// Your server responds with:
{
  "result": {
    "tools": [
      {
        "name": "search",
        "description": "Find MCP servers and APIs by natural language query",
        "inputSchema": { /* schema details */ }
      }
    ]
  }
}
```

## 🎯 How the Agent Decides to Use Your Tool

The agent uses **semantic matching** based on:

### 1. **Tool Description**
Your tool description is key:
```javascript
"description": "Find MCP servers and APIs by natural language query"
```

### 2. **Parameter Description**
```javascript
"query": { 
  "type": "string", 
  "description": "Tool request in natural language" 
}
```

### 3. **User Intent Recognition**
The agent recognizes these patterns and triggers your search tool:

**✅ Triggers Your Search Tool:**
- "Search for calendar integration tools"
- "Find MCP servers for database access"
- "Look for APIs related to file management"
- "What MCP servers are available for email?"
- "Find tools for project management"

**❌ Won't Trigger Your Search Tool:**
- "What's the weather today?" (not about MCP servers/APIs)
- "Help me write a function" (not a search request)
- "Calculate 2+2" (not related to finding tools)

## 🔧 Tool Invocation Process

When the agent decides to use your tool:

### 1. **Agent Analysis**
```
User: "Search for calendar integration tools"
Agent thinks: "User wants to find tools/servers related to calendars. 
              I have a 'search' tool that finds MCP servers and APIs. 
              This matches perfectly!"
```

### 2. **Tool Call**
```json
{
  "jsonrpc": "2.0",
  "id": 3,
  "method": "tools/call",
  "params": {
    "name": "search",
    "arguments": {
      "query": "calendar integration tools"
    }
  }
}
```

### 3. **Your Server Response**
```json
{
  "jsonrpc": "2.0",
  "id": 3,
  "result": {
    "content": [
      {
        "type": "text",
        "text": "{\n  \"results\": [\n    {\n      \"id\": \"notion_mcp\",\n      \"name\": \"Notion MCP\",\n      \"description\": \"Access Notion workspace tasks, notes, and projects\",\n      \"manifest_url\": \"https://mcp.notion.com/mcp\"\n    }\n  ]\n}"
      }
    ]
  }
}
```

### 4. **Agent Presents Results**
The agent then formats and presents your results to the user in a nice way.

## 💡 Making Your Tool More Discoverable

To make the agent use your tool more effectively, you could:

### 1. **Improve the Description**
```javascript
mcp.registerTool("search", {
  description: "Search and discover MCP servers, APIs, tools, and integrations by keywords, functionality, or use case",
  // ...
});
```

### 2. **Add More Specific Keywords**
```javascript
mcp.registerTool("search", {
  description: "Find MCP servers, APIs, and tools for: calendar integration, database access, file management, email, project management, automation, and more",
  // ...
});
```

### 3. **Better Parameter Descriptions**
```javascript
inputSchema: {
  type: "object",
  properties: {
    query: { 
      type: "string", 
      description: "Search query describing the type of tool, API, or integration you need (e.g., 'calendar tools', 'database APIs', 'file management')" 
    }
  },
  required: ["query"]
}
```

## 🎯 Key Takeaway

The agent uses **semantic understanding** of:
- Your tool's description
- Parameter descriptions  
- User's intent/request

When these align, the agent automatically calls your tool!
