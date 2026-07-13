import pytest

from agent_runtime_grid.storage.safety import UnsafeDatabaseResetError, require_safe_local_reset


@pytest.mark.parametrize(
    "database_url",
    [
        "postgresql+asyncpg://user:password@localhost:5432/agent_runtime_grid",
        "postgresql+asyncpg://user:password@127.0.0.1:5432/agent_runtime_grid_test",
        "postgresql+asyncpg://user:password@postgres:5432/agent_runtime_grid",
    ],
)
def test_local_project_databases_are_eligible_for_explicit_reset(database_url: str) -> None:
    require_safe_local_reset(database_url)


@pytest.mark.parametrize(
    "database_url",
    [
        "postgresql+asyncpg://user:password@db.example.com:5432/agent_runtime_grid",
        "postgresql+asyncpg://user:password@localhost:5432/postgres",
        "postgresql+asyncpg://user:password@localhost:5432/customer_data",
    ],
)
def test_remote_or_unrelated_databases_are_never_reset(database_url: str) -> None:
    with pytest.raises(UnsafeDatabaseResetError, match="restricted"):
        require_safe_local_reset(database_url)
