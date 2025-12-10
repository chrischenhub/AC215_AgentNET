from __future__ import annotations

import os
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from workflow import (
    DEFAULT_K_TOOLS,
    DEFAULT_PERSIST_DIR,
    DEFAULT_TOP_SERVERS,
    AgentRunEnvelope,
    add_direct_answer_option,
    async_rag_search,
    execute_agent_workflow,
)


app = FastAPI(title="AgentNet Web")


def _parse_origins(raw: str | None) -> list[str]:
    if not raw:
        return ["*"]
    return [origin.strip() for origin in raw.split(",") if origin.strip()]


allowed_origins = _parse_origins(os.getenv("FRONTEND_ORIGINS"))
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class SearchPayload(BaseModel):
    query: str = Field(..., description="Natural language query for the RAG search.")
    notion_instruction: str | None = Field(
        None,
        description="Optional instruction for the Agent. Defaults to the query when omitted.",
    )
    persist_dir: str = Field(
        DEFAULT_PERSIST_DIR,
        description="Location of the Chroma DB.",
    )
    catalog: str | None = Field(
        None,
        description="Optional catalog path override.",
    )
    top_servers: int = Field(
        DEFAULT_TOP_SERVERS,
        ge=1,
        le=10,
        description="Number of servers to return.",
    )
    k_tools: int = Field(
        DEFAULT_K_TOOLS,
        ge=1,
        description="Number of tool chunks to retrieve before aggregation.",
    )
    reindex: bool = Field(
        False,
        description="Whether to force a rebuild of the vector store.",
    )


class ExecutePayload(BaseModel):
    notion_instruction: str = Field(..., description="Instruction to send to the AgentNet.")
    child_link: str | None = Field(
        None,
        description="MCP child link for the selected server.",
    )
    server_name: str | None = Field(
        None,
        description="Display name of the selected server (used for contextual prompts).",
    )
    clarified_instruction: str | None = Field(
        None,
        description="Optional refined instruction to override the original query.",
    )
    notion_mcp_base_url_override: str | None = Field(
        None,
        description="Direct override of the MCP base URL (advanced).",
    )
    mode: str | None = Field(
        None,
        description="Optional execution mode. Use 'direct' to skip MCP tools.",
    )
    history: list[dict[str, str]] | None = Field(
        None,
        description="Recent conversation turns to provide short-term memory.",
    )


def render_agent_response(envelope: AgentRunEnvelope) -> dict[str, Any]:
    return {
        "mcp_base_url": envelope.mcp_base_url,
        "final_output": envelope.final_output,
        "raw_output": envelope.raw_output,
    }


@app.get("/", response_class=HTMLResponse)
async def index() -> HTMLResponse:
    frontend_url = os.getenv("FRONTEND_URL")
    body = "AgentNet API is running."
    if frontend_url:
        body += f' Frontend is served at <a href="{frontend_url}">{frontend_url}</a>.'
    return HTMLResponse(body)


@app.post("/api/search")
async def api_search(payload: SearchPayload) -> dict[str, Any]:
    try:
        results = add_direct_answer_option(
            await async_rag_search(
                payload.query,
                persist_dir=payload.persist_dir,
                catalog_path=payload.catalog,
                top_servers=payload.top_servers,
                k_tools=payload.k_tools,
                force_reindex=payload.reindex,
            )
        )
    except Exception as exc:  # pragma: no cover - surfaced back to UI
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {
        "results": results,
        "notion_instruction": payload.notion_instruction or payload.query,
    }


@app.post("/api/execute")
async def api_execute(payload: ExecutePayload) -> dict[str, Any]:
    try:
        envelope = await execute_agent_workflow(
            notion_instruction=payload.notion_instruction,
            child_link=payload.child_link,
            server_name=payload.server_name,
            clarified_instruction=payload.clarified_instruction,
            notion_mcp_base_url_override=payload.notion_mcp_base_url_override,
            include_raw_payload=True,
            mode=payload.mode,
            history=payload.history,
        )
    except Exception as exc:  # pragma: no cover - surfaced back to UI
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return render_agent_response(envelope)


def create_app() -> FastAPI:
    return app


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app,
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", "8000")),
        reload=bool(os.getenv("DEV_RELOAD")),
    )
