import os
from collections.abc import AsyncIterator
from uuid import uuid4

import pytest
import pytest_asyncio
from redis.asyncio import Redis
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from agent_runtime_grid.domain.jobs import JobSubmission
from agent_runtime_grid.queue.redis_streams import RedisStreamsQueue
from agent_runtime_grid.queue.types import QueueJobMessage
from agent_runtime_grid.storage.models import job_events_table, jobs_table, metadata
from agent_runtime_grid.storage.repositories import JobRepository
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
        stream_name=f"worker-jobs:{suffix}",
        consumer_group="workers",
        dlq_stream_name=f"worker-jobs:{suffix}:dlq",
    )


async def _create_job(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    payload: dict[str, object],
    max_retries: int = 1,
) -> tuple:
    async with session_factory() as session:
        repository = JobRepository(session)
        job = await repository.create_job(
            JobSubmission(
                job_type="stub.echo",
                payload=payload,
                idempotency_key=f"job-key-{uuid4().hex}",
                timeout_seconds=30,
                max_retries=max_retries,
                trace_id="trace-worker-001",
            )
        )
    return job, QueueJobMessage(
        job_id=str(job.id),
        run_id=str(job.run_id),
        attempt_number=1,
        trace_id=job.trace_id,
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


@pytest.mark.asyncio
async def test_worker_completes_stub_job(
    session_factory: async_sessionmaker[AsyncSession],
    queue: RedisStreamsQueue,
) -> None:
    _job, message = await _create_job(session_factory, payload={"message": "ok"})
    entry_id = await queue.publish_job(message)

    worker = Worker(worker_id="worker-1", queue=queue, session_factory=session_factory)

    assert await worker.process_one() is True

    assert [event_type for event_type, _data in await _events(session_factory)] == [
        "submitted",
        "running",
        "completed",
    ]
    assert await _job_status(session_factory) == "completed"
    assert await queue.acknowledge(entry_id) == 0


@pytest.mark.asyncio
async def test_transient_error_requeues_until_retry_limit(
    session_factory: async_sessionmaker[AsyncSession],
    queue: RedisStreamsQueue,
) -> None:
    _job, message = await _create_job(
        session_factory,
        payload={"mode": "transient_error"},
        max_retries=1,
    )
    await queue.publish_job(message)
    worker = Worker(worker_id="worker-1", queue=queue, session_factory=session_factory)

    assert await worker.process_one() is True
    requeued = await queue.lease_jobs(consumer_name="assert-worker", block_ms=10)
    assert len(requeued) == 1
    assert requeued[0].attempt_number == 2
    if requeued[0].entry_id is not None:
        await queue.acknowledge(requeued[0].entry_id)
    await queue.publish_job(
        QueueJobMessage(
            job_id=requeued[0].job_id,
            run_id=requeued[0].run_id,
            attempt_number=requeued[0].attempt_number,
            trace_id=requeued[0].trace_id,
        )
    )

    assert await worker.process_one() is True

    assert [event_type for event_type, _data in await _events(session_factory)] == [
        "submitted",
        "running",
        "retry_scheduled",
        "running",
        "failed",
    ]
    assert await _job_status(session_factory) == "failed"
    assert await queue.lease_jobs(consumer_name="assert-worker-2", block_ms=10) == []


@pytest.mark.asyncio
async def test_policy_error_is_not_retried(
    session_factory: async_sessionmaker[AsyncSession],
    queue: RedisStreamsQueue,
) -> None:
    _job, message = await _create_job(
        session_factory,
        payload={"mode": "policy_error"},
        max_retries=3,
    )
    await queue.publish_job(message)
    worker = Worker(worker_id="worker-1", queue=queue, session_factory=session_factory)

    assert await worker.process_one() is True

    events = await _events(session_factory)
    assert [event_type for event_type, _data in events] == ["submitted", "running", "failed"]
    assert events[-1][1]["error_class"] == "PolicyValidationError"
    assert events[-1][1]["retryable"] is False
    assert await _job_status(session_factory) == "failed"
    assert await queue.lease_jobs(consumer_name="assert-worker", block_ms=10) == []
