from __future__ import annotations

from sqlalchemy.engine import make_url


class UnsafeDatabaseResetError(RuntimeError):
    pass


_LOCAL_HOSTS = frozenset({"localhost", "127.0.0.1", "::1", "postgres"})
_LOCAL_DATABASES = frozenset({"agent_runtime_grid", "agent_runtime_grid_test"})


def require_safe_local_reset(database_url: str) -> None:
    url = make_url(database_url)
    host = (url.host or "").lower()
    database = (url.database or "").lower()
    if host not in _LOCAL_HOSTS or database not in _LOCAL_DATABASES:
        raise UnsafeDatabaseResetError(
            "database reset is restricted to the local agent_runtime_grid project/test database"
        )
