import os

from fastapi import FastAPI

from agent_runtime_grid.api.routes.jobs import router as jobs_router
from agent_runtime_grid.config import validate_local_auth_boundary


def create_app() -> FastAPI:
    validate_local_auth_boundary(
        api_token=os.environ.get("API_TOKEN"),
        api_bind_host=os.environ.get("API_BIND_HOST", "127.0.0.1"),
    )
    app = FastAPI(title="Agent Runtime Grid")
    app.include_router(jobs_router)

    # Public by design: docs/ARCHITECTURE.md#security-boundaries keeps health status secret-free.
    @app.get("/health", include_in_schema=False)
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
