import asyncio
import os
from collections.abc import AsyncIterator
from contextlib import suppress
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
from agent_runtime_grid.worker.recovery import recover_stale_leases

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
        stream_name=f"heartbeat-jobs:{suffix}",
        consumer_group="workers",
        dlq_stream_name=f"heartbeat-jobs:{suffix}:dlq",
    )


@pytest.mark.asyncio
async def test_worker_heartbeat_prevents_false_stale_recovery_for_long_job(
    session_factory: async_sessionmaker[AsyncSession],
    queue: RedisStreamsQueue,
) -> None:
    await _submit_sleep_job(session_factory, queue, duration_seconds=0.35)
    worker = Worker(
        worker_id="heartbeat-worker",
        queue=queue,
        session_factory=session_factory,
        lease_renewal_interval_seconds=0.01,
    )
    worker_task = asyncio.create_task(worker.process_one())

    await _wait_for_status(session_factory, "running")
    await asyncio.sleep(0.12)

    stale_leases = await queue.find_stale_leases(stale_after_ms=80)
    recovery = await recover_stale_leases(
        queue=queue,
        session_factory=session_factory,
        recovery_worker_id="operator-recovery",
        stale_after_ms=80,
    )

    assert stale_leases == []
    assert recovery.detected_count == 0
    assert await worker_task is True
    assert await _job_status(session_factory) == "completed"
    assert "stale_lease_recovered" not in await _event_types(session_factory)


@pytest.mark.asyncio
async def test_heartbeat_stops_after_terminal_acknowledgement(
    session_factory: async_sessionmaker[AsyncSession],
    queue: RedisStreamsQueue,
) -> None:
    await _submit_sleep_job(session_factory, queue, duration_seconds=0.08)
    worker = Worker(
        worker_id="heartbeat-worker",
        queue=queue,
        session_factory=session_factory,
        lease_renewal_interval_seconds=0.01,
    )

    assert await worker.process_one() is True

    assert await queue.find_stale_leases(stale_after_ms=0) == []
    assert await _event_types(session_factory) == ["submitted", "running", "completed"]
    assert await _job_status(session_factory) == "completed"


@pytest.mark.asyncio
async def test_disabled_heartbeat_preserves_stale_recovery_behavior(
    session_factory: async_sessionmaker[AsyncSession],
    queue: RedisStreamsQueue,
) -> None:
    await _submit_sleep_job(session_factory, queue, duration_seconds=0.35)
    worker = Worker(
        worker_id="no-heartbeat-worker",
        queue=queue,
        session_factory=session_factory,
        lease_renewal_interval_seconds=None,
    )
    worker_task = asyncio.create_task(worker.process_one())

    await _wait_for_status(session_factory, "running")
    await asyncio.sleep(0.08)

    recovery = await recover_stale_leases(
        queue=queue,
        session_factory=session_factory,
        recovery_worker_id="operator-recovery",
        stale_after_ms=20,
    )
    worker_task.cancel()
    with suppress(asyncio.CancelledError):
        await worker_task

    assert recovery.detected_count == 1
    assert recovery.requeued_count == 1
    assert await _job_status(session_factory) == "queued"
    assert await _event_types(session_factory) == [
        "submitted",
        "running",
        "stale_lease_recovered",
    ]


async def _submit_sleep_job(
    session_factory: async_sessionmaker[AsyncSession],
    queue: RedisStreamsQueue,
    *,
    duration_seconds: float,
) -> None:
    async with session_factory() as session:
        repository = JobRepository(session)
        job = await repository.create_job(
            JobSubmission(
                job_type="stub.echo",
                payload={"mode": "sleep", "duration_seconds": duration_seconds},
                idempotency_key=f"heartbeat-job-{uuid4().hex}",
                timeout_seconds=2,
                max_retries=1,
                trace_id="trace-heartbeat-001",
            )
        )
        await queue.publish_job(
            QueueJobMessage(
                job_id=str(job.id),
                run_id=str(job.run_id),
                attempt_number=1,
                trace_id=job.trace_id,
            )
        )


async def _wait_for_status(
    session_factory: async_sessionmaker[AsyncSession],
    expected_status: str,
) -> None:
    deadline = asyncio.get_running_loop().time() + 2
    while asyncio.get_running_loop().time() < deadline:
        if await _job_status(session_factory) == expected_status:
            return
        await asyncio.sleep(0.01)
    raise AssertionError(f"job did not reach status {expected_status}")


async def _job_status(session_factory: async_sessionmaker[AsyncSession]) -> str:
    async with session_factory() as session:
        status = await session.scalar(select(jobs_table.c.status))
    assert status is not None
    return status


async def _event_types(session_factory: async_sessionmaker[AsyncSession]) -> list[str]:
    async with session_factory() as session:
        rows = (
            await session.execute(
                select(job_events_table.c.event_type).order_by(job_events_table.c.id.asc())
            )
        ).scalars()
    return list(rows)
