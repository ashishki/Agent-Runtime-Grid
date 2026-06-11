from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_compose() -> dict[str, Any]:
    with (REPO_ROOT / "docker-compose.yml").open(encoding="utf-8") as compose_file:
        return yaml.safe_load(compose_file)


def test_required_services_declared() -> None:
    compose = _load_compose()

    assert set(compose["services"]) >= {
        "api",
        "worker",
        "postgres",
        "redis",
        "prometheus",
        "grafana",
    }


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
