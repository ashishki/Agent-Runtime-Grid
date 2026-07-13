from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_compose() -> dict[str, Any]:
    with (REPO_ROOT / "docker-compose.yml").open(encoding="utf-8") as compose_file:
        return yaml.safe_load(compose_file)


def test_required_services_declared() -> None:
    compose = _load_compose()

    assert set(compose["services"]) == {"postgres", "redis"}
    assert compose["services"]["postgres"]["image"] == (
        "postgres:16.14-alpine3.24@sha256:"
        "57c72fd2a128e416c7fcc499958864df5301e940bca0a56f58fddf30ffc07777"
    )
    assert compose["services"]["redis"]["image"] == (
        "redis:7.2.14-alpine3.21@sha256:"
        "dfa18828cbc07b3ae6a95ec7343f6c214fdee2d836197b4be8e9904420762cd8"
    )
    assert compose["services"]["postgres"]["ports"] == ["127.0.0.1:5432:5432"]
    assert compose["services"]["redis"]["ports"] == ["127.0.0.1:6379:6379"]


def test_compose_does_not_commit_real_secret_markers() -> None:
    compose_text = (REPO_ROOT / "docker-compose.yml").read_text(encoding="utf-8")

    forbidden_secret_markers = (
        "sk-",
        "ghp_",
        "gho_",
        "github_pat_",
        "OPENAI_API_KEY",
        "GITHUB_TOKEN",
        "API_TOKEN",
    )
    for marker in forbidden_secret_markers:
        assert marker not in compose_text
