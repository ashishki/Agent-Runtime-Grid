import os
from collections.abc import AsyncIterator
from pathlib import Path
from uuid import uuid4

import pytest
import pytest_asyncio
from redis.asyncio import Redis
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from agent_runtime_grid.cli.main import (
    cleanup_run_outputs,
    format_status,
    lifecycle_counts,
    submit_batch,
)
from agent_runtime_grid.queue.redis_streams import RedisStreamsQueue
from agent_runtime_grid.storage.models import jobs_table, metadata

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
        stream_name=f"cli-jobs:{suffix}",
        consumer_group="workers",
        dlq_stream_name=f"cli-jobs:{suffix}:dlq",
    )


@pytest.mark.asyncio
async def test_submit_batch_creates_expected_job_count(
    session_factory: async_sessionmaker[AsyncSession],
    queue: RedisStreamsQueue,
    redis_client: Redis,
) -> None:
    result = await submit_batch(
        session_factory=session_factory,
        queue=queue,
        count=100,
        job_type="stub",
    )

    async with session_factory() as session:
        job_count = await session.scalar(
            select(func.count()).select_from(jobs_table).where(jobs_table.c.run_id == result.run_id)
        )
        run_count = await session.scalar(select(func.count(func.distinct(jobs_table.c.run_id))))

    assert result.job_count == 100
    assert job_count == 100
    assert run_count == 1
    assert await redis_client.xlen(queue.stream_name) == 100


@pytest.mark.asyncio
async def test_status_reports_lifecycle_counts(
    session_factory: async_sessionmaker[AsyncSession],
    queue: RedisStreamsQueue,
) -> None:
    result = await submit_batch(
        session_factory=session_factory,
        queue=queue,
        count=3,
        job_type="stub",
    )

    status_text = format_status(
        await lifecycle_counts(session_factory=session_factory, run_id=result.run_id)
    )

    assert "queued: 3" in status_text
    assert "running: 0" in status_text
    assert "completed: 0" in status_text
    assert "failed: 0" in status_text
    assert "timed out: 0" in status_text
    assert "cancelled: 0" in status_text
    assert "retry: 0" in status_text
    assert "DLQ: 0" in status_text


@pytest.mark.asyncio
async def test_cleanup_removes_artifacts_without_metadata_delete(
    session_factory: async_sessionmaker[AsyncSession],
    queue: RedisStreamsQueue,
    tmp_path: Path,
) -> None:
    result = await submit_batch(
        session_factory=session_factory,
        queue=queue,
        count=1,
        job_type="stub",
    )
    artifact_root = tmp_path / "artifacts"
    reports_root = tmp_path / "reports"
    run_artifacts = artifact_root / str(result.run_id)
    run_artifacts.mkdir(parents=True)
    (run_artifacts / "artifact.json").write_text("{}", encoding="utf-8")
    reports_root.mkdir(parents=True)
    (reports_root / f"{result.run_id}.md").write_text("report", encoding="utf-8")

    removed = cleanup_run_outputs(
        run_id=result.run_id,
        artifact_root=artifact_root,
        reports_root=reports_root,
    )

    async with session_factory() as session:
        job_count = await session.scalar(select(func.count()).select_from(jobs_table))

    assert {path.name for path in removed} == {str(result.run_id), f"{result.run_id}.md"}
    assert not run_artifacts.exists()
    assert not (reports_root / f"{result.run_id}.md").exists()
    assert job_count == 1
