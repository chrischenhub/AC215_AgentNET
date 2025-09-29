# Set Up

## Docker Onboard
- create a file named `.env` in the folder root to add the api key into the container
    ```
    OPENAI_API_KEY=xxx
    ```
- Build image:
    ```
    docker compose build agentnet
    ```
- Run the docker environment
    ```
    docker compose run --rm agentnet
    ```
## Project ommand documentation
- For windows set up docker:
```
# build iamge
docker build -t agentnet-cli .

# run image
docker run -it --rm --env-file .env -v "${PWD}\DB\chroma_store:/app/DB/chroma_store" agentnet-cli

# Remove all the images built
docker system prune
```
- main.py command
```
# build chroma DB
python main.py ingest --json Data/Agents.json

# Implement RAG search
python main.py search --q "I want to use Notion"
```

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

# AgentNET Search CLI

Minimal retrieval utility for browsing MCP agents stored in Data/Agents.json.

## Prerequisites
- Python 3.10+
- OpenAI API key in .env (copy .env.example -> .env)
- Virtual environment recommended

## Installation
    python -m venv .venv
    source .venv/bin/activate  # Windows: .venv\Scripts\activate
    pip install -r requirements.txt

## Ingest Agents
    python main.py ingest --json Data/Agents.json
Parses multi-agent (mcp array) or single-agent (agent object) manifests, builds OpenAI embeddings (text-embedding-3-large), and persists them to Chroma at DB/chroma_store.

## Search Catalog
    python main.py search --q "I want to use Notion"
Returns the top-3 matches with similarity scores, overlap rationale, endpoint, and leading capabilities.

## Notes
- Chroma collection name: agents_v1
- Capabilities and tags are stored in vector metadata for downstream use.
- Ensure the .env file exists before running commands.
