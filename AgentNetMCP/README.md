# AgentNET MCP Server

A Model Context Protocol (MCP) server that provides search and discovery capabilities for MCP servers. This server allows AI assistants to search for relevant tools and services by natural language queries.

## Quick Start

### Prerequisites

- **Node.js** (v16 or higher)
- **Docker** and **Docker Compose**
- **Cursor** IDE (or any MCP-compatible client)

### Installation

1. **Clone and navigate to the project:**
   ```bash
   git clone <your-repo-url>
   cd AgentNET/AgentNetMCP
   ```

2. **Install dependencies:**
   ```bash
   npm install
   ```

3. **Start the database:**
   ```bash
   # From the project root directory
   cd ..
   docker-compose up postgres -d
   ```

4. **Populate the database:**
   ```bash
   cd AgentNetMCP
   node populate-db.js
   ```

5. **Test the server:**
   ```bash
   node test-integration.js
   ```

## Connecting to Cursor

### Method 1: Global Configuration (Recommended)

Add the MCP server to your Cursor settings:

1. **Open Cursor Settings:**
   - Press `Cmd+,` (Mac) or `Ctrl+,` (Windows/Linux)
   - Or go to `Cursor > Preferences > Settings`

2. **Add MCP Server Configuration:**
   - Click the "Open Settings (JSON)" icon in the top-right
   - Add the following configuration:

   ```json
   {
     "mcp.servers": {
       "agentnet": {
         "command": "node",
         "args": [
           "/absolute/path/to/AgentNET/AgentNetMCP/mcp-server.js"
         ]
       }
     }
   }
   ```

   **⚠️ Important:** Replace `/absolute/path/to/AgentNET/AgentNetMCP/mcp-server.js` with the actual absolute path to your `mcp-server.js` file.

3. **Restart Cursor** to load the new configuration.

## Available Tools

The AgentNET MCP server provides the following tools:

### 1. `search`
Find MCP servers and APIs by natural language query.

**Parameters:**
- `query` (string, required): Tool request in natural language
- `limit` (integer, optional): Maximum number of results to return (default: 10)

**Example:**
```
Search for "notion MCP servers"
```

### 2. `get_agent`
Get detailed information about a specific agent by ID.

**Parameters:**
- `agent_id` (string, required): The unique identifier of the agent

**Example:**
```
Get details for agent "urn:agent:notion:mcp"
```

### 3. `list_agents`
List all available agents with pagination.

**Parameters:**
- `limit` (integer, optional): Maximum number of agents to return (default: 50)
- `offset` (integer, optional): Number of agents to skip for pagination (default: 0)

**Example:**
```
List all agents
```

### 4. `search_by_capability`
Find agents that have a specific capability.

**Parameters:**
- `capability` (string, required): The capability to search for
- `limit` (integer, optional): Maximum number of results to return (default: 10)

**Example:**
```
Find agents with "search" capability
```

### 5. `search_by_tag`
Find agents that have a specific tag.

**Parameters:**
- `tag` (string, required): The tag to search for
- `limit` (integer, optional): Maximum number of results to return (default: 10)

**Example:**
```
Find agents tagged with "productivity"
```

### 6. `semantic_search`
Find agents using semantic similarity search with vector embeddings.

**Parameters:**
- `query` (string, required): Natural language query for semantic search
- `k` (integer, optional): Number of results to return (default: 3)

**Example:**
```
Semantic search for "document management tools"
```

## Database Configuration

The server uses PostgreSQL with the following default configuration:

- **Host:** localhost
- **Port:** 5433 (to avoid conflicts with existing PostgreSQL)
- **Database:** agentnet
- **User:** postgres
- **Password:** mySecurePassword123

### Environment Variables

Create a `.env` file in the `AgentNetMCP` directory to customize database settings:

```bash
# Database Configuration
DB_HOST=localhost
DB_PORT=5433
DB_NAME=agentnet
DB_USER=postgres
DB_PASSWORD=mySecurePassword123

# OpenAI API Key (for semantic search)
OPENAI_API_KEY=your_openai_api_key_here
```

## Testing

### Test Database Connection
```bash
node test-integration.js
```

### Test MCP Server
```bash
# Start the server
node mcp-server.js

# In another terminal, test with JSON-RPC messages
echo '{"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}' | node mcp-server.js
```

Once connected to Cursor, you can use the AgentNET MCP server by asking questions like:

### Basic Search
- "Search for notion MCP servers"
- "Find agents that can help with document management"
- "Look for productivity tools"

### Specific Capabilities
- "Find agents with search capabilities"
- "Show me agents that can create pages"
- "List agents with database management features"

### Tag-based Search
- "Find agents tagged with 'mcp'"
- "Show productivity-related agents"
- "List workspace management tools"

### Detailed Information
- "Get details about the Notion MCP agent"
- "Show me all available agents"
- "List agents with pagination"

## 🔍 Current Data

The database comes pre-populated with:

- **1 Agent:** Notion MCP (Hosted)
- **14 Tools:** Including search, fetch, create-pages, update-page, etc.
- **Provider:** Notion Labs, Inc.
- **Endpoint:** https://mcp.notion.com/mcp
- **Authentication:** OAuth2 required

### Direct Database Access

Connect directly to the database:

```bash
# Using Docker
docker exec -it agentnet-postgres-1 psql -U postgres -d agentnet

# Using local PostgreSQL client
psql -h localhost -p 5433 -U postgres -d agentnet
```

## API Reference

### Agent Schema

```json
{
  "id": "string (unique identifier)",
  "type": "string (agent type)",
  "name": "string (display name)",
  "description": "string (detailed description)",
  "provider": "string (company/organization)",
  "endpoint": "string (API endpoint URL)",
  "capabilities": ["array of strings"],
  "tags": ["array of strings"],
  "auth_required": "boolean",
  "auth_method": "string (auth type)",
  "auth_docs": "string (documentation URL)",
  "trust_verified": "boolean",
  "trust_popularity": "number",
  "trust_source": "string",
  "created_at": "ISO 8601 timestamp"
}
```

### Tool Schema

```json
{
  "agent_id": "string (references agent.id)",
  "name": "string (tool name)",
  "description": "string (tool description)",
  "input_schema": "object (JSON schema)",
  "output_schema": "object (JSON schema)"
}
```