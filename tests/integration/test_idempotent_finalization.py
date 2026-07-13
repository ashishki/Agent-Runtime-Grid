import asyncio
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
    finalize_job,
)
from agent_runtime_grid.storage.models import (
    job_events_table,
    job_finalizations_table,
    metadata,
)
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
        stream_name=f"finalize-jobs:{suffix}",
        consumer_group="workers",
        dlq_stream_name=f"finalize-jobs:{suffix}:dlq",
    )


async def _create_job(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    payload: dict[str, object] | None = None,
) -> JobRecord:
    async with session_factory() as session:
        repository = JobRepository(session)
        return await repository.create_job(
            JobSubmission(
                job_type="stub.echo",
                payload=payload or {"message": "ok"},
                idempotency_key=f"job-key-{uuid4().hex}",
                timeout_seconds=30,
                max_retries=1,
                trace_id="trace-finalize-001",
            )
        )


async def _terminal_event_count(
    session_factory: async_sessionmaker[AsyncSession],
) -> int:
    async with session_factory() as session:
        count = await session.scalar(
            select(func.count())
            .select_from(job_events_table)
            .where(job_events_table.c.event_type.in_(("completed", "failed")))
        )
    assert count is not None
    return count


async def _event_types(session_factory: async_sessionmaker[AsyncSession]) -> list[str]:
    async with session_factory() as session:
        rows = (
            await session.execute(
                select(job_events_table.c.event_type).order_by(job_events_table.c.id.asc())
            )
        ).all()
    return [row.event_type for row in rows]


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


async def _finalize_once(
    session_factory: async_sessionmaker[AsyncSession],
    job: JobRecord,
):
    async with session_factory() as session:
        async with session.begin():
            return await finalize_job(
                session,
                job,
                status="completed",
                event_type="completed",
                event_data={"worker_id": "race-worker", "attempt_number": 1},
            )


@pytest.mark.asyncio
async def test_racing_workers_produce_one_terminal_event(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    job = await _create_job(session_factory)

    results = await asyncio.gather(
        _finalize_once(session_factory, job),
        _finalize_once(session_factory, job),
    )

    assert [result.finalized for result in results].count(True) == 1
    assert [result.conflict_recorded for result in results].count(True) == 1
    assert await _terminal_event_count(session_factory) == 1
    assert await _finalization_count(session_factory) == 1
    assert await _finalization_guard_counts(session_factory) == (1, 0)


@pytest.mark.asyncio
async def test_replayed_message_after_finalization_is_noop(
    session_factory: async_sessionmaker[AsyncSession],
    queue: RedisStreamsQueue,
) -> None:
    job = await _create_job(session_factory)
    message = QueueJobMessage(
        job_id=str(job.id),
        run_id=str(job.run_id),
        attempt_number=1,
        trace_id=job.trace_id,
    )
    await queue.publish_job(message)

    worker = Worker(worker_id="worker-1", queue=queue, session_factory=session_factory)
    assert await worker.process_one() is True

    replayed_entry_id = await queue.publish_job(message)
    assert await worker.process_one() is True

    assert await _event_types(session_factory) == ["submitted", "running", "completed"]
    assert await queue.acknowledge(replayed_entry_id) == 0


@pytest.mark.asyncio
async def test_replayed_worker_message_does_not_reach_finalization_guard(
    session_factory: async_sessionmaker[AsyncSession],
    queue: RedisStreamsQueue,
) -> None:
    job = await _create_job(session_factory)
    message = QueueJobMessage(
        job_id=str(job.id),
        run_id=str(job.run_id),
        attempt_number=1,
        trace_id=job.trace_id,
    )

    await queue.publish_job(message)
    worker = Worker(worker_id="worker-1", queue=queue, session_factory=session_factory)
    assert await worker.process_one() is True

    await queue.publish_job(message)
    assert await worker.process_one() is True

    assert await _terminal_event_count(session_factory) == 1
    assert await _finalization_guard_counts(session_factory) == (0, 0)
