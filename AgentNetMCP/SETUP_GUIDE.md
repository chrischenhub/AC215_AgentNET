# AgentNet MCP Setup Guide

## Port Conflict Resolution

Your system already has PostgreSQL running on port 5432. I've updated the Docker configuration to use port 5433 instead.

## Setup Steps

### 1. Create Environment File
Create a `.env` file in the `AgentNetMCP` directory with:

```bash
# Database Configuration for Docker PostgreSQL
DB_HOST=localhost
DB_PORT=5433
DB_NAME=agentnet
DB_USER=postgres
DB_PASSWORD=password

# OpenAI API Key (for vector embeddings if needed)
OPENAI_API_KEY=your_openai_api_key_here
```

### 2. Install Dependencies
```bash
cd AgentNetMCP
npm install
```

### 3. Start PostgreSQL Database
```bash
# Start the PostgreSQL container on port 5433
docker-compose up postgres -d
```

### 4. Verify Database is Running
```bash
# Check if the container is running
docker ps

# Check logs if needed
docker-compose logs postgres
```

### 5. Populate Database
```bash
# First, ingest the agent data into the database
python main.py ingest --json Data/Agents.json
```

### 6. Test Integration
```bash
cd AgentNetMCP
node test-integration.js
```

### 7. Start MCP Server
```bash
node mcp-server.js
```

## Alternative: Use Existing PostgreSQL

If you prefer to use your existing PostgreSQL installation instead of Docker:

1. **Create the database:**
   ```bash
   /Library/PostgreSQL/17/bin/createdb -U postgres agentnet
   ```

2. **Load the schema:**
   ```bash
   /Library/PostgreSQL/17/bin/psql -U postgres -d agentnet -f DB/schema.sql
   ```

3. **Update .env file to use port 5432:**
   ```bash
   DB_HOST=localhost
   DB_PORT=5432
   DB_NAME=agentnet
   DB_USER=postgres
   DB_PASSWORD=your_postgres_password
   ```

4. **Install pgvector extension** (if not already installed):
   ```bash
   /Library/PostgreSQL/17/bin/psql -U postgres -d agentnet -c "CREATE EXTENSION IF NOT EXISTS vector;"
   ```

## Troubleshooting

### Port Already in Use
- ✅ **Fixed**: Docker now uses port 5433 instead of 5432
- Your existing PostgreSQL on port 5432 will remain unaffected

### Database Connection Issues
- Verify the database is running: `docker ps`
- Check database logs: `docker-compose logs postgres`
- Ensure environment variables are correct

### Vector Search Issues
- Make sure OpenAI API key is set in `.env`
- Verify Chroma vector store is populated
- Check Python dependencies are installed

## Next Steps

Once the database is running and populated, you can:
1. Test the MCP server integration
2. Configure your MCP client to use the server
3. Start using the AgentNet search capabilities
