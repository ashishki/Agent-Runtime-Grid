from agent_runtime_grid.config import Settings, load_settings


def test_settings_load_runtime_contract(monkeypatch, tmp_path) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".env").write_text(
        "\n".join(
            [
                "DATABASE_URL=postgresql+asyncpg://wrong:wrong@wrong:5432/wrong",
                "REDIS_URL=redis://wrong:6379/9",
                "ARTIFACT_ROOT=/wrong",
                "LLM_MODE=live",
            ]
        ),
        encoding="utf-8",
    )

    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql+asyncpg://testuser:testpassword@localhost:5432/agent_runtime_grid_test",
    )
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("ARTIFACT_ROOT", str(tmp_path / "artifacts"))
    monkeypatch.setenv("API_TOKEN", "test-token")
    monkeypatch.setenv("LLM_MODE", "stub")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)

    settings = load_settings()

    assert isinstance(settings, Settings)
    assert settings.database_url.endswith("/agent_runtime_grid_test")
    assert settings.redis_url == "redis://localhost:6379/0"
    assert settings.artifact_root == str(tmp_path / "artifacts")
    assert settings.api_token == "test-token"
    assert settings.llm_mode == "stub"
    assert settings.openai_api_key is None
    assert settings.github_token is None
