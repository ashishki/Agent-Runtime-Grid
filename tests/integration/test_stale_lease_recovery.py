import os
from collections.abc import AsyncIterator
from uuid import uuid4

import pytest
import pytest_asyncio
from redis.asyncio import Redis
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from agent_runtime_grid.domain.jobs import JobRecord, JobSubmission
from agent_runtime_grid.queue.redis_streams import RedisStreamsQueue
from agent_runtime_grid.queue.types import QueueJobMessage
from agent_runtime_grid.storage.finalization import (
    duplicate_terminal_event_count,
    finalization_conflict_attempt_count,
)
from agent_runtime_grid.storage.models import (
    job_events_table,
    job_finalizations_table,
    jobs_table,
    metadata,
)
from agent_runtime_grid.storage.repositories import JobRepository
from agent_runtime_grid.worker.lease import (
    STALE_LEASE_ERROR_CLASS,
    STALE_LEASE_EXHAUSTED_ERROR_CLASS,
)
from agent_runtime_grid.worker.loop import Worker
from agent_runtime_grid.worker.recovery import recover_stale_leases
from agent_runtime_grid.worker.state_machine import load_job_for_update, record_running

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
        stream_name=f"stale-jobs:{suffix}",
        consumer_group="workers",
        dlq_stream_name=f"stale-jobs:{suffix}:dlq",
    )


async def _create_job(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    max_retries: int,
) -> JobRecord:
    async with session_factory() as session:
        repository = JobRepository(session)
        return await repository.create_job(
            JobSubmission(
                job_type="stub.echo",
                payload={"message": "ok"},
                idempotency_key=f"job-key-{uuid4().hex}",
                timeout_seconds=30,
                max_retries=max_retries,
                trace_id="trace-stale-001",
            )
        )


async def _lease_and_mark_running(
    session_factory: async_sessionmaker[AsyncSession],
    queue: RedisStreamsQueue,
    *,
    max_retries: int,
) -> QueueJobMessage:
    job = await _create_job(session_factory, max_retries=max_retries)
    await queue.publish_job(
        QueueJobMessage(
            job_id=str(job.id),
            run_id=str(job.run_id),
            attempt_number=1,
            trace_id=job.trace_id,
        )
    )
    leased = await queue.lease_jobs(consumer_name="crashed-worker", block_ms=10)
    assert len(leased) == 1

    async with session_factory() as session:
        async with session.begin():
            locked_job = await load_job_for_update(session, job.id)
            assert locked_job is not None
            await record_running(
                session,
                locked_job,
                worker_id="crashed-worker",
                attempt_number=leased[0].attempt_number,
            )
    return leased[0]


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


async def _finalization_count(session_factory: async_sessionmaker[AsyncSession]) -> int:
    async with session_factory() as session:
        count = await session.scalar(select(func.count()).select_from(job_finalizations_table))
    assert count is not None
    return count


async def _finalization_guard_counts(
    session_factory: async_sessionmaker[AsyncSession],
) -> tuple[int, int]:
    async with session_factory() as session:
        return (
            await finalization_conflict_attempt_count(session),
            await duplicate_terminal_event_count(session),
        )


@pytest.mark.asyncio
async def test_stale_lease_is_detected(
    session_factory: async_sessionmaker[AsyncSession],
    queue: RedisStreamsQueue,
) -> None:
    leased = await _lease_and_mark_running(session_factory, queue, max_retries=1)

    assert await queue.find_stale_leases(stale_after_ms=60_000) == []

    stale_leases = await queue.find_stale_leases(stale_after_ms=0)

    assert len(stale_leases) == 1
    assert stale_leases[0].message.entry_id == leased.entry_id
    assert stale_leases[0].message.attempt_number == 1
    assert stale_leases[0].consumer_name == "crashed-worker"


@pytest.mark.asyncio
async def test_stale_job_requeues_and_completes_once(
    redis_client: Redis,
    session_factory: async_sessionmaker[AsyncSession],
    queue: RedisStreamsQueue,
) -> None:
    await _lease_and_mark_running(session_factory, queue, max_retries=1)

    result = await recover_stale_leases(
        queue=queue,
        session_factory=session_factory,
        recovery_worker_id="recovery-worker",
        stale_after_ms=0,
    )

    assert result.detected_count == 1
    assert result.requeued_count == 1
    assert result.dlq_count == 0
    assert await redis_client.xlen(queue.stream_name) == 2
    assert await queue.find_stale_leases(stale_after_ms=0) == []

    worker = Worker(worker_id="replacement-worker", queue=queue, session_factory=session_factory)
    assert await worker.process_one() is True

    events = await _events(session_factory)
    assert [event_type for event_type, _data in events] == [
        "submitted",
        "running",
        "stale_lease_recovered",
        "running",
        "completed",
    ]
    assert events[2][1]["error_class"] == STALE_LEASE_ERROR_CLASS
    assert events[2][1]["stale_consumer_name"] == "crashed-worker"
    assert events[2][1]["attempt_number"] == 1
    assert events[2][1]["next_attempt_number"] == 2
    assert events[-1][1]["attempt_number"] == 2
    assert await _job_status(session_factory) == "completed"
    assert await _finalization_count(session_factory) == 1
    assert await _finalization_guard_counts(session_factory) == (0, 0)


@pytest.mark.asyncio
async def test_exhausted_stale_recovery_routes_to_dlq_without_duplicate_finalization(
    redis_client: Redis,
    session_factory: async_sessionmaker[AsyncSession],
    queue: RedisStreamsQueue,
) -> None:
    await _lease_and_mark_running(session_factory, queue, max_retries=0)

    result = await recover_stale_leases(
        queue=queue,
        session_factory=session_factory,
        recovery_worker_id="recovery-worker",
        stale_after_ms=0,
    )

    assert result.detected_count == 1
    assert result.requeued_count == 0
    assert result.dlq_count == 1
    assert await redis_client.xlen(queue.dlq_stream_name) == 1
    assert await queue.find_stale_leases(stale_after_ms=0) == []

    events = await _events(session_factory)
    assert [event_type for event_type, _data in events] == ["submitted", "running", "failed"]
    assert events[-1][1]["error_class"] == STALE_LEASE_EXHAUSTED_ERROR_CLASS
    assert events[-1][1]["retryable"] is True
    assert await _job_status(session_factory) == "failed"
    assert await _finalization_count(session_factory) == 1
    assert await _finalization_guard_counts(session_factory) == (0, 0)
