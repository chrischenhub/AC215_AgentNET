Agent Net MVP Roadmap
Phase 0 — Foundations (Week 0–1)
Goal: Get the skeleton of the system up.
Define the unified manifest schema (JSON format for MCP servers, APIs, true agents).


Pick core tech stack:


Backend: Python (FastAPI) or Node.js (Express).


DB: Postgres + pgvector.


Embeddings: OpenAI text-embedding-3-small or open-source (e.g., bge-small).


Set up repo, CI/CD, and simple deployment target (Railway/Render/Heroku).


Deliverable: Empty but running API + DB with manifest schema defined.

Phase 1 — Seed Registry (Week 1–2)
Goal: Have something searchable.
Ingest 10–15 MCP-native servers (Stripe, Notion, Perplexity, etc.) → store endpoint + manifest.


Manually stub 5–10 non-MCP APIs (Slack, Gmail, FedEx).


Add 2–3 “true agents” (simple scripted workflows).


Store all in Postgres with embeddings pre-computed.


Deliverable: ~20 searchable entries in registry.

Phase 2 — Search API (Week 2–3)
Goal: Make the index callable by LLMs.
Implement /search endpoint:


Input: { "query": "take notes", "top_k": 5 }


Output: ranked list of manifests.


Ranking = BM25 + embeddings hybrid.


Add simple AgentRank scoring (relevance + trust flag).


Test with basic LLM calls (query → get manifest → print result).


Deliverable: API that LLMs can query for tool discovery.

Phase 3 — Minimal Web UI (Week 3–4)
Goal: Human-facing demo surface.
Build lightweight Next.js app with:


Search bar.


Result list (name, description, endpoint).


Tool details page (manifest, config snippet, “How to use” instructions).


Style minimally (think npmjs.org, not fancy).


Ensure copy-paste config snippets work in Cursor/Claude Desktop.


Deliverable: Demo-ready UI that feels like “Google/NPM for agents.”

Phase 4 — Demo Integration (Week 4–5)
Goal: Prove end-to-end value.
Set up a mock runtime (tiny script) that queries Agent Net → retrieves Notion MCP → prints config.


Show human flow: “search → copy snippet → paste into Cursor → authenticate → create Notion page.”


Polish investor demo with 2–3 canonical use cases:


“Take notes” → Notion.


“Send payment” → Stripe.


“Track package” → FedEx.


Deliverable: End-to-end demo showing Agent Net as the discovery layer.

Phase 5 — Stretch / Post-MVP (Optional, Week 6+)
Crawl MCP Market and auto-ingest MCP servers.


Add filters (category, verified, trending).


Export configs directly into runtimes (Cursor, LangChain).


Collect usage telemetry → feed back into AgentRank.



Timeline Snapshot
Week 0–1: Foundations


Week 1–2: Seed registry


Week 2–3: Search API


Week 3–4: Minimal Web UI


Week 4–5: Demo integration


Week 6+: Stretch



