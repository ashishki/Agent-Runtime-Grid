from fastapi.testclient import TestClient

from agent_runtime_grid.api.app import create_app


def test_health_returns_ok(monkeypatch) -> None:
    monkeypatch.setenv("API_TOKEN", "test-token")

    client = TestClient(create_app())
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
