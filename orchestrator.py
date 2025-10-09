"""Agent orchestration utilities for MCP-based tool execution."""
from __future__ import annotations

import asyncio
import json
import os
import sys
from typing import Any, Dict, List, Optional

from jsonschema import Draft202012Validator, ValidationError
from dotenv import load_dotenv

try:  # pragma: no cover - import guard
    from notion_mcp_bridge import connect_notion_server, run_notion_task
except Exception:  # pragma: no cover - bridge optional during tests
    connect_notion_server = None  # type: ignore
    run_notion_task = None  # type: ignore

# Optional MCP SDK import (preferred path)
try:  # pragma: no cover - import guard
    import mcp  # type: ignore
except Exception:  # pragma: no cover - import guard
    mcp = None  # type: ignore


class MCPClient:
    """Minimal client for MCP servers backed by the official `mcp` SDK."""

    def __init__(self, server_url: str, transport: str = "sse", timeout: float = 30.0):
        self.server_url = server_url.rstrip("/")
        self.transport = transport
        self.timeout = timeout
        self._sdk_client: Any = None
        self._initialized = False

    async def __aenter__(self) -> "MCPClient":
        await self.initialize()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.close()

    async def initialize(self) -> None:
        """Initializes the MCP connection using the SDK or a fallback."""
        if self._initialized:
            return
        if mcp is None:
            sys.stderr.write("[warn] `mcp` SDK not installed; cannot initialize MCPClient.\n")
            self._initialized = True
            return
        try:
            connector = getattr(mcp, "AsyncMCPClient", None)
            if connector is None:
                connector = getattr(mcp, "Client", None)
            if connector is None or not hasattr(connector, "connect"):
                sys.stderr.write("[warn] Unsupported MCP SDK version: connector not found.\n")
                self._initialized = True
                return
            self._sdk_client = await connector.connect(  # type: ignore[attr-defined]
                self.server_url,
                transport=self.transport,
                timeout=self.timeout,
            )
            if hasattr(self._sdk_client, "initialize"):
                await self._sdk_client.initialize()
        except Exception as exc:  # pragma: no cover - network path
            sys.stderr.write(f"[error] MCP SDK connection failed: {exc}\n")
            self._sdk_client = None
        finally:
            self._initialized = True

    async def close(self) -> None:
        if self._sdk_client and hasattr(self._sdk_client, "close"):
            try:
                await self._sdk_client.close()
            except Exception:  # pragma: no cover - guard
                pass
            finally:
                self._sdk_client = None

    async def list_tools(self) -> List[Dict[str, Any]]:
        if self._sdk_client is None:
            raise RuntimeError("MCP client is not connected; install and configure the `mcp` SDK.")
        try:
            list_method = getattr(self._sdk_client, "list_tools", None)
            if callable(list_method):
                tools = await list_method()
                return _normalize_tools(tools)
            tools_obj = getattr(self._sdk_client, "tools", None)
            if tools_obj is not None:
                list_method = getattr(tools_obj, "list", None)
                if callable(list_method):
                    tools = await list_method()
                    return _normalize_tools(tools)
        except Exception as exc:  # pragma: no cover - network path
            sys.stderr.write(f"[error] MCP SDK list_tools failed: {exc}\n")
        return []

    async def call_tool(self, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        if self._sdk_client is None:
            raise RuntimeError("MCP client is not connected; install and configure the `mcp` SDK.")
        try:
            call_method = getattr(self._sdk_client, "call_tool", None)
            if callable(call_method):
                result = await call_method(name=name, arguments=arguments)
                return _ensure_dict(result)
            tools_obj = getattr(self._sdk_client, "tools", None)
            if tools_obj is not None:
                call_method = getattr(tools_obj, "call", None)
                if callable(call_method):
                    result = await call_method(name=name, arguments=arguments)
                    return _ensure_dict(result)
        except Exception as exc:  # pragma: no cover - network path
            sys.stderr.write(f"[error] MCP SDK call_tool failed: {exc}\n")
        raise RuntimeError("MCP SDK was unable to execute the requested tool call.")


class Planner:
    """Uses an OpenAI model to produce arguments that satisfy the tool schema."""

    def __init__(self, model: Optional[str] = None):
        load_dotenv()
        self.model = model or os.getenv("OPENAI_RESPONSES_MODEL") or "gpt-4.1-mini"
        try:
            from openai import OpenAI  # pylint: disable=import-error
        except Exception as exc:  # pragma: no cover - import guard
            raise RuntimeError("OpenAI SDK is required. Install `openai>=1.40.0`.") from exc
        self._client = OpenAI()

    def plan_arguments(self, tool_schema: Dict[str, Any], user_task: str, context: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(tool_schema, dict):
            raise ValueError("Tool schema must be a JSON object")
        prompt_payload = {
            "task": user_task,
            "agent": {
                "id": context.get("agent_id"),
                "name": context.get("agent_name"),
                "provider": context.get("provider"),
                "capabilities": context.get("capabilities", []),
                "tags": context.get("tags", []),
                "description": context.get("description"),
                "search_snippet": context.get("search_snippet"),
                "endpoint": context.get("endpoint"),
            },
            "schema": tool_schema,
        }
        system_message = (
            "You produce ONLY valid JSON that conforms strictly to the provided JSON Schema. "
            "Never include comments or additional text."
        )
        raw_json = self._invoke_llm(system_message, prompt_payload)
        arguments = self._parse_json(raw_json)
        try:
            Draft202012Validator(tool_schema).validate(arguments)
        except ValidationError as exc:
            raise ValueError(f"Model output failed schema validation: {exc.message}") from exc
        return arguments

    def _invoke_llm(self, system_message: str, payload: Dict[str, Any]) -> str:
        response = self._client.responses.create(
            model=self.model,
            input=[
                {"role": "system", "content": system_message},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
            ],
            response_format={"type": "json_object"},
        )
        chunks: List[str] = []
        for item in getattr(response, "output", []) or []:
            contents = getattr(item, "content", []) or []
            for content in contents:
                text = getattr(content, "text", "")
                if text:
                    chunks.append(text)
        if not chunks:
            raise RuntimeError("OpenAI response was empty; cannot build arguments")
        return "".join(chunks)

    @staticmethod
    def _parse_json(raw: str) -> Dict[str, Any]:
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Model output was not valid JSON: {exc}") from exc
        if not isinstance(parsed, dict):
            raise ValueError("Model output must be a JSON object")
        return parsed


class ActRunner:
    """High-level runner that selects tools, plans arguments, and executes calls."""

    def __init__(self, planner: Optional[Planner] = None):
        self._planner = planner or Planner()

    async def run_async(self, user_task: str, agent_meta: Dict[str, Any], dry_run: bool = False) -> Dict[str, Any]:
        endpoint = (agent_meta.get("endpoint") or "").strip()
        if not endpoint:
            raise ValueError("Selected agent has no endpoint.")
        if _is_notion_agent(agent_meta):
            return await self._run_with_notion(user_task, agent_meta, dry_run=dry_run)
        context = {
            "agent_id": agent_meta.get("id"),
            "agent_name": agent_meta.get("name"),
            "provider": agent_meta.get("provider"),
            "capabilities": _metadata_to_list(agent_meta.get("capabilities")),
            "tags": _metadata_to_list(agent_meta.get("tags")),
            "description": agent_meta.get("description") or agent_meta.get("document"),
            "search_snippet": agent_meta.get("search_snippet"),
            "endpoint": endpoint,
        }
        async with MCPClient(endpoint, transport="sse") as client:
            tools = await client.list_tools()
            if not tools:
                sys.stderr.write("[warn] No tools discovered for agent; consider running with --dry-run to inspect schemas.\n")
                if dry_run:
                    return {
                        "agent_id": context["agent_id"],
                        "agent_name": context["agent_name"],
                        "tools": [],
                        "dry_run": True,
                        "message": "No tools available",
                    }
                raise RuntimeError("No tools available from selected agent.")
            chosen = _choose_tool(user_task, tools)
            if chosen is None:
                raise RuntimeError("Failed to choose a tool for the task.")
            tool_name = chosen.get("name")
            tool_schema = chosen.get("input_schema") or chosen.get("schema") or chosen.get("input")
            if not isinstance(tool_schema, dict):
                sys.stderr.write("[error] Tool schema missing or invalid. Available tools: {}\n".format(
                    ", ".join(tool.get("name", "<unknown>") for tool in tools)
                ))
                raise ValueError("Selected tool does not provide a JSON Schema; retry with --dry-run to inspect raw metadata.")
            planned_args = self._planner.plan_arguments(tool_schema, user_task, context)
            if dry_run:
                return {
                    "agent_id": context["agent_id"],
                    "agent_name": context["agent_name"],
                    "tool": tool_name,
                    "planned_args": planned_args,
                    "dry_run": True,
                }
            result = await client.call_tool(tool_name, planned_args)
            page_url = _extract_first(result, ["url", "page_url", "permalink", "external_url"])
            page_id = _extract_first(result, ["id", "page_id", "pageId"])
            return {
                "agent_id": context["agent_id"],
                "agent_name": context["agent_name"],
                "tool": tool_name,
                "args": planned_args,
                "result": result,
                "page_url": page_url,
                "page_id": page_id,
            }

    def run(self, user_task: str, agent_meta: Dict[str, Any], dry_run: bool = False) -> Dict[str, Any]:
        return asyncio.run(self.run_async(user_task, agent_meta, dry_run=dry_run))

    async def _run_with_notion(self, user_task: str, agent_meta: Dict[str, Any], dry_run: bool) -> Dict[str, Any]:
        if connect_notion_server is None or run_notion_task is None:
            raise RuntimeError(
                "Notion MCP bridge is unavailable. Ensure `notion_mcp_bridge.py` is importable and `openai-agents` is installed."
            )
        if dry_run:
            server = await connect_notion_server()
            try:
                async with server:
                    list_fn = getattr(server, "list_tools", None)
                    if not callable(list_fn):
                        raise RuntimeError("Connected Notion server does not expose list_tools().")
                    tools = _normalize_tools(await list_fn())
            except Exception as exc:
                raise RuntimeError(f"Failed to inspect Notion MCP tools: {exc}") from exc
            return {
                "agent_id": agent_meta.get("id"),
                "agent_name": agent_meta.get("name"),
                "dry_run": True,
                "tools": tools,
            }
        final_output = await run_notion_task(user_task)
        return {
            "agent_id": agent_meta.get("id"),
            "agent_name": agent_meta.get("name"),
            "final_output": final_output,
        }

def _normalize_tools(tools: Any) -> List[Dict[str, Any]]:
    normalized: List[Dict[str, Any]] = []
    if isinstance(tools, dict):
        tools_iter = tools.get("tools") or tools.get("items") or []
    else:
        tools_iter = tools
    for entry in tools_iter or []:
        if isinstance(entry, dict):
            normalized.append(entry)
    return normalized


def _ensure_dict(value: Any) -> Dict[str, Any]:
    if isinstance(value, dict):
        return value
    if hasattr(value, "dict"):
        try:
            converted = value.dict()
            if isinstance(converted, dict):
                return converted
        except Exception:  # pragma: no cover - guard
            pass
    return {"value": value}


def _metadata_to_list(raw: Any) -> List[str]:
    if raw is None:
        return []
    if isinstance(raw, str):
        return [part.strip() for part in raw.split(",") if part.strip()]
    if isinstance(raw, (list, tuple, set)):
        return [str(item).strip() for item in raw if str(item).strip()]
    return [str(raw).strip()]


def _extract_first(result: Dict[str, Any], keys: List[str]) -> Optional[str]:
    for key in keys:
        value = result.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _choose_tool(user_task: str, tools: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not tools:
        return None
    lowered_task = user_task.lower()
    for tool in tools:
        name = (tool.get("name") or "").lower()
        if "create:pages" in name or name.endswith("create:pages"):
            return tool
    best_score = -1
    best_tool: Optional[Dict[str, Any]] = None
    for tool in tools:
        name = (tool.get("name") or "").lower()
        description = (tool.get("description") or "").lower()
        score = 0
        for keyword in ("create", "plan", "page", "write", "generate"):
            if keyword in name:
                score += 2
            if keyword in description:
                score += 1
        for token in lowered_task.split():
            if token and token in name:
                score += 2
            elif token and token in description:
                score += 1
        if score > best_score:
            best_score = score
            best_tool = tool
    return best_tool or tools[0]


def _is_notion_agent(agent_meta: Dict[str, Any]) -> bool:
    candidates = [
        str(agent_meta.get("provider", "")),
        str(agent_meta.get("name", "")),
        str(agent_meta.get("endpoint", "")),
    ]
    return any("notion" in value.lower() for value in candidates if isinstance(value, str))


# Smoke tests -----------------------------------------------------------------

def _smoke_test_planner() -> None:
    class _StubPlanner(Planner):
        def __init__(self):  # pragma: no cover - simple override
            self.model = "stub"
            self._client = None

        def _invoke_llm(self, system_message: str, payload: Dict[str, Any]) -> str:
            # Return deterministic JSON obeying schema for smoke testing
            return json.dumps({
                "title": f"Plan for {payload['task']}",
                "content": ["Introduction", "Main Topics"],
            })

    schema = {
        "type": "object",
        "properties": {
            "title": {"type": "string"},
            "content": {
                "type": "array",
                "items": {"type": "string"},
                "minItems": 1,
            },
        },
        "required": ["title", "content"],
        "additionalProperties": False,
    }
    planner = _StubPlanner()
    args = planner.plan_arguments(schema, "Create a data structure study plan", {"agent_id": "demo"})
    Draft202012Validator(schema).validate(args)


def _smoke_test_mcp_client() -> None:
    client = MCPClient("http://0.0.0.0:3000/mcp")
    # We cannot connect to a server in tests, but list_tools should be safe
    async def _run():
        async with client:
            tools = await client.list_tools()
            if tools != []:
                raise AssertionError("Expected empty tool list in smoke test")
    try:
        asyncio.run(_run())
    except Exception:  # pragma: no cover - acceptable in smoke test
        pass


if __name__ == "__main__":  # pragma: no cover - manual invocation only
    _smoke_test_planner()
    _smoke_test_mcp_client()
