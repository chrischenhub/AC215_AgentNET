# Virtual Machine Set Up

# AgentNet RAG search + MCP Execution
## Quickstart
1. Copy the example environment file and fill in your keys:
   ```bash
   cp .env.example .env
   # edit .env to add OPENAI_API_KEY, SMITHERY_API_KEY, etc.
   ```
2. Build the image and start the stack (Postgres + dev container):
   ```bash
   docker compose up -d --build
   ```

3. Execute the workflow RAG search + MCP
    ```
    docker compose exec agentnet python notion_agent.py "What do you want to do"
    ```

## Data Pipeline

`parentPageExtract.py`: discover and scrape MCP parent pages to build a list of MCP servers (id, discovery_url, minimal metadata) and write the result to servers.csv

`childpageextract.py`: read servers.csv, visit each server entry to extract full server details (tools, parameters, descriptions, endpoints, provider, tags), normalize fields, and write the result to servers_full.csv

`mcp_to_json.py`: convert servers_full.csv into a canonical agents.json (serialize rows into the expected JSON schema / `mcp` array or top-level `agent` objects), validate required fields, and write agents.json

`RAG.py`: load agents.json, chunk content **by tool** (one chunk per tool including tool_name, tool_description, parameters, plus agent metadata), compute embeddings for each chunk, add texts+metadata to a Chroma collection persisted at DB/chroma_store, call persist(), and upload the DB/chroma_store directory to the configured Google Cloud Storage bucket (e.g., gs://your-bucket/agents_v1)



# Agent Net MVP Roadmap

## Phase 0 — Foundations (Week 0–1)
**Goal:** Get the skeleton of the system up.  

- Define the unified manifest schema (JSON format for MCP servers, APIs, true agents).
- Pick core tech stack:
  - **Backend:** Python (FastAPI) or Node.js (Express)
  - **DB:** Postgres + pgvector
  - **Embeddings:** OpenAI `text-embedding-3-small` or open-source (e.g., `bge-small`)
- Set up repo, CI/CD, and simple deployment target (Railway/Render/Heroku).  

**Deliverable:** Empty but running API + DB with manifest schema defined.

---

## Phase 1 — Seed Registry (Week 1–2)
**Goal:** Have something searchable.  

- Ingest 10–15 MCP-native servers (Stripe, Notion, Perplexity, etc.) → store endpoint + manifest.  
- Manually stub 5–10 non-MCP APIs (Slack, Gmail, FedEx).  
- Add 2–3 “true agents” (simple scripted workflows).  
- Store all in Postgres with embeddings pre-computed.  

**Deliverable:** ~20 searchable entries in registry.

---

## Phase 2 — Search API (Week 2–3)
**Goal:** Make the index callable by LLMs.  

- Implement `/search` endpoint:  
  **Input:**  
  ```json
  { "query": "take notes", "top_k": 5 }



## Notes
- Python 3.10+ recommended.
- Chroma collection name: agents_v1.
- Capabilities and tags are stored in vector metadata for downstream use.
- Ensure the .env file exists before running commands.
