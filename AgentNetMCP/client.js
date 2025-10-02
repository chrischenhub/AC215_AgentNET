import fetch from "node-fetch";

const res = await fetch("http://localhost:3000/mcp", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({
    jsonrpc: "2.0",
    id: 1,
    method: "search",
    params: { query: "calendar integration" }
  })
});

const data = await res.json();
console.log("MCP server response:", JSON.stringify(data, null, 2));
