# AgentNET MCP Server

A Model Context Protocol (MCP) server that provides search and discovery capabilities for MCP servers, APIs, and agents. This server allows AI assistants to search for relevant tools and services by natural language queries.

## 🚀 Quick Start

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

## 🔧 Connecting to Cursor

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

### Method 2: Workspace Configuration

Create a `.cursor-mcp-config.json` file in your workspace root:

```json
{
  "mcpServers": {
    "agentnet": {
      "command": "node",
      "args": [
        "/absolute/path/to/AgentNET/AgentNetMCP/mcp-server.js"
      ]
    }
  }
}
```

## 🛠️ Available Tools

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

## 📊 Database Configuration

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

## 🧪 Testing

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

## 📝 Usage Examples

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

## 🚨 Troubleshooting

### Common Issues

1. **Database Connection Failed**
   ```bash
   # Check if PostgreSQL is running
   docker ps
   
   # Check database logs
   docker-compose logs postgres
   
   # Restart the database
   docker-compose restart postgres
   ```

2. **MCP Server Not Found**
   - Verify the absolute path in your Cursor configuration
   - Ensure the `mcp-server.js` file exists and is executable
   - Restart Cursor after configuration changes

3. **Empty Search Results**
   ```bash
   # Repopulate the database
   node populate-db.js
   ```

4. **Port Conflicts**
   - The database runs on port 5433 to avoid conflicts
   - If you have issues, check what's running on port 5433:
     ```bash
     lsof -i :5433
     ```

### Debug Mode

Enable debug logging by setting environment variables:

```bash
export DEBUG=mcp:*
node mcp-server.js
```

## 🔄 Adding More Data

### Add New Agents

1. **Edit the data file:**
   ```bash
   # Modify Data/Agents.json with new agent data
   ```

2. **Repopulate the database:**
   ```bash
   node populate-db.js
   ```

### Direct Database Access

Connect directly to the database:

```bash
# Using Docker
docker exec -it agentnet-postgres-1 psql -U postgres -d agentnet

# Using local PostgreSQL client
psql -h localhost -p 5433 -U postgres -d agentnet
```

## 📚 API Reference

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

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Add your agent data to `Data/Agents.json`
4. Test your changes
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🆘 Support

If you encounter issues:

1. Check the troubleshooting section above
2. Review the logs: `docker-compose logs postgres`
3. Test the database connection: `node test-integration.js`
4. Verify your Cursor configuration
5. Open an issue on GitHub

---

**🎉 Happy searching! The AgentNET MCP server is ready to help you discover and connect with powerful MCP tools and agents.**
