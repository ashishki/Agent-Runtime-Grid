from fastapi import FastAPI

from agent_runtime_grid.api.routes.jobs import router as jobs_router


def create_app() -> FastAPI:
    app = FastAPI(title="Agent Runtime Grid")
    app.include_router(jobs_router)

    # Public by design: docs/ARCHITECTURE.md#security-boundaries keeps health status secret-free.
    @app.get("/health", include_in_schema=False)
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
