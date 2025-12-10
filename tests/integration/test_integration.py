from fastapi.testclient import TestClient
from app import app

def test_health_check_integration():
    """
    Simple integration test to verify the app is up and running.
    This uses the TestClient which brings up the FastAPI app.
    """
    with TestClient(app) as client:
        response = client.get("/")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
