from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_gitignore_excludes_runtime_outputs() -> None:
    ignored_patterns = {
        line.strip()
        for line in (REPO_ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    }

    assert {
        ".env",
        ".env.*",
        "/.artifacts/",
        "/artifacts/",
        "/reports/",
        "__pycache__/",
        ".pytest_cache/",
        ".ruff_cache/",
        ".coverage",
        "htmlcov/",
    } <= ignored_patterns
