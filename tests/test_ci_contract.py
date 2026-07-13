from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
CI_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "ci.yml"


def _load_ci_workflow() -> dict[str, Any]:
    with CI_WORKFLOW.open(encoding="utf-8") as workflow_file:
        return yaml.safe_load(workflow_file)


def _test_job() -> dict[str, Any]:
    workflow = _load_ci_workflow()
    return workflow["jobs"]["test"]


def _step_named(steps: list[dict[str, Any]], name_fragment: str) -> dict[str, Any]:
    for step in steps:
        if name_fragment.lower() in step.get("name", "").lower():
            return step
    raise AssertionError(f"Missing CI step containing {name_fragment!r}")


def test_ci_has_required_gates() -> None:
    job = _test_job()
    steps = job["steps"]

    assert any(step.get("uses") == "actions/checkout@v5" for step in steps)

    setup_python = next(step for step in steps if step.get("uses") == "actions/setup-python@v6")
    assert setup_python["with"]["python-version"] == "3.12"

    install = _step_named(steps, "Install dependencies")
    assert "requirements-dev.txt" in install["run"]

    lint = _step_named(steps, "ruff check")
    assert "ruff check" in lint["run"]

    format_check = _step_named(steps, "ruff format")
    assert "ruff format --check" in format_check["run"]

    test = _step_named(steps, "Run tests")
    assert "python -m pytest" in test["run"]


def test_ci_service_env_matches_runtime_contract() -> None:
    job = _test_job()

    postgres = job["services"]["postgres"]
    redis = job["services"]["redis"]

    assert postgres["image"] == (
        "postgres:16.14-alpine3.24@sha256:"
        "57c72fd2a128e416c7fcc499958864df5301e940bca0a56f58fddf30ffc07777"
    )
    assert "pg_isready" in postgres["options"]
    assert postgres["ports"] == ["5432:5432"]
    assert postgres["env"] == {
        "POSTGRES_USER": "testuser",
        "POSTGRES_PASSWORD": "testpassword",
        "POSTGRES_DB": "agent_runtime_grid_test",
    }

    assert redis["image"] == (
        "redis:7.2.14-alpine3.21@sha256:"
        "dfa18828cbc07b3ae6a95ec7343f6c214fdee2d836197b4be8e9904420762cd8"
    )
    assert "redis-cli ping" in redis["options"]
    assert redis["ports"] == ["6379:6379"]

    test_step = _step_named(job["steps"], "Run tests")
    assert test_step["env"]["DATABASE_URL"] == (
        "postgresql+asyncpg://testuser:testpassword@localhost:5432/agent_runtime_grid_test"
    )
    assert test_step["env"]["REDIS_URL"] == "redis://localhost:6379/0"
    assert test_step["env"]["ARTIFACT_ROOT"] == ".artifacts/test"
    assert test_step["env"]["LLM_MODE"] == "stub"
