# Debugging Cursor MCP Integration

## Current Status
- ✅ MCP server (`mcp-server.js`) is working correctly
- ✅ Configuration files created (`mcp.json`, `cursor-mcp-config.json`)
- ❓ Cursor still shows "no tools, prompts, or resources"

## Steps to Fix Cursor Integration:

### 1. **Place Configuration in Correct Location**
Copy the content from `mcp.json` to one of these locations:

**Global Configuration (Recommended):**
- Windows: `%USERPROFILE%\.cursor\mcp.json`
- macOS: `~/.cursor/mcp.json`

**Project Configuration:**
- Place `mcp.json` in your project root (already done)

### 2. **Verify Configuration Content**
Your `mcp.json` should contain:
```json
{
  "mcpServers": {
    "agentnet": {
      "command": "node",
      "args": [
        "C:/Users/Chris/Documents/GitHub/AgentNetMCP/mcp-server.js"
      ]
    }
  }
}
```

### 3. **Restart Cursor Completely**
- Close all Cursor windows
- Restart the application
- This is crucial for loading new MCP configurations

### 4. **Check Cursor Settings**
- Go to Settings → Tools & Integrations → MCP Tools
- Look for "agentnet" server
- Ensure the toggle is ON

### 5. **Test in Cursor Chat**
Once configured:
1. Open chat panel (`Ctrl+I` or `Cmd+I`)
2. Make sure you're in **Agent mode**
3. Try: "Search for calendar integration tools"

### 6. **If Still Not Working**
Check Cursor's developer console:
- Press `Ctrl+Shift+I` (Windows) or `Cmd+Option+I` (macOS)
- Look for MCP-related errors in Console tab

## Expected Search Results
When working, your search should return:
- Notion MCP (Access Notion workspace tasks, notes, and projects)
- GitHub MCP (Interact with GitHub repositories and issues)

