import os
from collections.abc import AsyncIterator
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import pytest
import pytest_asyncio
from redis.asyncio import Redis
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from typer.testing import CliRunner

from agent_runtime_grid.cli.benchmark import ReliabilityReport
from agent_runtime_grid.cli.main import app
from agent_runtime_grid.cli.smoke import (
    SmokeValidationError,
    run_smoke,
    validate_smoke_report,
)
from agent_runtime_grid.queue.redis_streams import RedisStreamsQueue
from agent_runtime_grid.storage.models import job_events_table, jobs_table, metadata

DEFAULT_DATABASE_URL = (
    "postgresql+asyncpg://agent_runtime_grid:local-dev-password@localhost:5432/agent_runtime_grid"
)
DEFAULT_REDIS_URL = "redis://localhost:6379/0"


@pytest_asyncio.fixture
async def session_factory() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine = create_async_engine(os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL))
    lock_connection = await engine.connect()
    await lock_connection.execute(text("SELECT pg_advisory_lock(7400)"))

    try:
        async with engine.begin() as connection:
            await connection.run_sync(metadata.drop_all)
            await connection.run_sync(metadata.create_all)

        yield async_sessionmaker(engine, expire_on_commit=False)

        async with engine.begin() as connection:
            await connection.run_sync(metadata.drop_all)
    finally:
        await lock_connection.execute(text("SELECT pg_advisory_unlock(7400)"))
        await lock_connection.close()
        await engine.dispose()


@pytest_asyncio.fixture
async def redis_client() -> AsyncIterator[Redis]:
    client = Redis.from_url(
        os.environ.get("REDIS_URL", DEFAULT_REDIS_URL),
        decode_responses=True,
    )
    try:
        yield client
    finally:
        await client.aclose()


@pytest.fixture
def queue(redis_client: Redis) -> RedisStreamsQueue:
    suffix = uuid4().hex
    return RedisStreamsQueue(
        redis_client,
        stream_name=f"smoke-test-jobs:{suffix}",
        consumer_group="workers",
        dlq_stream_name=f"smoke-test-jobs:{suffix}:dlq",
    )


@pytest.mark.asyncio
async def test_smoke_command_processes_jobs_through_runtime(
    session_factory: async_sessionmaker[AsyncSession],
    queue: RedisStreamsQueue,
    tmp_path: Path,
) -> None:
    result = await run_smoke(
        session_factory=session_factory,
        queue=queue,
        jobs=100,
        workers=4,
        failure_rate=0,
        mode="stub",
        artifact_root=tmp_path / "artifacts",
        report_path=tmp_path / "reports" / "smoke.md",
    )

    async with session_factory() as session:
        completed_jobs = await session.scalar(
            select(func.count())
            .select_from(jobs_table)
            .where(jobs_table.c.run_id == result.run_id, jobs_table.c.status == "completed")
        )
        running_events = await session.scalar(
            select(func.count())
            .select_from(job_events_table)
            .where(
                job_events_table.c.run_id == result.run_id,
                job_events_table.c.event_type == "running",
            )
        )

    assert result.report.submitted_jobs == 100
    assert completed_jobs == 100
    assert running_events == 100
    assert result.report.lifecycle_counts["completed"] == 100
    assert result.report.duplicate_finalization_count == 0
    assert result.report.artifact_completeness == 1
    assert result.report_path.is_file()


@pytest.mark.asyncio
async def test_smoke_report_uses_runtime_state(
    session_factory: async_sessionmaker[AsyncSession],
    queue: RedisStreamsQueue,
    tmp_path: Path,
) -> None:
    result = await run_smoke(
        session_factory=session_factory,
        queue=queue,
        jobs=5,
        workers=2,
        failure_rate=0,
        mode="stub",
        artifact_root=tmp_path / "artifacts",
        report_path=tmp_path / "reports" / "smoke.md",
    )

    async with session_factory() as session:
        persisted_jobs = await session.scalar(
            select(func.count()).select_from(jobs_table).where(jobs_table.c.run_id == result.run_id)
        )

    report_text = result.report_path.read_text(encoding="utf-8")

    assert persisted_jobs == 5
    assert result.report.submitted_jobs == persisted_jobs
    assert result.report.source.startswith("runtime_state:")
    assert f"run id: {result.run_id}" in report_text
    assert "submitted_jobs: 5" in report_text
    assert "artifact completeness: 100.00%" in report_text


def test_smoke_command_fails_on_lifecycle_mismatch(monkeypatch) -> None:
    async def fail_smoke(**_kwargs):
        validate_smoke_report(
            ReliabilityReport(
                submitted_jobs=100,
                lifecycle_counts={"completed": 99, "failed": 0, "timed_out": 0, "cancelled": 0},
                completion_rate=0.99,
                duplicate_finalization_count=0,
                retry_count=0,
                queue_lag_seconds=0,
                p95_duration_seconds=0,
                artifact_completeness=1,
                estimated_cost_usd=Decimal("0"),
            ),
            expected_jobs=100,
        )

    monkeypatch.setattr("agent_runtime_grid.cli.smoke.run_smoke_from_urls", fail_smoke)

    result = CliRunner().invoke(
        app,
        [
            "smoke",
            "--jobs",
            "100",
            "--workers",
            "4",
            "--failure-rate",
            "0",
            "--mode",
            "stub",
            "--report",
            "reports/smoke.md",
        ],
    )

    assert result.exit_code == 1
    assert isinstance(result.exception, SmokeValidationError) is False
    assert "smoke failed:" in result.output
