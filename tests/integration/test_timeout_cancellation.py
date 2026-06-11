import asyncio
import os
from collections.abc import AsyncIterator
from pathlib import Path
from uuid import uuid4

import pytest
import pytest_asyncio
from redis.asyncio import Redis
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from agent_runtime_grid.artifacts.store import ArtifactStore
from agent_runtime_grid.domain.jobs import JobRecord, JobSubmission
from agent_runtime_grid.queue.redis_streams import RedisStreamsQueue
from agent_runtime_grid.queue.types import QueueJobMessage
from agent_runtime_grid.storage.models import job_events_table, jobs_table, metadata
from agent_runtime_grid.storage.repositories import JobRepository
from agent_runtime_grid.worker.cancellation import CancellationRegistry, cancel_queued_job
from agent_runtime_grid.worker.loop import Worker

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
        stream_name=f"timeout-jobs:{suffix}",
        consumer_group="workers",
        dlq_stream_name=f"timeout-jobs:{suffix}:dlq",
    )


async def _create_job(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    payload: dict[str, object],
    timeout_seconds: int = 5,
) -> JobRecord:
    async with session_factory() as session:
        repository = JobRepository(session)
        return await repository.create_job(
            JobSubmission(
                job_type="stub.echo",
                payload=payload,
                idempotency_key=f"job-key-{uuid4().hex}",
                timeout_seconds=timeout_seconds,
                max_retries=1,
                trace_id="trace-timeout-001",
            )
        )


async def _publish_job(queue: RedisStreamsQueue, job: JobRecord) -> str:
    return await queue.publish_job(
        QueueJobMessage(
            job_id=str(job.id),
            run_id=str(job.run_id),
            attempt_number=1,
            trace_id=job.trace_id,
        )
    )


async def _events(
    session_factory: async_sessionmaker[AsyncSession],
) -> list[tuple[str, dict[str, object]]]:
    async with session_factory() as session:
        rows = (
            await session.execute(
                select(job_events_table.c.event_type, job_events_table.c.event_data).order_by(
                    job_events_table.c.id.asc()
                )
            )
        ).all()
    return [(row.event_type, row.event_data) for row in rows]


async def _job_status(session_factory: async_sessionmaker[AsyncSession]) -> str:
    async with session_factory() as session:
        status = await session.scalar(select(jobs_table.c.status))
    assert status is not None
    return status


async def _wait_for_event(
    session_factory: async_sessionmaker[AsyncSession],
    event_type: str,
) -> None:
    for _ in range(50):
        if event_type in [name for name, _data in await _events(session_factory)]:
            return
        await asyncio.sleep(0.02)
    raise AssertionError(f"event {event_type!r} was not recorded")


@pytest.mark.asyncio
async def test_timeout_marks_job_timed_out(
    session_factory: async_sessionmaker[AsyncSession],
    queue: RedisStreamsQueue,
    tmp_path: Path,
) -> None:
    job = await _create_job(
        session_factory,
        payload={"mode": "sleep", "duration_seconds": 2},
        timeout_seconds=1,
    )
    await _publish_job(queue, job)
    artifact_root = tmp_path / "artifacts"
    worker = Worker(
        worker_id="worker-1",
        queue=queue,
        session_factory=session_factory,
        artifact_store=ArtifactStore(artifact_root),
    )

    assert await worker.process_one() is True

    assert [event_type for event_type, _data in await _events(session_factory)] == [
        "submitted",
        "running",
        "timed_out",
    ]
    assert await _job_status(session_factory) == "timed_out"
    assert not artifact_root.exists()


@pytest.mark.asyncio
async def test_cancel_queued_job_prevents_execution(
    session_factory: async_sessionmaker[AsyncSession],
    queue: RedisStreamsQueue,
) -> None:
    job = await _create_job(session_factory, payload={"message": "queued"})
    entry_id = await _publish_job(queue, job)
    async with session_factory() as session:
        async with session.begin():
            await cancel_queued_job(session, job)

    worker = Worker(worker_id="worker-1", queue=queue, session_factory=session_factory)

    assert await worker.process_one() is True

    assert [event_type for event_type, _data in await _events(session_factory)] == [
        "submitted",
        "cancelled",
    ]
    assert await _job_status(session_factory) == "cancelled"
    assert await queue.acknowledge(entry_id) == 0


@pytest.mark.asyncio
async def test_cancel_running_job_records_worker_shutdown(
    session_factory: async_sessionmaker[AsyncSession],
    queue: RedisStreamsQueue,
) -> None:
    job = await _create_job(
        session_factory,
        payload={"mode": "sleep", "duration_seconds": 5},
        timeout_seconds=10,
    )
    await _publish_job(queue, job)
    cancellation_registry = CancellationRegistry()
    worker = Worker(
        worker_id="worker-1",
        queue=queue,
        session_factory=session_factory,
        cancellation_registry=cancellation_registry,
    )

    worker_task = asyncio.create_task(worker.process_one())
    await _wait_for_event(session_factory, "running")
    cancellation_registry.request_cancel(job.id)

    assert await asyncio.wait_for(worker_task, timeout=2) is True

    events = await _events(session_factory)
    assert [event_type for event_type, _data in events] == ["submitted", "running", "cancelled"]
    assert events[-1][1]["worker_id"] == "worker-1"
    assert events[-1][1]["cancelled_while"] == "running"
    assert await _job_status(session_factory) == "cancelled"
