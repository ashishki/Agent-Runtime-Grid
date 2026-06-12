import pytest
from fastapi.testclient import TestClient

from agent_runtime_grid.api.app import create_app


def test_health_is_public_and_secret_free(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("API_TOKEN", "test-token")
    monkeypatch.setenv("API_BIND_HOST", "0.0.0.0")
    client = TestClient(create_app())

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    rendered = response.text
    assert "test-token" not in rendered
    assert "API_TOKEN" not in rendered
    assert "DATABASE_URL" not in rendered


def test_non_health_routes_require_configured_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("API_TOKEN", "test-token")
    monkeypatch.setenv("API_BIND_HOST", "0.0.0.0")
    client = TestClient(create_app())

    assert client.post("/jobs/batch", json={"count": 1, "job_type": "stub"}).status_code == 401
    assert (
        client.get(
            "/jobs/runs/run-1/status",
            headers={"Authorization": "Bearer wrong-token"},
        ).status_code
        == 401
    )

    accepted = client.post(
        "/jobs/batch",
        json={"count": 1, "job_type": "stub"},
        headers={"Authorization": "Bearer test-token"},
    )
    status_response = client.get(
        "/jobs/runs/run-1/status",
        headers={"Authorization": "Bearer test-token"},
    )

    assert accepted.status_code == 202
    assert accepted.json() == {"status": "accepted"}
    assert status_response.status_code == 200
    assert status_response.json() == {"run_id": "run-1", "status": "pending"}


def test_no_token_mode_requires_localhost_bind(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("API_TOKEN", raising=False)
    monkeypatch.setenv("API_BIND_HOST", "127.0.0.1")
    local_client = TestClient(create_app())

    local_response = local_client.post("/jobs/batch", json={"count": 1, "job_type": "stub"})

    assert local_response.status_code == 202

    monkeypatch.setenv("API_BIND_HOST", "0.0.0.0")
    with pytest.raises(ValueError, match="API_TOKEN is required"):
        create_app()
