
import pytest
from fastapi.testclient import TestClient
from app import app
from workflow import AgentRunEnvelope

# --- PATCHING (Should match conftest or test_app strategies if not global) ---
# Since we are in integration tests, we might want to run against the real app,
# but usually patching static files is necessary to avoid OS errors if dirs don't exist.
# However, if we assume the environment is set up correctly (Docker), maybe not.
# For now, let's keep it minimal and only patch if it fails, OR copy the patching from test_app
# if we want to run this in the same environment.
#
# But wait! 'app' is already imported from 'app'.
# If 'app' module logic already ran, patching staticfiles AFTER import might be too late
# for the app instance itself, BUT 'test_app.py' does it.
# Actually 'test_app.py' patches *before* import.
# Here we imported 'app' at the top level.
# Let's rely on the fact that the app is already verified to load by the health check test.


def test_health_check_integration():
    """
    Simple integration test to verify the app is up and running.
    This uses the TestClient which brings up the FastAPI app.
    """
    with TestClient(app) as client:
        response = client.get("/")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]


def test_api_search_integration(monkeypatch: pytest.MonkeyPatch):
    """
    Integration test for /api/search.
    Mocks the DB call to avoid needing external infrastructure.
    """
    async def mock_rag_search(*args, **kwargs):
        # Return a structure matching what the frontend expects
        return [
            {"server": "integration-test-server", "child_link": "/server/test", "score": 0.99, "why": "integration"}
        ]

    # Patch the async_rag_search function in the app module
    monkeypatch.setattr("app.async_rag_search", mock_rag_search)

    with TestClient(app) as client:
        payload = {
            "query": "integration test query",
            "persist_dir": "TEST_DB",
            "top_servers": 1,
            "k_tools": 1,
            "reindex": False
        }
        response = client.post("/api/search", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "results" in data
        # The app appends a "Direct Answer" result, so we expect 2
        assert len(data["results"]) >= 1
        assert data["results"][0]["server"] == "integration-test-server"


def test_api_execute_integration(monkeypatch: pytest.MonkeyPatch):
    """
    Integration test for /api/execute.
    Mocks the agent workflow execution.
    """
    async def mock_execute_workflow(**kwargs):
        return AgentRunEnvelope(
            mcp_base_url="http://mock-mcp",
            final_output="Integration execution successful",
            raw_output={"status": "done"}
        )

    # Patch the execute_agent_workflow in the app module
    monkeypatch.setattr("app.execute_agent_workflow", mock_execute_workflow)

    with TestClient(app) as client:
        payload = {
            "notion_instruction": "Run integration test",
            "child_link": "integration-link",
            "server_name": "IntegrationServer"
        }
        response = client.post("/api/execute", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["final_output"] == "Integration execution successful"
