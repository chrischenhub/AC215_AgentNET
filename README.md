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
