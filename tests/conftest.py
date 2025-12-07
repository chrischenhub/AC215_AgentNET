from __future__ import annotations

import sys
import types
from pathlib import Path
import importlib.util
import typing

from pydantic._internal import _typing_extra


# Install a lightweight stub for the external `agents` package so tests can run
# in environments without the dependency (or on Python versions it doesn't support).
def _install_agents_stub() -> None:
    if "agents" in sys.modules:
        return

    agents_mod = types.ModuleType("agents")

    class Agent:
        def __init__(self, *args, **kwargs):
            pass

        # Agent instances carry MCP servers; keep interface minimal for tests.
        mcp_servers: list = []

    class Runner:
        @staticmethod
        async def run(*args, **kwargs):
            return {"final_output": "", "raw_output": {}}

    mcp_mod = types.ModuleType("agents.mcp")

    class MCPServerStreamableHttp:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            return False

    model_settings_mod = types.ModuleType("agents.model_settings")

    class ModelSettings:
        def __init__(self, *args, **kwargs):
            pass

    agents_mod.Agent = Agent
    agents_mod.Runner = Runner
    agents_mod.mcp = mcp_mod
    agents_mod.model_settings = model_settings_mod
    mcp_mod.MCPServerStreamableHttp = MCPServerStreamableHttp
    model_settings_mod.ModelSettings = ModelSettings

    sys.modules["agents"] = agents_mod
    sys.modules["agents.mcp"] = mcp_mod
    sys.modules["agents.model_settings"] = model_settings_mod


def _load_notion_agent_with_future_annotations() -> None:
    """
    On Python 3.9 the `|` union syntax in notion_agent.py fails at import time
    because the module does not use `from __future__ import annotations`.
    Rather than change the source, we load it here with the future flag injected.
    """
    if sys.version_info >= (3, 10) or "notion_agent" in sys.modules:
        return

    path = Path(__file__).resolve().parents[1] / "src" / "models" / "notion_agent.py"
    source = path.read_text()
    if "from __future__ import annotations" not in source.splitlines()[:3]:
        source = "from __future__ import annotations\n" + source

    spec = importlib.util.spec_from_loader("notion_agent", loader=None)
    module = importlib.util.module_from_spec(spec)
    sys.modules["notion_agent"] = module
    exec(compile(source, str(path), "exec"), module.__dict__)


_install_agents_stub()
_load_notion_agent_with_future_annotations()
_orig_eval_type_backport = _typing_extra.eval_type_backport


def _safe_eval_type_backport(value, globalns=None, localns=None, type_params=None):
    if isinstance(value, str) and "|" in value:
        # Pydantic tries to evaluate PEP 604 unions; on Python 3.9 fallback to Any.
        return typing.Any
    try:
        return _orig_eval_type_backport(value, globalns, localns, type_params)
    except TypeError:
        return typing.Any


# Ensure pydantic doesn't crash on PEP 604 union strings under Python 3.9.
_typing_extra.eval_type_backport = _safe_eval_type_backport

# Ensure the src/models directory is importable when running tests locally.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
MODELS_PATH = PROJECT_ROOT / "src" / "models"
if str(MODELS_PATH) not in sys.path:
    sys.path.insert(0, str(MODELS_PATH))
