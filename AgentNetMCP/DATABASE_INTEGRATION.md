# AgentNet MCP Database Integration

This document explains how the AgentNet MCP server is now connected to the PostgreSQL database.

## Database Configuration

The MCP server now connects to the PostgreSQL database using the following environment variables:

```bash
DB_HOST=localhost
DB_PORT=5432
DB_NAME=agentnet
DB_USER=postgres
DB_PASSWORD=password
```

## Available Tools

The MCP server now provides the following tools that interact with the real database:

### 1. `search`
- **Description**: Find MCP servers and APIs by natural language query
- **Parameters**:
  - `query` (required): Natural language search query
  - `limit` (optional): Maximum number of results (default: 10)

### 2. `get_agent`
- **Description**: Get detailed information about a specific agent by ID
- **Parameters**:
  - `agent_id` (required): The unique identifier of the agent

### 3. `list_agents`
- **Description**: List all available agents with pagination
- **Parameters**:
  - `limit` (optional): Maximum number of agents to return (default: 50)
  - `offset` (optional): Number of agents to skip for pagination (default: 0)

### 4. `search_by_capability`
- **Description**: Find agents that have a specific capability
- **Parameters**:
  - `capability` (required): The capability to search for
  - `limit` (optional): Maximum number of results (default: 10)

### 5. `search_by_tag`
- **Description**: Find agents that have a specific tag
- **Parameters**:
  - `tag` (required): The tag to search for
  - `limit` (optional): Maximum number of results (default: 10)

## Database Schema

The integration uses the following tables:

- **agents**: Main table storing agent information
- **tools**: Tools associated with each agent
- **agent_embeddings**: Vector embeddings for semantic search (future enhancement)

## Setup Instructions

1. **Install Dependencies**:
   ```bash
   cd AgentNetMCP
   npm install
   ```

2. **Set Environment Variables**:
   Create a `.env` file in the AgentNetMCP directory with:
   ```bash
   DB_HOST=localhost
   DB_PORT=5432
   DB_NAME=agentnet
   DB_USER=postgres
   DB_PASSWORD=password
   ```

3. **Start PostgreSQL Database**:
   ```bash
   docker-compose up postgres -d
   ```

4. **Populate Database**:
   Use the existing AgentNet Python scripts to ingest data:
   ```bash
   python main.py ingest --json Data/Agents.json
   ```

5. **Test MCP Server**:
   ```bash
   cd AgentNetMCP
   node mcp-server.js
   ```

## Docker Integration

The `docker-compose.yml` has been updated to include:
- PostgreSQL service with pgvector extension
- Automatic schema initialization
- Health checks for proper startup ordering
- Persistent data volume

## Future Enhancements

- Vector search integration using the existing Chroma setup
- Real-time agent discovery
- Caching layer for improved performance
- Authentication and authorization

